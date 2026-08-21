from __future__ import annotations

import argparse
import json
from pathlib import Path

from surf.snapshots import load_snapshot
from surf.validator import validate_recommendation


def experiment_version(row: dict) -> str:
    if row.get("experiment_version"):
        return row["experiment_version"]
    if row.get("orchestrator_usage"):
        return "compact-handoff-v1"
    return "baseline-original"


def failure_reason(row: dict) -> str | None:
    if row.get("success"):
        return None
    evidence = f"{row.get('swarm_text', '')}\n{row.get('recommendation', '')}"
    if "maximum token limit" in evidence:
        return "safety_agent_max_tokens"
    if "does not support assistant message prefill" in evidence:
        return "pricing_agent_assistant_prefill_validation"
    if row.get("node_path", [])[-2:] == ["pricing_agent", "conditions_agent"]:
        return "unexpected_agent_cycle_iteration_limit"
    return "unclassified_swarm_failure"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="runs/log.jsonl")
    parser.add_argument("--output", default="runs/sample-log.jsonl")
    parser.add_argument("--start-line", type=int, default=1, help="First one-based JSONL line to export")
    parser.add_argument("--end-line", type=int, help="Last one-based JSONL line to export, inclusive")
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    rows = rows[args.start_line - 1:args.end_line]
    manifest = json.loads(Path("snapshots/scenarios/manifest.json").read_text())
    scenario_names = {item["snapshot_id"]: item["name"] for item in manifest}
    samples = []
    for row in rows:
        recommendation = row.get("recommendation", "")
        samples.append({
            "timestamp": row["timestamp"],
            "snapshot_id": row["snapshot_id"],
            "scenario": scenario_names.get(row["snapshot_id"], "unmapped"),
            "experiment_version": experiment_version(row),
            "model_id": row["model_id"],
            "node_path": row.get("node_path", []),
            "path_complete": row.get("path_complete", False),
            "handoff_count": row.get("handoff_count", 0),
            "tool_calls": row.get("tool_calls", {}),
            "total_elapsed_ms": row["total_elapsed_ms"],
            "swarm_usage": row.get("usage", {}),
            "orchestrator_usage": row.get("orchestrator_usage", {}),
            "nodes": row.get("nodes", {}),
            "validation": (
                validate_recommendation(recommendation, load_snapshot(row["snapshot_id"]))
                if recommendation else row.get("validation", {})
            ),
            "status": row.get("status", "unknown"),
            "success": row.get("success", False),
            "failure_reason": failure_reason(row),
        })
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(sample, sort_keys=True) + "\n" for sample in samples))


if __name__ == "__main__":
    main()
