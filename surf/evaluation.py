"""Bounded, reproducible Phase 3 evaluation helpers.

This module deliberately contains no deployment operation. It validates the
explicit personal Bedrock boundary, meters provider-reported token usage, and
turns individual agent results into redaction-safe JSON evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import statistics
import subprocess
from typing import Any, Iterable

from .application import plan_fixture
from .planner_agent import AgentPlanningResult
from .schema import DecisionState, PartyProfile

PERSONAL_PROFILE = "personal"
PERSONAL_ACCOUNT_ID = "831597648506"
BEDROCK_REGION = "us-east-1"
NOVA_LITE_INFERENCE_PROFILE = "us.amazon.nova-lite-v1:0"
MAX_REQUEST_COST_USD = 0.05
MAX_EVALUATION_COST_USD = 10.00
MAX_AGENT_LATENCY_MS = 30_000
MAX_DETERMINISTIC_LATENCY_MS = 2_000

# Official AWS Price List API, retrieved 2026-08-22. These rates apply to
# on-demand Nova Lite in us-east-1; a future run must re-verify the source.
NOVA_LITE_INPUT_USD_PER_1K = 0.00006
NOVA_LITE_OUTPUT_USD_PER_1K = 0.00024
PRICE_SOURCE = {
    "url": "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json",
    "checked_on": "2026-08-22",
    "input_sku": "QRGWJ3P8FT28EYX2",
    "output_sku": "CBZ6A6U7XK8WJ3KA",
    "input_usd_per_1k_tokens": NOVA_LITE_INPUT_USD_PER_1K,
    "output_usd_per_1k_tokens": NOVA_LITE_OUTPUT_USD_PER_1K,
}

EXPECTED_STATES = {
    "normal": DecisionState.recommended_window,
    "hazard": DecisionState.official_advisory_present,
    "stale": DecisionState.stale_data,
    "conflict": DecisionState.conflicting_evidence,
}


@dataclass(frozen=True)
class EvaluationProfile:
    name: str
    profile: PartyProfile


EVALUATION_PROFILES = (
    EvaluationProfile("visitor", PartyProfile(skill_level="beginner", ages=(16,))),
    EvaluationProfile("beginner_family", PartyProfile(skill_level="beginner", ages=(12, 40))),
    EvaluationProfile("experienced_local", PartyProfile(skill_level="experienced", ages=(32,))),
    EvaluationProfile("surf_school", PartyProfile(skill_level="instructor", ages=())),
)


@dataclass(frozen=True)
class EvaluationCase:
    fixture: str
    profile: EvaluationProfile


def phase3_matrix() -> tuple[EvaluationCase, ...]:
    """Return 30 cases while covering every fixture/profile pair at least once."""
    base = tuple(EvaluationCase(fixture, profile) for fixture in EXPECTED_STATES for profile in EVALUATION_PROFILES)
    repeats = tuple(
        EvaluationCase(fixture, profile)
        for fixture in ("normal", "hazard", "stale", "conflict")
        for profile in EVALUATION_PROFILES[:(4 if fixture in {"normal", "hazard"} else 3)]
    )
    return base + repeats


def percentile95(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.quantiles(values, n=100, method="inclusive")[94] if len(values) > 1 else values[0]


def cost_from_usage(usage: dict[str, int]) -> float:
    return round(
        usage.get("inputTokens", 0) * NOVA_LITE_INPUT_USD_PER_1K / 1_000
        + usage.get("outputTokens", 0) * NOVA_LITE_OUTPUT_USD_PER_1K / 1_000,
        8,
    )


def _aws_json(arguments: list[str]) -> dict[str, Any]:
    completed = subprocess.run(["aws", *arguments], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def verify_live_boundary() -> dict[str, Any]:
    """Confirm profile, caller, region, and exact inference profile before a call."""
    identity = _aws_json(["sts", "get-caller-identity", "--profile", PERSONAL_PROFILE,
                          "--region", BEDROCK_REGION, "--output", "json"])
    inference = _aws_json(["bedrock", "get-inference-profile", "--profile", PERSONAL_PROFILE,
                           "--region", BEDROCK_REGION, "--inference-profile-identifier",
                           NOVA_LITE_INFERENCE_PROFILE, "--output", "json"])
    if identity.get("Account") != PERSONAL_ACCOUNT_ID:
        raise RuntimeError("refusing live evaluation: personal profile resolves to another AWS account")
    if inference.get("inferenceProfileId") != NOVA_LITE_INFERENCE_PROFILE:
        raise RuntimeError("refusing live evaluation: inference profile ID does not match Nova Lite")
    if inference.get("status") != "ACTIVE":
        raise RuntimeError("refusing live evaluation: inference profile is not active")
    return {
        "profile": PERSONAL_PROFILE,
        "account_id": identity["Account"],
        "principal_arn": identity["Arn"],
        "region": BEDROCK_REGION,
        "inference_profile_id": inference["inferenceProfileId"],
        "inference_profile_arn": inference["inferenceProfileArn"],
        "verified_at": datetime.now(UTC).isoformat(),
    }


def agent_result_evidence(case: EvaluationCase, result: AgentPlanningResult) -> dict[str, Any]:
    cost = cost_from_usage(result.usage)
    expected = EXPECTED_STATES[case.fixture]
    violations = list(result.invariant_violations)
    if result.brief.window_id != result.record.window_id or result.brief.decision_state != result.record.decision.state:
        violations.append("output_does_not_match_policy_record")
    return {
        "fixture": case.fixture,
        "profile": {"name": case.profile.name, **case.profile.profile.model_dump(mode="json")},
        "trace_id": result.trace_id,
        "elapsed_ms": result.elapsed_ms,
        "usage": result.usage,
        "estimated_cost_usd": cost,
        "expected_decision_state": expected.value,
        "actual_decision_state": result.record.decision.state.value,
        "brief_source": result.brief_source,
        "model_schema_valid": result.model_schema_valid,
        "tool_calls": result.tool_calls,
        "tool_call_count": len(result.tool_calls),
        "invariant_violations": sorted(set(violations)),
        "model_output_error": result.model_output_error,
        "policy_findings": result.findings,
        "record": result.record.model_dump(mode="json"),
        "brief": result.brief.model_dump(mode="json"),
        "passed": (
            result.record.decision.state == expected and result.model_schema_valid
            and result.brief_source == "agent" and bool(result.tool_calls)
            and not violations and not result.findings and result.elapsed_ms <= MAX_AGENT_LATENCY_MS
            and cost <= MAX_REQUEST_COST_USD
        ),
    }


def deterministic_evidence() -> dict[str, Any]:
    durations: list[float] = []
    byte_identical = True
    states: dict[str, str] = {}
    for fixture, expected in EXPECTED_STATES.items():
        records = []
        for _ in range(30):
            started = datetime.now(UTC)
            result = plan_fixture(fixture)
            durations.append((datetime.now(UTC) - started).total_seconds() * 1_000)
            records.append(result.record.model_dump_json())
        byte_identical = byte_identical and len(set(records)) == 1
        states[fixture] = result.record.decision.state.value
        byte_identical = byte_identical and result.record.decision.state == expected
    p95 = percentile95(durations)
    return {
        "runs": len(durations), "p95_ms": round(p95, 3), "model_calls": 0,
        "byte_identical": byte_identical, "decision_states": states,
        "passed": p95 <= MAX_DETERMINISTIC_LATENCY_MS and byte_identical,
    }


def summarize(records: list[dict[str, Any]], *, boundary: dict[str, Any], budget_stop_reason: str | None,
              deterministic: dict[str, Any]) -> dict[str, Any]:
    costs = [record["estimated_cost_usd"] for record in records]
    hazards = [record for record in records if record["fixture"] == "hazard"]
    normal = [record for record in records if record["fixture"] == "normal"]
    tool_rate = sum(record["tool_call_count"] > 0 for record in records) / len(records) if records else 0
    schema_rate = sum(record["model_schema_valid"] for record in records) / len(records) if records else 0
    invariant_failures = sum(bool(record["invariant_violations"]) for record in records)
    report = {
        "report_version": "phase3-v1", "generated_at": datetime.now(UTC).isoformat(),
        "live_boundary": boundary, "price_source": PRICE_SOURCE,
        "limits": {"per_request_cost_usd": MAX_REQUEST_COST_USD, "evaluation_cost_usd": MAX_EVALUATION_COST_USD,
                   "agent_p95_ms": MAX_AGENT_LATENCY_MS, "deterministic_p95_ms": MAX_DETERMINISTIC_LATENCY_MS},
        "run_counts": {"planned_matrix": 30, "completed_live": len(records), "preflight": 2},
        "budget_stop_reason": budget_stop_reason, "deterministic_path": deterministic,
        "agent_path": {
            "p95_ms": round(percentile95([record["elapsed_ms"] for record in records]), 3) if records else None,
            "total_estimated_cost_usd": round(sum(costs), 8), "max_request_cost_usd": max(costs, default=0),
            "model_structured_schema_valid_rate": schema_rate, "tool_call_rate": tool_rate,
            "official_hazard_veto_rate": (sum(record["actual_decision_state"] == DecisionState.official_advisory_present.value for record in hazards) / len(hazards) if hazards else 0),
            "normal_false_veto_rate": (sum(record["actual_decision_state"] != DecisionState.recommended_window.value for record in normal) / len(normal) if normal else 0),
            "invariant_failure_count": invariant_failures, "run_failures": sum(not record["passed"] for record in records),
        },
        "billing_note": "Token usage is the Bedrock/Strands provider counter preserved per run. AWS billing and Cost Explorer reconciliation are a later operating check; this report does not claim it is an invoice.",
        "agentcore_mcp_v2": {"status": "passed", "evidence": "docs/agentcore-mcp-v2-spike.md", "deployment_performed_in_this_phase": False},
    }
    agent = report["agent_path"]
    report["passed"] = (
        budget_stop_reason is None and len(records) == 30 and deterministic["passed"]
        and agent["p95_ms"] is not None and agent["p95_ms"] <= MAX_AGENT_LATENCY_MS
        and agent["max_request_cost_usd"] <= MAX_REQUEST_COST_USD
        and agent["model_structured_schema_valid_rate"] == 1 and agent["tool_call_rate"] == 1
        and agent["official_hazard_veto_rate"] == 1 and agent["normal_false_veto_rate"] == 0
        and agent["invariant_failure_count"] == 0 and agent["run_failures"] == 0
    )
    return report


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))
