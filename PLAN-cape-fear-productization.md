# Cape Fear Surf Guide Productization Plan

## 1. Product decision

Turn the existing `surf-school-swarm` evidence PoC into **Cape Fear Surf Guide**, a Good Neighbor agent for the Cape Fear coast.

The product converts difficult marine, weather, hazard, tide, and water-quality information into evidence-backed surf windows that ordinary people can understand and local organizations can reuse.

The first supported area is:

- Wrightsville Beach
- Carolina Beach
- Kure Beach
- Fort Fisher

The existing snapshot system, validators, run logs, scenario matrix, and measured Strands Swarm failure evidence are the starting point. The five-agent handoff chain is a prior-art experiment, not the production architecture.

The 33-run baseline completed the intended path in 27 runs (81.8%), averaged 136.7 seconds and about 65,730 tokens per run, and failed six times without an AWS throttle or timeout. Four failures came from handoff payload growth. Cape Fear Surf Guide therefore replaces context-amplifying handoffs with deterministic collection, normalization, and policy code followed by one explanation-focused Strands agent.

## 2. People and jobs to be done

### Residents and visitors

People who cannot easily interpret wave height, swell period, wind, tides, rip-current risk, thunderstorms, and water-quality advisories need a plain-language answer to:

> Which beach and time window best fits my experience level, and what could change that recommendation?

### Local surf schools

Schools need a fast first-pass shortlist of promising lesson dates and hours by skill level. The agent reduces repetitive forecast review; the school retains final authority over whether a lesson runs.

### Visitor centers and trip-planning agents

Organizations such as a Wilmington visitor center, concierge, or travel-planning agent need a structured MCP tool that can add an evidence-backed surf option to a larger itinerary without scraping the user-facing interface.

## 3. Product promise and safety boundary

Cape Fear Surf Guide recommends **planning windows**, not a guarantee that ocean activity is safe.

It must:

- explain the evidence in plain language;
- show source names, source URLs, observation or forecast times, and freshness;
- distinguish official advisories from derived model interpretation;
- fail closed when required evidence is missing, stale, or conflicting;
- state that current beach conditions, lifeguards, posted flags, and local officials take priority;
- avoid medical, rescue, or emergency advice;
- never autonomously book, charge, or cancel a lesson in the MVP.

The model may summarize and compare evidence. It may not override deterministic vetoes.

## 4. MVP interaction surfaces

### Human interface

The required hackathon interface is a CLI plus a generated static HTML report. This keeps the demo fast, reproducible, and testable without accounts, OAuth, or a public webhook. Slack is a stretch adapter after the core demo and MCP tools are complete.

Example request:

> My 12-year-old and I are beginners. Which Cape Fear beach looks best Saturday morning?

Example result:

- recommendation state: `recommended_window`, `experienced_only`, `not_recommended`, or `insufficient_data`;
- best one to three beach/time windows;
- three-line plain-language explanation;
- skill-level fit and accessibility notes;
- official advisories and deterministic vetoes;
- source links and data freshness;
- conditions that should trigger re-checking the recommendation.

### MCP interface

Expose a read-only MCP server for other agents.

Initial MVP tools:

- `find_surf_windows(date, party_profile, preferred_area?, time_range?)`
- `explain_surf_window(window_id, reading_level?)`

Later tools may add `get_beach_advisories` and `compare_beaches` only after the first two are measured end to end.

Every tool returns structured evidence and the deterministic decision state. MCP consumers must not receive a bare natural-language recommendation without its evidence and freshness metadata.

### Surf-school interface

Reuse the same core service with a school-specific request:

- date range;
- skill level;
- lesson hours;
- optional instructor availability;
- school-defined conservative thresholds.

The MVP returns candidate windows for human review. Pricing and automatic booking remain out of scope.

## 5. Evidence sources

Use official local sources where an official signal exists and retain Open-Meteo as supplemental forecast data.

Target evidence categories:

- NWS Wilmington surf-zone forecast and beach-hazard statements;
- NWS weather and thunderstorm alerts;
- NOAA tide predictions;
- NC DEQ recreational-water-quality advisory pages or feeds when machine-readable access is verified;
- Open-Meteo marine and weather forecasts for hourly comparison;
- optional local beach closure or flag status when a stable official feed is available.

Each normalized evidence item must contain:

- `source_name`
- `source_url`
- `source_kind`
- `issued_at`
- `valid_from`
- `valid_until`
- `retrieved_at`
- `location`
- `facts`
- `freshness_state`
- `original_timezone`
- `raw_reference`

Internal timestamps use UTC. User-visible times use `America/New_York`. Every evidence item preserves the original timezone or offset string so daylight-saving conversion can be audited.

Water quality is not a universally required feed. Its states are:

- `advisory_active`: deterministic veto;
- `no_advisory_found`: continue with the official page link and last-checked time;
- `out_of_season`: continue with a seasonal-coverage label;
- `feed_unavailable`: continue with an unavailable label and direct-check link.

Synthetic and frozen snapshots remain mandatory for tests and demos. Do not make the demo depend on favorable live conditions.

## 6. Runtime design

Use a deterministic core followed by one explanation-focused Strands agent.

### Deterministic Python core

- Fetch NWS, NOAA, NC DEQ when available, and Open-Meteo concurrently.
- Parse and normalize source payloads into the evidence schema.
- Convert source times to UTC while retaining original timezone strings.
- Apply official-advisory vetoes and source-quality rules as pure functions.
- Apply separately labeled, unreviewed planning filters only after official classifications.
- Produce an immutable `RecommendationRecord` before any model call.

### `community_brief_agent`

- Receives only the finalized decision record.
- Produces a plain-language explanation for the requested reading level and audience.
- Cannot create measurements, change decision states, remove warnings, or invent source URLs.
- If the model call fails, the deterministic record and a template-based fallback remain usable.

The existing availability tool can remain as an optional surf-school adapter outside the common policy core. The old five-agent Swarm remains as documented experimental evidence explaining why the new architecture is bounded and deterministic.

## 7. Deterministic decision policy

Implement the decision engine outside model prompts.

Required states:

- `recommended_window`
- `experienced_only`
- `not_recommended`
- `official_advisory_present`
- `insufficient_data`
- `stale_data`
- `conflicting_evidence`

Initial hard veto classes:

- active official beach-hazard statement or active swimming advisory applicable to the location;
- lightning or severe-weather alert overlapping the window;
- required NWS hazard evidence missing or stale;
- source-location mapping is ambiguous;
- official and supplemental evidence conflict in a safety-significant way.

Authority order is explicit:

1. official NWS classifications and active government advisories;
2. deterministic source freshness, location, and conflict checks;
3. derived planning filters stored in configuration.

Derived thresholds are never described as safety standards. Every value must include provenance and `review_status`; unreviewed values appear as experimental planning filters and cannot be presented in the same visual or verbal style as an official risk classification.

Internal fail-closed states remain distinct for audit and MCP consumers. The human UI collapses them to “We cannot recommend a window right now,” followed by one reason and the official link to check.

## 8. Target architecture

```text
CLI / static HTML / MCP / optional Slack / surf-school adapter
                           |
                 request normalization
                           |
       parallel deterministic source fetchers
       NWS | NOAA | NC DEQ | Open-Meteo
                           |
       Python normalization + UTC conversion
                           |
        pure deterministic policy engine
                           |
          immutable recommendation record
                           |
       Strands agent: explanation only, one call
                           |
             response or template fallback
```

Recommended AWS path:

- Strands Agents on Amazon Bedrock AgentCore Runtime;
- API Gateway and Lambda for MCP or optional Slack ingress where appropriate;
- DynamoDB for request, evidence, and recommendation records;
- S3 for reviewed frozen snapshots and evaluation artifacts;
- EventBridge Scheduler for requested re-checks;
- CloudWatch or AgentCore observability for traces, latency, and failures.

No AWS resource creation is authorized by this plan. Before deployment, document the personal AWS account, role, region, infrastructure entrypoint, budget, retention, rollback, and smoke test.

## 9. Reuse map from `surf-school-swarm`

### Keep

- measured Strands Swarm runs as prior-art evidence, not production orchestration;
- Bedrock model configuration;
- Open-Meteo collection tools;
- frozen snapshots and scenario generation;
- run logging, tool-call recording, latency, and token metrics;
- offline validator and pytest structure;
- repeat-run matrix for nondeterminism evidence.

### Refactor

- `Seal Beach` configuration into Cape Fear beach and source-location mappings;
- conditions and weather outputs into the common evidence schema;
- linear prompt-only handoffs into deterministic Python stages and one bounded explanation call;
- final pricing JSON into a recommendation record;
- safety prompt into deterministic policy plus model explanation;
- CLI command into a shared application service callable by CLI, Slack, and MCP.

### Remove from the core product

- dynamic pricing;
- minimum-price logic;
- automatic booking;
- claims that a window is safe;
- article-specific wording and experiment-only scope statements.

## 10. Hackathon delivery plan

Submission deadline: **September 14, 2026 at 5:00 PM PDT**. The plan optimizes first for a reproducible judged demo, then for optional integrations.

### Phase 0 — Product contracts and Cape Fear fixtures

- Create `surf/locations.py` for the four beaches with coordinates, NWS zone, NOAA station, DEQ mapping, timezone, and explicit `None` plus reason for every unverified mapping.
- Verify NWS requests with an identifying `User-Agent`, NOAA station mappings, DEQ machine-readable availability, and local surfing restrictions from official sources.
- Create `surf/schema.py` for evidence, party profile, beach window, policy decision, and recommendation records.
- Create `config/thresholds.yaml`; every value includes provenance and review status.
- Create `surf/policy.py` as a pure function with no model call.
- Create normal, official-hazard, stale, and conflict fixtures with expected outcomes.
- Document UTC storage and `America/New_York` display rules in `docs/timezone-contract.md`.

Exit gate: fixtures contain no personal information; all expected decisions can be reviewed with zero model calls; unresolved source mappings remain explicit rather than guessed.

### Phase 1 — Local judged-demo slice

- Adapt the existing marine and weather fetchers into deterministic evidence adapters.
- Add stubbed NWS and NC DEQ tools backed by frozen fixtures.
- Implement deterministic policy and structured final response.
- Add one explanation-focused Strands agent plus a template fallback.
- Generate a CLI response and static HTML report from the same record.
- Preserve trace, cost, latency, and violation recording.

Exit gate: 30 repeated offline runs are schema-valid; hazard decisions are identical across repeats; the normal fixture has no false veto; no `unverifiable_slot` finding occurs.

### Phase 2 — MCP and one live source

- Add NWS Wilmington surf-zone and alert retrieval.
- Implement `find_surf_windows` and `explain_surf_window` as read-only MCP tools.
- Keep NOAA, NC DEQ, and Open-Meteo replayable from reviewed snapshots; add live adapters only as time permits.
- Record retrieval time, validity, raw-source reference, and parsing errors.

Exit gate: an MCP client can obtain and explain a frozen recommendation with full evidence; a live NWS response can be captured and replayed offline.

### Phase 3 — Evaluation and presentation

- Implement reading-level-aware explanation without changing policy decisions.
- Add evidence links, data-age labels, and re-check guidance.
- Test with visitor, family beginner, experienced resident, and surf-school scenarios.
- Rewrite README, disclose the copied `surf-school-swarm` baseline, add the architecture diagram, and document setup.
- Record the five-minute demo from frozen evidence.

Exit gate: the quantitative acceptance gates pass and the recorded demo completes without live-network dependence.

### Phase 4 — Optional score boosters

- Deploy the same service to AgentCore after explicit AWS approval.
- Add a trip-planning example using MCP.
- Add Slack only if the CLI, static HTML, MCP, evaluation, README, and video are complete.
- Add live NOAA and DEQ adapters only after source contracts are verified.

Exit gate: each optional feature has its own measured smoke test and does not bypass the shared policy engine.

### Submission gate

- Add an MIT or Apache license and expose it in repository metadata.
- Confirm all source, assets, and setup instructions are present.
- Make the repository public before submission.
- Publish a working project or test build through the judging period.
- Disclose the copied `surf-school-swarm` code and identify the new work built during the submission period.

## 11. Five-minute demo story

1. A visiting parent asks for a beginner-friendly Saturday morning option near Wilmington using the CLI or static demo page.
2. Deterministic adapters gather frozen marine, official hazard, tide, and water-quality evidence.
3. Cape Fear Surf Guide recommends one or two planning windows and explains them in plain language.
4. The response shows official sources, issue times, freshness, and what would invalidate the recommendation.
5. The Strands agent turns the finalized record into a simple community brief without changing its decision.
6. A trip-planning agent calls the MCP tool and adds the reviewed window to a draft itinerary.
7. A hazard fixture activates an official advisory; deterministic policy withdraws the recommendation even if other conditions look favorable.
8. The trace contrasts the old five-agent failure evidence with the new bounded explanation path.

## 12. Acceptance criteria

- Schema-valid response rate is 100% across 30 repeated fixture runs.
- Official-hazard veto reproduction is 100% with zero variation across repeats.
- False-veto rate on the reviewed normal fixture is 0%.
- `unverifiable_slot` findings are zero.
- Every recommendation includes source URLs, original timezone, and freshness metadata.
- Official hazard and active water-quality advisories cannot be overridden by a model.
- Missing, stale, ambiguous, or conflicting required NWS hazard evidence fails closed.
- Every implemented adapter uses the same policy engine.
- MCP tools are read-only, bounded, and return structured results.
- Frozen snapshots reproduce both the normal and hazard demos without live network access.
- Normal and hazard demos complete in CI with network access disabled.
- End-to-end p95 latency is at most 10 seconds across 30 measured runs.
- Estimated model cost is at most $0.02 per request from recorded usage.
- Repeated runs record tools, latency, token usage, errors, and policy outcomes.
- No result claims that surfing is guaranteed safe.
- No booking, payment, cancellation, rescue, or emergency action is available.
- A full AgentCore smoke test covers one recommendation and one deterministic veto.

## 13. Explicitly out of scope for MVP

- Real-time emergency or rescue guidance
- Guaranteeing ocean safety
- Automatic lesson booking, cancellation, or payment
- Dynamic pricing
- User accounts and a standalone mobile application
- Nationwide beach coverage
- Community-submitted hazard reports without moderation
- Replacing lifeguards, local officials, or professional instructor judgment

## 14. First implementation decision

Do not begin with Slack, MCP, or AWS infrastructure.

The first executable product slice is:

`Cape Fear frozen snapshot -> deterministic normalization -> deterministic policy -> immutable record -> one Strands explanation call or template fallback`

Build it with two mandatory cases:

1. a normal beginner planning window;
2. an official-advisory fixture that must return `not_recommended` or `official_advisory_present`.

Once that slice is reliable, expose the same service through the two MCP tools. Add AgentCore and Slack only after the judged demo, evaluation gates, and submission materials are complete.

## 15. Phase 0 source and identity contracts

### Location and tide mapping

Each beach record must include a verified NOAA station or an explicit fallback mapping. When a nearest station is used, the evidence records the station name, distance or rationale, and the fact that it is a proxy. Wrightsville Beach station `8658163` is a candidate verified by the review; it must still be captured in the source-verification note before becoming configuration. Never guess mappings for Carolina Beach, Kure Beach, or Fort Fisher.

### Stable window identity

The MVP does not require DynamoDB. Derive `window_id` from a versioned hash of request parameters, snapshot ID, beach ID, and UTC interval. `explain_surf_window` can then reproduce the record from frozen inputs. Persistence can be added later without changing the public identifier contract.

### Local rules

Phase 0 must check official municipal or county sources for seasonal surfing zones, pier-distance rules, closures, and other location restrictions. Unverified community knowledge never becomes a veto.

### Prior-art disclosure

The official rules require a new project during the August 10 through September 14 submission period and disclosure of pre-existing work. All current repository commits are dated inside the submission period, but the README must still state that the repository began as a copied `surf-school-swarm` research baseline and clearly list the Cape Fear-specific product work added for the submission.
