"""Fail-closed request budget for the short-lived public MCP exposure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


class ExposureUnavailable(Exception):
    """Public-safe failure returned when the exposure must not serve a request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RequestBudget(Protocol):
    """Grant one valid MCP POST permit or reject it before source retrieval."""

    def acquire(self) -> None: ...


@dataclass(frozen=True)
class ExposureSettings:
    table_name: str
    exposure_id: str
    max_requests: int
    public_until_epoch: int

    @classmethod
    def from_environment(cls, environment: dict[str, str]) -> "ExposureSettings":
        table_name = environment.get("MCP_EXPOSURE_CONTROL_TABLE", "")
        exposure_id = environment.get("MCP_EXPOSURE_ID", "")
        if not table_name or not exposure_id:
            raise RuntimeError("MCP_EXPOSURE_CONTROL_TABLE and MCP_EXPOSURE_ID must be configured")
        try:
            max_requests = int(environment.get("MCP_MAX_PUBLIC_POST_REQUESTS", ""))
            value = environment.get("MCP_PUBLIC_UNTIL_UTC", "")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            public_until_epoch = int(parsed.timestamp())
        except (TypeError, ValueError) as error:
            raise RuntimeError("Public exposure controls must use a positive request limit and ISO-8601 UTC expiry") from error
        if max_requests < 1:
            raise RuntimeError("MCP_MAX_PUBLIC_POST_REQUESTS must be positive")
        return cls(table_name, exposure_id, max_requests, public_until_epoch)


class DynamoDbRequestBudget:
    """Atomically consume a permit in one isolated DynamoDB control table."""

    def __init__(self, settings: ExposureSettings, *, client: Any | None = None,
                 now: callable | None = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("dynamodb")
        self.settings = settings
        self.client = client
        self.now = now or _unix_now

    def acquire(self) -> None:
        now = self.now()
        if now >= self.settings.public_until_epoch:
            raise ExposureUnavailable("public_window_expired", "The public demonstration window has ended.")
        try:
            self.client.update_item(
                TableName=self.settings.table_name,
                Key={"exposure_id": {"S": self.settings.exposure_id}},
                UpdateExpression=(
                    "SET request_count = if_not_exists(request_count, :zero) + :one, "
                    "#state = if_not_exists(#state, :enabled), "
                    "public_until = if_not_exists(public_until, :public_until), "
                    "expires_at = :expires_at"
                ),
                ConditionExpression=(
                    "(attribute_not_exists(#state) OR #state = :enabled) AND "
                    "(attribute_not_exists(request_count) OR request_count < :max_requests) AND "
                    "(attribute_not_exists(public_until) OR public_until > :now)"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":zero": {"N": "0"}, ":one": {"N": "1"}, ":enabled": {"S": "enabled"},
                    ":max_requests": {"N": str(self.settings.max_requests)},
                    ":now": {"N": str(now)}, ":public_until": {"N": str(self.settings.public_until_epoch)},
                    ":expires_at": {"N": str(self.settings.public_until_epoch + 86_400)},
                },
            )
        except Exception as error:
            if not _is_conditional_failure(error):
                raise ExposureUnavailable("exposure_control_unavailable", "The public request budget is unavailable.") from error
            self._raise_current_state(now)

    def _raise_current_state(self, now: int) -> None:
        response = self.client.get_item(
            TableName=self.settings.table_name,
            Key={"exposure_id": {"S": self.settings.exposure_id}},
            ConsistentRead=True,
        )
        item = response.get("Item", {})
        state = item.get("state", {}).get("S")
        count = int(item.get("request_count", {}).get("N", "0"))
        public_until = int(item.get("public_until", {}).get("N", str(self.settings.public_until_epoch)))
        if now >= public_until:
            raise ExposureUnavailable("public_window_expired", "The public demonstration window has ended.")
        if state and state != "enabled":
            raise ExposureUnavailable("public_demo_disabled", "The public demonstration is temporarily disabled.")
        if count >= self.settings.max_requests:
            raise ExposureUnavailable("demo_request_budget_exhausted", "The public demonstration request budget is exhausted.")
        raise ExposureUnavailable("exposure_control_unavailable", "The public request budget is unavailable.")


class InMemoryRequestBudget:
    """Deterministic test double that mirrors the public failure boundary."""

    def __init__(self, max_requests: int, *, now: callable | None = None, public_until_epoch: int | None = None) -> None:
        self.max_requests = max_requests
        self.now = now or _unix_now
        self.public_until_epoch = public_until_epoch
        self.count = 0
        self.enabled = True

    def acquire(self) -> None:
        if self.public_until_epoch is not None and self.now() >= self.public_until_epoch:
            raise ExposureUnavailable("public_window_expired", "The public demonstration window has ended.")
        if not self.enabled:
            raise ExposureUnavailable("public_demo_disabled", "The public demonstration is temporarily disabled.")
        if self.count >= self.max_requests:
            raise ExposureUnavailable("demo_request_budget_exhausted", "The public demonstration request budget is exhausted.")
        self.count += 1


def _is_conditional_failure(error: Exception) -> bool:
    response = getattr(error, "response", {})
    return isinstance(response, dict) and response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _unix_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
