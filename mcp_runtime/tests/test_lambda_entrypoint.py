from __future__ import annotations

import json

import pytest

import mcp_runtime.lambda_entrypoint as lambda_entrypoint
from mcp_runtime.lambda_entrypoint import _allowed_origins_from_environment, _max_request_body_bytes_from_environment
from mcp_runtime.server import PROTOCOL_VERSION
from mcp_runtime.exposure_control import InMemoryRequestBudget
from surf.live_store import InMemoryRecordStore


def test_lambda_environment_parses_explicit_origins_and_size(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://claude.ai, https://chatgpt.com")
    monkeypatch.setenv("MCP_MAX_REQUEST_BODY_BYTES", "8192")
    assert _allowed_origins_from_environment() == ("https://claude.ai", "https://chatgpt.com")
    assert _max_request_body_bytes_from_environment() == 8192
    monkeypatch.setenv("MCP_MAX_REQUEST_BODY_BYTES", "zero")
    with pytest.raises(RuntimeError, match="integer"):
        _max_request_body_bytes_from_environment()


def test_api_gateway_rest_adapter_accepts_a_gateway_authenticated_tools_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_RECORD_TABLE", "live-records")
    monkeypatch.setenv("MCP_EXPOSURE_CONTROL_TABLE", "exposure-control")
    monkeypatch.setenv("MCP_EXPOSURE_ID", "test")
    monkeypatch.setenv("MCP_MAX_PUBLIC_POST_REQUESTS", "120")
    monkeypatch.setenv("MCP_PUBLIC_UNTIL_UTC", "2099-01-01T00:00:00")
    monkeypatch.setattr(lambda_entrypoint, "DynamoDbRecordStore", lambda _: InMemoryRecordStore())
    monkeypatch.setattr(lambda_entrypoint, "DynamoDbRequestBudget", lambda _: InMemoryRequestBudget(120))
    monkeypatch.setattr(lambda_entrypoint.AgentCorePlanner, "from_environment", lambda: lambda *args: None)
    event = {
        "resource": "/mcp", "path": "/mcp", "httpMethod": "POST", "headers": {
            "content-type": "application/json", "accept": "application/json, text/event-stream",
            "mcp-protocol-version": PROTOCOL_VERSION,
        }, "requestContext": {"resourcePath": "/mcp", "httpMethod": "POST"},
        "body": json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {
            "_meta": {"io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                      "io.modelcontextprotocol/clientCapabilities": {}},
        }}), "isBase64Encoded": False,
    }
    response = lambda_entrypoint.handler(event, object())
    assert response["statusCode"] == 200
    names = {tool["name"] for tool in json.loads(response["body"])["result"]["tools"]}
    assert names == {"find_surf_windows", "explain_surf_window"}
