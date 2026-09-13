# Five-minute demo script

This is a recording plan, not a promise that an ocean is safe. Never display
an API key, an `x-api-key` header, terminal environment, private AWS identifier,
company information, or an unrelated application window.

Devpost requires the pitch to state the problem, who the product is for, and
why it matters. Sections 1 and 7 carry those points; do not cut them for time.
Track: **Good Neighbor Agents**.

## Time budget

| Time | Seconds | Scene |
| --- | ---: | --- |
| 0:00-0:45 | 45 | Pitch: problem, audience, stakes |
| 0:45-1:15 | 30 | Architecture: where the agent may act |
| 1:15-2:45 | 90 | Live `find` and independent `explain` through Claude Desktop |
| 2:45-3:30 | 45 | The veto the model cannot remove |
| 3:30-4:10 | 40 | What happens when evidence is bad |
| 4:10-4:40 | 30 | Measured gates, not claims |
| 4:40-5:00 | 20 | Close on the boundary |

The live product receives 90 seconds; the fixture evidence receives 85. Show
the working product first, then prove why its safety boundary is credible.

## Before recording: prepare the screens

1. Confirm the approved judge exposure is enabled, unexpired, and has request
   budget. The preparation exposure was `judge-20260913-a`, expiring at
   `2026-09-16T12:25:20Z`; re-check rather than assuming this is current.
2. Confirm Claude Desktop shows `cape_fear_surf_guide` with exactly
   `find_surf_windows` and `explain_surf_window`.
3. Select a `DEMO_DATE` from today through six days ahead in the
   `America/New_York` calendar. The prompts below use `2026-09-14`; replace it
   everywhere if recording on a different day.
4. Perform exactly one dry run of `find` followed by `explain`. Record the
   returned state and adjust the narration to match. Do not rerun to search for
   a friendlier result.
5. Prepare two clean Claude conversations: A for `find`, B for `explain`.
6. Open the README boundary, `docs/assets/architecture.svg`, the committed
   Phase 3 `summary.json`, and a clean terminal at the repository root.
7. Hide usernames, company hostnames, private paths, notifications, unrelated
   browser tabs, and unrelated MCP servers.
8. Collapse raw request details if the client could show headers. Expand only
   the sanitized result fields named below.

If the dry run returns HTTP 403, 429, a missing tool, or a connection error,
stop before recording. Do not remove authentication, weaken WAF, or retry in a
loop. Follow the company-laptop runbook and contact the exposure owner.

## 1. Pitch — 0:00 to 0:45

### On screen

Show the README safety boundary.

### Say

> Deciding whether to take people into the water on the Cape Fear coast means
> reconciling a marine forecast, an NWS zone forecast, active alerts, tide
> predictions, and water-quality status. They go stale at different rates and
> none of them answers the question a person is actually asking.
>
> This is for surf schools running beginner lessons, families planning a
> morning, and local volunteers who answer for other people. The dangerous
> language-model failure here is not being unhelpful. It is being fluent while
> quietly talking past an active hazard advisory. So this agent is built to be
> structurally unable to override one.

## 2. Architecture — 0:45 to 1:15

### On screen

Show `docs/assets/architecture.svg`. Point to the agent/tool loop,
deterministic policy, and immutable record.

### Say

> The Strands agent handles intake, chooses fact-only retrieval tools, and
> emits a schema-validated SurfBrief. Deterministic Python normalizes evidence,
> checks freshness and conflicts, and applies official-advisory vetoes. The
> agent writes the explanation, never the decision. The live MCP request enters
> through API Gateway and Lambda and executes the agent on Amazon Bedrock
> AgentCore Runtime.

## 3. Live end-to-end — 1:15 to 2:45

### 3A. `find_surf_windows` — about 55 seconds

Use Claude conversation A. Paste this prompt, changing only the date if needed:

```text
Cape Fear Surf Guide MCP만 사용해 2026-09-14 오전 Wrightsville Beach의
초보자용 서핑 가능 창을 찾아줘.

반드시 find_surf_windows를 실제 호출하고 아래 입력을 사용해:
- date: 2026-09-14
- preferred_area: Wrightsville Beach
- time_range: morning
- party_profile: {"skill_level":"beginner","ages":[],"accessibility_needs":[]}

웹 검색이나 다른 도구는 사용하지 마. 호출할 수 없다면 일반 지식으로
대답하지 말고 오류를 그대로 알려줘. 결과에서는 window_id,
decision.state, retrieval.mode, brief_source, 시작/종료 시각만 짧게 정리해줘.
```

Approve only `find_surf_windows`. Point at these fields in order:

| Field | Required evidence | What to say |
| --- | --- | --- |
| Tool name | `find_surf_windows` | "This is an MCP call, not a prose-only answer." |
| `resultType` | `complete` | "The structured contract completed." |
| `retrieval.mode` | `live` | "It queried current public evidence and did not substitute a fixture." |
| `retrieval.sources` | URL, retrieval time, freshness on each entry | "Each input is attributable and freshness-labelled." |
| `brief_source` | `agent` | "The bounded Strands agent produced the brief on AgentCore." |
| `decision.state` | any valid deterministic state | "Python produced this state; the model cannot edit it." |
| `safety_limit` | present | "The result explicitly remains a planning aid." |
| `window_id` | non-empty random ID | "This identifies the stored record used next." |

Do not say "four sources" while the screen shows five evidence entries. Say
"current public evidence" or the exact visible count. Do not describe
supplemental sources as if they have the same authority as official sources.

Copy only `window_id`, not the full payload. A `caution`, `do_not_recommend`,
or `insufficient_data` result is valid product behavior. Never rerun to obtain
`recommended_window`.

### 3B. Independent `explain_surf_window` — about 35 seconds

Switch to clean conversation B. Replace `WINDOW_ID` with conversation A's ID:

```text
Cape Fear Surf Guide MCP만 사용해 아래 저장된 결과를 다시 설명해줘.

반드시 explain_surf_window를 실제 호출해:
- window_id: WINDOW_ID
- reading_level: beginner

find_surf_windows를 다시 호출하거나 웹 검색을 하지 마. 저장된 결과를 찾을
수 없다면 일반 지식으로 재구성하지 말고 오류를 그대로 알려줘. 결과에서는
window_id, decision.state, retrieval.mode가 첫 호출과 같은지만 짧게 정리해줘.
```

Approve only `explain_surf_window`. Show the tool name, `resultType: complete`,
the exact same `window_id`, and the same decision and evidence.

### Say

> This second conversation does not know the first conversation's history. It
> reads the stored record by ID instead of asking the model to remember or
> refreshing the sources. The decision is reproducible and auditable.

The record lasts 24 hours. An unknown or expired ID is a valid fail-closed
error, not a successful replay.

## 4. The veto the model cannot remove — 2:45 to 3:30

Run the reviewed fixture:

```bash
uv run python main.py --fixture hazard
```

Point to `official_advisory_present` and the veto state. Say:

> The agent is still free to explain the result, but the recommendation is
> still no. The veto is applied in Python before model prose is accepted, and
> the model has no path that can remove it.

Do not manufacture a live hazard. The fixture is intentional reviewed evidence.

## 5. When evidence is bad — 3:30 to 4:10

Run:

```bash
uv run python main.py --fixture stale
uv run python main.py --fixture conflict
```

Point to `stale_data` and `conflicting_evidence`. Say:

> These are distinct states, not one generic error. If a required live source
> fails, the service returns insufficient data. It never silently substitutes
> a friendly fixture.

## 6. Measured gates — 4:10 to 4:40

Open the committed Phase 3 summary and show only:

- 30 cases across normal, hazard, stale, and conflict scenarios;
- deterministic path: zero model calls, byte-identical output, p95 below 2s;
- agentic p95 `6,496.835 ms` against 30s;
- max estimated request cost `$0.00086886` against `$0.05`;
- 100% schema, tool-call, and official-veto success;
- zero normal false vetoes and zero immutable-field violations.

Say:

> These are measured acceptance gates, not architecture claims. Provider token
> counters are evidence, not an AWS billing invoice.

## 7. Close — 4:40 to 5:00

Return to the README warning and source links. Say:

> The operator is often not the person entering the water, and one answer can
> travel to a group. Cape Fear Surf Guide proposes a window and shows its
> evidence, but posted flags, lifeguards, and local officials always take
> priority. It never says the water is safe.

## Live-scene acceptance record

Fill this out after the dry run. It contains no secret:

```text
Recording date and timezone:
Claude Desktop version:
DEMO_DATE:
MCP server: cape_fear_surf_guide
Discovered tools: find_surf_windows, explain_surf_window
find resultType:
find decision.state:
find retrieval.mode:
find brief_source:
window_id:
explain resultType:
explain window_id matches: yes/no
explain decision.state matches: yes/no
```

The scene is ready only when discovery and both calls pass. "Connected" alone
is not execution evidence.

## Recording checklist

- [ ] Video is public and no longer than five minutes.
- [ ] Opening states the problem, audience, and why it matters.
- [ ] Claude shows exactly the expected MCP tools.
- [ ] Live result shows `retrieval.mode: live` and `brief_source: agent`.
- [ ] Replay shows the same `window_id` and decision state.
- [ ] Hazard, stale, and conflict states are visibly distinct.
- [ ] Narration says official advisories override model explanation.
- [ ] No API key, header, credential, AWS identifier, company detail,
      username, hostname, private path, notification, or unrelated MCP appears.
- [ ] No narration claims that ocean activity is safe.
- [ ] No repeated live calls fish for a nicer answer.

## Failure plan during recording

- If Claude proposes web search, cancel it and restart with the exact prompt.
- If `invalid_party_profile` appears, restore the exact `skill_level` object;
  do not improvise a field such as `experience`.
- If HTTP 403 or 429 appears, stop. Have the owner check key status, expiry,
  request count, and WAF metrics before one new attempt.
- Keep a legitimate veto or `insufficient_data`; explain that fail-closed
  behavior is the product working.
- For an unknown replay ID, compare it character for character before
  considering another budget-consuming `find` call.

Never switch to a cached response and describe it as live.
