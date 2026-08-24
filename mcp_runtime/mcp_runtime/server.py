"""Stateless Streamable HTTP MCP v2 server for the API-key-gated live demo."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for candidate in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
    if (candidate / "surf").is_dir():
        PROJECT_ROOT = candidate
        break
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from surf.live_planner import LivePlanningResult, plan_live
from surf.live_store import DynamoDbRecordStore, RecordStore, unix_now

from .exposure_control import ExposureUnavailable, RequestBudget

PROTOCOL_VERSION = "2026-07-28"
MCP_PATH = "/mcp"
DEFAULT_MAX_REQUEST_BODY_BYTES = 65_536
RECORD_TTL_SECONDS = 24 * 60 * 60
SUPPORTED_METHODS = frozenset({"tools/list", "tools/call"})
SUPPORTED_TOOL_NAMES = frozenset({"find_surf_windows", "explain_surf_window"})


def _result_payload(result: LivePlanningResult, *, expires_at: int | None = None) -> dict[str, Any]:
    return {
        "resultType": "complete",
        "record": result.record.model_dump(mode="json"),
        "brief": result.brief.model_dump(mode="json"),
        "brief_source": result.brief_source,
        "retrieval": {
            "mode": "live",
            "sources": [
                {"source_name": item.source_name, "source_url": item.source_url,
                 "retrieved_at": item.retrieved_at.isoformat(), "freshness_state": item.freshness_state}
                for item in result.record.evidence
            ],
        },
        "safety_limit": "This is a planning aid, not a guarantee that ocean activity is safe. Check posted flags, lifeguards, and local officials.",
        **({"expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat()} if expires_at is not None else {}),
    }


def _error_result(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"resultType": "error", "error": {"code": code, "message": message, "details": details or {}}}


def create_server(record_store: RecordStore, *, now: Callable[[], int] = unix_now,
                  planner: Callable[..., Any] = plan_live) -> MCPServer:
    server = MCPServer(
        "cape-fear-surf-guide", title="Cape Fear Surf Guide",
        description="Read-only live evidence-backed surf planning. Deterministic policy owns every verdict.", version="0.1.0",
    )

    @server.tool(name="find_surf_windows", structured_output=True)
    def find_surf_windows(
        date: str, party_profile: dict[str, Any], preferred_area: str | None = None, time_range: str | None = None
    ) -> dict[str, Any]:
        """Retrieve live evidence for Wrightsville Beach and store its decision for 24 hours."""
        result = planner(date, party_profile, preferred_area, time_range)
        if isinstance(result, tuple):
            return _error_result(*result)
        expires_at = now() + RECORD_TTL_SECONDS
        payload = _result_payload(result, expires_at=expires_at)
        record_store.put(result.record.window_id, payload, expires_at)
        return {"resultType": "complete", "windows": [payload]}

    @server.tool(name="explain_surf_window", structured_output=True)
    def explain_surf_window(window_id: str, reading_level: str | None = None) -> dict[str, Any]:
        """Return the exact stored live decision without performing a live re-query."""
        payload, expires_at = record_store.get(window_id)
        if payload is None or expires_at is None:
            return _error_result("unknown_window_id", "window_id is not present in the live 24-hour record store.", {"window_id": window_id})
        if expires_at <= now():
            return _error_result("expired_window_id", "window_id has expired and cannot be replayed.", {"window_id": window_id})
        return payload

    return server


class ProtocolContractMiddleware:
    """Validate protocol shape before handing the request to the MCP SDK.

    It deliberately never logs the request body, party profile, or credential
    headers. API Gateway validates `x-api-key` before Lambda is invoked.
    """

    def __init__(self, app: Callable[..., Awaitable[None]], allowed_origins: tuple[str, ...],
                 max_request_body_bytes: int, request_budget: RequestBudget | None = None,
                 require_agentcore_routing_headers: bool = False) -> None:
        self.app = app
        self.allowed_origins = allowed_origins
        self.max_request_body_bytes = max_request_body_bytes
        self.request_budget = request_budget
        self.require_agentcore_routing_headers = require_agentcore_routing_headers

    async def __call__(self, scope: dict[str, Any], receive: Callable[[], Awaitable[dict[str, Any]]],
                       send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        if scope["type"] != "http" or scope.get("path") != MCP_PATH:
            await self.app(scope, receive, send)
            return
        if scope.get("method") != "POST":
            await _send_error(send, 405, "method_not_allowed", "The stateless MCP endpoint accepts POST only.")
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_request_body_bytes:
                    await _send_error(send, 413, "request_too_large", "Request body exceeds the configured limit.")
                    return
            except ValueError:
                await _send_error(send, 400, "invalid_content_length", "Content-Length must be an integer.")
                return
        body = await _read_body(receive)
        if len(body) > self.max_request_body_bytes:
            await _send_error(send, 413, "request_too_large", "Request body exceeds the configured limit.")
            return
        error = _validate_request(headers, body, self.allowed_origins,
                                  require_agentcore_routing_headers=self.require_agentcore_routing_headers)
        if error is not None:
            await _send_error(send, *error)
            return
        if self.request_budget is not None:
            try:
                self.request_budget.acquire()
            except ExposureUnavailable as control_error:
                await _send_error(send, 429, control_error.code, control_error.message)
                return
        sent = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        sdk_scope = scope if self.require_agentcore_routing_headers else _public_sdk_scope(scope, json.loads(body))
        await self.app(sdk_scope, replay_receive, send)


async def _read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] == "http.request":
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
    return b"".join(chunks)


def _public_sdk_scope(scope: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Derive SDK routing headers from the already validated JSON-RPC body."""
    headers = [(key, value) for key, value in scope.get("headers", []) if key.lower() not in {b"mcp-method", b"mcp-name"}]
    headers.append((b"mcp-method", request["method"].encode("latin-1")))
    if request["method"] == "tools/call":
        headers.append((b"mcp-name", request["params"]["name"].encode("latin-1")))
    return {**scope, "headers": headers}


def _validate_request(headers: dict[str, str], body: bytes, allowed_origins: tuple[str, ...], *,
                      require_agentcore_routing_headers: bool = False) -> tuple[int, str, str] | None:
    origin = headers.get("origin")
    if origin is not None and origin not in allowed_origins:
        return 403, "origin_not_allowed", "Origin is not in the configured allowlist."
    if headers.get("mcp-protocol-version") != PROTOCOL_VERSION:
        return 400, "invalid_protocol_version", f"MCP-Protocol-Version must be {PROTOCOL_VERSION}."
    try:
        request = json.loads(body)
    except json.JSONDecodeError:
        return 400, "invalid_json", "Request body must be JSON."
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return 400, "invalid_json_rpc", "Request body must be a JSON-RPC 2.0 object."
    if "id" not in request:
        return 400, "missing_request_id", "A stateless MCP request must include a JSON-RPC id."
    params = request.get("params")
    if not isinstance(params, dict):
        return 400, "invalid_params", "Request params must be a JSON object."
    metadata = params.get("_meta")
    if not isinstance(metadata, dict):
        return 400, "missing_request_metadata", "params._meta must carry the MCP v2 request envelope."
    if metadata.get("io.modelcontextprotocol/protocolVersion") != PROTOCOL_VERSION:
        return 400, "metadata_protocol_mismatch", "Request metadata must match MCP-Protocol-Version."
    if not isinstance(metadata.get("io.modelcontextprotocol/clientCapabilities"), dict):
        return 400, "missing_client_capabilities", "Request metadata must contain client capabilities."
    method = request.get("method")
    if method not in SUPPORTED_METHODS:
        return 400, "unsupported_method", "This public demo supports only tools/list and tools/call."
    if method == "tools/call" and params.get("name") not in SUPPORTED_TOOL_NAMES:
        return 400, "unsupported_tool", "This public demo supports only its two read-only tools."
    if require_agentcore_routing_headers:
        if headers.get("mcp-method") != method:
            return 400, "method_mismatch", "Mcp-Method must match JSON-RPC method."
        if method == "tools/call" and headers.get("mcp-name") != params["name"]:
            return 400, "name_mismatch", "Mcp-Name must match params.name for tools/call."
    return None


async def _send_error(send: Callable[[dict[str, Any]], Awaitable[None]], status: int, code: str, message: str) -> None:
    response = json.dumps({"error": {"code": code, "message": message}}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(response)).encode())]})
    await send({"type": "http.response.body", "body": response, "more_body": False})


def create_app(*, record_store: RecordStore | None = None, allowed_origins: tuple[str, ...] = (),
               max_request_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES,
               require_agentcore_routing_headers: bool = False,
               transport_security: TransportSecuritySettings | None = None,
               planner: Callable[..., Any] = plan_live, now: Callable[[], int] = unix_now,
               request_budget: RequestBudget | None = None) -> Any:
    if max_request_body_bytes < 1:
        raise ValueError("max_request_body_bytes must be positive")
    store = record_store or DynamoDbRecordStore(os.environ.get("MCP_RECORD_TABLE", ""))
    server = create_server(store, planner=planner, now=now)
    app = server.streamable_http_app(
        streamable_http_path=MCP_PATH, json_response=True, stateless_http=True,
        max_request_body_size=max_request_body_bytes,
        transport_security=transport_security or TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=["localhost:*", "127.0.0.1:*"],
            allowed_origins=list(allowed_origins),
        ), host="0.0.0.0",
    )
    return ProtocolContractMiddleware(app, allowed_origins, max_request_body_bytes, request_budget,
                                      require_agentcore_routing_headers=require_agentcore_routing_headers)


def create_agentcore_app() -> Any:
    return create_app(require_agentcore_routing_headers=True, allowed_origins=(),
                      transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
