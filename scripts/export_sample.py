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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="runs/log.jsonl")
    parser.add_argument("--output", default="runs/sample-log.jsonl")
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    samples = []
    for row in rows:
        samples.append({
            "timestamp": row["timestamp"],
            "snapshot_id": row["snapshot_id"],
            "experiment_version": experiment_version(row),
            "model_id": row["model_id"],
            "node_path": row.get("node_path", []),
            "tool_calls": row.get("tool_calls", {}),
            "total_elapsed_ms": row["total_elapsed_ms"],
            "swarm_usage": row.get("usage", {}),
            "orchestrator_usage": row.get("orchestrator_usage", {}),
            "nodes": row.get("nodes", {}),
            "validation": validate_recommendation(
                row["recommendation"], load_snapshot(row["snapshot_id"])
            ),
            "success": row.get("success", False),
        })
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(sample, sort_keys=True) + "\n" for sample in samples))


if __name__ == "__main__":
    main()
