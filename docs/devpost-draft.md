# Devpost draft — Cape Fear Surf Guide

Track: **Good Neighbor Agents**

## What it does

Cape Fear Surf Guide turns four disagreeing public marine feeds into one
reviewable surf-planning window, with its evidence attached. Ask it for a
Wrightsville Beach morning for a beginner group and it returns a decision state,
the five sources it read, when it read each one, how fresh each one is, the
warnings that apply, and when to check again.

It never says the water is safe. That sentence is a product decision, not a
disclaimer, and the rest of this describes how the system is built so that it
cannot drift away from it.

## The problem, and who has it

Deciding whether to take people into the water means reconciling an NWS zone
forecast, NWS active alerts, NOAA tide predictions, and marine wind and swell
data. Those four feeds disagree with each other, go stale at different rates,
and none of them answers the question that is actually being asked, which is
whether this particular group should go in at this particular hour.

The people doing that reconciliation are not power users. They are surf schools
running beginner lessons, families planning a morning, and the volunteers and
small local organizations along the Cape Fear coast who get asked "is it okay
today?" and have to answer on behalf of someone else.

That last part is why this is a Good Neighbor agent rather than a personal
assistant. The person operating it is rarely the person who gets in the water.
A single answer travels to a group, so the cost of a confident wrong answer is
not one ruined morning.

## Why it matters

The dangerous failure mode for a language model here is not being unhelpful. It
is being fluent. A well-written explanation that quietly talks past an active
hazard advisory reads more trustworthy than a blunt refusal, and it is the
output most likely to be believed and acted on.

So the design question was never "how do we prompt the model to be careful."
It was "what has to be true so that the model is structurally unable to produce
that output."

## How we built it

A single **Strands agent** owns intake, calls fact-only retrieval tools, and
emits a schema-validated `SurfBrief`. It is the part of the system allowed to
write prose.

Deterministic Python owns everything that decides. It normalizes the four
feeds, converts time zones, derives candidate windows, checks freshness and
cross-source conflicts, applies official-advisory vetoes, and emits an immutable
`RecommendationRecord` through `policy.decide`. An active NWS or NC DEQ advisory
becomes a veto **before** the agent is asked for anything, so there is no point
in the pipeline where a well-worded explanation can reach the decision.

The public surface is a stateless MCP Python SDK v2 server on protocol
`2026-07-28`, with a compatibility path for standard MCP hosts. The judge path
is API Gateway plus WAF plus Lambda; Lambda invokes a dedicated **Amazon Bedrock
AgentCore Runtime** that runs the same live-source normalization, the same
deterministic policy, and the bounded Strands agent. AgentCore is the execution
and observability path, not an anonymous public endpoint.

`find_surf_windows` writes the exact decision under a random `window_id` to
encrypted DynamoDB with a 24-hour TTL. `explain_surf_window` reads that record
back. It performs no second live retrieval and uses no chat memory, so any
explanation the tool gave can be reproduced and audited afterwards from the
`window_id` alone.

## The design decision that defines the project

The agent cannot change the record it is explaining.

That constraint came from measurement, not taste. The prior `surf-school-swarm`
research baseline ran a five-agent handoff chain and completed 27 of 33 intended
runs. Four of the six failures traced to handoff payload growth. Putting the
safety decision anywhere inside that conversational surface meant accepting
those failure modes for the one output that must never fail. So the decision
moved into Python, and the agent kept the job it is actually good at, which is
explaining a fixed record to a specific audience.

## What we measured

A 30-case matrix across four fixtures and four party profiles, with two
preflight requests that must pass before the matrix runs at all:

- deterministic path: zero model calls, byte-identical outputs, p95 under 2
  seconds
- agentic path: p95 6,496.835 ms against a 30-second budget; maximum request
  cost $0.00086886 against a $0.05 per-request cap and a $10 whole-run guard
- 100% structured-schema success, 100% tool-call success, 100% official-veto
  success
- zero false vetoes on the normal fixture, zero immutable-field violations

The cost figure uses AWS Price List API rates for Nova Lite in `us-east-1`
checked on 2026-08-22 ($0.00006 per 1K input tokens, $0.00024 per 1K output
tokens). Provider token counters are preserved as evidence. They are not a
billing invoice.

The live path was verified end to end through an MCP client on 2026-09-13:
`retrieval.mode: live`, five sources with URLs and freshness labels,
`brief_source: agent`, a deterministic decision state, and an
`explain_surf_window` replay whose `window_id` and decision state matched the
original call exactly.

## Safety and limits

- Official advisories and deterministic policy override every model
  explanation.
- Required NWS hazard evidence that is missing or stale prevents a
  recommendation rather than producing a hedged one.
- Only an active NC DEQ advisory is a water-quality veto. Missing, seasonal, or
  unavailable coverage is labeled as such and is never treated as proof that the
  water is clean.
- A failed public source returns `insufficient_data`. It never falls back to a
  fixture.
- Unverified station, source, and local-rule mappings stay explicit. The code
  does not guess them.
- Booking, payment, cancellation, rescue guidance, and any claim that surfing is
  safe are out of scope.
- Posted flags, lifeguards, and local officials take priority over this tool.

## Live demo access

The public MCP endpoint is deliberately not an open URL. It is gated by a
manually issued `x-api-key`, and it is bounded by WAF rate rules, an API Gateway
usage plan, a hard budget of 120 valid requests per exposure window, and a
circuit breaker that sets Lambda concurrency to zero at budget or expiry.

Those controls exist because an unbounded public agent endpoint on a personal
account is a cost and abuse problem, not because the demo is fragile.

Access is available on request during the judging period. Email
yoonsoo@duck.com and a dedicated 72-hour exposure window is opened for that
request, with its own exposure ID, its own key, and its own request budget. The
endpoint is deliberately not continuously live between requests, and each
window closes itself on a scheduled circuit breaker rather than on trust.

## What we learned

Measuring the prior baseline was worth more than any amount of prompt iteration.
It produced a number, 4 of 6 failures from handoff payload growth, and that
number decided the architecture. The habit generalizes: when a system must not
fail in one specific way, find where that failure is currently possible and
remove the possibility, rather than instructing the model to avoid it.

## Prior work disclosure

This repository incorporates a pre-existing `surf-school-swarm` research
baseline. The legacy Swarm, run logs, snapshots, and validators are retained as
disclosed prior-art evidence. The Cape Fear locations, policy schema,
deterministic safety core, single-agent path, structured brief, MCP boundary,
AgentCore deployment, and acceptance evaluation are new work for this hackathon.
