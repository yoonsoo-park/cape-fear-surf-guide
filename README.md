# Cape Fear Surf Guide

Cape Fear Surf Guide converts official and supplemental marine evidence into reviewable surf-planning windows for Wrightsville Beach, Carolina Beach, Kure Beach, and Fort Fisher. It does not guarantee that ocean activity is safe.

Deterministic Python owns normalization, window derivation, freshness and conflict checks, and official-advisory vetoes. One Strands agent owns intake, fact retrieval through real tools, and a schema-validated brief. The agent cannot change the immutable policy record; a template brief remains available if the model fails.

## Offline judged-demo slice

Python 3.11 and `uv` are required. These commands use reviewed fixtures and make no AWS or live-network call.

```bash
uv sync
uv run python main.py --fixture normal --html /tmp/cape-fear-normal.html
uv run python main.py --fixture hazard
uv run python scripts/evaluate_phase1.py
```

The CLI JSON and static HTML embed the same `RecommendationRecord`. Available fixtures are `normal`, `hazard`, `stale`, and `conflict`. Add `--deterministic-only` to skip the offline Strands agent and render the template brief directly.

## Validation

```bash
uv run pytest
uv run python -m compileall -q main.py surf scripts
uv run python scripts/evaluate_phase1.py
```

## Phase 3 live Nova Lite evaluation

The fixture-only command above is intentionally separate from the live agent
evaluation. The live runner accepts only AWS profile `personal`, account
`831597648506`, region `us-east-1`, and inference profile
`us.amazon.nova-lite-v1:0`. Before any model call, it records the caller
identity and profile status; it refuses a mismatch. It creates, modifies, and
deletes no AWS resource.

```bash
uv run python scripts/evaluate_phase3.py
```

The runner first performs two preflight requests. Both must call tools, return
the structured `SurfBrief`, preserve the immutable policy fields, satisfy the
30-second limit, and stay within the $0.05 request cap. Only then does it run a
fixed 30-case matrix covering normal, official-hazard, stale, and conflicting
fixtures across visitor, beginner-family, experienced-local, and surf-school
profiles. It writes `reports/phase3/<UTC-run>/raw-runs.jsonl` and
`summary.json`.

The summary keeps two independent gates: the deterministic path has zero model
calls, byte-identical outputs, and p95 at most two seconds; the agentic path
has p95 at most 30 seconds, cost at most $0.05 per request, a $10 whole-run
budget guard, 100% structured-schema/tool/official-veto success, zero normal
false vetoes, and zero immutable-field violations. The cost estimate uses the
official AWS Price List API rates checked on 2026-08-22 for Nova Lite in
`us-east-1`: $0.00006 per 1K input tokens and $0.00024 per 1K output tokens.
The provider token counters are preserved as evidence, but they are not an AWS
billing invoice.

## Submission package

- [Architecture diagram](docs/assets/architecture.svg)
- [Five-minute recording script](docs/demo-script.md)
- [Devpost draft](docs/devpost-draft.md)
- [Submission checklist](docs/submission-checklist.md)
- [AgentCore MCP v2 compatibility result](docs/agentcore-mcp-v2-spike.md)
- [External HTTPS MCP frozen-demo runbook](docs/external-mcp-demo.md)

Publishing the repository, uploading a video, submitting to Devpost, and
publishing blog posts remain explicit human-approved actions.

## MCP v2 frozen-demo runtime

The MCP service has its own Python SDK v2 runtime because the current Strands
dependency requires MCP SDK v1. The service imports the same `surf` application
and deterministic policy code; it does not duplicate a policy engine. Start it
only after supplying a local bearer token through the process environment,
never source control or a shell transcript:

```bash
uv run --project mcp_runtime python -m mcp_runtime.server
```

It exposes one authenticated, stateless Streamable HTTP `POST /mcp` endpoint
on port 8000. The public mode requires protocol `2026-07-28`, validated
JSON-RPC tool names, and an allowed `Origin` when supplied. It does not require
the AgentCore-specific `Mcp-Method` or `Mcp-Name` headers. The frozen
demonstration accepts the reviewed 2026-08-29 beginner profile and
reconstructs `explain_surf_window(window_id)` from reviewed snapshots on each
request. It deliberately returns a structured unavailable error instead of
inventing coverage for another date, beach, time range, or party profile.

Run its isolated validation with:

```bash
uv run --directory mcp_runtime pytest
```

The AgentCore-compatible container artifact is
`mcp_runtime/Dockerfile`. Its actual AgentCore compatibility gate is documented
in `docs/agentcore-mcp-v2-spike.md`; deploying it still requires explicit AWS
approval and the documented personal-account runtime controls.

The separate Lambda Function URL implementation is a time-limited external
demo only. Its SSM-backed bearer authentication, request bounds, rotation, and
teardown requirements are in [the external MCP runbook](docs/external-mcp-demo.md).

Capture a reviewed live NWS alert response for offline replay only when a real
identifying NWS `User-Agent` contact route has been selected:

```bash
uv run python scripts/capture_nws_alerts.py --zone NCZ106 \
  --user-agent 'cape-fear-surf-guide contact@example.com' \
  --output fixtures/captured/nws-alerts-NCZ106.json

uv run python scripts/capture_nws_zone_forecast.py --zone NCZ108 \
  --user-agent 'cape-fear-surf-guide https://github.com/yoonsoo-park/cape-fear-surf-guide' \
  --output fixtures/captured/nws-zone-forecast-NCZ108.json
```

## Safety and evidence boundary

- Official advisories and deterministic policy override every model explanation.
- Required NWS hazard evidence that is missing or stale prevents a recommendation.
- Only an active NC DEQ advisory is a water-quality veto. Missing, seasonal, or unavailable coverage is labeled and is not proof of safety.
- Unverified station, source, and local-rule mappings remain explicit; the code never guesses them.
- Booking, payment, cancellation, rescue guidance, and claims that surfing is safe are outside the MVP.
- Live Bedrock calls require explicit confirmation of the personal AWS account, role, region, `personal` profile, and inference-profile ID. Deployment requires separate approval.

## Prior-art disclosure

This repository began from the pre-existing `surf-school-swarm` research baseline. That baseline measured a five-agent handoff chain across 33 Bedrock runs and is preserved in `NOTES.md`, `runs/sample-log.jsonl`, the original snapshot tooling, validator, and legacy Swarm modules. Cape Fear locations, schemas, deterministic policy, fixtures, single-agent retrieval path, structured brief, CLI/HTML output, and acceptance evaluation are new productization work. The legacy Swarm is evidence explaining the bounded architecture; it is not the production orchestration.

See `PLAN-cape-fear-productization.md` for scope and `docs/source-verification.md` for verified and unresolved source contracts.
