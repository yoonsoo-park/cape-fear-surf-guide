"""Run the bounded live Nova Lite Phase 3 evaluation; no AWS resources are changed."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

import boto3

from surf.evaluation import (
    BEDROCK_REGION, MAX_EVALUATION_COST_USD, MAX_REQUEST_COST_USD,
    NOVA_LITE_INFERENCE_PROFILE, PERSONAL_PROFILE, agent_result_evidence,
    deterministic_evidence, phase3_matrix, summarize, verify_live_boundary, write_jsonl,
)
from surf.planner_agent import bedrock_model, plan_fixture_with_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3"))
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir / run_id
    boundary = verify_live_boundary()
    session = boto3.Session(profile_name=PERSONAL_PROFILE, region_name=BEDROCK_REGION)
    model = bedrock_model(BEDROCK_REGION, NOVA_LITE_INFERENCE_PROFILE, boto_session=session)
    deterministic = deterministic_evidence()
    matrix = phase3_matrix()
    # Exercise both the normal and official-hazard paths before spending on the
    # full matrix. The hazard case also proves warning preservation.
    preflight_cases = (matrix[0], next(case for case in matrix if case.fixture == "hazard"))
    records = []
    budget_stop_reason = None

    for case in preflight_cases:
        result = plan_fixture_with_agent(case.fixture, model, profile_override=case.profile.profile)
        record = agent_result_evidence(case, result)
        record["phase"] = "preflight"
        records.append(record)
    preflight_passed = all(record["passed"] for record in records)
    if not preflight_passed:
        budget_stop_reason = "preflight_failed: a tool, schema, invariant, latency, policy, or per-request cost gate failed"
    elif args.preflight_only:
        budget_stop_reason = "preflight_only_requested"
    else:
        cumulative = sum(record["estimated_cost_usd"] for record in records)
        forecast_per_run = max(MAX_REQUEST_COST_USD, *(record["estimated_cost_usd"] for record in records))
        for case in matrix:
            if cumulative + forecast_per_run > MAX_EVALUATION_COST_USD:
                budget_stop_reason = "budget_guard: next run's conservative request-cost forecast would exceed $10"
                break
            result = plan_fixture_with_agent(case.fixture, model, profile_override=case.profile.profile)
            record = agent_result_evidence(case, result)
            record["phase"] = "matrix"
            records.append(record)
            cumulative += record["estimated_cost_usd"]
            forecast_per_run = max(forecast_per_run, record["estimated_cost_usd"])
            if record["estimated_cost_usd"] > MAX_REQUEST_COST_USD:
                budget_stop_reason = "per_request_cost_guard: an observed request exceeded $0.05"
                break

    # The two preflight calls demonstrate the gate. The published matrix report
    # contains only the 30 post-gate requests, so pass-rate denominators are exact.
    matrix_records = [record for record in records if record["phase"] == "matrix"]
    report = summarize(matrix_records, boundary=boundary, budget_stop_reason=budget_stop_reason,
                       deterministic=deterministic)
    report["preflight"] = [
        {key: value for key, value in record.items() if key != "record"}
        for record in records if record["phase"] == "preflight"
    ]
    report["preflight_passed"] = preflight_passed
    report["preflight_total_estimated_cost_usd"] = round(
        sum(record["estimated_cost_usd"] for record in records if record["phase"] == "preflight"), 8,
    )
    report["evaluation_total_estimated_cost_usd"] = round(
        report["preflight_total_estimated_cost_usd"] + report["agent_path"]["total_estimated_cost_usd"], 8,
    )
    write_jsonl(output_dir / "raw-runs.jsonl", records)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output_dir": str(output_dir), "passed": report["passed"],
                      "budget_stop_reason": budget_stop_reason}, indent=2))
    return 0 if (preflight_passed if args.preflight_only else report["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
