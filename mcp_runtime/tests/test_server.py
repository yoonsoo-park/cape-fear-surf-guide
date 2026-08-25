from __future__ import annotations

import json

from starlette.testclient import TestClient

from mcp_runtime.server import PROTOCOL_VERSION, SUPPORTED_TOOL_NAMES, _validate_request, create_app
from mcp_runtime.exposure_control import InMemoryRequestBudget
from surf.application import plan_fixture
from surf.live_store import InMemoryRecordStore


def _request(method: str, params: dict) -> dict:
    return {
        "jsonrpc": "2.0", "id": 1, "method": method,
        "params": {**params, "_meta": {"io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                                           "io.modelcontextprotocol/clientCapabilities": {}}},
    }


def _headers() -> dict[str, str]:
    return {"MCP-Protocol-Version": PROTOCOL_VERSION, "Accept": "application/json, text/event-stream"}


def _standard_request(method: str, params: dict | None = None, *, request_id: int | None = 1) -> dict:
    request = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        request["id"] = request_id
    if params is not None:
        request["params"] = params
    return request


def _planner(*args):
    return plan_fixture("normal")


def test_public_transport_is_unauthenticated_but_rejects_invalid_protocol_and_body():
    headers = {"mcp-protocol-version": PROTOCOL_VERSION}
    assert _validate_request(headers, b"not-json", ())[1] == "invalid_json"
    assert _validate_request({}, b"{}", ())[1] == "invalid_json_rpc"
    unsupported = _request("tools/call", {"name": "other", "arguments": {}})
    assert _validate_request(headers, json.dumps(unsupported).encode(), ())[1] == "unsupported_tool"


def test_standard_mcp_handshake_is_accepted_for_codex_without_relaxing_v2_contract():
    initialize = _standard_request("initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "codex-mcp-client", "version": "0.144.3"},
    })
    assert _validate_request({}, json.dumps(initialize).encode(), ()) is None
    assert _validate_request({}, json.dumps(_standard_request("notifications/initialized", {}, request_id=None)).encode(), ()) is None
    assert _validate_request({}, json.dumps(_standard_request("tools/list", {})).encode(), ()) is None
    assert _validate_request({}, json.dumps(_request("tools/list", {})).encode(), ()) [1] == "invalid_protocol_version"


def test_standard_codex_initialize_discovery_and_tool_call_use_the_same_deterministic_server():
    store = InMemoryRecordStore()
    app = create_app(record_store=store, planner=_planner, now=lambda: 1_000)
    with TestClient(app, base_url="http://localhost:8000") as client:
        initialize = client.post("/mcp", json=_standard_request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "codex-mcp-client", "version": "0.144.3"},
        }), headers={"Accept": "text/event-stream, application/json"})
        assert initialize.status_code == 200
        assert initialize.json()["result"]["protocolVersion"] == "2025-06-18"

        initialized = client.post("/mcp", json=_standard_request("notifications/initialized", {}, request_id=None),
                                  headers={"Accept": "text/event-stream, application/json"})
        assert initialized.status_code in {200, 202}

        tools = client.post("/mcp", json=_standard_request("tools/list", {}),
                            headers={"Accept": "text/event-stream, application/json"})
        assert tools.status_code == 200
        assert {tool["name"] for tool in tools.json()["result"]["tools"]} == set(SUPPORTED_TOOL_NAMES)

        called = client.post("/mcp", json=_standard_request("tools/call", {
            "name": "find_surf_windows", "arguments": {
                "date": "2026-08-22", "party_profile": {"skill_level": "beginner", "ages": [12, 40]},
                "preferred_area": "wrightsville-beach",
            },
        }), headers={"Accept": "text/event-stream, application/json"})
        assert called.status_code == 200
        assert called.json()["result"]["structuredContent"]["windows"][0]["retrieval"]["mode"] == "live"


def test_live_find_and_explain_return_the_stored_record_without_bearer_or_requery():
    store = InMemoryRecordStore()
    planner_calls: list[tuple] = []

    def planner(*args):
        planner_calls.append(args)
        return _planner(*args)

    app = create_app(record_store=store, planner=planner, now=lambda: 1_000)
    find_request = _request("tools/call", {"name": "find_surf_windows", "arguments": {
        "date": "2026-08-22", "party_profile": {"skill_level": "beginner", "ages": [12, 40]},
        "preferred_area": "wrightsville-beach",
    }})
    with TestClient(app, base_url="http://localhost:8000") as client:
        find_response = client.post("/mcp", json=find_request, headers=_headers())
        assert find_response.status_code == 200
        window = find_response.json()["result"]["structuredContent"]["windows"][0]
        assert window["retrieval"]["mode"] == "live"
        assert window["record"]["window_id"] in store.records
        explain_response = client.post("/mcp", json=_request("tools/call", {
            "name": "explain_surf_window", "arguments": {"window_id": window["record"]["window_id"]},
        }), headers=_headers())
    assert explain_response.status_code == 200
    assert explain_response.json()["result"]["structuredContent"]["record"] == window["record"]
    assert len(planner_calls) == 1


def test_expired_and_unknown_window_ids_are_explicit_errors():
    store = InMemoryRecordStore(records={"expired": ({"resultType": "complete"}, 100)})
    app = create_app(record_store=store, planner=_planner, now=lambda: 101)
    with TestClient(app, base_url="http://localhost:8000") as client:
        expired = client.post("/mcp", json=_request("tools/call", {
            "name": "explain_surf_window", "arguments": {"window_id": "expired"},
        }), headers=_headers())
        unknown = client.post("/mcp", json=_request("tools/call", {
            "name": "explain_surf_window", "arguments": {"window_id": "unknown"},
        }), headers=_headers())
    assert expired.json()["result"]["structuredContent"]["error"]["code"] == "expired_window_id"
    assert unknown.json()["result"]["structuredContent"]["error"]["code"] == "unknown_window_id"


def test_post_only_origin_and_request_size_boundaries_hold_without_inspecting_authorization():
    app = create_app(record_store=InMemoryRecordStore(), planner=_planner,
                     allowed_origins=("https://claude.ai",), max_request_body_bytes=2048)
    with TestClient(app, base_url="http://localhost:8000") as client:
        assert client.get("/mcp").status_code == 405
        assert client.post("/mcp", json=_request("tools/list", {}),
                           headers={**_headers(), "Origin": "https://chatgpt.com"}).status_code == 403
        assert client.post("/mcp", content=b"x" * 2049, headers=_headers()).status_code == 413


def test_valid_mcp_posts_consume_a_hard_budget_before_any_tool_or_live_source_runs():
    budget = InMemoryRequestBudget(1)
    app = create_app(record_store=InMemoryRecordStore(), planner=_planner, request_budget=budget)
    with TestClient(app, base_url="http://localhost:8000") as client:
        first = client.post("/mcp", json=_request("tools/list", {}), headers=_headers())
        second = client.post("/mcp", json=_request("tools/list", {}), headers=_headers())
        malformed = client.post("/mcp", content=b"not-json", headers=_headers())
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "demo_request_budget_exhausted"
    assert malformed.status_code == 400
    assert budget.count == 1
