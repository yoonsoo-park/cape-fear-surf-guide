# Agents for Humans: I Measured a Five-Agent Strands Swarm 33 Times and It Failed 18% of the Time

Status: draft for builder.aws. Target publish date 2026-08-24.
Every number below comes from a recorded run log, not from an estimate.

## The setup

I am building a Good Neighbor agent for the Cape Fear coast in North Carolina. It answers a question that sounds simple and is not: which beach and time window fits a beginner, and what evidence supports that answer?

Before designing the product I wanted to know whether the standard multi-agent picture actually holds up. The picture is familiar. You draw five specialists, you draw arrows between them, each one adds its piece, and the last one produces the answer. Every architecture diagram I had seen looked like that, including the ones I was copying from.

So I built it and measured it.

The chain was `conditions_agent` to `weather_agent` to `availability_agent` to `safety_agent` to `pricing_agent`, wrapped in one orchestrator tool call. Strands Agents SDK 1.52.0, Bedrock, temperature 0. Data came from captured Open-Meteo marine and weather snapshots plus a local inventory file, so every run saw byte-identical input. Eleven scenarios, three repeats each, 33 runs total.

Frozen input and temperature 0 were deliberate. I wanted the only variable to be the model and the framework.

## What the log says

| Measurement | Value |
| --- | --- |
| Runs | 33 (11 scenarios, 3 repeats) |
| Successful runs | 27 (81.8%) |
| Failed runs | 6 (18.2%) |
| Runs that took the exact intended five-agent path | 27 (81.8%) |
| Mean latency | 136.7 s |
| Median latency | 132.5 s |
| p95 latency | 159.6 s |
| Latency range | 115.2 s to 186.2 s |
| Input tokens | 1,812,651 |
| Output tokens | 356,427 |
| Total tokens | 2,169,078 |
| Mean total tokens per run | 65,730 |
| p95 total tokens per run | 76,275 |
| Estimated batch cost | $10.78 at $3/M input and $15/M output |
| AWS throttles recorded | 0 |
| Timeouts recorded | 0 |

Two numbers deserve a caveat. The $10.78 is derived from recorded token usage at published rates, not from an AWS invoice. And the batch ran serially, so its roughly 75 minutes of accumulated latency is not a throughput measurement.

## Where the failures actually came from

Zero throttles. Zero timeouts. That surprised me, because "it is probably rate limiting" was my first guess. Here is what actually happened in the six failures.

1. `high-swell-and-gusts` repeat 1: `safety_agent` hit the 4,000 token generation limit while constructing its handoff to pricing.
2. `beginner-boundary` repeat 1: `safety_agent` hit the same limit while serializing 21 approved slots. Repeats 2 and 3 succeeded on the identical snapshot.
3. `cold-calm` repeat 1: pricing produced a valid eight-slot result, then the swarm handed control back to `conditions_agent`. The resulting six-node cycle exhausted the iteration budget and the run was marked failed.
4. `variable-conditions` repeat 1: `safety_agent` hit the generation limit during handoff.
5. `premium-clean` repeat 1: same.
6. `high-demand` repeat 1: `pricing_agent` failed Bedrock validation because the framework tried to continue a conversation that ended with an assistant message. Bedrock rejected that shape.

Four of six failures are the same failure: the handoff payload grew until the agent producing it ran out of room. One was nondeterministic routing. One was a conversation-shape incompatibility between the SDK and the model.

The mechanism is not exotic. Each specialist reads everything the previous ones observed and writes it forward with its own additions. The last handoff in the chain is therefore the largest and the most fragile. I reduced it once already: compacting the handoff format took a same-snapshot comparison from 306.0 s to 135.0 s and from 108,827 swarm tokens to 64,781. That helped a lot and it did not fix the failure mode. The 33-run batch still averaged 65,730 tokens and still failed 18.2% of the time.

I have started calling this context amplification. The arrows in the diagram look like they carry a message. They actually carry an accumulating transcript.

## Temperature 0 did not buy determinism

This was the finding that changed the product.

Temperature was 0. Every repeat used the same snapshot and the same inventory. Five of eleven scenarios still produced one failure followed by two successes. Not just a different failure rate, a different failure location, and in one case a different agent path.

Earlier baselines also produced incompatible JSON shapes for the same field: `slots` as an array in some runs, and an object containing `approved_slots` in others. My offline validator normalizes known shapes so it can check them, but it deliberately does not rewrite what the model produced.

Temperature 0 constrains token sampling. It does not constrain tool-call formatting, handoff length, or routing.

## What the safety numbers do and do not show

The validator found zero beginner threshold violations and zero price-floor violations in the recommendations it could verify. High-swell and strong-gust scenarios removed unsafe beginner recommendations in every completed output.

It would be easy to write "prompt-only safety worked." That claim is not supported, for five reasons.

- Six runs failed before producing a usable result at all.
- Five failures were classified as malformed output.
- Two `missing-hour` repeats recommended three slots at a 10:00 observation that did not exist in the snapshot. The validator flagged these as `unverifiable_slot`. A slot cannot be called safe merely because no numeric violation was measurable against absent data.
- The validator checks the final extracted slots. It does not check every natural-language claim or every intermediate handoff.
- The thresholds themselves were experiment inputs I chose. They are not professional surf-safety guidance.

The supportable conclusion is narrow: no measurable safety or price-floor violation occurred in the verifiable completed recommendations in this batch. That is not a reliability rate.

## What I changed

The product I am building recommends ocean activity windows to families, sometimes with children. An 18.2% failure rate would be survivable. A decision path whose failure location changes under identical input is not, because it means I cannot write a test that proves the safety rule holds.

So the safety decision left the model.

The production architecture is now a deterministic Python core that fetches, parses, normalizes timestamps to UTC, derives candidate windows, and applies vetoes as pure functions. Official National Weather Service classifications outrank anything I derive. Above that core sits a single Strands agent that owns the parts where being wrong is cheap and visible: asking the user a clarifying question, deciding which beaches and sources to query, calling the retrieval tools, and turning the finished record into plain language.

The rule I keep coming back to:

> The agent decides what to look up and how to explain it.
> The agent has no path to deciding whether the water is safe.

Pro: the safety decision becomes a pure function, so "this hazard fixture always produces a veto" is a unit test rather than a hope. Latency and cost for the decision drop to near zero. The agent still does real agentic work, and its tool calls are recorded.

Con: I gave up the tidy five-box diagram, and I had to accept that a chunk of what looked like agent work was really a parser wearing a costume.

## If you are drawing one of those diagrams

Three things I would check before trusting it.

1. Measure repeats on frozen input before you trust a path. One successful run tells you the path is possible, not that it is reliable.
2. Look at what your arrows actually carry. If each node rewrites its predecessors' output, your last handoff is your real bottleneck and your real failure point.
3. Ask which of your agents would be better as a function. Anything whose job is "normalize this JSON" or "pick one of four enum values" is a parser, and turning it into a parser removes a place where a hallucinated number can enter your system.

Next post: what the official surf forecast actually says, and why `api.weather.gov` returns 403 until you introduce yourself.

Code and the full run log summary: https://github.com/yoonsoo-park/cape-fear-surf-guide
