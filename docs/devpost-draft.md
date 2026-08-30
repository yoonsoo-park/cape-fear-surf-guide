# Devpost draft — Cape Fear Surf Guide

## Inspiration

Cape Fear visitors, families, and surf schools must turn marine forecasts, weather alerts, tides, and water-quality information into a practical plan. The difficult part is not writing a fluent answer; it is preserving the distinction between facts, official advisories, and an explanation.

## What it does

Cape Fear Surf Guide creates evidence-backed surf-planning windows for Wrightsville Beach, Carolina Beach, Kure Beach, and Fort Fisher. It returns a structured brief with sources, freshness, warnings, and re-check guidance. It does not guarantee that ocean activity is safe.

## How we built it

A single Strands agent interprets the request, calls fact-only retrieval tools, and emits a `SurfBrief` structured output. Deterministic Python normalizes evidence, converts time, derives windows, and produces an immutable `RecommendationRecord` through `policy.decide`. An active NWS or NC DEQ advisory becomes a deterministic veto before the model explains anything.

The repository also includes a stateless MCP Python SDK v2 (`2026-07-28`) boundary
with a compatibility path for standard hosts such as Codex. The public judge
endpoint is API-key-gated API Gateway and Lambda; Lambda invokes a dedicated
Amazon Bedrock AgentCore Runtime that runs the same live-source normalization,
deterministic policy, and bounded Strands agent. AgentCore is an AWS-native
execution and observability path, not an anonymous public endpoint. The public
MCP boundary remains independently bounded by API keys, WAF, request budgets,
and a circuit breaker.

For evidence rather than decoration, the repository includes an offline DuckDB
report that reproduces the compatibility summary and adds node-token,
scenario-failure, and schema-presence analytics. An explanation-only AgentCore
Web Search adapter is separately guarded, with a private live smoke and teardown
recorded in [`NOTES-websearch.md`](../NOTES-websearch.md).

## What we learned

The prior five-agent research baseline completed only 27 of 33 intended runs. Its handoff payload growth caused four of six failures. This project uses that measured result as the reason to put the safety decision in deterministic Python rather than in a prompt.

## Safety and limits

Official advisories override the model. Missing, seasonal, or unavailable NC DEQ coverage is labeled, not treated as proof of safe water. The product does not book lessons, process payments, offer rescue advice, or replace posted flags, lifeguards, or local officials.

Web Search context is supplemental explanation evidence, not an official
advisory or safety signal. It cannot flip a deterministic decision.

## Evidence and reproducibility

Use the README commands for the four frozen fixtures. The Phase 3 JSON report
records the allowed personal account boundary, provider-reported tokens,
estimated Nova Lite cost, tool calls, immutable-field checks, and latency gates.
The live MCP smoke records `retrieval.mode: live`, a structured decision, and a
separate `window_id` replay through `explain_surf_window`. Token estimates are
not presented as billing invoices.

## Prior work disclosure

This repository incorporates a pre-existing `surf-school-swarm` research baseline. The legacy Swarm, run logs, snapshots, and validators are retained as disclosed prior-art evidence. Cape Fear locations, policy schema, deterministic safety core, single-agent path, structured brief, MCP boundary, and acceptance evaluation are new work.
