# AGENTS.md

## Project Purpose

- This repository is an evidence-focused Strands Swarm PoC that reproduces the AWS restaurant dynamic-pricing pattern for a surf-school article; optimize for reproducible runtime evidence, not production product breadth.


## Agent Operating Rules

- Start by reading this file and use cxdoc search commands before relying on memory.
- Use `cxdoc current . --json` to confirm the project mapping when context matters.
- Keep durable project instructions in this file; keep searchable details in cxdoc knowledge notes.

- Before any live Bedrock call, confirm the AWS account, role, region, profile, and inference-profile ID; never use an nCino account for this personal PoC.

## Validation Commands

- Run `uv run pytest` and `uv run python -m compileall -q main.py surf scripts` for offline validation; real Bedrock smoke and matrix runs require an explicitly confirmed personal AWS identity.


## Deployment And Release Notes

- AgentCore and all AWS resource deployment are out of scope. Never deploy, destroy, create, modify, or delete AWS resources without explicit human approval.


## Privacy And Secrets

- Do not commit secrets, credentials, tokens, or private customer data.
- Prefer local/private configuration stores for sensitive operational details.

## cxdoc managed memory

