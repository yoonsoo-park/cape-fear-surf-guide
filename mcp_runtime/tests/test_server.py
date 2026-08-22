from __future__ import annotations

import asyncio

from mcp.server import MCPServer
from mcp.client import Client
from mcp_types import CallToolResult
from starlette.testclient import TestClient

from mcp_runtime.server import PROTOCOL_VERSION, _validate_request, create_agentcore_app, create_app, create_server


def test_v2_server_registers_only_the_two_read_only_tools():
    async def run() -> None:
        server = create_server()
        tools = await server.list_tools()
        assert isinstance(server, MCPServer)
        assert {tool.name for tool in tools} == {"find_surf_windows", "explain_surf_window"}

    asyncio.run(run())


def test_find_then_explain_rebuilds_the_same_frozen_record_without_session_state():
    async def run() -> None:
        server = create_server()
        found = await server.call_tool("find_surf_windows", {
            "date": "2026-08-29",
            "party_profile": {"skill_level": "beginner", "ages": [12, 40]},
            "preferred_area": "wrightsville-beach",
        })
        assert found.result_type == "complete"
        window = found.structured_content["windows"][0]
        first = await server.call_tool("explain_surf_window", {"window_id": window["record"]["window_id"]})
        second = await create_server().call_tool("explain_surf_window", {"window_id": window["record"]["window_id"]})
        assert first.result_type == second.result_type == "complete"
        assert first.structured_content["record"] == second.structured_content["record"] == window["record"]

    asyncio.run(run())


def test_sdk_v2_client_obtains_a_structured_frozen_recommendation():
    async def run() -> None:
        async with Client(create_server()) as client:
            result = await client.call_tool("find_surf_windows", {
                "date": "2026-08-29",
                "party_profile": {"skill_level": "beginner", "ages": [12, 40]},
            })
        assert result.result_type == "complete"
        assert result.structured_content["windows"][0]["record"]["decision"]["state"] == "recommended_window"

    asyncio.run(run())


def test_unknown_window_is_a_deterministic_structured_tool_error():
    async def run() -> None:
        result = await create_server().call_tool("explain_surf_window", {"window_id": "does-not-exist"})
        assert isinstance(result, CallToolResult)
        assert result.result_type == "complete"
        assert result.is_error is True
        assert result.structured_content["error"]["code"] == "unknown_window_id"

    asyncio.run(run())


def test_http_headers_must_match_json_rpc_request_and_origin_must_be_allowed():
    body = (
        b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"find_surf_windows",'
        b'"arguments":{},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",'
        b'"io.modelcontextprotocol/clientCapabilities":{}}}}'
    )
    headers = {
        "authorization": "Bearer test-token",
        "origin": "http://localhost",
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": "tools/call",
        "mcp-name": "find_surf_windows",
    }
    assert _validate_request(headers, body, "test-token", ("http://localhost",)) is None
    assert _validate_request({**headers, "mcp-method": "tools/list"}, body, "test-token", ("http://localhost",))[1] == "method_mismatch"
    assert _validate_request({**headers, "mcp-name": "other"}, body, "test-token", ("http://localhost",))[1] == "name_mismatch"
    assert _validate_request({**headers, "origin": "https://untrusted.example"}, body, "test-token", ("http://localhost",))[1] == "origin_not_allowed"
    assert _validate_request({key: value for key, value in headers.items() if key != "authorization"}, body, "test-token", ("http://localhost",))[1] == "unauthorized"


def test_http_transport_accepts_matching_request_and_rejects_a_mismatch():
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "find_surf_windows",
            "arguments": {
                "date": "2026-08-29",
                "party_profile": {"skill_level": "beginner", "ages": [12, 40]},
                "preferred_area": "wrightsville-beach",
            },
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    headers = {
        "Authorization": "Bearer test-token",
        "Origin": "http://localhost",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": "tools/call",
        "Mcp-Name": "find_surf_windows",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(create_app(auth_token="test-token"), base_url="http://localhost:8000") as client:
        accepted = client.post("/mcp", json=request, headers=headers)
        rejected = client.post("/mcp", json=request, headers={**headers, "Mcp-Name": "wrong"})
    assert accepted.status_code == 200
    payload = accepted.json()
    assert payload["result"]["resultType"] == "complete"
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "name_mismatch"


def test_stateless_runtime_rejects_get_streams():
    with TestClient(create_app(auth_token="test-token"), base_url="http://localhost:8000") as client:
        response = client.get("/mcp", headers={"Accept": "text/event-stream"})
    assert response.status_code in {404, 405}


def test_agentcore_variant_relies_on_the_outer_iam_boundary_but_preserves_protocol_checks():
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "find_surf_windows",
            "arguments": {"date": "2026-08-29", "party_profile": {"skill_level": "beginner", "ages": [12, 40]}},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    headers = {
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": "tools/call",
        "Mcp-Name": "find_surf_windows",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(create_agentcore_app(), base_url="http://agentcore.internal:8000") as client:
        response = client.post("/mcp", json=request, headers=headers)
    assert response.status_code == 200
    assert response.json()["result"]["resultType"] == "complete"
