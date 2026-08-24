"""API Gateway REST adapter for the unauthenticated public live MCP demo."""

from __future__ import annotations

import os
from typing import Any

from mangum import Mangum
from mcp.server.transport_security import TransportSecuritySettings

from surf.live_store import DynamoDbRecordStore

from .exposure_control import DynamoDbRequestBudget, ExposureSettings
from .server import DEFAULT_MAX_REQUEST_BODY_BYTES, create_app


def _allowed_origins_from_environment() -> tuple[str, ...]:
    value = os.environ.get("MCP_ALLOWED_ORIGINS", "")
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


def _max_request_body_bytes_from_environment() -> int:
    raw_value = os.environ.get("MCP_MAX_REQUEST_BODY_BYTES", str(DEFAULT_MAX_REQUEST_BODY_BYTES))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError("MCP_MAX_REQUEST_BODY_BYTES must be an integer.") from error
    if value < 1:
        raise RuntimeError("MCP_MAX_REQUEST_BODY_BYTES must be positive.")
    return value


def create_lambda_app() -> Any:
    return create_app(
        record_store=DynamoDbRecordStore(os.environ.get("MCP_RECORD_TABLE", "")),
        allowed_origins=_allowed_origins_from_environment(),
        max_request_body_bytes=_max_request_body_bytes_from_environment(),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        request_budget=DynamoDbRequestBudget(ExposureSettings.from_environment(os.environ)),
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Run a fresh stateless ASGI lifespan; DynamoDB owns cross-request state."""
    return Mangum(create_lambda_app(), lifespan="auto")(event, context)
