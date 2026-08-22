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

Technology verification baseline: official MCP and Amazon Bedrock AgentCore documentation was checked on **2026-08-22**. The MCP target is Python SDK v2 with the date-versioned wire protocol **`2026-07-28`**. “MCP 2.0” in this plan means SDK v2, not a wire-protocol version named 2.0. Any later implementation plan that depends on current external technology must re-check official documentation, record the verification date and target version, and avoid claiming “latest” when that cannot be verified.

The 33-run baseline completed the intended path in 27 runs (81.8%), averaged 136.7 seconds and about 65,730 tokens per run, and failed six times without an AWS throttle or timeout. Four failures came from handoff payload growth. Cape Fear Surf Guide therefore moves the safety decision out of the model entirely: deterministic Python owns collection, normalization, window derivation, and vetoes, while a single Strands agent owns request interpretation, tool-driven retrieval, and the plain-language brief. The agent decides what to look up and how to explain it. It has no path to deciding whether the water is safe.

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

Expose a read-only MCP server for other agents using Python SDK v2 `MCPServer` and protocol `2026-07-28`.

Initial MVP tools:

- `find_surf_windows(date, party_profile, preferred_area?, time_range?)`
- `explain_surf_window(window_id, reading_level?)`

Later tools may add `get_beach_advisories` and `compare_beaches` only after the first two are measured end to end.

Every tool returns structured evidence and the deterministic decision state. MCP consumers must not receive a bare natural-language recommendation without its evidence and freshness metadata.

The deployment transport is stateless Streamable HTTP on one POST-only `/mcp` endpoint. Each request is independently reconstructible and returns JSON. The verified MCP Python SDK v2 `2026-07-28` stateless path does not use a GET event stream, resumable Server-Sent Events (SSE), initialization handshake, protocol session, connection identity, or process memory. `stdio`, which exchanges messages over a local process's standard input and output, remains a local compatibility and test transport only.

Each successful result includes a structured `resultType`, including `complete` or `input_required`. Sampling, elicitation, or roots use the protocol's multi-request tool result pattern (MRTR): the server returns `input_required`, and the client sends a later request with the required input. The initial `reading_level` remains an optional client-supplied default; Phase 2 does not add MRTR unless a measured use case requires it.

The HTTP boundary validates `MCP-Protocol-Version` against the required request metadata; validates `Mcp-Method` against the JSON-RPC `method`; validates `Mcp-Name` against `params.name` where applicable; rejects mismatches; validates the HTTP `Origin` header against an allowlist; and enforces authorization. Closing a request's SSE response is cancellation of that request. `window_id` and frozen snapshot inputs reconstruct records across independent requests, including requests handled by different processes.

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

The governing principle:

> The agent decides **what to look up** and **how to explain it**.
> The agent is structurally incapable of deciding **whether the water is safe**.

Everything the agent does is a task where being wrong is cheap and visible. Everything that determines a veto is deterministic Python that the agent can neither call selectively nor override.

### Layer 1 — `surf_planner_agent` (Strands, agentic)

The Strands agent owns request interpretation and evidence retrieval. It has three responsibilities.

**1. Multi-turn intake.** Real requests are underspecified. "This weekend with my kid" does not name a beach, a skill level, an age, a travel radius, or an accessibility need. The agent asks at most two clarifying questions, then commits to a resolved `PartyProfile` and candidate set. It never fills a missing safety-relevant field with a guess; an unresolved field stays `None` and the policy engine treats it conservatively.

**2. Retrieval orchestration through real tools.** Every deterministic fetcher is exposed as a Strands `@tool`. The agent decides which beaches, dates, hours, and sources to query and issues actual tool calls, looping when a source returns nothing useful. The tools return normalized facts only. They never return a verdict.

Registered tools for the MVP:

- `get_nws_hazards(zone, date_range)`
- `get_nws_surf_zone_forecast(zone, date_range)`
- `get_tide_predictions(station, date_range)`
- `get_water_quality_status(deq_site, date)`
- `get_marine_forecast(lat, lon, date_range)` (Open-Meteo, supplemental)
- `list_supported_beaches()`

Tool calls, arguments, latency, and failures are recorded per request. The existing `ToolCallRecorder` from the prior-art PoC is reused unchanged for this.

**3. Brief generation via structured output.** After the record is frozen, the agent produces the community brief as a Strands structured output conforming to a declared schema, not as free prose. Free prose cannot satisfy the 100% schema-validity gate.

Hard limits on the agent:

- It cannot create, alter, or round any measurement.
- It cannot change a decision state, remove a warning, or invent a source URL.
- It cannot skip the policy engine; the only path from evidence to response runs through `policy.decide`.
- If the model call fails, the deterministic record plus a template brief remain a complete, shippable answer.

### Layer 2 — Deterministic Python core

- Fetch NWS, NOAA, NC DEQ when available, and Open-Meteo concurrently.
- Parse and normalize source payloads into the evidence schema.
- Convert source times to UTC while retaining original timezone strings.
- Derive candidate windows from normalized hourly facts.
- Apply official-advisory vetoes and source-quality rules as pure functions.
- Apply separately labeled, unreviewed planning filters only after official classifications.
- Produce an immutable `RecommendationRecord` before any brief is generated.

Layer 2 contains no model call and no network call at decision time. Given the same evidence set and profile it returns the same decision every time, which is what makes the veto gates in section 12 measurable.

### Why this split is the product

The prior-art PoC put safety inside prompts and measured the result: 81.8% path completion, 18.2% failure, and a changing failure location under identical input at temperature zero. A recommendation engine for families near an ocean cannot inherit that variance. Moving the decision out of the model is not a performance optimization, it is the correctness argument.

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
        +------------------v-------------------+
        |   surf_planner_agent  (Strands)      |
        |   multi-turn intake                  |
        |   retrieval orchestration            |
        |   structured brief generation        |
        +---+------------------------------+---+
            |  @tool calls (recorded)      |  structured output
            v                              |
   parallel deterministic source fetchers   |
   NWS | NOAA | NC DEQ | Open-Meteo         |
            |                               |
   Python normalization + UTC conversion    |
            |                               |
   window derivation                        |
            |                               |
   pure deterministic policy engine         |   <-- agent cannot
            |                               |       call selectively
   immutable RecommendationRecord ----------+       or override
            |
   brief (structured output) or template fallback
            |
   response
```

The agent sits above the deterministic core and below the response. It reaches the record only by going through `policy.decide`, and it receives the record only after the record is frozen.

Recommended AWS path:

- Strands Agents on Amazon Bedrock AgentCore Runtime;
- a stateless Streamable HTTP POST `/mcp` boundary for MCP, with API Gateway and Lambda only where they preserve the verified protocol contract;
- DynamoDB for request, evidence, and recommendation records;
- S3 for reviewed frozen snapshots and evaluation artifacts;
- EventBridge Scheduler for requested re-checks;
- CloudWatch or AgentCore observability for traces, latency, and failures.

No AWS resource creation is authorized by this plan. Before deployment, document the personal AWS account, role, region, infrastructure entrypoint, budget, retention, rollback, and smoke test.

The MCP specification and current AgentCore examples are not assumed to be compatible. As checked on 2026-08-22, AgentCore documentation still demonstrates the older `FastMCP`, client initialization, and `Mcp-Session-Id` surface, while MCP `2026-07-28` uses `MCPServer`, has no initialization handshake, and has no protocol-level session. Phase 3 therefore begins with a compatibility spike. AgentCore remains an optional deployment target, never a correctness dependency.

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
- linear prompt-only handoffs into deterministic Python stages plus one agent that orchestrates `@tool` retrieval and emits a structured brief;
- `ToolCallRecorder` reused unchanged to record the new agent's tool calls;
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

Submission deadline: **September 14, 2026 at 5:00 PM PDT**. Track: **Good Neighbor Agents**. The plan optimizes first for a reproducible judged demo, then for score boosters the official rules name explicitly.

### Dated schedule

Video, README, and architecture diagram always slip, so they get fixed dates rather than "when the code is done".

| Window | Dates | Work |
| --- | --- | --- |
| Submission prerequisites | 08-22 to 08-24 | `LICENSE` (MIT) done, AWS Builder ID, track confirmation, blog post 1 |
| Phase 0 | 08-24 to 08-28 | locations, source verification, schema, thresholds, policy, fixtures, tests, timezone contract |
| Phase 1 | 08-28 to 09-02 | deterministic vertical slice plus `surf_planner_agent` intake, tool orchestration, structured brief |
| Phase 2 | 09-02 to 09-06 | live NWS, MCP SDK v2 stateless HTTP tools, CLI and static HTML |
| **Feature freeze** | **09-07** | no new capability after this date |
| Phase 3 | 09-07 to 09-09 | evaluation matrix, AgentCore MCP v2 compatibility gate, optional deployment and live demo link |
| Phase 4 | 09-09 to 09-12 | README, architecture diagram, video recording and upload, text description, blog posts 2 and 3 |
| Buffer | 09-12 to 09-14 | repository public, link audit, submit |

Fixed constraints:

- **09-07**: self-imposed feature freeze. Anything unfinished on this date is cut, not extended.
- The $50 AWS promotional credits are already received. They expire **10-31**, which is after the judging period ends on 10-08, so they cover both the build and the period when judges may exercise the live demo. Anything beyond $50 comes out of pocket, so AgentCore and Bedrock usage in Phase 3 is metered against that ceiling and the eval matrix is sized to fit inside it.
- The prior-art batch cost about $0.33 per run. At the agentic-path gate of $0.05 per request, a 30-run eval matrix costs roughly $1.50 in model spend, which leaves ample headroom for AgentCore runtime and the live demo.


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
- Wrap every fetcher as a Strands `@tool` and build `surf_planner_agent` with multi-turn intake, retrieval orchestration, and structured brief output.
- Keep the template brief as a fallback path, not as the primary path.
- Generate a CLI response and static HTML report from the same record.
- Preserve trace, tool-call, cost, latency, and violation recording.

Exit gate: 30 repeated offline runs are schema-valid; hazard decisions are identical across repeats regardless of what the agent asked or retrieved; the normal fixture has no false veto; no `unverifiable_slot` finding occurs; the recorded tool-call log shows the agent actually driving retrieval rather than receiving a prebuilt payload.

### Phase 2 — MCP and one live source

- Add NWS Wilmington surf-zone and alert retrieval.
- Pin the implementation contract to Python SDK v2 `MCPServer` and MCP protocol `2026-07-28`.
- Implement `find_surf_windows` and `explain_surf_window` as read-only tools with structured `resultType`, evidence, freshness, and deterministic decision fields.
- Serve one stateless Streamable HTTP POST endpoint at `/mcp`; retain `stdio` only for local compatibility tests.
- Reconstruct `explain_surf_window` from the versioned `window_id` and frozen inputs without a protocol session, connection affinity, or process memory.
- Validate protocol header against required request metadata, and method/tool-name headers against the corresponding JSON-RPC fields; reject missing, conflicting, or unsupported metadata deterministically.
- Add an `Origin` allowlist, an explicit authorization boundary, and reject GET/SSE stream attempts on the stateless deployment path.
- Test with the SDK v2 in-memory client and over Streamable HTTP, including two requests handled by fresh server processes.
- Keep NOAA, NC DEQ, and Open-Meteo replayable from reviewed snapshots; add live adapters only as time permits.
- Record retrieval time, validity, raw-source reference, and parsing errors.

Exit gate: an MCP `2026-07-28` client can obtain and explain a frozen recommendation with full evidence; no initialization or session dependency exists; two fresh processes reproduce the same record from `window_id`; invalid or mismatched metadata fails correctly; JSON POST behavior and GET/SSE rejection behave as specified; and a live NWS response can be captured and replayed offline.

### Phase 3 — Evaluation and AgentCore (09-07 to 09-09)

- Run the scenario matrix and record every gate in section 12.
- Implement reading-level-aware explanation without changing policy decisions.
- Add evidence links, data-age labels, and re-check guidance.
- Test with visitor, family beginner, experienced resident, and surf-school scenarios.
- Begin with an AgentCore compatibility spike that verifies POST `/mcp`, protocol `2026-07-28` metadata and headers, SDK v2 `MCPServer`, structured JSON results, GET/SSE rejection, and the absence of session affinity.
- Perform the compatibility spike or deployment only after explicit AWS approval and confirmation of the personal account, role, region, `personal` profile, inference-profile ID, budget, retention, rollback, and smoke test.
- Deploy the same service to AgentCore Runtime and publish a live demo link only if AgentCore passes the MCP v2 compatibility gate.
- If AgentCore cannot preserve the contract, cut AgentCore deployment without downgrading the protocol or adding session coupling. Keep the standalone Streamable HTTP demo and document the verified incompatibility.

The official rules state that an AgentCore deployment and a live demo link each strengthen the Technical Implementation score. Both remain optional score boosters. They are cut on 09-09 if the acceptance gates or AgentCore compatibility gate have not passed.

Exit gate: the quantitative acceptance gates pass and the recorded demo completes without live-network dependence. If AgentCore passed compatibility and was deployed, its smoke test covers one recommendation, one deterministic veto, two independent requests, and rejected GET/SSE. Otherwise, the plan records the incompatibility and the standalone MCP v2 demo remains complete.

### Phase 4 — Submission materials (09-09 to 09-12)

Every item below is required by the official rules, not optional polish.

| Required item | Detail |
| --- | --- |
| Public repository URL | github, gitlab, or bitbucket; contains all source, assets, and setup instructions |
| Open-source license | MIT or Apache, as a `LICENSE` file GitHub auto-detects so the badge appears in the About section. A line in the README does not satisfy this |
| README | Problem, three user groups, setup, architecture, prior-art disclosure |
| Architecture diagram | Required, not optional |
| Video | At most five minutes, public on YouTube or Vimeo, showing the project working end to end plus a pitch covering the problem, the audience, and why it matters |
| Text description | Features and functionality |
| AWS Builder ID | Submission field |
| Track | Good Neighbor Agents |
| Live demo link | Optional, but the rules state it improves the Technical Implementation score |

### Bonus score boosters

The rules award up to 0.6 additional points for publicly posted builder.aws content, 0.2 each, with "Agents for Humans" in the title. Base scores top out at 5.0, so this is worth roughly 12%. Three posts are planned, and post 1 needs no new code because `NOTES.md` already contains the measurement.

| # | Working title | Source material | Target date |
| --- | --- | --- | --- |
| 1 | Agents for Humans: I measured a five-agent Strands Swarm 33 times and it failed 18% of the time | `NOTES.md` | 08-24 |
| 2 | Agents for Humans: moving the safety decision out of the model | `docs/plan-review-decisions.md`, `surf/policy.py` | 09-10 |
| 3 | Agents for Humans: what the official surf forecast actually says | `docs/source-verification.md` | 09-12 |

### Deferred until everything above is complete

- Slack ingress.
- A trip-planning integration example beyond the MCP tools.
- Live NOAA and DEQ adapters, only after their source contracts are verified.

Exit gate: each deferred feature has its own measured smoke test and does not bypass the shared policy engine.

### Submission gate (09-12 to 09-14)

- Make the repository public.
- Verify the license badge renders in the About section.
- Verify every submitted link resolves for an anonymous visitor, including the video and the live demo.
- Disclose the copied `surf-school-swarm` baseline and identify the new work built during the submission period.
- Keep the working project or test build reachable through the end of the judging period on 10-08.

## 11. Five-minute demo story

1. A visiting parent types something vague into the CLI or demo page: "this weekend with my kid, we are both beginners."
2. `surf_planner_agent` asks one clarifying question, resolves the party profile, and decides which beaches, dates, and sources to query.
3. The recorded tool-call log shows the agent driving retrieval across NWS, NOAA, NC DEQ, and Open-Meteo.
4. Deterministic adapters normalize the frozen evidence, convert times to UTC, and derive candidate windows.
5. The policy engine produces the record. The agent has no path around it.
6. Cape Fear Surf Guide recommends one or two planning windows with official sources, issue times, freshness, and what would invalidate the recommendation.
7. A trip-planning agent calls the MCP tool and adds the reviewed window to a draft itinerary.
8. The demo makes a second independent MCP call with the returned `window_id`; a fresh server process reconstructs the same record without a session.
9. A hazard fixture activates an official advisory. Deterministic policy withdraws the recommendation even though the marine numbers still look favorable, and the same fixture produces the identical decision on every repeat.
10. The closing slide names protocol `2026-07-28`, shows the stateless/serverless request boundary, and contrasts the prior-art five-agent numbers with the measured gates from section 12.

## 12. Acceptance criteria

Latency and cost are measured per path, not end to end. A single combined budget would force the agentic layer back out of the product, which is the opposite of the intent. Splitting them also turns "the safety decision is fast and deterministic" into a measured claim rather than a slogan.

### Deterministic path (evidence set to frozen record, zero model calls)

| Gate | Target |
| --- | --- |
| p95 latency | at most 2 seconds across 30 runs |
| Model calls | zero |
| Official-hazard veto reproduction | 100%, zero variation across repeats |
| False-veto rate on the reviewed normal fixture | 0% |
| `unverifiable_slot` findings | zero |
| Same evidence and profile produce the same decision | byte-identical record, excluding `retrieved_at` |

### Agentic path (intake, tool orchestration, structured brief)

| Gate | Target |
| --- | --- |
| p95 latency | at most 30 seconds across 30 runs |
| Estimated model cost | at most $0.05 per request from recorded usage |
| Schema-valid brief rate | 100% across 30 repeated fixture runs |
| Recorded tool calls | present in every run, with arguments and outcomes |
| Model failure behavior | template brief and full record still returned |

For comparison, the prior-art five-agent Swarm measured 81.8% completion, 136.7 second mean latency, and about $0.33 per run. Those numbers are the baseline this architecture is judged against.

### MCP v2 path (frozen record, network disabled in CI)

| Gate | Target |
| --- | --- |
| Protocol version | exact `2026-07-28` match |
| Structured results | 100% valid, with `resultType` and full evidence |
| Stateless replay | 100% identical record across fresh server processes |
| Header/body mismatch rejection | 100% across the negative test matrix |
| Unknown `window_id` | deterministic structured error |
| Session or process-memory dependency | none |
| Frozen MCP demo | passes in CI with network disabled |
| Deterministic record retrieval | zero model calls |

### Correctness and scope

- Every recommendation includes source URLs, original timezone, and freshness metadata.
- Official hazard and active water-quality advisories cannot be overridden by a model.
- Missing, stale, ambiguous, or conflicting required NWS hazard evidence fails closed.
- Every implemented adapter uses the same policy engine.
- MCP tools are read-only, bounded, and return structured results.
- Frozen snapshots reproduce both the normal and hazard demos without live network access.
- Normal and hazard demos complete in CI with network access disabled.
- Repeated runs record tools, latency, token usage, errors, and policy outcomes.
- No result claims that surfing is guaranteed safe.
- No booking, payment, cancellation, rescue, or emergency action is available.
- AgentCore is reported as a verified deployment only if the MCP v2 compatibility gate passes; otherwise the verified incompatibility is documented and the standalone MCP path remains the release target.

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

`Cape Fear frozen snapshot -> deterministic normalization -> deterministic policy -> immutable record -> structured brief or template fallback`

Build it with two mandatory cases:

1. a normal beginner planning window;
2. an official-advisory fixture that must return `not_recommended` or `official_advisory_present`.

Only once both cases are reproducible does `surf_planner_agent` get wired in on top. Building the agent first would make it impossible to tell whether a wrong answer came from retrieval or from policy, which is exactly the ambiguity the prior-art PoC could not resolve.

After the agent layer is measured, expose the same service through the two MCP tools. Phase 3 tests whether AgentCore can host the verified MCP v2 contract; it does not assume deployment compatibility merely because the rules score AgentCore. Slack lands only after every required submission item is done.

## 15. Phase 0 source and identity contracts

### Location and tide mapping

Each beach record must include a verified NOAA station or an explicit fallback mapping. When a nearest station is used, the evidence records the station name, distance or rationale, and the fact that it is a proxy. Wrightsville Beach station `8658163` is a candidate verified by the review; it must still be captured in the source-verification note before becoming configuration. Never guess mappings for Carolina Beach, Kure Beach, or Fort Fisher.

### Stable window identity

The MVP does not require DynamoDB. Derive `window_id` from a versioned hash of request parameters, snapshot ID, beach ID, and UTC interval. `explain_surf_window` reproduces the record from frozen inputs on every request, even when a different process handles it. Persistence can be added later without changing the public identifier contract, but protocol sessions, connection affinity, and process memory cannot become hidden requirements.

### Local rules

Phase 0 must check official municipal or county sources for seasonal surfing zones, pier-distance rules, closures, and other location restrictions. Unverified community knowledge never becomes a veto.

### Prior-art disclosure

The official rules require a new project during the August 10 through September 14 submission period and disclosure of pre-existing work. All current repository commits are dated inside the submission period, but the README must still state that the repository began as a copied `surf-school-swarm` research baseline and clearly list the Cape Fear-specific product work added for the submission.
