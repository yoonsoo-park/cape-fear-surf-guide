"""Stateless Streamable HTTP MCP v2 server for the shared surf policy core."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Awaitable, Callable
from hmac import compare_digest
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import CallToolResult, TextContent

# The deployment build context contains this runtime and the shared ``surf``
# application package.  Keep that source boundary explicit so the MCP v2
# runtime can remain isolated from Strands' currently incompatible MCP v1 pin.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
for candidate in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
    if (candidate / "surf").is_dir():
        PROJECT_ROOT = candidate
        break
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from surf.mcp_contract import ContractError, explain_frozen_window, find_frozen_windows

PROTOCOL_VERSION = "2026-07-28"
MCP_PATH = "/mcp"
DEFAULT_MAX_REQUEST_BODY_BYTES = 65_536
SUPPORTED_METHODS = frozenset({"tools/list", "tools/call"})
SUPPORTED_TOOL_NAMES = frozenset({"find_surf_windows", "explain_surf_window"})


def _result_payload(result: Any) -> dict[str, Any]:
    return {
        "resultType": "complete",
        "record": result.record.model_dump(mode="json"),
        "brief": result.brief.model_dump(mode="json"),
        "brief_source": result.brief_source,
        "retrieval": {"mode": "frozen_snapshot", "snapshot_id": result.record.snapshot_id},
    }


def _error_result(error: ContractError) -> CallToolResult:
    payload = error.as_dict()
    return CallToolResult(
        content=[TextContent(text=json.dumps(payload, sort_keys=True))],
        structuredContent=payload,
        isError=True,
    )


def create_server() -> MCPServer:
    server = MCPServer(
        "cape-fear-surf-guide",
        title="Cape Fear Surf Guide",
        description="Read-only evidence-backed surf planning windows. Deterministic policy owns every verdict.",
        version="0.1.0",
    )

    @server.tool(name="find_surf_windows", structured_output=True)
    def find_surf_windows(
        date: str,
        party_profile: dict[str, Any],
        preferred_area: str | None = None,
        time_range: str | None = None,
    ) -> dict[str, Any]:
        """Return a reviewed frozen planning window with its full evidence record."""
        matches = find_frozen_windows(date, party_profile, preferred_area, time_range)
        if isinstance(matches, ContractError):
            return _error_result(matches)
        return {"resultType": "complete", "windows": [_result_payload(match) for match in matches]}

    @server.tool(name="explain_surf_window", structured_output=True)
    def explain_surf_window(window_id: str, reading_level: str | None = None) -> dict[str, Any]:
        """Rebuild a reviewed frozen record from window_id without a server session."""
        result = explain_frozen_window(window_id)
        if isinstance(result, ContractError):
            return _error_result(result)
        payload = _result_payload(result)
        payload["reading_level"] = reading_level or "default"
        return payload

    return server


class ProtocolContractMiddleware:
    """Apply the public MCP contract before passing a request to the SDK.

    ``Mcp-Method`` and ``Mcp-Name`` are an AgentCore routing extension.  They
    are deliberately checked only in the isolated AgentCore mode; ordinary
    Streamable HTTP clients route using the JSON-RPC body.
    """

    def __init__(self, app: Callable[..., Awaitable[None]], auth_token: str | None,
                 allowed_origins: tuple[str, ...], max_request_body_bytes: int,
                 require_agentcore_routing_headers: bool = False) -> None:
        self.app = app
        self.auth_token = auth_token
        self.allowed_origins = allowed_origins
        self.max_request_body_bytes = max_request_body_bytes
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
        error = _validate_request(
            headers,
            body,
            self.auth_token,
            self.allowed_origins,
            require_agentcore_routing_headers=self.require_agentcore_routing_headers,
        )
        if error is not None:
            await _send_error(send, *error)
            return

        sent = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            # Keep forwarding the original receive channel after replaying the
            # inspected request.  Returning a synthetic disconnect here would
            # cancel a request-scoped SSE response before the server can emit
            # it; a real client disconnect still reaches the MCP SDK.
            return await receive()

        # MCP Python SDK v2 currently performs an internal routing-header
        # consistency check even for its modern stateless transport.  Public
        # callers do not send AgentCore's extra headers, so derive ephemeral
        # values from the already-validated body at this adapter boundary.
        # Strict AgentCore mode instead passes its client-supplied headers
        # through unchanged and verifies them above.
        sdk_scope = scope if self.require_agentcore_routing_headers else _public_sdk_scope(scope, json.loads(body))
        await self.app(sdk_scope, replay_receive, send)


async def _read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _public_sdk_scope(scope: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Give the SDK body-derived routing metadata without trusting client extras."""
    headers = [
        (key, value)
        for key, value in scope.get("headers", [])
        if key.lower() not in {b"mcp-method", b"mcp-name"}
    ]
    headers.append((b"mcp-method", request["method"].encode("latin-1")))
    if request["method"] == "tools/call":
        headers.append((b"mcp-name", request["params"]["name"].encode("latin-1")))
    return {**scope, "headers": headers}


def _validate_request(
    headers: dict[str, str],
    body: bytes,
    auth_token: str | None,
    allowed_origins: tuple[str, ...],
    *,
    require_agentcore_routing_headers: bool = False,
) -> tuple[int, str, str] | None:
    """Validate only protocol facts; never log the request or bearer token."""
    supplied_authorization = headers.get("authorization", "")
    expected_authorization = f"Bearer {auth_token}" if auth_token is not None else ""
    if auth_token is not None and not compare_digest(supplied_authorization, expected_authorization):
        return 401, "unauthorized", "A configured bearer token is required."
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
        return 400, "unsupported_method", "This frozen demo supports only tools/list and tools/call."
    if method == "tools/call":
        name = params.get("name")
        if name not in SUPPORTED_TOOL_NAMES:
            return 400, "unsupported_tool", "This frozen demo supports only its reviewed read-only tools."
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


def create_app(
    *,
    auth_token: str | None = None,
    allowed_origins: tuple[str, ...] = ("http://localhost",),
    max_request_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES,
    require_bearer_token: bool = True,
    require_agentcore_routing_headers: bool = False,
    transport_security: TransportSecuritySettings | None = None,
) -> Any:
    """Create a stateless JSON-over-POST `/mcp` application.

    The standalone service requires its own bearer token and accepts standard
    MCP JSON-RPC routing.  The AgentCore entry point keeps its proprietary
    routing-header checks in a separate configuration.
    """
    token = auth_token if auth_token is not None else os.environ.get("MCP_AUTH_TOKEN")
    if require_bearer_token and not token:
        raise RuntimeError("MCP_AUTH_TOKEN must be configured; the MCP endpoint never starts unauthenticated.")
    if max_request_body_bytes < 1:
        raise ValueError("max_request_body_bytes must be positive")
    server = create_server()
    app = server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        json_response=True,
        stateless_http=True,
        max_request_body_size=max_request_body_bytes,
        transport_security=transport_security or TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["localhost:*", "127.0.0.1:*"],
            allowed_origins=list(allowed_origins),
        ),
        host="127.0.0.1" if require_bearer_token else "0.0.0.0",
    )
    return ProtocolContractMiddleware(
        app,
        token if require_bearer_token else None,
        allowed_origins,
        max_request_body_bytes,
        require_agentcore_routing_headers=require_agentcore_routing_headers,
    )


def create_agentcore_app() -> Any:
    """Create the managed-runtime variant protected by AgentCore IAM auth.

    AgentCore terminates the public IAM (SigV4) authentication before invoking
    the container.  The managed network boundary has no browser origin, so DNS
    rebinding host checks for an internet-facing local server do not apply.
    """
    return create_app(
        require_bearer_token=False,
        require_agentcore_routing_headers=True,
        allowed_origins=(),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
