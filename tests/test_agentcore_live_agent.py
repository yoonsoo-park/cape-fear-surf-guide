from __future__ import annotations

from dataclasses import dataclass

from agentcore_runtime.server import process_invocation


@dataclass
class Result:
    record: object
    brief: object
    brief_source: str = "agent"
    tool_calls: tuple = ()
    model_schema_valid: bool = True
    invariant_violations: tuple = ()


def test_agentcore_runtime_rejects_missing_structured_input_without_invoking_a_model():
    status, response = process_invocation({"input": {}})
    assert status == 400
    assert response["error"]["code"] == "invalid_input"


def test_agentcore_runtime_returns_only_safe_structured_agent_result():
    class Model:
        def model_dump(self, **kwargs): return {"decision": {"state": "recommended_window"}}

    result = Result(record=Model(), brief=Model(), tool_calls=({"name": "get_nws_hazards"},))

    def planner(*args, **kwargs): return result

    status, response = process_invocation(
        {"input": {"date": "2026-08-25", "party_profile": {"skill_level": "beginner"}}}, planner=planner,
    )
    assert status == 200
    assert response["output"]["tool_calls"] == ["get_nws_hazards"]
    assert response["output"]["invariant_violations"] == ()
