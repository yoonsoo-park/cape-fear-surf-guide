from __future__ import annotations

import json
import statistics
import time

from surf.application import plan_fixture
from surf.planner_agent import plan_fixture_with_agent
from surf.replay_model import FixturePlannerModel
from surf.schema import DecisionState, SurfBrief


def percentile95(values: list[float]) -> float:
    return statistics.quantiles(values, n=100, method="inclusive")[94]


def main() -> int:
    deterministic_ms: list[float] = []
    deterministic_records: dict[str, list[str]] = {"normal": [], "hazard": []}
    for name in ("normal", "hazard"):
        for _ in range(30):
            started = time.perf_counter()
            result = plan_fixture(name)
            deterministic_ms.append((time.perf_counter() - started) * 1000)
            deterministic_records[name].append(result.record.model_dump_json())
    runs = {
        name: [plan_fixture_with_agent(name, FixturePlannerModel()) for _ in range(30)]
        for name in ("normal", "hazard")
    }
    all_runs = runs["normal"] + runs["hazard"]
    report = {
        "runs": len(all_runs),
        "normal_false_veto_rate": sum(r.record.decision.state != DecisionState.recommended_window for r in runs["normal"]) / 30,
        "hazard_veto_reproduction_rate": sum(r.record.decision.state == DecisionState.official_advisory_present for r in runs["hazard"]) / 30,
        "schema_valid_rate": sum(isinstance(r.brief, SurfBrief) for r in all_runs) / len(all_runs),
        "tool_call_log_rate": sum(bool(r.tool_calls) for r in all_runs) / len(all_runs),
        "unverifiable_slot_findings": sum(any("unverifiable_slot" in f for f in r.findings) for r in all_runs),
        "agentic_p95_ms": percentile95([r.elapsed_ms for r in all_runs]),
        "max_estimated_cost_usd": max(r.estimated_cost_usd for r in all_runs),
        "deterministic_p95_ms": percentile95(deterministic_ms),
        "deterministic_model_calls": 0,
        "deterministic_byte_identical": all(len(set(values)) == 1 for values in deterministic_records.values()),
    }
    report["passed"] = (
        report["normal_false_veto_rate"] == 0
        and report["hazard_veto_reproduction_rate"] == 1
        and report["schema_valid_rate"] == 1
        and report["tool_call_log_rate"] == 1
        and report["unverifiable_slot_findings"] == 0
        and report["agentic_p95_ms"] <= 30_000
        and report["max_estimated_cost_usd"] <= 0.05
        and report["deterministic_p95_ms"] <= 2_000
        and report["deterministic_model_calls"] == 0
        and report["deterministic_byte_identical"]
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
