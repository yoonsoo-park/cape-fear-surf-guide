"""Private Lambda that stops or manually re-enables the public MCP exposure."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any, *, dynamodb_client: Any | None = None,
            lambda_client: Any | None = None, now: Callable[[], int] | None = None) -> dict[str, str]:
    """Handle DynamoDB budget events, SNS volume alarms, scheduler expiry, or manual recovery."""
    started = time.monotonic()
    action = "unknown"
    reason = ""
    try:
        if dynamodb_client is None or lambda_client is None:
            default_dynamodb, default_lambda = _default_clients()
            dynamodb_client = dynamodb_client or default_dynamodb
            lambda_client = lambda_client or default_lambda
        now_epoch = (now or _unix_now)()
        settings = _settings(os.environ)
        action, reason = _resolve_action(event, settings["max_requests"])
        if action == "ignore":
            result = {"status": "ignored"}
        elif action == "reenable":
            result = _reenable(dynamodb_client, lambda_client, settings, now_epoch)
        else:
            result = _disable(dynamodb_client, lambda_client, settings, reason, now_epoch)
        LOGGER.info(
            "circuit_breaker action=%s reason=%s status=%s elapsed_ms=%d",
            action,
            reason,
            result.get("status", "unknown"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception:
        LOGGER.exception(
            "circuit_breaker action=%s reason=%s status=failed elapsed_ms=%d",
            action,
            reason,
            int((time.monotonic() - started) * 1000),
        )
        raise


def _default_clients() -> tuple[Any, Any]:
    """Build bounded AWS clients so a control-plane outage cannot exhaust the Lambda timeout."""
    import boto3

    try:
        from botocore.config import Config
    except ImportError:  # pragma: no cover - boto3's runtime dependency provides botocore in AWS.
        return boto3.client("dynamodb"), boto3.client("lambda")

    config = Config(
        connect_timeout=2,
        read_timeout=5,
        retries={"mode": "standard", "max_attempts": 2},
    )
    return boto3.client("dynamodb", config=config), boto3.client("lambda", config=config)


def _settings(environment: dict[str, str]) -> dict[str, Any]:
    try:
        public_until = datetime.fromisoformat(environment["MCP_PUBLIC_UNTIL_UTC"].replace("Z", "+00:00"))
        if public_until.tzinfo is None:
            public_until = public_until.replace(tzinfo=timezone.utc)
        return {
            "table": environment["MCP_EXPOSURE_CONTROL_TABLE"], "exposure_id": environment["MCP_EXPOSURE_ID"],
            "function_name": environment["MCP_PUBLIC_FUNCTION_NAME"],
            "reserved_concurrency": int(environment["MCP_NORMAL_RESERVED_CONCURRENCY"]),
            "max_requests": int(environment["MCP_MAX_PUBLIC_POST_REQUESTS"]),
            "public_until": int(public_until.timestamp()),
        }
    except (KeyError, ValueError) as error:
        raise RuntimeError("Circuit breaker exposure settings are incomplete") from error


def _resolve_action(event: dict[str, Any], max_requests: int) -> tuple[str, str]:
    if event.get("action") == "reenable":
        return "reenable", "manual_reenable"
    if event.get("action") == "disable":
        return "disable", str(event.get("reason", "scheduled_expiry"))
    if event.get("Records"):
        first = event["Records"][0]
        if first.get("EventSource") == "aws:sns":
            return "disable", "volume_alarm"
        for record in event["Records"]:
            image = record.get("dynamodb", {}).get("NewImage", {})
            count = int(image.get("request_count", {}).get("N", "0"))
            if count >= max_requests:
                return "disable", "request_budget_exhausted"
    return "ignore", ""


def _disable(dynamodb_client: Any, lambda_client: Any, settings: dict[str, Any], reason: str, now: int) -> dict[str, str]:
    current = _read(dynamodb_client, settings)
    already_disabled = current.get("state") == "disabled"
    effective_reason = current.get("disabled_reason") or reason or "unknown"

    # Always repeat the idempotent stop. A previous invocation may have written
    # state=disabled and then timed out before the Lambda control-plane call.
    lambda_client.put_function_concurrency(FunctionName=settings["function_name"], ReservedConcurrentExecutions=0)
    if already_disabled:
        return {"status": "already_disabled", "reason": effective_reason}

    # Record the terminal state only after the public function is confirmed
    # stopped. If this write fails, a Stream retry repeats the safe stop and
    # then retries the state transition.
    dynamodb_client.update_item(
        TableName=settings["table"], Key={"exposure_id": {"S": settings["exposure_id"]}},
        UpdateExpression="SET #state = :disabled, disabled_reason = :reason, disabled_at = :now",
        ExpressionAttributeNames={"#state": "state"},
        ExpressionAttributeValues={":disabled": {"S": "disabled"}, ":reason": {"S": effective_reason}, ":now": {"N": str(now)}},
    )
    return {"status": "disabled", "reason": effective_reason}


def _reenable(dynamodb_client: Any, lambda_client: Any, settings: dict[str, Any], now: int) -> dict[str, str]:
    current = _read(dynamodb_client, settings)
    if current.get("disabled_reason") != "volume_alarm":
        return {"status": "not_reenabled", "reason": "only_volume_alarm_can_be_reenabled"}
    if now >= int(current.get("public_until", settings["public_until"])):
        return {"status": "not_reenabled", "reason": "public_window_expired"}
    if int(current.get("request_count", 0)) >= settings["max_requests"]:
        return {"status": "not_reenabled", "reason": "request_budget_exhausted"}
    # Mirror _disable's ordering: only publish enabled state after the public
    # function has actually been restored. A failed update leaves the
    # exposure fail-closed and a human can retry the approved action.
    lambda_client.put_function_concurrency(
        FunctionName=settings["function_name"], ReservedConcurrentExecutions=settings["reserved_concurrency"]
    )
    dynamodb_client.update_item(
        TableName=settings["table"], Key={"exposure_id": {"S": settings["exposure_id"]}},
        UpdateExpression="SET #state = :enabled REMOVE disabled_reason, disabled_at",
        ExpressionAttributeNames={"#state": "state"}, ExpressionAttributeValues={":enabled": {"S": "enabled"}},
    )
    return {"status": "reenabled"}


def _read(client: Any, settings: dict[str, Any]) -> dict[str, str]:
    response = client.get_item(TableName=settings["table"], Key={"exposure_id": {"S": settings["exposure_id"]}}, ConsistentRead=True)
    item = response.get("Item", {})
    return {key: value.get("S", value.get("N", "")) for key, value in item.items()}


def _unix_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
