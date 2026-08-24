from __future__ import annotations

import json

from mcp_runtime.agentcore_planner import AgentCorePlanner
from surf.application import plan_fixture
from surf.brief import template_brief


class _Body:
    def __init__(self, value: dict): self.value = value
    def read(self) -> bytes: return json.dumps(self.value).encode()


class _Client:
    def __init__(self, response: dict): self.response = response; self.calls: list[dict] = []
    def invoke_agent_runtime(self, **kwargs): self.calls.append(kwargs); return self.response


def _output() -> dict:
    result = plan_fixture("normal")
    brief = template_brief(result.record)
    return {"output": {"record": result.record.model_dump(mode="json"), "brief": brief.model_dump(mode="json"),
                       "brief_source": "template", "model_schema_valid": True, "invariant_violations": []}}


def test_agentcore_planner_uses_new_isolated_session_and_validates_the_immutable_record():
    client = _Client({"statusCode": 200, "contentType": "application/json", "response": _Body(_output())})
    planner = AgentCorePlanner("arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/cape-fear", client=client)
    result = planner("2026-08-25", {"skill_level": "beginner"})
    assert result.record.window_id
    call = client.calls[0]
    assert call["runtimeSessionId"].startswith("cape-fear-mcp-")
    assert len(call["runtimeSessionId"]) >= 33
    assert json.loads(call["payload"])["input"]["date"] == "2026-08-25"


def test_agentcore_planner_fails_closed_on_invariant_violation():
    output = _output()
    output["output"]["invariant_violations"] = ["source_urls_changed"]
    client = _Client({"statusCode": 200, "contentType": "application/json", "response": _Body(output)})
    result = AgentCorePlanner("arn", client=client)("2026-08-25", {"skill_level": "beginner"})
    assert result[0] == "agentcore_policy_validation_failed"


def test_agentcore_planner_normalizes_generic_mcp_skill_alias_before_invoke():
    client = _Client({"statusCode": 200, "contentType": "application/json", "response": _Body(_output())})
    planner = AgentCorePlanner("arn", client=client)
    result = planner("2026-08-25", {"skill": "beginner", "ages": [12, 40]})
    assert result.record.window_id
    payload = json.loads(client.calls[0]["payload"])
    assert payload["input"]["party_profile"] == {"skill_level": "beginner", "ages": [12, 40], "accessibility_needs": []}


def test_agentcore_planner_rejects_invalid_profile_without_runtime_call():
    client = _Client({"statusCode": 200, "contentType": "application/json", "response": _Body(_output())})
    result = AgentCorePlanner("arn", client=client)("2026-08-25", {"ages": [12, 40]})
    assert result[0] == "invalid_party_profile"
    assert client.calls == []


def test_agentcore_planner_normalizes_human_preferred_area_before_invoke():
    client = _Client({"statusCode": 200, "contentType": "application/json", "response": _Body(_output())})
    planner = AgentCorePlanner("arn", client=client)
    result = planner("2026-08-25", {"skill_level": "beginner"}, "Wrightsville Beach")
    assert result.record.window_id
    payload = json.loads(client.calls[0]["payload"])
    assert payload["input"]["preferred_area"] == "wrightsville-beach"


def test_agentcore_planner_rejects_unknown_area_without_runtime_call():
    client = _Client({"statusCode": 200, "contentType": "application/json", "response": _Body(_output())})
    result = AgentCorePlanner("arn", client=client)("2026-08-25", {"skill_level": "beginner"}, "Carolina Beach")
    assert result[0] == "unsupported_area"
    assert client.calls == []
