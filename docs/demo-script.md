# Five-minute demo script

This script is a recording plan, not a promise that an ocean is safe. Use the reviewed fixtures so that the recording is reproducible and does not depend on live weather.

| Time | Scene | What to show and say | Verification |
| --- | --- | --- | --- |
| 0:00–0:30 | Problem and boundary | Explain that local marine evidence is hard to interpret; this tool proposes planning windows and never declares the water safe. | README safety boundary visible. |
| 0:30–1:10 | Architecture | Show `docs/assets/architecture.svg`: one Strands agent retrieves facts, while Python alone normalizes evidence and makes veto decisions. | Point out the immutable record arrow. |
| 1:10–2:05 | Normal fixture | Run `uv run python main.py --fixture normal --html /tmp/cape-fear-normal.html`; open the generated HTML. | Show state, source URLs, freshness, and re-check guidance. |
| 2:05–2:55 | Official-hazard fixture | Run `uv run python main.py --fixture hazard`. | Show `official_advisory_present` and the deterministic veto. State that the model cannot remove it. |
| 2:55–3:35 | Failure modes | Run the stale and conflict fixtures. | Show distinct `stale_data` and `conflicting_evidence` states. |
| 3:35–4:15 | Agent evidence | Run `uv run python scripts/evaluate_phase1.py`; then open the committed Phase 3 summary. | Show schema/tool/policy gates and the distinct latency budgets. |
| 4:15–4:45 | MCP / AgentCore boundary | Show `docs/agentcore-mcp-v2-spike.md`. | State that MCP v2 was tested statelessly and this demo makes no deployment. |
| 4:45–5:00 | Close | Restate that posted flags, lifeguards, and officials take priority. | Show the README safety warning and source links. |

## Recording checklist

- [ ] Video is public and no longer than five minutes.
- [ ] Terminal has no credentials, account cookies, private paths, or secret environment variables visible.
- [ ] Every shown result uses the commands above and reviewed fixture inputs.
- [ ] The normal, hazard, stale, and conflict states are all visibly distinct.
- [ ] The recording says that an official advisory overrides the explanation.
- [ ] The recording does not claim a live forecast, a deployment, or that surfing is safe.
