# AGENTS.md

## Project Purpose

- Cape Fear Surf Guide turns difficult marine, weather, hazard, tide, and water-quality evidence into plain-language surf planning windows for Cape Fear residents, visitors, local surf schools, and external trip-planning agents.
- The existing evidence-focused Strands Swarm PoC is the implementation baseline. Preserve its snapshots, validators, traces, and repeat-run evidence while productizing it for Wrightsville Beach, Carolina Beach, Kure Beach, and Fort Fisher.
- Read `PLAN-cape-fear-productization.md` before changing product scope or architecture.


## Agent Operating Rules

- Start by reading this file and use cxdoc search commands before relying on memory.
- Use `cxdoc current . --json` to confirm the project mapping when context matters.
- Keep durable project instructions in this file; keep searchable details in cxdoc knowledge notes.

- Official advisories and deterministic policy override model recommendations. The model cannot declare ocean activity safe, override a hazard or water-quality advisory, or act when required evidence is missing, stale, ambiguous, or conflicting.
- Keep Slack, MCP, and surf-school adapters on one shared application service and policy engine.

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
