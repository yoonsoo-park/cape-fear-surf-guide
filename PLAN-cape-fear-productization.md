# Cape Fear Surf Guide Productization Plan

## 1. Product decision

Turn the existing `surf-school-swarm` evidence PoC into **Cape Fear Surf Guide**, a Good Neighbor agent for the Cape Fear coast.

The product converts difficult marine, weather, hazard, tide, and water-quality information into evidence-backed surf windows that ordinary people can understand and local organizations can reuse.

The first supported area is:

- Wrightsville Beach
- Carolina Beach
- Kure Beach
- Fort Fisher

The existing Strands multi-agent runtime, snapshot system, validators, run logs, and scenario matrix are the starting point. This is a productization project, not a rewrite.

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

Start with one small chat surface rather than a standalone frontend. Slack is the preferred demo interface because it supports questions, evidence links, status blocks, and follow-up actions with little UI work.

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

Initial tools:

- `find_surf_windows(date, party_profile, preferred_area?, time_range?)`
- `explain_surf_window(window_id, reading_level?)`
- `get_beach_advisories(beach, date)`
- `compare_beaches(date, party_profile)`

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
- NC DEQ recreational-water-quality advisories;
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

Synthetic and frozen snapshots remain mandatory for tests and demos. Do not make the demo depend on favorable live conditions.

## 6. Agent design

Replace the commercial five-agent chain with a community planning swarm.

1. `marine_conditions_agent`
   - Reads wave height, swell height, period, and direction when available.
   - Produces normalized hourly facts, not a safety conclusion.

2. `local_hazards_agent`
   - Reads NWS surf-zone forecasts, rip-current risk, lightning or thunderstorm risk, heat, and beach-hazard statements.
   - Preserves official wording and validity times.

3. `water_quality_agent`
   - Reads NC DEQ swimming advisories and maps them to supported beaches.
   - Reports `clear`, `advisory`, `unknown`, or `stale`.

4. `party_fit_agent`
   - Compares candidate windows with beginner, intermediate, child, family, and accessibility needs.
   - Cannot approve a window vetoed by deterministic policy.

5. `community_brief_agent`
   - Produces the final plain-language brief and structured MCP response.
   - Cites only evidence passed through tools.

The existing availability agent can remain as an optional surf-school adapter outside the common safety swarm.

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

- active official beach-hazard or swimming advisory applicable to the location;
- lightning or severe-weather alert overlapping the window;
- required official source missing or stale;
- source-location mapping is ambiguous;
- child or beginner profile exceeds configured conservative thresholds;
- official and supplemental evidence conflict in a safety-significant way.

Threshold values must be configuration with named provenance and review status. Do not present experimental thresholds as professional surf-safety standards.

## 8. Target architecture

```text
Slack / MCP client / surf-school adapter
                 |
          API ingress layer
                 |
       request normalization
                 |
     Strands community swarm
        |       |       |
      NWS     NOAA    NC DEQ + Open-Meteo
                 |
    deterministic policy engine
                 |
 evidence-backed recommendation record
                 |
      Slack response / MCP result
```

Recommended AWS path:

- Strands Agents on Amazon Bedrock AgentCore Runtime;
- API Gateway and Lambda for Slack and MCP ingress where appropriate;
- DynamoDB for request, evidence, and recommendation records;
- S3 for reviewed frozen snapshots and evaluation artifacts;
- EventBridge Scheduler for requested re-checks;
- CloudWatch or AgentCore observability for traces, latency, and failures.

No AWS resource creation is authorized by this plan. Before deployment, document the personal AWS account, role, region, infrastructure entrypoint, budget, retention, rollback, and smoke test.

## 9. Reuse map from `surf-school-swarm`

### Keep

- Strands Swarm orchestration pattern;
- Bedrock model configuration;
- Open-Meteo collection tools;
- frozen snapshots and scenario generation;
- run logging, tool-call recording, latency, and token metrics;
- offline validator and pytest structure;
- repeat-run matrix for nondeterminism evidence.

### Refactor

- `Seal Beach` configuration into Cape Fear beach and source-location mappings;
- conditions and weather outputs into the common evidence schema;
- linear prompt-only handoffs into bounded, schema-validated handoffs;
- final pricing JSON into a recommendation record;
- safety prompt into deterministic policy plus model explanation;
- CLI command into a shared application service callable by CLI, Slack, and MCP.

### Remove from the core product

- dynamic pricing;
- minimum-price logic;
- automatic booking;
- claims that a window is safe;
- article-specific wording and experiment-only scope statements.

## 10. Delivery phases

### Phase 0 — Product contracts and Cape Fear fixtures

- Define request, evidence, party profile, beach window, policy decision, and response schemas.
- Add supported Cape Fear locations and official-source mappings.
- Capture one reviewed normal snapshot and create synthetic hazard, stale-data, and conflict variants.
- Write the end-user, surf-school, and MCP demo scripts.

Exit gate: fixtures contain no personal information; expected decisions and evidence can be reviewed without a model call.

### Phase 1 — Local vertical slice

- Adapt the existing marine and weather agents.
- Add stubbed NWS and NC DEQ tools backed by frozen fixtures.
- Implement deterministic policy and structured final response.
- Preserve trace, cost, latency, and violation recording.

Exit gate: the same frozen input produces a schema-valid result, while all hazard, stale, and conflict fixtures fail closed.

### Phase 2 — Live official-source adapters

- Add NWS Wilmington surf-zone and alert retrieval.
- Add NOAA tide retrieval.
- Add NC DEQ advisory retrieval and location mapping.
- Record retrieval time, validity, raw-source reference, and parsing errors.

Exit gate: live adapters can be captured into frozen snapshots and replayed offline.

### Phase 3 — Human usability

- Add the Slack question and response flow.
- Implement reading-level-aware explanation without changing policy decisions.
- Add evidence links, data-age labels, and re-check guidance.
- Test with visitor, family beginner, experienced resident, and surf-school scenarios.

Exit gate: a non-expert can identify the recommendation, reason, official warning, and next step from one Slack response.

### Phase 4 — MCP product surface

- Implement the four read-only MCP tools.
- Add input validation, bounded date ranges, rate limits, and structured errors.
- Provide example integration for a trip-planning agent.
- Ensure MCP and Slack use the same application service and policy engine.

Exit gate: an external planning agent can add a surf window to an itinerary while preserving evidence and warnings.

### Phase 5 — AgentCore and evaluation

- Package the Strands runtime for AgentCore.
- Add deployment configuration only after explicit AWS approval.
- Run a scenario matrix across supported beaches and party profiles.
- Measure completion, schema validity, evidence coverage, veto correctness, latency, and cost.

Exit gate: the deployed happy path and fail-closed hazard path both complete with correlated traces.

### Phase 6 — Hackathon presentation

- Rewrite README around the community problem and three user groups.
- Add MIT license and repository About metadata.
- Add architecture diagram and setup instructions.
- Record a five-minute demo using frozen, reviewed evidence.
- Review history and assets, then make the repository public.

Exit gate: the public repository contains all source, assets, setup instructions, license, and reproducible demo fixtures.

## 11. Five-minute demo story

1. A visiting parent asks for a beginner-friendly Saturday morning option near Wilmington.
2. The swarm gathers marine, official hazard, tide, and water-quality evidence.
3. Cape Fear Surf Guide recommends one or two planning windows and explains them in plain language.
4. The response shows official sources, issue times, freshness, and what would invalidate the recommendation.
5. A trip-planning agent calls the MCP tool and adds the reviewed window to a draft itinerary.
6. A local surf school asks for candidate beginner lesson windows across three days.
7. A hazard fixture activates an official advisory; deterministic policy withdraws the recommendation even if other conditions look favorable.
8. The trace shows which agents and tools contributed and why the final state was fail-closed.

## 12. Acceptance criteria

- All responses validate against the declared schema.
- Every recommendation includes source URLs and freshness metadata.
- Official hazard and water-quality advisories cannot be overridden by a model.
- Missing, stale, ambiguous, or conflicting required evidence fails closed.
- Slack, MCP, and surf-school requests use the same policy engine.
- MCP tools are read-only and return bounded, structured results.
- Frozen snapshots reproduce both the normal and hazard demos without live network access.
- Repeated runs record route, tools, latency, token usage, errors, and policy outcomes.
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

`Cape Fear frozen snapshot -> Strands evidence agents -> deterministic policy -> schema-valid plain-language recommendation`

Build it with two mandatory cases:

1. a normal beginner planning window;
2. an official-advisory fixture that must return `not_recommended` or `official_advisory_present`.

Once that slice is reliable, expose the same service through Slack and MCP, then deploy it to AgentCore.
