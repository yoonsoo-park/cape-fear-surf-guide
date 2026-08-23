"""Local stdio MCP bridge for Claude Desktop's bearer-protected frozen demo.

Claude Desktop speaks MCP to this process over standard input and output.  The
bridge owns the one-way adaptation to the deployed stateless HTTPS endpoint:
it reads the bearer token from the macOS Keychain and sends one independent
JSON-RPC request for each tool call.  It deliberately does not implement OAuth
or retain an MCP session.
"""

from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from mcp.server import MCPServer
from mcp_types import CallToolResult, TextContent

from .server import MCP_PATH, PROTOCOL_VERSION, SUPPORTED_TOOL_NAMES

KEYCHAIN_SERVICE = "cape-fear-surf-guide-mcp"
KEYCHAIN_ACCOUNT = "claude-desktop"
DEFAULT_TIMEOUT_SECONDS = 20.0


class TokenProvider(Protocol):
    """Load a bearer value without exposing it to the bridge configuration."""

    def get_token(self) -> str: ...


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes


class HttpPoster(Protocol):
    """Small injected boundary so secret and network failures are testable."""

    def post(self, url: str, headers: Mapping[str, str], body: bytes) -> HttpResponse: ...


class BridgeFailure(Exception):
    """A public bridge error that intentionally has no secret-bearing cause."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class KeychainTokenProvider:
    """Read the dedicated generic-password item through macOS ``security``."""

    def __init__(self, service: str = KEYCHAIN_SERVICE, account: str = KEYCHAIN_ACCOUNT) -> None:
        self.service = service
        self.account = account

    def get_token(self) -> str:
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-w", "-s", self.service, "-a", self.account],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise BridgeFailure("keychain_token_unavailable", "The dedicated Keychain token is unavailable.") from error
        token = result.stdout.strip()
        if result.returncode != 0 or not token:
            raise BridgeFailure("keychain_token_unavailable", "The dedicated Keychain token is unavailable.")
        return token


class UrllibHttpPoster:
    """POST JSON without adding another dependency to the pinned MCP runtime."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, ca_bundle: str | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.context = ssl.create_default_context(cafile=ca_bundle) if ca_bundle else None

    def post(self, url: str, headers: Mapping[str, str], body: bytes) -> HttpResponse:
        request = Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds, context=self.context) as response:  # noqa: S310 - endpoint is validated config
                return HttpResponse(response.status, response.read())
        except HTTPError as error:
            return HttpResponse(error.code, error.read())
        except (OSError, URLError) as error:
            raise BridgeFailure("remote_network_error", "The remote MCP endpoint could not be reached.") from error


def _error_result(code: str, message: str, details: dict[str, Any] | None = None) -> CallToolResult:
    payload = {"resultType": "error", "error": {"code": code, "message": message, "details": details or {}}}
    return CallToolResult(
        content=[TextContent(text=json.dumps(payload, sort_keys=True))],
        structuredContent=payload,
        isError=True,
    )


def _log_request(endpoint: str, tool_name: str, status: int | str) -> None:
    """Keep the audit line useful without writing requests or credentials."""
    print(
        f"cape-fear-mcp-bridge url={endpoint} tool={tool_name} http_status={status}",
        file=sys.stderr,
        flush=True,
    )


def validate_endpoint(endpoint: str) -> str:
    """Accept only the public HTTPS MCP path; the URL itself is not a secret."""
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path != MCP_PATH or parsed.query or parsed.fragment:
        raise ValueError("--endpoint must be an HTTPS URL ending exactly in /mcp")
    return endpoint


def validate_ca_bundle(path: str) -> str:
    """Require a readable local CA bundle; its path is configuration, not a secret."""
    certificate_path = Path(path)
    if not certificate_path.is_file():
        raise ValueError("--ca-bundle must name a readable certificate bundle file")
    return str(certificate_path)


class RemoteMcpProxy:
    """Translate local tool calls into independent authenticated HTTP requests."""

    def __init__(self, endpoint: str, token_provider: TokenProvider, http: HttpPoster) -> None:
        self.endpoint = validate_endpoint(endpoint)
        self.token_provider = token_provider
        self.http = http
        self._request_ids = count(1)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> CallToolResult:
        try:
            token = self.token_provider.get_token()
        except BridgeFailure as error:
            return _error_result(error.code, error.message, error.details)

        request = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            },
        }
        body = json.dumps(request, separators=(",", ":")).encode("utf-8")
        headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        try:
            response = self.http.post(self.endpoint, headers, body)
        except BridgeFailure as error:
            _log_request(self.endpoint, tool_name, "unavailable")
            return _error_result(error.code, error.message, error.details)

        _log_request(self.endpoint, tool_name, response.status_code)
        if response.status_code != 200:
            return _error_result(
                "remote_http_error",
                "The remote MCP endpoint rejected the request.",
                {"http_status": response.status_code},
            )
        try:
            payload = json.loads(response.body)
        except (TypeError, json.JSONDecodeError):
            return _error_result("remote_invalid_response", "The remote MCP endpoint returned invalid JSON.")
        if not isinstance(payload, dict):
            return _error_result("remote_invalid_response", "The remote MCP endpoint returned an invalid JSON-RPC response.")
        result = payload.get("result")
        if not isinstance(result, dict):
            return _error_result("remote_json_rpc_error", "The remote MCP endpoint returned a JSON-RPC error.")
        try:
            # A valid MCP tool result is passed through unchanged, including its
            # structuredContent, resultType, and deterministic tool errors.
            return CallToolResult.model_validate(result)
        except ValueError:
            return _error_result("remote_invalid_result", "The remote MCP endpoint returned an invalid tool result.")


def create_bridge_server(proxy: RemoteMcpProxy) -> MCPServer:
    """Create the local MCP server that Claude Desktop discovers over stdio."""
    server = MCPServer(
        "cape-fear-surf-guide-local",
        title="Cape Fear Surf Guide (local bridge)",
        description="Read-only bridge to reviewed frozen surf-planning evidence.",
        version="0.1.0",
    )

    @server.tool(name="find_surf_windows", structured_output=True)
    def find_surf_windows(
        date: str,
        party_profile: dict[str, Any],
        preferred_area: str | None = None,
        time_range: str | None = None,
    ) -> CallToolResult:
        """Return a reviewed frozen planning window with full deterministic evidence."""
        return proxy.call_tool(
            "find_surf_windows",
            {
                "date": date,
                "party_profile": party_profile,
                "preferred_area": preferred_area,
                "time_range": time_range,
            },
        )

    @server.tool(name="explain_surf_window", structured_output=True)
    def explain_surf_window(window_id: str, reading_level: str | None = None) -> CallToolResult:
        """Rebuild a frozen result by window ID without relying on local session state."""
        return proxy.call_tool(
            "explain_surf_window",
            {"window_id": window_id, "reading_level": reading_level},
        )

    assert set(SUPPORTED_TOOL_NAMES) == {"find_surf_windows", "explain_surf_window"}
    return server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Claude Desktop MCP bridge.")
    parser.add_argument("--endpoint", required=True, type=validate_endpoint, help="Public HTTPS MCP URL ending in /mcp.")
    parser.add_argument("--keychain-service", default=KEYCHAIN_SERVICE)
    parser.add_argument("--keychain-account", default=KEYCHAIN_ACCOUNT)
    parser.add_argument("--ca-bundle", type=validate_ca_bundle, help="Optional local CA bundle for HTTPS inspection proxies.")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    proxy = RemoteMcpProxy(
        args.endpoint,
        KeychainTokenProvider(args.keychain_service, args.keychain_account),
        UrllibHttpPoster(args.timeout_seconds, args.ca_bundle),
    )
    create_bridge_server(proxy).run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover - exercised by Claude Desktop manually
    main()
