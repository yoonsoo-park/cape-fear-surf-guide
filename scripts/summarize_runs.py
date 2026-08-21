from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from surf.snapshots import load_snapshot
from surf.validator import validate_recommendation


def token_count(row: dict) -> int:
    return (
        row.get("usage", {}).get("totalTokens", 0)
        + row.get("orchestrator_usage", {}).get("totalTokens", 0)
    )


def experiment_version(row: dict) -> str:
    if row.get("experiment_version"):
        return row["experiment_version"]
    if row.get("orchestrator_usage"):
        return "compact-handoff-v1"
    return "baseline-original"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="runs/log.jsonl")
    args = parser.parse_args()
    records = [json.loads(line) for line in Path(args.path).read_text().splitlines() if line.strip()]
    latencies = [row["total_elapsed_ms"] for row in records]
    total_tokens = [token_count(row) for row in records]
    validations = [
        validate_recommendation(row["recommendation"], load_snapshot(row["snapshot_id"]))
        if row.get("recommendation") else row.get("validation", {})
        for row in records
    ]
    violations = Counter(v["type"] for result in validations for v in result.get("violations", []))
    paths = Counter(" -> ".join(row.get("node_path", [])) for row in records)
    versions = {}
    for row in records:
        version = experiment_version(row)
        versions.setdefault(version, []).append(row)
    summary = {
        "runs": len(records),
        "success_rate": sum(bool(row.get("success")) for row in records) / len(records),
        "latency_ms": {"mean": round(statistics.mean(latencies)), "median": round(statistics.median(latencies)),
                       "min": min(latencies), "max": max(latencies)},
        "tokens": {"total": sum(total_tokens), "mean_per_run": round(statistics.mean(total_tokens))},
        "violations": violations,
        "schema_variants": Counter(result.get("schema_variant", "malformed") for result in validations),
        "paths": paths,
        "errors": Counter(row.get("error_type", "none") for row in records),
        "experiments": {
            version: {
                "runs": len(rows),
                "mean_latency_ms": round(statistics.mean(row["total_elapsed_ms"] for row in rows)),
                "mean_tokens": round(statistics.mean(token_count(row) for row in rows)),
            }
            for version, rows in versions.items()
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
