# AGENTS.md

## Project Purpose

- Cape Fear Surf Guide turns difficult marine, weather, hazard, tide, and water-quality evidence into plain-language surf planning windows for Cape Fear residents, visitors, local surf schools, and external trip-planning agents.
- The existing evidence-focused Strands Swarm PoC is the measured prior-art baseline, not the production orchestration. Preserve its snapshots, validators, traces, and repeat-run evidence while replacing context-amplifying handoffs with a deterministic policy core plus one Strands agent that owns intake, tool-driven retrieval, and the brief.
- The governing rule: the agent decides what to look up and how to explain it. The agent has no path to deciding whether the water is safe.
- Read `PLAN-cape-fear-productization.md` before changing product scope or architecture.


## Agent Operating Rules

- Start by reading this file and use cxdoc search commands before relying on memory.
- Use `cxdoc current . --json` to confirm the project mapping when context matters.
- Keep durable project instructions in this file; keep searchable details in cxdoc knowledge notes.

- Source normalization, time conversion, window derivation, and veto decisions belong in deterministic Python. Expose the fetchers as Strands `@tool`s so the agent drives retrieval, but the tools return facts only and never a verdict.
- The agent may ask clarifying questions and choose what to query. It cannot invent or modify a measurement, change a decision state, remove a warning, invent a source URL, or reach the record without going through `policy.decide`.
- Emit the brief as Strands structured output, not free prose. Free prose cannot satisfy the 100% schema-validity gate.
- Latency and cost gates are per path: deterministic path p95 at most 2s with zero model calls, agentic path p95 at most 30s and at most $0.05 per request. Never merge them into one end-to-end budget.
- Official advisories and deterministic policy override model explanations. The model cannot declare ocean activity safe or override a hazard advisory.
- Treat an active NC DEQ advisory as a veto. `no_advisory_found`, `out_of_season`, or `feed_unavailable` must be labeled but are not automatic vetoes.
- Keep CLI, static HTML, MCP, optional Slack, and surf-school adapters on one shared application service and policy engine.

- Before any live Bedrock call, confirm the AWS account, role, region, profile, and inference-profile ID; never use an nCino account for this personal PoC.

## Validation Commands

- Run `uv run pytest` and `uv run python -m compileall -q main.py surf scripts` for offline validation; real Bedrock smoke and matrix runs require an explicitly confirmed personal AWS identity.


## Deployment And Release Notes

- Amazon Bedrock AgentCore is the target runtime, but no deployment is authorized by the product plan alone.
- Never deploy, destroy, create, modify, or delete AWS resources without explicit human approval and a documented personal AWS identity, region, budget, retention policy, rollback path, and smoke test.


## Privacy And Secrets

- Do not commit secrets, credentials, tokens, or private customer data.
- Prefer local/private configuration stores for sensitive operational details.

## cxdoc managed memory
