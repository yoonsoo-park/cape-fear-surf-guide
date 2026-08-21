# Hermes Evidence Notes

## Architecture observed

The live path completed as `conditions → weather → availability → safety → pricing`, wrapped by one orchestrator tool call. All three live runs used the same five specialists and each specialist called its intended data tool or handoff tool.

## Actual findings

1. The installed Strands SDK is `1.52.0`, while the source plan referenced an older sample. `SwarmResult` has no `final_response` field in this version; the final pricing node must be read from `result.results`, and aggregate usage is available directly on the swarm result.
2. Context-only tools work, but Bedrock emits `failed to parse tool input json, defaulting to empty dict` for every argument-free call. The calls still completed successfully in all three runs.
3. The first two identical-contract prompts produced incompatible JSON shapes: `slots` was a list in the normal run and an object containing `approved_slots` in the high-swell run. The observer now records the schema variant and normalizes both without changing the recommendation.
4. The original handoffs repeated all 24 hourly observations and large prose tables. Restricting handoffs to lesson hours and capping the final recommendations reduced the same-snapshot run from 306.0 to 135.0 seconds and from 108,827 swarm tokens to 64,781 swarm tokens.
5. No throttling or timeout occurred in the first three runs. The main operational problem was latency and token amplification, not API reliability.

## Measurements

Three Bedrock runs completed. The first two prompt-only baselines averaged 303.9 seconds and together used 218,021 swarm tokens. The tuned same-snapshot comparison used 64,781 swarm tokens plus 3,354 orchestrator tokens and completed in 135.0 seconds. At an explicitly assumed on-demand rate of $3/M input tokens and $15/M output tokens, the baseline swarm runs were approximately $0.65 and $0.66, while the tuned swarm plus orchestrator was approximately $0.34. Baseline orchestrator usage was not captured, so those two estimates are lower bounds. These are PoC observations, not billing or production capacity claims.

## Prompt-only guardrail result

The normal baseline and 1.8 m high-swell baseline were revalidated after normalizing their observed schemas. Both had zero safety or price-floor violations. In the high-swell run, all beginner offerings were removed and 16 instructor slots remained. Two samples do not prove prompt-only reliability, so no deterministic guardrail was added.

## AWS diagram versus execution

The diagram hides context amplification: every child rewrites prior observations, so later agents receive and generate increasingly large payloads. It also hides schema instability and the extra top-level orchestrator pass. The five-node path was reliable in these runs, but one result cost roughly five minutes and more than 100k swarm tokens before prompt tuning.
