# Submission checklist

## Repository package

- [x] GitHub repository made public on 2026-08-22 after human approval: <https://github.com/yoonsoo-park/cape-fear-surf-guide>.
- [x] MIT license: [`LICENSE`](../LICENSE).
- [x] Run instructions and safety limits: [`README.md`](../README.md).
- [x] Architecture asset: [`docs/assets/architecture.svg`](assets/architecture.svg).
- [x] AgentCore MCP v2 live-spike evidence: [`docs/agentcore-mcp-v2-spike.md`](agentcore-mcp-v2-spike.md).
- [x] Public live MCP contract and source capture: [`docs/external-mcp-demo.md`](external-mcp-demo.md) and [`docs/live-source-contract.md`](live-source-contract.md).
- [x] Prior-work disclosure: README and [`docs/devpost-draft.md`](devpost-draft.md).

## Validation evidence

- [x] Run `uv run pytest` (45 passed) and `uv run python -m compileall -q main.py surf scripts` on 2026-08-22.
- [x] Run `uv run --directory mcp_runtime pytest` (16 passed) on 2026-08-22.
- [x] Run `uv run python scripts/evaluate_phase1.py` for the fixture-only acceptance check on 2026-08-22.
- [x] Live Phase 3 evidence: [`summary.json`](../reports/phase3/20260822T210549Z/summary.json) and [`raw-runs.jsonl`](../reports/phase3/20260822T210549Z/raw-runs.jsonl), generated 2026-08-22 21:05:49 UTC.
- [x] Confirmed the report has 30 matrix runs, two successful preflights, a passing deterministic path, 100% structured schema/tool/veto gates, zero normal false vetoes, zero invariant failures, agent p95 6,496.835 ms, and max request cost $0.00086886.
- [x] Checked the README report/diagram/checklist links and the successful report paths on 2026-08-22.

## Recording and submission

- [ ] Record the public video using [`docs/demo-script.md`](demo-script.md); keep it at five minutes or less.
- [ ] After explicit AWS approval, deploy the API Gateway REST + WAF API-key-gated live MCP stack and record Claude Desktop plus ChatGPT Desktop/Codex tool discovery, live call, and 24-hour `window_id` replay. Use the environment-backed `x-api-key`; do not record its value.
- [ ] For that deployment, record the new `ExposureId`, approved 72-hour `PublicUntilUtc`, $10 budget-email confirmation, and circuit-breaker status. After expiry, confirm concurrency is zero before requesting separate stack-deletion approval.
- [ ] Upload the video after human approval and add its public URL to the Devpost entry.
- [ ] Paste and review [`docs/devpost-draft.md`](devpost-draft.md) in Devpost after human approval.
- [ ] Publish blog drafts [`01`](blog/01-measuring-a-strands-swarm.md), [`02`](blog/02-why-the-safety-decision-is-not-a-prompt.md), and [`03`](blog/03-measuring-one-bounded-agent.md) only after human approval.

## Public-repository security check

- [x] Ran `git grep -n -I -E '(AKIA[0-9A-Z]{16}|aws_secret_access_key|BEGIN (RSA |OPENSSH )?PRIVATE KEY)'` on 2026-08-22. The public runbook prohibits secrets and request content in source, images, logs, and README files.
- [x] Ran `gitleaks detect --no-git --source . --redact --exit-code 1 --verbose` on 2026-08-22. It scanned approximately 2.14 MB of submission files and reported no leaks.
- [ ] Run `git status --short`; stage only intended submission files.
- [ ] Inspect generated raw evidence for secrets before adding it. The report may contain the approved account and inference-profile identifiers, but must never contain credentials or session tokens.
