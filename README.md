# Surf School Swarm

An evidence-focused proof of concept that reproduces the AWS restaurant dynamic-pricing Strands Swarm pattern in a surf-school domain. It is an article research instrument, not a production booking or safety system.

Five Bedrock-backed specialists analyze captured Open-Meteo signals, instructor availability, prompt-only safety rules, and prompt-only pricing rules. Every run records the collaboration path, tool calls, latency, token usage, errors, and independently detected rule violations.

## Prerequisites

- Python 3.11+
- `uv`
- AWS credentials authorized to invoke the selected Bedrock inference profile
- `AWS_REGION` and `BEDROCK_MODEL_ID`

```bash
uv sync
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6
uv run python main.py --once "Seal Beach" 2026-08-22
```

The first run captures live Open-Meteo data under `snapshots/live/`. Reuse evidence with `--snapshot ID` so comparisons use identical inputs.

## Evidence matrix

```bash
uv run python scripts/generate_scenarios.py BASE_SNAPSHOT_ID
uv run python scripts/run_matrix.py --repeats 3 --confirm-live-cost
uv run python scripts/summarize_runs.py
uv run python scripts/export_sample.py
```

The scenario matrix deliberately derives stress cases from one public live snapshot. The manifest records each transformation. Matrix execution requires `--confirm-live-cost` because the faithful five-agent pattern is expensive. Generated live snapshots and full run logs are ignored; publish only reviewed samples.

The first baseline used 108,827 swarm tokens and took 285 seconds. Compact lesson-hour handoffs plus an eight-recommendation cap reduced the same-snapshot comparison to 64,781 swarm tokens and 125 seconds without changing the five-agent path.

## Validation

```bash
uv run pytest
uv run python -m compileall -q main.py surf scripts
cxdoc current . --json
cxdoc doctor --project surf-school-swarm
```

## Evidence boundary

- `prompt-only` is the baseline. The Python validator detects violations but never changes recommendations.
- A deterministic guardrail comparison is added only if the baseline produces an observed safety or price-floor violation.
- The thresholds are PoC experiment inputs, not professional surf-safety guidance.
- AgentCore, payments, real reservations, authentication, and a web UI are out of scope.
