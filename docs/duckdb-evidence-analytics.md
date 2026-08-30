# DuckDB run-evidence analytics

`runs/*.jsonl` is the evidence boundary for the prior Strands experiment. The
DuckDB report is an offline, read-only view over that evidence; it does not
invoke Bedrock, AgentCore, a source API, or the policy engine.

## Usage

Run from the repository root:

```bash
PYTHONPATH=. uv run python scripts/analyze_runs_duckdb.py runs/sample-log.jsonl
```

The `analytics` dependency group is enabled by default for local `uv run`
commands, but DuckDB is intentionally absent from the application and
`mcp_runtime` runtime dependencies. Pass more than one JSONL file to analyze a
combined batch. `read_json_objects` keeps each line as JSON so logs with
different nested `nodes` keys can be combined without losing fields.

## Compatibility report

The top-level fields match `scripts/summarize_runs.py`:

- run count, success rate, and latency mean/median/min/max;
- token totals and mean per run (model usage plus orchestrator usage);
- validator violations and schema variants;
- node paths, error types, and experiment groups.

When a recommendation is present, the existing snapshot validator remains the
source of validation results. Otherwise the recorded `validation` object is
used, preserving the prior report's behavior.

## Additional DuckDB analyses

The `analytics` object adds three deterministic views:

1. `node_token_distribution` expands the nested `nodes` object with DuckDB
   `json_each`, then reports runs, mean/median/min/max, p95 tokens, and failed
   node executions for each observed node.
2. `scenario_failure_rate` groups success flags by scenario and reports runs,
   failures, and a four-decimal failure rate.
3. `schema_field_presence` uses `json_keys`/`UNNEST` to show how often each
   top-level field appears. This makes a missing-field or schema-drift pattern
   visible before it becomes a misleading aggregate.

## Reproduced sample evidence

The checked-in sample contains 33 runs across 11 scenarios. The analyzer
reproduces the existing report: 27 successful runs (0.8181818181818182), mean
latency 136,702 ms, median 132,508 ms, and 105,937 orchestrator tokens. The
additional views show 33 availability-node records, one failed pricing-node
record, and a 1/3 failure rate for each of `beginner-boundary`, `cold-calm`,
`high-demand`, `high-swell-and-gusts`, `premium-clean`, and
`variable-conditions`.

These are measurements of the captured fixture, not a production reliability
claim. The parity test compares every pre-existing field against
`summarize_runs.py` and separately asserts the nested analyses.
