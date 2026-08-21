# Hermes Evidence Notes

## Evidence boundary

This report analyzes lines 5–37 of the private `runs/log.jsonl`: 11 frozen scenarios repeated three times with `compact-handoff-v1`, for 33 Bedrock runs total. The batch reused captured Open-Meteo snapshots and local inventory; it did not deploy AgentCore or any AWS resource. The public `runs/sample-log.jsonl` removes long model prose but preserves scenario, path, tool calls, node status, latency, token usage, validation, and failure classification.

## Architecture actually observed

The intended path was `conditions_agent → weather_agent → availability_agent → safety_agent → pricing_agent`, wrapped by one orchestrator tool call. It completed exactly in 27 of 33 runs. The conditions, weather, and availability tools ran in all 33 runs; the pricing tool ran in 29 because four runs failed in `safety_agent` before pricing.

The installed Strands SDK is `1.52.0`. `SwarmResult` has no `final_response` field in this version, so the PoC reads the pricing node from `result.results` and usage from the aggregate swarm result. Argument-free tools repeatedly emitted `failed to parse tool input json, defaulting to empty dict`; Strands substituted `{}` and continued. This warning is a tool-call formatting defect even when the final recommendation validates.

## 33-run result

- Runs: 33 across 11 scenarios, three repeats each
- Successful runs: 27 (81.8%); failed runs: 6 (18.2%)
- Exact five-agent path: 27 (81.8%)
- Latency: mean 136.7 s, median 132.5 s, p95 159.6 s, range 115.2–186.2 s
- Tokens including orchestrator: 1,812,651 input and 356,427 output, 2,169,078 total
- Total-token distribution: mean 65,730, median 67,476, p95 76,275 per run
- Estimated batch cost: $10.78, assuming $3/M input tokens and $15/M output tokens
- Throttles and timeouts recorded in JSONL: zero

The cost is an estimate from recorded model usage, not an AWS invoice. The batch ran serially, so its approximately 75-minute accumulated latency is not a production throughput measurement.

## Six failures and causes

1. `high-swell-and-gusts` repeat 1: `safety_agent` reached the 4,000-token generation limit while constructing its pricing handoff.
2. `beginner-boundary` repeat 1: `safety_agent` reached the same limit while serializing 21 approved slots. Repeats 2 and 3 succeeded with the identical snapshot.
3. `cold-calm` repeat 1: pricing completed with a valid eight-slot result, but the swarm handed control back to `conditions_agent`; the six-node cycle exhausted the iteration budget and marked the run failed. Repeats 2 and 3 followed the intended path.
4. `variable-conditions` repeat 1: `safety_agent` reached the generation limit during handoff; repeats 2 and 3 succeeded.
5. `premium-clean` repeat 1: `safety_agent` reached the generation limit during handoff; repeats 2 and 3 succeeded.
6. `high-demand` repeat 1: `pricing_agent` failed Bedrock validation because Strands attempted to continue a conversation ending with an assistant message. Bedrock rejected that assistant-prefill shape; repeats 2 and 3 succeeded.

Four failures therefore came from handoff payload growth, one from nondeterministic routing, and one from an SDK/model conversation-shape incompatibility. None was an AWS throttle or timeout.

## Nondeterminism

Temperature was zero and every repeat used the same snapshot and inventory, but five scenarios had one failure followed by two successes. The failure location and even the agent path changed across identical inputs. Temperature zero therefore did not make tool formatting, handoff length, or routing deterministic.

The earlier baselines also produced incompatible JSON shapes (`slots` as a list versus an object containing `approved_slots`). The validator observes and normalizes known shapes for checking, but it does not rewrite the model's recommendation.

## Prompt-only safety and pricing result

The validator found zero beginner safety-threshold violations and zero price-floor violations in recommendations it could verify. High-swell and strong-gust scenarios removed unsafe beginner recommendations in all completed outputs. The deterministic guardrail experiment was not activated because the planned trigger—an observed safety veto or price-floor violation—did not occur.

This does not prove that prompt-only policy is reliable:

- Six runs failed before producing a usable complete result.
- Five failures were classified as malformed output by the validator.
- Two `missing-hour` repeats recommended three total slots at the absent 10:00 observation, producing `unverifiable_slot` findings. Those slots cannot be counted as safe merely because no numeric threshold violation was measurable.
- The validator checks the final extracted slots, not every natural-language claim or every intermediate handoff.
- The thresholds are experiment inputs, not professional surf-safety guidance.

The supported conclusion is narrow: no measurable safety or price-floor violation occurred in the verifiable completed recommendations from this batch. The sample does not establish a general reliability rate for prompt-only safety.

## AWS diagram versus execution

The AWS example's clean sequence hides context amplification: each specialist reads and rewrites prior observations, so later handoffs become the most expensive and failure-prone. Compact lesson-hour handoffs reduced a same-snapshot comparison from 306.0 to 135.0 seconds and from 108,827 swarm tokens to 64,781 swarm tokens, but the 33-run batch still averaged 65,730 total tokens and failed 18.2% of runs.

The diagram also hides malformed argument-free tool calls, schema drift, a possible backward agent cycle, the extra orchestrator pass, and SDK/model conversation constraints. The five-agent pattern did collaborate on real Bedrock calls, but the evidence shows that prompt contracts alone did not guarantee a complete linear execution.
