from surf.evaluation import (
    EVALUATION_PROFILES, EvaluationCase, agent_result_evidence, cost_from_usage,
    deterministic_evidence, phase3_matrix, summarize,
)
from surf.planner_agent import plan_fixture_with_agent
from surf.replay_model import FixturePlannerModel


def test_phase3_matrix_covers_every_fixture_profile_pair_in_thirty_runs():
    matrix = phase3_matrix()
    assert len(matrix) == 30
    assert {(case.fixture, case.profile.name) for case in matrix} == {
        (fixture, profile.name)
        for fixture in ("normal", "hazard", "stale", "conflict")
        for profile in EVALUATION_PROFILES
    }


def test_phase3_evidence_uses_provider_usage_and_preserves_policy_fields():
    case = EvaluationCase("hazard", EVALUATION_PROFILES[2])
    result = plan_fixture_with_agent(case.fixture, FixturePlannerModel(), profile_override=case.profile.profile)
    evidence = agent_result_evidence(case, result)
    assert evidence["passed"]
    assert evidence["usage"] == {"inputTokens": 9, "outputTokens": 9, "totalTokens": 18}
    assert evidence["estimated_cost_usd"] == cost_from_usage(evidence["usage"])
    assert evidence["actual_decision_state"] == "official_advisory_present"
    assert evidence["invariant_violations"] == []


def test_summary_requires_complete_passing_matrix_and_separates_deterministic_path():
    case = EvaluationCase("normal", EVALUATION_PROFILES[0])
    result = plan_fixture_with_agent(case.fixture, FixturePlannerModel(), profile_override=case.profile.profile)
    report = summarize(
        [agent_result_evidence(case, result)],
        boundary={"profile": "personal"}, budget_stop_reason=None,
        deterministic=deterministic_evidence(),
    )
    assert report["deterministic_path"]["model_calls"] == 0
    assert report["passed"] is False
