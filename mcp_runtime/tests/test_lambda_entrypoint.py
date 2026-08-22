from __future__ import annotations

import json

import pytest

import mcp_runtime.lambda_entrypoint as lambda_entrypoint
from mcp_runtime.lambda_entrypoint import _allowed_origins_from_environment, _max_request_body_bytes_from_environment, load_bearer_token
from mcp_runtime.server import PROTOCOL_VERSION


class FakeSsm:
    def __init__(self, value: str) -> None:
        self.value = value
        self.calls: list[tuple[str, bool]] = []

    def get_parameter(self, *, Name: str, WithDecryption: bool) -> dict[str, object]:
        self.calls.append((Name, WithDecryption))
        return {"Parameter": {"Value": self.value}}


def test_lambda_reads_only_the_named_secure_string():
    client = FakeSsm("short-lived-token")
    assert load_bearer_token("/cape-fear/demo", ssm_client=client) == "short-lived-token"
    assert client.calls == [("/cape-fear/demo", True)]


def test_lambda_rejects_a_missing_or_empty_token_without_disclosing_a_value():
    with pytest.raises(RuntimeError, match="must name"):
        load_bearer_token("", ssm_client=FakeSsm("ignored"))
    with pytest.raises(RuntimeError, match="missing or empty"):
        load_bearer_token("/cape-fear/demo", ssm_client=FakeSsm(""))


def test_lambda_environment_parses_explicit_origins_and_size(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://claude.ai, https://chatgpt.com")
    monkeypatch.setenv("MCP_MAX_REQUEST_BODY_BYTES", "8192")
    assert _allowed_origins_from_environment() == ("https://claude.ai", "https://chatgpt.com")
    assert _max_request_body_bytes_from_environment() == 8192
    monkeypatch.setenv("MCP_MAX_REQUEST_BODY_BYTES", "zero")
    with pytest.raises(RuntimeError, match="integer"):
        _max_request_body_bytes_from_environment()


def test_function_url_adapter_accepts_a_public_mcp_request_without_agentcore_headers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN_PARAMETER", "/cape-fear/demo")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://claude.ai")
    monkeypatch.setattr(lambda_entrypoint, "load_bearer_token", lambda _: "short-lived-token")
    monkeypatch.setattr(lambda_entrypoint, "_bearer_token", None)
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/mcp",
        "rawQueryString": "",
        "headers": {
            "authorization": "Bearer short-lived-token",
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": PROTOCOL_VERSION,
        },
        "requestContext": {"http": {"method": "POST", "path": "/mcp", "protocol": "HTTP/1.1", "sourceIp": "127.0.0.1"}},
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION, "io.modelcontextprotocol/clientCapabilities": {}}},
        }),
        "isBase64Encoded": False,
    }
    response = lambda_entrypoint.handler(event, object())
    assert response["statusCode"] == 200
    assert {tool["name"] for tool in json.loads(response["body"])["result"]["tools"]} == {
        "find_surf_windows", "explain_surf_window"
    }
