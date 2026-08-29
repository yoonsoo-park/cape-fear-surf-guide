from __future__ import annotations

import sys
import types
from datetime import datetime, timezone

import pytest

import mcp_runtime.circuit_breaker as circuit_breaker
from mcp_runtime.exposure_control import DynamoDbRequestBudget, ExposureSettings, ExposureUnavailable, InMemoryRequestBudget


def test_in_memory_request_budget_fails_closed_at_the_exact_limit_and_after_expiry():
    budget = InMemoryRequestBudget(2, now=lambda: 100, public_until_epoch=101)
    budget.acquire()
    budget.acquire()
    with pytest.raises(ExposureUnavailable, match="budget is exhausted") as exhausted:
        budget.acquire()
    assert exhausted.value.code == "demo_request_budget_exhausted"
    expired = InMemoryRequestBudget(1, now=lambda: 101, public_until_epoch=101)
    with pytest.raises(ExposureUnavailable, match="window has ended") as ended:
        expired.acquire()
    assert ended.value.code == "public_window_expired"


def test_dynamodb_request_budget_uses_a_conditional_atomic_increment():
    class Client:
        def __init__(self): self.kwargs = None
        def update_item(self, **kwargs): self.kwargs = kwargs

    client = Client()
    settings = ExposureSettings("control", "demo", 120, 1_000)
    DynamoDbRequestBudget(settings, client=client, now=lambda: 100).acquire()
    assert client.kwargs["TableName"] == "control"
    assert "request_count < :max_requests" in client.kwargs["ConditionExpression"]
    assert client.kwargs["ExpressionAttributeValues"][":max_requests"] == {"N": "120"}


class _Dynamo:
    def __init__(self, item: dict[str, dict[str, str]] | None = None):
        self.item = item or {}
        self.updates: list[dict] = []
    def get_item(self, **kwargs): return {"Item": self.item}
    def update_item(self, **kwargs):
        self.updates.append(kwargs)


class _Lambda:
    def __init__(self, *, error: Exception | None = None, events: list[str] | None = None):
        self.calls: list[dict] = []
        self.error = error
        self.events = events

    def put_function_concurrency(self, **kwargs):
        if self.events is not None:
            self.events.append("lambda")
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


def _circuit_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_EXPOSURE_CONTROL_TABLE", "control")
    monkeypatch.setenv("MCP_EXPOSURE_ID", "demo")
    monkeypatch.setenv("MCP_MAX_PUBLIC_POST_REQUESTS", "120")
    monkeypatch.setenv("MCP_PUBLIC_UNTIL_UTC", "2099-01-01T00:00:00")
    monkeypatch.setenv("MCP_PUBLIC_FUNCTION_NAME", "public-mcp")
    monkeypatch.setenv("MCP_NORMAL_RESERVED_CONCURRENCY", "2")


def test_circuit_breaker_disables_for_budget_stream_and_only_reenables_volume_alarm(monkeypatch: pytest.MonkeyPatch):
    _circuit_environment(monkeypatch)
    dynamodb, lambda_client = _Dynamo(), _Lambda()
    event = {"Records": [{"dynamodb": {"NewImage": {"request_count": {"N": "120"}}}}]}
    result = circuit_breaker.handler(event, object(), dynamodb_client=dynamodb, lambda_client=lambda_client, now=lambda: 100)
    assert result == {"status": "disabled", "reason": "request_budget_exhausted"}
    assert lambda_client.calls == [{"FunctionName": "public-mcp", "ReservedConcurrentExecutions": 0}]

    blocked = _Dynamo({"state": {"S": "disabled"}, "disabled_reason": {"S": "request_budget_exhausted"},
                       "request_count": {"N": "120"}, "public_until": {"N": "9999999999"}})
    assert circuit_breaker.handler({"action": "reenable"}, object(), dynamodb_client=blocked, lambda_client=_Lambda(), now=lambda: 100)["status"] == "not_reenabled"

    volume = _Dynamo({"state": {"S": "disabled"}, "disabled_reason": {"S": "volume_alarm"},
                      "request_count": {"N": "40"}, "public_until": {"N": "9999999999"}})
    reenable_lambda = _Lambda()
    assert circuit_breaker.handler({"action": "reenable"}, object(), dynamodb_client=volume, lambda_client=reenable_lambda, now=lambda: 100) == {"status": "reenabled"}
    assert reenable_lambda.calls == [{"FunctionName": "public-mcp", "ReservedConcurrentExecutions": 2}]


def test_disable_stops_function_before_recording_terminal_state(monkeypatch: pytest.MonkeyPatch):
    _circuit_environment(monkeypatch)
    events: list[str] = []

    class OrderedDynamo(_Dynamo):
        def update_item(self, **kwargs):
            events.append("dynamodb")
            super().update_item(**kwargs)

    dynamodb = OrderedDynamo()
    lambda_client = _Lambda(events=events)
    result = circuit_breaker.handler(
        {"action": "disable", "reason": "scheduled_expiry"},
        object(),
        dynamodb_client=dynamodb,
        lambda_client=lambda_client,
        now=lambda: 100,
    )
    assert result == {"status": "disabled", "reason": "scheduled_expiry"}
    assert events == ["lambda", "dynamodb"]


def test_already_disabled_retries_the_stop_call_after_a_partial_failure(monkeypatch: pytest.MonkeyPatch):
    _circuit_environment(monkeypatch)
    dynamodb = _Dynamo({"state": {"S": "disabled"}, "disabled_reason": {"S": "request_budget_exhausted"}})
    lambda_client = _Lambda()

    result = circuit_breaker.handler(
        {"action": "disable", "reason": "request_budget_exhausted"},
        object(),
        dynamodb_client=dynamodb,
        lambda_client=lambda_client,
        now=lambda: 100,
    )

    assert result == {"status": "already_disabled", "reason": "request_budget_exhausted"}
    assert lambda_client.calls == [{"FunctionName": "public-mcp", "ReservedConcurrentExecutions": 0}]
    assert dynamodb.updates == []


def test_failed_stop_does_not_record_disabled_state(monkeypatch: pytest.MonkeyPatch):
    _circuit_environment(monkeypatch)
    dynamodb = _Dynamo()
    lambda_client = _Lambda(error=RuntimeError("control plane unavailable"))

    with pytest.raises(RuntimeError, match="control plane unavailable"):
        circuit_breaker.handler(
            {"action": "disable", "reason": "request_budget_exhausted"},
            object(),
            dynamodb_client=dynamodb,
            lambda_client=lambda_client,
            now=lambda: 100,
        )

    assert dynamodb.updates == []


def test_reenable_restores_function_before_publishing_enabled_state(monkeypatch: pytest.MonkeyPatch):
    _circuit_environment(monkeypatch)
    events: list[str] = []

    class OrderedDynamo(_Dynamo):
        def update_item(self, **kwargs):
            events.append("dynamodb")
            super().update_item(**kwargs)

    dynamodb = OrderedDynamo({
        "state": {"S": "disabled"},
        "disabled_reason": {"S": "volume_alarm"},
        "request_count": {"N": "40"},
        "public_until": {"N": "9999999999"},
    })
    lambda_client = _Lambda(events=events)

    result = circuit_breaker.handler(
        {"action": "reenable"},
        object(),
        dynamodb_client=dynamodb,
        lambda_client=lambda_client,
        now=lambda: 100,
    )

    assert result == {"status": "reenabled"}
    assert events == ["lambda", "dynamodb"]


def test_default_clients_use_bounded_control_plane_timeouts(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, object]] = []

    class FakeBoto3:
        def client(self, service: str, *, config: object):
            calls.append((service, config))
            return service

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_botocore_config = types.ModuleType("botocore.config")
    fake_botocore_config.Config = FakeConfig
    monkeypatch.setitem(sys.modules, "boto3", FakeBoto3())
    monkeypatch.setitem(sys.modules, "botocore.config", fake_botocore_config)

    assert circuit_breaker._default_clients() == ("dynamodb", "lambda")
    assert [service for service, _ in calls] == ["dynamodb", "lambda"]
    assert calls[0][1].kwargs == {
        "connect_timeout": 2,
        "read_timeout": 5,
        "retries": {"mode": "standard", "max_attempts": 2},
    }
