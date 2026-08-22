from __future__ import annotations

from surf.planner_agent import plan_fixture_with_agent
from surf.replay_model import FixturePlannerModel
from surf.schema import DecisionState


def test_single_strands_agent_drives_real_tools_and_preserves_hazard_decision():
    results = [plan_fixture_with_agent("hazard", FixturePlannerModel()) for _ in range(30)]
    for result in results:
        assert result.record.decision.state == DecisionState.official_advisory_present
        assert result.brief.decision_state == result.record.decision.state
        assert result.brief.window_id == result.record.window_id
        assert result.brief_source == "agent"
        assert [call["name"] for call in result.tool_calls] == [
            "list_supported_beaches", "get_nws_hazards", "get_nws_surf_zone_forecast",
            "get_tide_predictions", "get_water_quality_status", "get_marine_forecast",
        ]
        assert all("arguments" in call and "outcome" in call for call in result.tool_calls)
        assert result.findings == ()
    assert len({result.record.model_dump_json() for result in results}) == 1


def test_normal_agent_path_has_no_false_veto():
    results = [plan_fixture_with_agent("normal", FixturePlannerModel()) for _ in range(30)]
    assert all(result.record.decision.state == DecisionState.recommended_window for result in results)
    assert all(result.findings == () for result in results)
    assert all(result.elapsed_ms < 30_000 and result.estimated_cost_usd <= 0.05 for result in results)


class BrokenBriefModel(FixturePlannerModel):
    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        if any(spec.get("name") == "SurfBrief" for spec in (tool_specs or [])):
            raise RuntimeError("simulated model failure")
        async for event in super().stream(messages, tool_specs, system_prompt, **kwargs):
            yield event


def test_model_failure_returns_template_and_full_record():
    result = plan_fixture_with_agent("hazard", BrokenBriefModel())
    assert result.brief_source == "template"
    assert result.brief.window_id == result.record.window_id
    assert result.brief.decision_state == result.record.decision.state


class SkipsHazardToolModel(FixturePlannerModel):
    tool_sequence = tuple(item for item in FixturePlannerModel.tool_sequence if item[0] != "get_nws_hazards")


def test_agent_cannot_change_hazard_policy_by_skipping_the_hazard_tool():
    result = plan_fixture_with_agent("hazard", SkipsHazardToolModel())
    assert "get_nws_hazards" not in [call["name"] for call in result.tool_calls]
    assert result.record.decision.state == DecisionState.official_advisory_present
    assert result.brief.decision_state == DecisionState.official_advisory_present
