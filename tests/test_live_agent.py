from __future__ import annotations

from surf.application import plan_fixture
from surf.live_agent import explain_live_record_with_agent
from surf.replay_model import FixturePlannerModel


def test_live_agent_explanation_uses_fact_tools_without_changing_hazard_policy():
    record = plan_fixture("hazard").record
    result = explain_live_record_with_agent(record, FixturePlannerModel())

    assert result.brief_source == "agent"
    assert result.model_schema_valid is True
    assert result.invariant_violations == ()
    assert result.brief.window_id == record.window_id
    assert result.brief.decision_state == record.decision.state
    assert [call["name"] for call in result.tool_calls] == [
        "list_supported_beaches", "get_nws_hazards", "get_nws_surf_zone_forecast",
        "get_tide_predictions", "get_water_quality_status", "get_marine_forecast",
    ]
