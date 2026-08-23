from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping

import pytest

from mcp_runtime.claude_desktop_bridge import (
    BridgeFailure,
    HttpResponse,
    RemoteMcpProxy,
    create_bridge_server,
    parse_args,
    validate_endpoint,
)
from mcp_runtime.server import PROTOCOL_VERSION


class FakeTokenProvider:
    def __init__(self, token: str = "test-token") -> None:
        self.token = token

    def get_token(self) -> str:
        return self.token


class MissingTokenProvider:
    def get_token(self) -> str:
        raise BridgeFailure("keychain_token_unavailable", "The dedicated Keychain token is unavailable.")


class FakeHttp:
    def __init__(self, response: HttpResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, str], bytes]] = []

    def post(self, url: str, headers: Mapping[str, str], body: bytes) -> HttpResponse:
        self.calls.append((url, headers, body))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _result_response() -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "resultType": "complete",
                    "content": [{"type": "text", "text": "reviewed frozen result"}],
                    "structuredContent": {"retrieval": {"mode": "frozen_snapshot"}, "window_id": "window-1"},
                },
            }
        ).encode(),
    )


def test_bridge_registers_only_the_two_reviewed_tools():
    async def run() -> None:
        server = create_bridge_server(RemoteMcpProxy("https://example.invalid/mcp", FakeTokenProvider(), FakeHttp(_result_response())))
        assert {tool.name for tool in await server.list_tools()} == {"find_surf_windows", "explain_surf_window"}

    asyncio.run(run())


def test_bridge_forwards_each_tool_call_as_a_fresh_authenticated_v2_request(capsys: pytest.CaptureFixture[str]):
    http = FakeHttp(_result_response())
    proxy = RemoteMcpProxy("https://example.invalid/mcp", FakeTokenProvider("not-a-real-token"), http)
    first = proxy.call_tool("find_surf_windows", {"date": "2026-08-29", "party_profile": {"skill_level": "beginner"}})
    second = proxy.call_tool("explain_surf_window", {"window_id": "window-1"})

    assert first.structured_content == {"retrieval": {"mode": "frozen_snapshot"}, "window_id": "window-1"}
    assert second.structured_content == first.structured_content
    assert [json.loads(call[2])["id"] for call in http.calls] == [1, 2]
    assert all(call[1]["Authorization"] == "Bearer not-a-real-token" for call in http.calls)
    forwarded = json.loads(http.calls[0][2])
    assert forwarded["params"]["_meta"] == {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    assert http.calls[0][1]["MCP-Protocol-Version"] == PROTOCOL_VERSION
    assert "not-a-real-token" not in capsys.readouterr().err


def test_local_mcp_tool_call_preserves_a_valid_remote_structured_result():
    async def run() -> None:
        server = create_bridge_server(
            RemoteMcpProxy("https://example.invalid/mcp", FakeTokenProvider(), FakeHttp(_result_response()))
        )
        result = await server.call_tool(
            "find_surf_windows",
            {"date": "2026-08-29", "party_profile": {"skill_level": "beginner", "ages": [12, 40]}},
        )
        assert result.is_error is False
        assert result.result_type == "complete"
        assert result.structured_content == {"retrieval": {"mode": "frozen_snapshot"}, "window_id": "window-1"}

    asyncio.run(run())


@pytest.mark.parametrize(
    ("http_response", "expected_code"),
    [
        (HttpResponse(401, b'{"error":"nope"}'), "remote_http_error"),
        (HttpResponse(200, b"not-json"), "remote_invalid_response"),
        (BridgeFailure("remote_network_error", "The remote MCP endpoint could not be reached."), "remote_network_error"),
    ],
)
def test_bridge_maps_remote_failures_to_secret_safe_mcp_errors(
    http_response: HttpResponse | Exception, expected_code: str, capsys: pytest.CaptureFixture[str]
):
    token = "not-a-real-token"
    result = RemoteMcpProxy("https://example.invalid/mcp", FakeTokenProvider(token), FakeHttp(http_response)).call_tool(
        "find_surf_windows", {"date": "2026-08-29"}
    )
    assert result.is_error is True
    assert result.structured_content["error"]["code"] == expected_code
    assert token not in result.content[0].text
    assert token not in capsys.readouterr().err


def test_bridge_maps_a_missing_keychain_token_without_attempting_http():
    http = FakeHttp(_result_response())
    result = RemoteMcpProxy("https://example.invalid/mcp", MissingTokenProvider(), http).call_tool("find_surf_windows", {})
    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "keychain_token_unavailable"
    assert http.calls == []


@pytest.mark.parametrize("endpoint", ["http://example.invalid/mcp", "https://example.invalid/other", "https://example.invalid/mcp?x=1"])
def test_bridge_requires_the_exact_public_https_mcp_endpoint(endpoint: str):
    with pytest.raises(ValueError, match="HTTPS URL"):
        validate_endpoint(endpoint)


def test_bridge_accepts_an_explicit_nonsecret_ca_bundle(tmp_path):
    bundle = tmp_path / "company-ca.pem"
    bundle.write_text("test certificate bundle")
    assert parse_args(["--endpoint", "https://example.invalid/mcp", "--ca-bundle", str(bundle)]).ca_bundle == str(bundle)
