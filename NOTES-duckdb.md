# DuckDB implementation notes

## Architecture

- B1 adds `duckdb>=1.4.0` to the `analytics` dependency group only. It is in
  `uv`'s local default groups so the documented command works, but it is not a
  project runtime dependency and is not copied into `mcp_runtime`.
- B2 reads JSONL with DuckDB `read_json_objects`, uses SQL aggregates for the
  compatibility report, and uses `json_each`/`UNNEST` for nested analyses.
- Existing recommendation validation remains unchanged; the analyzer calls
  the same validator only when a run contains a recommendation.

## Verified numbers

Against `runs/sample-log.jsonl` (33 captured lines):

- Compatibility parity: exact match with `scripts/summarize_runs.py`.
- Success rate: `27/33 = 0.8181818181818182`.
- Mean/median latency: `136702/132508 ms`.
- Total tokens under the existing contract: `105937`.
- Pricing node failures: `1`; `high-swell-and-gusts` failures: `1/3`.

## Actual pitfalls encountered

1. Running the new script without the repository on `PYTHONPATH` failed with
   `ModuleNotFoundError: No module named 'surf.snapshots'`. The runbook and
   parity test therefore invoke it from the root with `PYTHONPATH=.`; this is
   consistent with the existing summary script.
2. The first DuckDB probe tried `map_keys(nodes)` and failed with `Binder Error:
   No function matches the given name and argument types 'map_keys(STRUCT(...))`.
   `nodes` is an inferred STRUCT, not a MAP; converting it to JSON and using
   `json_each` handles variable node keys.
3. The required compile command hit the existing sandbox-owned bytecode
   directories with `PermissionError: [Errno 1] Operation not permitted:
   'surf/__pycache__/...'`. This is an environment write restriction, not a
   source assertion; compilation can be directed to a task-specific
   `PYTHONPYCACHEPREFIX` outside the checkout.
4. Local `uv` emitted `WARN Failed to acquire environment lock: Could not create
   temporary file` while concurrent invocations shared the default cache. A
   task-specific `UV_CACHE_DIR` was used for deterministic runs.

No AWS credentials, network calls, or application data were added by this
feature. The report is read-only analytics over the checked-in fixture.
