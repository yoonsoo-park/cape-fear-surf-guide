from __future__ import annotations

import json
import re

import pytest

from surf.application import plan_fixture
from surf.fixtures import load_fixture
from surf.policy import decide
from surf.schema import BeachWindow, DecisionState, EvidenceItem


@pytest.mark.parametrize(("name", "state"), [
    ("normal", DecisionState.recommended_window),
    ("hazard", DecisionState.official_advisory_present),
    ("stale", DecisionState.stale_data),
    ("conflict", DecisionState.conflicting_evidence),
])
def test_reviewed_fixtures_have_expected_decision(name, state):
    assert plan_fixture(name).record.decision.state == state


def test_policy_is_byte_identical_across_30_runs():
    normal = [plan_fixture("normal").record.model_dump_json() for _ in range(30)]
    hazard = [plan_fixture("hazard").record.model_dump_json() for _ in range(30)]
    assert len(set(normal)) == 1
    assert len(set(hazard)) == 1
    assert '"official_advisory_present"' in hazard[0]


def test_schema_rejects_naive_times():
    with pytest.raises(ValueError, match="timezone"):
        BeachWindow(beach_id="x", starts_at="2026-08-29T12:00:00", ends_at="2026-08-29T13:00:00")


def test_only_active_deq_status_is_a_water_quality_veto():
    snapshot_id, profile, window, evidence = load_fixture("normal")
    assert decide(snapshot_id, profile, window, evidence).decision.state == DecisionState.recommended_window
    active = tuple(
        item.model_copy(update={"facts": {"status": "advisory_active"}})
        if item.source_kind == "nc_deq_water_quality" else item
        for item in evidence
    )
    assert decide(snapshot_id, profile, window, active).decision.state == DecisionState.official_advisory_present


def test_missing_required_nws_hazard_evidence_fails_closed():
    snapshot_id, profile, window, evidence = load_fixture("normal")
    without_nws = tuple(item for item in evidence if item.source_kind != "nws_hazards")
    assert decide(snapshot_id, profile, window, without_nws).decision.state == DecisionState.insufficient_data
