# 5분 데모 녹화 대본

이 문서는 녹화 진행자를 위한 한국어 안내서다. 화면에 입력하는 프롬프트와
실제로 말하는 문장은 심사위원을 위해 영어로 작성했다. 영어 내레이션은
기술적으로 정확하면서도 자연스러운 발표 문장으로 구성한다.

이 서비스는 바다가 안전하다고 보장하지 않는다. 녹화 화면에 API 키,
`x-api-key` 헤더, 환경변수, 개인 AWS 식별자, 회사 정보, 알림 또는
관련 없는 앱을 노출하지 않는다.

참가 트랙: **Good Neighbor Agents**

## 전체 시간표

| 시간 | 장면 |
| --- | --- |
| 0:00-0:45 | 문제, 사용자, 중요한 이유 |
| 0:45-1:15 | 실제 실행 구조 |
| 1:15-2:45 | Claude Desktop에서 live `find`와 독립 `explain` |
| 2:45-3:30 | 모델이 없앨 수 없는 veto |
| 3:30-4:10 | 데이터가 나쁠 때의 동작 |
| 4:10-4:40 | 측정 결과 |
| 4:40-5:00 | 안전 경계로 마무리 |

## 반드시 이해하고 말해야 할 실행 구조

녹화에서 “Strands가 모든 것을 결정한다”고 말하면 안 된다. 실제 순서는
다음과 같다.

1. **Claude Desktop**이 사용자의 자연어를 읽고 공개 MCP 도구
   `find_surf_windows`를 선택한다.
2. API Gateway와 Lambda가 인증, WAF, 요청 예산을 적용한다.
3. Lambda가 각 `find` 요청마다 새로운 AgentCore Runtime session을
   호출한다.
4. AgentCore 안의 **결정론적 Python**이 입력을 검증하고, 라이브 소스를
   가져오고, 데이터를 정규화하고, `policy.decide`로 판정을 확정한다.
5. 판정이 확정된 뒤 **Strands retrieval pass**가 fact-only tools를 통해
   정규화된 증거를 읽는다. 이 도구들은 판정을 만들거나 바꾸지 않는다.
6. **Strands explanation pass**가 확정된 record를 짧은 `SurfBrief`로
   묶는다.
7. 코드가 모델 출력의 `window_id`, 판정, URL, 경고를 다시 검사한다.
   하나라도 바뀌면 모델 설명을 버리고 template brief를 사용한다.
8. Lambda가 결과를 반환하고, `window_id`를 키로 DynamoDB에 24시간
   저장한다.

현재 구현은 AgentCore 안에서 Strands `Agent` 객체를 retrieval과
explanation에 각각 하나씩 사용한다. “one agent”라고 강조하지 말고
**a bounded Strands workflow**라고 표현한다.

### `window_id`가 의미하는 것

`window_id`는 AgentCore session ID가 아니다.

- AgentCore의 `runtimeSessionId`는 각 `find` 호출마다 새로 생성되는
  내부 실행 식별자이며 사용자에게 반환되지 않는다.
- `window_id`는 확정된 `RecommendationRecord`를 DynamoDB에서 찾는
  임의의 조회 키다.
- `explain_surf_window`는 이 키로 저장된 결과를 그대로 반환한다.
- Strands의 이전 대화를 이어가거나 모델 memory를 복구하지 않는다.
- 따라서 이것은 **conversation continuation**이 아니라
  **stateless record replay**다.

## 녹화 전 준비

1. judge exposure가 활성 상태이고, 만료되지 않았고, 요청 예산이 남아
   있는지 확인한다. 준비 시 사용한 exposure는
   `judge-20260913-a`, 만료 시각은 `2026-09-16T12:25:20Z`였다.
   녹화 당일에는 이 값을 다시 확인한다.
2. Claude Desktop에 `cape_fear_surf_guide`가 연결되어 있고 아래 도구
   두 개만 보이는지 확인한다.
   - `find_surf_windows`
   - `explain_surf_window`
3. 미국 동부 날짜 기준 오늘부터 6일 안의 `DEMO_DATE`를 정한다.
   아래 프롬프트는 `2026-09-14`를 사용한다. 다른 날이면 두 군데의
   날짜를 모두 바꾼다.
4. 녹화 전에 `find` 1회와 `explain` 1회만 드라이런한다.
   더 좋은 판정을 얻기 위해 반복 호출하지 않는다.
5. Claude 대화 두 개를 미리 연다.
   - 대화 A: `find_surf_windows`
   - 대화 B: `explain_surf_window`
6. 다음 화면을 미리 연다.
   - README의 safety boundary
   - `docs/assets/architecture.svg`
   - Phase 3 `summary.json`
   - 저장소 루트의 깨끗한 terminal
7. 사용자명, 회사 hostname, 개인 경로, 알림, 다른 브라우저 탭과 다른 MCP
   server를 숨긴다.
8. raw request나 header가 보일 수 있는 패널은 접는다. 아래에서 지정한
   결과 필드만 펼친다.

드라이런에서 HTTP 403, 429, 연결 오류 또는 도구 누락이 나오면 녹화를
시작하지 않는다. 인증이나 WAF를 약하게 만들지 말고 exposure owner에게
확인을 요청한다.

## 1. 문제와 사용자 — 0:00-0:45

### 화면

README의 safety boundary를 보여준다.

### 영어로 말하기

> Deciding whether to take people into the water on the Cape Fear coast means
> reconciling marine conditions, weather alerts, tide predictions, and
> water-quality evidence. These sources update at different times, sometimes
> disagree, and none of them directly answers the question a person is asking.
>
> Cape Fear Surf Guide is for surf schools running beginner lessons, families
> planning a morning, and local organizations that answer for other people.
> The dangerous failure mode for a language model here is not being unhelpful.
> It is being fluent while quietly talking past an active hazard advisory. So
> the system is designed so that an official warning always wins.

## 2. 실행 구조 — 0:45-1:15

### 화면

`docs/assets/architecture.svg`에서 MCP, AgentCore, Python policy,
immutable record 순서로 가리킨다.

### 영어로 말하기

> Claude turns the user's request into a structured MCP tool call. API Gateway
> and Lambda enforce the public access controls, then invoke a bounded Strands
> workflow on AgentCore. Inside that runtime, deterministic Python retrieves
> and normalizes the evidence and finalizes the policy decision first. Strands
> can then explain that fixed record, but it cannot change the decision, remove
> a warning, or invent a source.

“Strands decides which sources are safe” 또는 “the same agent session continues”
라고 말하지 않는다.

## 3. Claude Desktop live demo — 1:15-2:45

### 3A. `find_surf_windows` — 약 55초

Claude 대화 A에 아래 **영어 프롬프트**를 붙여 넣는다. 필요하면 날짜만
바꾼다.

```text
Use only the Cape Fear Surf Guide MCP to find a beginner-friendly morning
surf window at Wrightsville Beach on 2026-09-14.

You must call find_surf_windows with exactly these inputs:
- date: 2026-09-14
- preferred_area: Wrightsville Beach
- time_range: morning
- party_profile: {"skill_level":"beginner","ages":[],"accessibility_needs":[]}

Do not use web search or any other tool. If the MCP call fails, show the error
instead of answering from general knowledge. After the call, briefly show only
the window_id, decision.state, retrieval.mode, brief_source, start time, and
end time.
```

Claude가 허가를 요청하면 `find_surf_windows`만 승인한다.

다음 필드를 순서대로 가리킨다.

| 필드 | 확인값 | 화면을 가리키며 말할 영어 문장 |
| --- | --- | --- |
| tool name | `find_surf_windows` | “This is the live MCP tool call, not a prose-only answer.” |
| `resultType` | `complete` | “The request completed through the structured contract.” |
| `retrieval.mode` | `live` | “The service used its live evidence path rather than substituting a fixture.” |
| `retrieval.sources` | 각 항목에 URL, 시각, freshness | “Every input remains attributable and carries its own freshness state.” |
| `brief_source` | `agent` 또는 정직하게 `template` | “The bounded Strands workflow produced this brief.” 또는 “The model output was rejected, so the safe template was used.” |
| `decision.state` | 유효한 결정 상태 | “This state was finalized by deterministic Python, not by the model.” |
| `safety_limit` | 존재 | “The response explicitly remains a planning aid, not a safety guarantee.” |
| `window_id` | 비어 있지 않은 ID | “This ID points to the immutable record stored for independent replay.” |

화면에 evidence가 5개라면 “four sources”라고 말하지 않는다.
“current public data” 또는 실제로 보이는 개수만 말한다.

`window_id`만 복사한다. 전체 payload는 복사하지 않는다.
`recommended_window`가 아니어도 성공이다. `official_advisory_present`,
`stale_data`, `conflicting_evidence`, `not_recommended`, 또는
`insufficient_data`가 나오면 그대로 설명한다.

### 3B. `explain_surf_window` — 약 35초

새 Claude 대화 B로 이동한다. `WINDOW_ID`만 실제 값으로 교체하고 아래
**영어 프롬프트**를 붙여 넣는다.

```text
Use only the Cape Fear Surf Guide MCP to explain this saved result.

You must call explain_surf_window with exactly these inputs:
- window_id: WINDOW_ID
- reading_level: beginner

Do not call find_surf_windows again. Do not use web search. If the saved result
cannot be found, show the error instead of rebuilding an answer. After the
call, briefly confirm whether the window_id and decision.state match the first
result.
```

`explain_surf_window`만 승인한다. 아래를 보여준다.

- tool name이 `explain_surf_window`다.
- `resultType`이 `complete`다.
- `window_id`가 첫 호출과 정확히 같다.
- `decision.state`와 evidence가 첫 결과와 같다.

### 영어로 말하기

> This is a separate Claude conversation, so the replay does not depend on
> chat history. The window ID is not an AgentCore session ID. It is a lookup
> key for the immutable record stored by the first call. This second tool reads
> that record directly, without model memory and without refreshing the
> sources.

저장 record는 24시간 후 만료된다. 없는 ID와 만료된 ID가 오류를 내는 것은
정상적인 fail-closed 동작이다.

## 4. 모델이 없앨 수 없는 veto — 2:45-3:30

### 화면

```bash
uv run python main.py --fixture hazard
```

`official_advisory_present`와 veto를 보여준다. live hazard를 일부러 만들지
않는다. 이 fixture가 검토된 위험 상황 증거다.

### 영어로 말하기

> Here an official advisory creates a deterministic veto. The agent is still
> free to explain the result, but the recommendation remains no because Python
> applies the veto before the final brief is accepted. The model has no path
> that can remove it.

## 5. 데이터가 나쁠 때 — 3:30-4:10

### 화면

```bash
uv run python main.py --fixture stale
uv run python main.py --fixture conflict
```

`stale_data`와 `conflicting_evidence`가 서로 다른 상태임을 보여준다.

### 영어로 말하기

> Stale evidence and conflicting evidence are different conditions, not one
> generic error. The policy names each state explicitly. In the live path, if
> a required source fails, the service returns insufficient data instead of
> silently replacing it with a friendlier fixture.

## 6. 측정 결과 — 4:10-4:40

### 화면

Phase 3 summary에서 아래 숫자만 보여준다.

- 30-case matrix
- deterministic path: model call 0, byte-identical output, p95 2초 미만
- agentic p95 `6,496.835 ms`, 제한 30초
- 최대 추정 요청 비용 `$0.00086886`, 제한 `$0.05`
- schema, tool-call, official-veto 성공률 100%
- normal false veto 0, immutable-field violation 0

### 영어로 말하기

> These are measured acceptance gates, not architecture claims. Across the
> evaluation matrix, the structured schema, tool-use, official-veto, and
> immutable-record checks all passed. The token counts are provider counters
> preserved as evidence; they are not presented as an AWS billing invoice.

## 7. 마무리 — 4:40-5:00

### 화면

README safety warning과 source link로 돌아간다.

### 영어로 말하기

> The person operating this tool is often not the person who gets in the water,
> and one answer can travel to a whole group. Cape Fear Surf Guide proposes a
> window and shows the evidence behind it. It never says the water is safe.
> Posted flags, lifeguards, and local officials always take priority.

## Live 장면 합격 기록

드라이런 직후 아래만 기록한다. API 키나 전체 요청은 기록하지 않는다.

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

도구가 “connected”라고 표시되는 것만으로는 부족하다. discovery와 두 번의
실제 호출이 모두 성공해야 한다.

## 녹화 체크리스트

- [ ] 영상은 5분 이하이고 공개로 업로드할 수 있다.
- [ ] 시작 45초 안에 문제, 사용자, 중요한 이유를 모두 말한다.
- [ ] Claude 화면에 예상한 MCP 도구만 보인다.
- [ ] live 결과에 `retrieval.mode: live`가 보인다.
- [ ] `brief_source`가 `agent`인지 `template`인지 정확히 말한다.
- [ ] replay에서 같은 `window_id`와 결정 상태가 보인다.
- [ ] `window_id`를 session ID라고 부르지 않는다.
- [ ] hazard, stale, conflict 상태가 서로 다르게 보인다.
- [ ] 공식 경고가 모델 설명보다 우선한다고 말한다.
- [ ] API 키, header, AWS 식별자, 회사 정보, 사용자명, hostname, 개인 경로,
      알림 또는 다른 MCP가 보이지 않는다.
- [ ] 바다가 안전하다고 말하지 않는다.
- [ ] 좋은 답을 찾으려고 live 호출을 반복하지 않는다.

## 녹화 중 실패하면

- Claude가 web search를 제안하면 취소하고 정확한 영어 프롬프트로 다시
  시작한다.
- `invalid_party_profile`이면 `experience` 같은 필드를 만들지 말고
  정확한 `skill_level` 객체를 복구한다.
- HTTP 403 또는 429면 중단한다. owner가 API 키, expiry, request count,
  WAF를 확인하기 전에는 다시 호출하지 않는다.
- 실제 veto나 `insufficient_data`는 그대로 사용한다. 이것은 시스템이
  실패한 것이 아니라 fail-closed로 동작한 것이다.
- replay ID 오류면 새 `find`를 호출하기 전에 복사한 문자열부터 비교한다.

cached 결과를 live 결과라고 설명하지 않는다.
