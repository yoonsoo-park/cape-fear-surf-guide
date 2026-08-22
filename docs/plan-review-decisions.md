# Productization Plan Review Decisions

Reviewed: 2026-08-22

Technology verification baseline: official MCP and Amazon Bedrock AgentCore documentation checked 2026-08-22; target Python SDK v2 and MCP protocol `2026-07-28`.

## Outcome

The review is accepted in substance. The production architecture changes from a five-agent handoff Swarm to a deterministic Python core followed by one explanation-focused Strands agent.

This is not a cosmetic optimization. The repository's 33-run baseline showed that the intended five-agent path completed in 27 runs (81.8%), averaged 136.7 seconds and 65,730 tokens per run, and failed six times without an AWS throttle or timeout. Four failures were caused by handoff payload growth. Adding more evidence to that handoff chain would amplify the measured failure mode.

## Decisions

### Accepted

- Fetch, parse, normalize, convert time, derive windows, and apply vetoes in deterministic Python.
- Use one Strands agent to explain an immutable decision record.
- Keep a template explanation when the model call fails.
- Make CLI plus static HTML the required judged-demo interface.
- Start MCP with `find_surf_windows` and `explain_surf_window`.
- Implement MCP with SDK v2 `MCPServer`, stateless Streamable HTTP POST `/mcp`, structured `resultType`, and explicit request metadata validation.
- Use `window_id` and frozen inputs to reconstruct records across independent processes; never depend on a protocol session, connection affinity, or process memory.
- Keep Slack as an optional score booster.
- Treat only an active NC DEQ advisory as a veto; absence, seasonal gaps, and unavailable feeds are labeled but do not automatically veto.
- Put official NWS classifications above experimental planning filters.
- Store time internally in UTC, display in `America/New_York`, and preserve original source offsets.
- Derive `window_id` from versioned request and snapshot inputs instead of requiring DynamoDB for the MVP.
- Add numeric acceptance gates for schema validity, veto reproduction, false vetoes, unverifiable slots, latency, cost, and offline replay.
- Disclose the copied `surf-school-swarm` baseline and identify the new Cape Fear work.

### Clarified

- The hackathon requires Strands Agents, not a multi-agent architecture.
- The repository must be public for submission, not necessarily throughout development.
- Current repository commits are dated within the official submission period, but copied baseline work is still disclosed because the rules require disclosure of pre-existing code or work.
- AgentCore strengthens Technical Implementation but is optional and must pass an MCP v2 compatibility gate before deployment is described as supported.

### Deferred until verified

- NC DEQ machine-readable feed contract.
- NOAA station or documented proxy mapping for Carolina Beach, Kure Beach, and Fort Fisher.
- Municipal surfing-zone, pier-distance, seasonal, and closure rules.
- Any planning threshold intended for beginner, child, family, or accessibility profiles.

Deferred values remain `None`, `unverified`, or `review_status: unreviewed`; they are never guessed.

## MCP v2 and AgentCore compatibility decision

The MCP target is the Python SDK v2 stable surface and date-versioned wire protocol `2026-07-28`. “MCP 2.0” refers to the SDK major version, not to a wire protocol numbered 2.0.

The protocol removes the initialization handshake, protocol-level sessions, and independent server-initiated requests. Streamable HTTP uses one POST-only endpoint. The verified Python SDK v2 `2026-07-28` stateless server path returns JSON and does not use GET or resumable Server-Sent Events (SSE). Sampling, elicitation, and roots use an `input_required` result followed by a later client request, called the multi-request tool result pattern (MRTR).

Phase 2 therefore uses `MCPServer`, validates `MCP-Protocol-Version` against required request metadata, `Mcp-Method` against JSON-RPC `method`, and `Mcp-Name` against `params.name`; it also validates `Origin`, enforces authorization, and rejects GET/SSE on the stateless deployment path. `stdio` is retained only for local compatibility testing.

Amazon Bedrock AgentCore documentation checked on 2026-08-22 still shows the older `FastMCP`, client initialization, and `Mcp-Session-Id` surface. This is a verified documentation mismatch, not proof that the runtime is incompatible. Phase 3 must test whether AgentCore passes the SDK v2 and `2026-07-28` contract unchanged. If it does not, the project keeps standalone stateless Streamable HTTP and cuts AgentCore deployment rather than downgrading the protocol or introducing session coupling.

Official sources:

- https://modelcontextprotocol.io/specification/2026-07-28
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- https://py.sdk.modelcontextprotocol.io/whats-new/
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html

Future plans that depend on current external technology must check official web documentation first, record the verification date and target version, and avoid claiming “latest” when current status cannot be verified.

## Verified official facts

### Hackathon

- Submission period: 2026-08-10 09:00 PDT through 2026-09-14 17:00 PDT.
- A new AI agent built with Strands Agents is required.
- Pre-existing code or work may be incorporated only with disclosure.
- Submission requires a public repository with an MIT or Apache license, README, architecture diagram, and a public video of at most five minutes.
- AgentCore deployment is optional but can strengthen the Technical Implementation score.

Source: https://agentsforhumans.devpost.com/rules

### NWS API

- `api.weather.gov` requires a `User-Agent` identifying the application.
- Phase 0 must use a non-secret project identifier and contact route in that header and test the exact endpoints used.

Source: https://www.weather.gov/documentation/services-web-api

### NOAA Wrightsville Beach station

- NOAA identifies station `8658163` as Wrightsville Beach, NC.
- This does not prove it is an appropriate proxy for the other three supported beaches.

Source: https://tidesandcurrents.noaa.gov/stationhome.html?id=8658163

### NC DEQ

- NC DEQ publishes recreational-water-quality and swimming-advisory information.
- A stable machine-readable feed contract has not yet been verified for this project.
- Seasonal or unavailable coverage must not be interpreted as proof of safe water or as an automatic veto.

Source: https://www.deq.nc.gov/about/divisions/marine-fisheries/shellfish-sanitation-and-recreational-water-quality/recreational-water-quality

## Phase 0 file order

1. `surf/locations.py`
2. `docs/source-verification.md`
3. `surf/schema.py`
4. `config/thresholds.yaml`
5. `surf/policy.py`
6. `fixtures/normal.json`, `fixtures/hazard.json`, `fixtures/stale.json`, `fixtures/conflict.json`
7. `tests/test_policy.py`
8. `docs/timezone-contract.md`

Location and source verification come first because their outcome can change the evidence schema and veto policy.
