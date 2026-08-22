# Devpost draft — Cape Fear Surf Guide

## Inspiration

Cape Fear visitors, families, and surf schools must turn marine forecasts, weather alerts, tides, and water-quality information into a practical plan. The difficult part is not writing a fluent answer; it is preserving the distinction between facts, official advisories, and an explanation.

## What it does

Cape Fear Surf Guide creates evidence-backed surf-planning windows for Wrightsville Beach, Carolina Beach, Kure Beach, and Fort Fisher. It returns a structured brief with sources, freshness, warnings, and re-check guidance. It does not guarantee that ocean activity is safe.

## How we built it

A single Strands agent interprets the request, calls fact-only retrieval tools, and emits a `SurfBrief` structured output. Deterministic Python normalizes evidence, converts time, derives windows, and produces an immutable `RecommendationRecord` through `policy.decide`. An active NWS or NC DEQ advisory becomes a deterministic veto before the model explains anything.

The repository also includes a stateless MCP Python SDK v2 (`2026-07-28`) boundary. The documented AgentCore compatibility spike passed without changing the policy engine; no AgentCore resource is created by the demo or Phase 3 evaluation.

## What we learned

The prior five-agent research baseline completed only 27 of 33 intended runs. Its handoff payload growth caused four of six failures. This project uses that measured result as the reason to put the safety decision in deterministic Python rather than in a prompt.

## Safety and limits

Official advisories override the model. Missing, seasonal, or unavailable NC DEQ coverage is labeled, not treated as proof of safe water. The product does not book lessons, process payments, offer rescue advice, or replace posted flags, lifeguards, or local officials.

## Evidence and reproducibility

Use the README commands for the four frozen fixtures. The Phase 3 JSON report records the allowed personal account boundary, provider-reported tokens, estimated Nova Lite cost, tool calls, immutable-field checks, and latency gates. Token estimates are not presented as billing invoices.

## Prior work disclosure

This repository incorporates a pre-existing `surf-school-swarm` research baseline. The legacy Swarm, run logs, snapshots, and validators are retained as disclosed prior-art evidence. Cape Fear locations, policy schema, deterministic safety core, single-agent path, structured brief, MCP boundary, and acceptance evaluation are new work.
