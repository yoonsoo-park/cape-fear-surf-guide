# Five-minute demo script

This script is a recording plan, not a promise that an ocean is safe. Never
display the API key, a private AWS identifier, or a terminal environment.

Devpost requires the pitch to cover three things explicitly: the problem, who it
is for, and why it matters. Sections 1 and 7 carry those; do not cut them for
time. Track: Good Neighbor Agents.

## Time budget

| Time | Seconds | Scene |
| --- | --- | --- |
| 0:00–0:45 | 45 | Pitch: problem, audience, stakes |
| 0:45–1:15 | 30 | Architecture: where the agent is allowed to act |
| 1:15–2:45 | 90 | Live end-to-end through an MCP client |
| 2:45–3:30 | 45 | The veto the model cannot remove |
| 3:30–4:10 | 40 | What it does when the evidence is bad |
| 4:10–4:40 | 30 | Measured gates, not claims |
| 4:40–5:00 | 20 | Close on the boundary |

Live product time is 90 seconds against 85 seconds of fixtures. That ratio is
deliberate: the Design criterion rewards a coherent product experience over a
proof of concept, and the Technological Implementation criterion asks first how
thoroughly the project uses Strands Agents.

## 1. Pitch — 0:00 to 0:45

Say all three of these out loud. They are graded.

**The problem.** Deciding whether to take people into the water on the Cape Fear
coast means reconciling four separate feeds: an NWS zone forecast, NWS active
alerts, NOAA tide predictions, and marine wind and swell. They disagree, they go
stale at different rates, and none of them answers the question a person is
actually asking.

**Who it is for.** Not one power user. Surf schools running beginner lessons,
families planning a morning, and the volunteers and small local organizations
along Wrightsville Beach who get asked "is it okay today?" and have to answer
for other people.

**Why it matters.** The wrong answer here is not an inconvenience. The failure
mode that matters is a fluent, confident explanation that quietly talks past an
active hazard advisory. So this agent is built so that it structurally cannot do
that.

On screen: the README safety boundary.

## 2. Architecture — 0:45 to 1:15

Show `docs/assets/architecture.svg` and name the split in one sentence each.

- The Strands agent handles intake, calls fact-only retrieval tools, and emits a
  schema-validated `SurfBrief`.
- Deterministic Python normalizes evidence, checks freshness and conflicts,
  applies official-advisory vetoes, and writes an immutable
  `RecommendationRecord`.
- Point at the immutable-record arrow: the agent writes the explanation, never
  the decision.

## 3. Live end-to-end — 1:15 to 2:45

This is the longest scene. Show the product working before explaining why it is
trustworthy.

In the MCP client, call `find_surf_windows` for a Wrightsville Beach morning
with a beginner party profile. In the returned result, point at, in this order:

| Field | Verified value on 2026-09-13 | What to say |
| --- | --- | --- |
| `retrieval.mode` | `live` | nothing frozen; four public sources were queried during this call |
| `retrieval.sources` | 5 entries | each with a URL, a retrieval time, and a freshness label |
| `brief_source` | `agent` | the Strands agent produced this prose, running on AgentCore |
| `decision.state` | `recommended_window` | deterministic Python decided this, not the model |
| `safety_limit` | present | the result says out loud that it is a planning aid |

Then open a second conversation and call `explain_surf_window` with the returned
`window_id`. Show that the returned `window_id` and decision state match the
first call exactly.

Say why that matters: the replay reads a stored record, not the model's memory
and not a fresh query. The explanation is reproducible, so it can be audited
after the fact.

`recommended_window` is not required for the demo to succeed. If the live
evidence produces a caution or a veto on the day you record, narrate that
instead. Never re-run to fish for a friendlier answer, and never edit the prompt
to force one.

## 4. The veto the model cannot remove — 2:45 to 3:30

Run the official-hazard fixture:

```bash
uv run python main.py --fixture hazard
```

Show `official_advisory_present` and the deterministic veto state. Say the
sentence that carries the whole project: the agent is still free to write
whatever explanation it wants, and the recommendation is still no, because the
veto is applied in Python before the model is asked for anything.

## 5. When the evidence is bad — 3:30 to 4:10

Run the stale and conflict fixtures:

```bash
uv run python main.py --fixture stale
uv run python main.py --fixture conflict
```

Show that `stale_data` and `conflicting_evidence` are distinct named states, not
a generic error. Add the live counterpart in one line: if a required public
source fails during a real call, the service returns `insufficient_data` and
never substitutes a fixture.

## 6. Measured gates — 4:10 to 4:40

Open the committed Phase 3 summary. Do not tour the JSON; read the gates.

- 30-case matrix across four fixtures and four party profiles
- deterministic path: zero model calls, byte-identical outputs, p95 under 2s
- agentic path: p95 6,496.835 ms against a 30s budget, max request cost
  $0.00086886 against a $0.05 cap
- 100% structured-schema, tool-call, and official-veto success; zero false
  vetoes on normal; zero immutable-field violations

Say that token counts are provider counters used as evidence, not a billing
invoice.

## 7. Close — 4:40 to 5:00

Restate the boundary and land the stakes again: posted flags, lifeguards, and
local officials take priority over this tool, always. It proposes a window and
shows its evidence. It never says the water is safe.

On screen: the README safety warning and the source links.

## Recording checklist

- [ ] Video is public and no longer than five minutes.
- [ ] The pitch says the problem, who it is for, and why it matters, in words.
- [ ] Terminal shows no credentials, account cookies, private paths, or secret
      environment variables.
- [ ] The MCP client window shows no API key and no `x-api-key` header.
- [ ] The live scene shows `retrieval.mode: live` and `brief_source: agent`.
- [ ] The `window_id` replay visibly matches the first call.
- [ ] The hazard, stale, and conflict states are visibly distinct.
- [ ] The recording says an official advisory overrides the explanation.
- [ ] The recording never claims that surfing is safe.

## Before you hit record

- The judge exposure `judge-20260913-a` is enabled until
  `2026-09-16T12:25:20Z`. Confirm it is still enabled and has request budget
  before recording; a dead exposure turns the live scene into a 403 on camera.
- Do one dry run of the live call. If it returns a caution or veto, rewrite the
  section 3 narration to match before recording, rather than discovering it mid
  take.
