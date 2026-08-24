from __future__ import annotations

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
    def __init__(self): self.calls: list[dict] = []
    def put_function_concurrency(self, **kwargs): self.calls.append(kwargs)


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
