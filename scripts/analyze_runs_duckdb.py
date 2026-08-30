"""Analyze run-evidence JSONL with DuckDB.

The existing ``summarize_runs.py`` output is the compatibility contract.  This
module reproduces those fields and adds analyses that are awkward to express
with line-by-line Python: nested per-node token distributions, failure rates by
scenario, and top-level schema-field presence.  No network or AWS calls are
made.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import duckdb

from surf.snapshots import load_snapshot
from surf.validator import validate_recommendation


READ_ROWS = "read_json_objects(?)"


def _paths(paths: Sequence[Path]) -> list[str]:
    values = [str(path) for path in paths]
    if not values:
        raise ValueError("at least one JSONL path is required")
    missing = [value for value in values if not Path(value).is_file()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    return values


def _raw_rows(connection: duckdb.DuckDBPyConnection, paths: Sequence[str]) -> list[dict[str, Any]]:
    # read_json_objects keeps each line as one JSON value, so nested fields are
    # not lost when different runs contain different node or validation keys.
    values = connection.execute(f"SELECT json::VARCHAR FROM {READ_ROWS}", [paths]).fetchall()
    return [json.loads(value[0]) for value in values]


def _validation(row: dict[str, Any]) -> dict[str, Any]:
    """Match summarize_runs.py's validation fallback exactly."""

    if row.get("recommendation"):
        return validate_recommendation(
            row["recommendation"], load_snapshot(row["snapshot_id"])
        )
    return row.get("validation", {})


def _compatibility_summary(
    connection: duckdb.DuckDBPyConnection,
    paths: Sequence[str],
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    query = f"""
        WITH rows AS (
            SELECT json AS row_json FROM {READ_ROWS}
        ), metrics AS (
            SELECT
                try_cast(json_extract(row_json, '$.total_elapsed_ms') AS BIGINT) AS latency,
                CASE WHEN coalesce(try_cast(json_extract(row_json, '$.success') AS BOOLEAN), FALSE)
                     THEN 1 ELSE 0 END AS succeeded,
                coalesce(try_cast(json_extract(row_json, '$.usage.totalTokens') AS BIGINT), 0)
                    + coalesce(try_cast(json_extract(row_json, '$.orchestrator_usage.totalTokens') AS BIGINT), 0)
                    AS tokens,
                coalesce(
                    nullif(json_extract_string(row_json, '$.experiment_version'), ''),
                    CASE WHEN json_extract(row_json, '$.orchestrator_usage') IS NOT NULL
                         THEN 'compact-handoff-v1' ELSE 'baseline-original' END
                ) AS experiment_version,
                coalesce(array_to_string(json_extract_string(row_json, '$.node_path[*]'), ' -> '), '') AS path,
                coalesce(json_extract_string(row_json, '$.error_type'), 'none') AS error_type
            FROM rows
        )
        SELECT
            count(*) AS runs,
            sum(succeeded)::DOUBLE / nullif(count(*), 0) AS success_rate,
            round(avg(latency)) AS latency_mean,
            median(latency) AS latency_median,
            min(latency) AS latency_min,
            max(latency) AS latency_max,
            sum(tokens) AS tokens_total,
            round(avg(tokens)) AS tokens_mean
        FROM metrics
    """
    metrics = connection.execute(query, [paths]).fetchone()
    if metrics is None or not rows:
        raise ValueError("JSONL input contains no records")
    if metrics[2] is None:
        raise ValueError("every record must contain total_elapsed_ms")

    validations = [_validation(row) for row in rows]
    violations = Counter(
        violation["type"]
        for result in validations
        for violation in result.get("violations", [])
    )
    schema_variants = Counter(
        result.get("schema_variant", "malformed") for result in validations
    )

    grouped = connection.execute(
        f"""
        WITH rows AS (
            SELECT json AS row_json FROM {READ_ROWS}
        ), metrics AS (
            SELECT
                coalesce(
                    nullif(json_extract_string(row_json, '$.experiment_version'), ''),
                    CASE WHEN json_extract(row_json, '$.orchestrator_usage') IS NOT NULL
                         THEN 'compact-handoff-v1' ELSE 'baseline-original' END
                ) AS experiment_version,
                try_cast(json_extract(row_json, '$.total_elapsed_ms') AS BIGINT) AS latency,
                coalesce(try_cast(json_extract(row_json, '$.usage.totalTokens') AS BIGINT), 0)
                    + coalesce(try_cast(json_extract(row_json, '$.orchestrator_usage.totalTokens') AS BIGINT), 0)
                    AS tokens
            FROM rows
        )
        SELECT experiment_version, count(*), round(avg(latency)), round(avg(tokens))
        FROM metrics
        GROUP BY experiment_version
        ORDER BY experiment_version
        """,
        [paths],
    ).fetchall()
    experiments = {
        version: {
            "runs": int(run_count),
            "mean_latency_ms": int(mean_latency),
            "mean_tokens": int(mean_tokens),
        }
        for version, run_count, mean_latency, mean_tokens in grouped
    }

    path_rows = connection.execute(
        f"""
        WITH rows AS (SELECT json AS row_json FROM {READ_ROWS})
        SELECT path, count(*)
        FROM (
            SELECT coalesce(array_to_string(json_extract_string(row_json, '$.node_path[*]'), ' -> '), '') AS path
            FROM rows
        )
        GROUP BY path
        ORDER BY path
        """,
        [paths],
    ).fetchall()
    error_rows = connection.execute(
        f"""
        WITH rows AS (SELECT json AS row_json FROM {READ_ROWS})
        SELECT error_type, count(*)
        FROM (
            SELECT coalesce(json_extract_string(row_json, '$.error_type'), 'none') AS error_type
            FROM rows
        )
        GROUP BY error_type
        ORDER BY error_type
        """,
        [paths],
    ).fetchall()

    return {
        "runs": int(metrics[0]),
        "success_rate": float(metrics[1]),
        "latency_ms": {
            "mean": int(metrics[2]),
            "median": int(metrics[3]) if float(metrics[3]).is_integer() else float(metrics[3]),
            "min": int(metrics[4]),
            "max": int(metrics[5]),
        },
        "tokens": {"total": int(metrics[6]), "mean_per_run": int(metrics[7])},
        "violations": dict(violations),
        "schema_variants": dict(schema_variants),
        "paths": {path: int(count) for path, count in path_rows},
        "errors": {error: int(count) for error, count in error_rows},
        "experiments": experiments,
    }


def _node_token_distribution(
    connection: duckdb.DuckDBPyConnection, paths: Sequence[str]
) -> dict[str, dict[str, int]]:
    rows = connection.execute(
        f"""
        WITH rows AS (SELECT json AS row_json FROM {READ_ROWS}), nodes AS (
            SELECT
                node.key AS node,
                try_cast(json_extract(node.value, '$.usage.totalTokens') AS BIGINT) AS tokens,
                json_extract_string(node.value, '$.status') AS status
            FROM rows, json_each(json_extract(rows.row_json, '$.nodes')) AS node
        )
        SELECT
            node,
            count(*) AS runs,
            round(avg(tokens)) AS mean_tokens,
            median(tokens) AS median_tokens,
            min(tokens) AS min_tokens,
            max(tokens) AS max_tokens,
            round(quantile_cont(tokens, 0.95)) AS p95_tokens,
            count(*) FILTER (WHERE status = 'failed') AS failures
        FROM nodes
        WHERE tokens IS NOT NULL
        GROUP BY node
        ORDER BY node
        """,
        [paths],
    ).fetchall()
    return {
        node: {
            "runs": int(runs),
            "mean_tokens": int(mean_tokens),
            "median_tokens": int(median_tokens)
            if float(median_tokens).is_integer()
            else float(median_tokens),
            "min_tokens": int(min_tokens),
            "max_tokens": int(max_tokens),
            "p95_tokens": int(p95_tokens),
            "failures": int(failures),
        }
        for node, runs, mean_tokens, median_tokens, min_tokens, max_tokens, p95_tokens, failures in rows
    }


def _scenario_failure_rate(
    connection: duckdb.DuckDBPyConnection, paths: Sequence[str]
) -> dict[str, dict[str, int | float]]:
    rows = connection.execute(
        f"""
        WITH rows AS (SELECT json AS row_json FROM {READ_ROWS}), scenarios AS (
            SELECT
                coalesce(json_extract_string(row_json, '$.scenario'), 'unknown') AS scenario,
                coalesce(try_cast(json_extract(row_json, '$.success') AS BOOLEAN), FALSE) AS success
            FROM rows
        )
        SELECT scenario, count(*) AS runs,
               sum(CASE WHEN success THEN 0 ELSE 1 END) AS failures,
               round(sum(CASE WHEN success THEN 0 ELSE 1 END)::DOUBLE / count(*), 4) AS failure_rate
        FROM scenarios
        GROUP BY scenario
        ORDER BY scenario
        """,
        [paths],
    ).fetchall()
    return {
        scenario: {
            "runs": int(runs),
            "failures": int(failures),
            "failure_rate": float(failure_rate),
        }
        for scenario, runs, failures, failure_rate in rows
    }


def _schema_field_presence(
    connection: duckdb.DuckDBPyConnection, paths: Sequence[str], run_count: int
) -> dict[str, dict[str, int | float]]:
    rows = connection.execute(
        f"""
        WITH rows AS (SELECT json AS row_json FROM {READ_ROWS}), fields AS (
            SELECT field_name
            FROM rows, unnest(json_keys(row_json)) AS key_list(field_name)
        )
        SELECT field_name, count(*) AS present
        FROM fields
        GROUP BY field_name
        ORDER BY field_name
        """,
        [paths],
    ).fetchall()
    return {
        field: {"present": int(present), "presence_rate": round(int(present) / run_count, 4)}
        for field, present in rows
    }


def analyze(paths: Sequence[Path]) -> dict[str, Any]:
    path_values = _paths(paths)
    connection = duckdb.connect()
    try:
        rows = _raw_rows(connection, path_values)
        summary = _compatibility_summary(connection, path_values, rows)
        summary["analytics"] = {
            "node_token_distribution": _node_token_distribution(connection, path_values),
            "scenario_failure_rate": _scenario_failure_rate(connection, path_values),
            "schema_field_presence": _schema_field_presence(
                connection, path_values, summary["runs"]
            ),
        }
        return summary
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("runs/log.jsonl")])
    args = parser.parse_args()
    print(json.dumps(analyze(args.paths), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
