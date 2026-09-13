# Claude Desktop company-laptop verification runbook

This runbook verifies Cape Fear Surf Guide from **Claude Desktop on a
company-managed macOS laptop**. It uses the local stdio bridge because that
route can send the judge API's non-OAuth `x-api-key` without writing the key to
Claude's JSON configuration.

This procedure is a client verification only. It does not deploy or modify AWS
resources. The remote path remains:

```text
Claude Desktop -> local stdio bridge -> API Gateway + WAF -> Lambda -> AgentCore Runtime
```

## 1. Stop conditions and owner confirmation

Do not begin until all of these are true:

- Company policy permits Claude Desktop, GitHub access, and this personal
  hackathon demo on the laptop.
- The repository contains no company code, credentials, customer information,
  or other company data.
- The demo owner privately confirms that the judge exposure is currently
  enabled, has not expired, and has request budget remaining.
- The owner sends an individually issued API key through a private channel.
  Do not request or paste the key in GitHub, Slack, a ticket, a screenshot, or
  this repository.
- The test uses only the synthetic beginner profile in this runbook.

Stop immediately if company TLS inspection, endpoint controls, or device
policy blocks the connection. Do not disable certificate verification, a
proxy, endpoint protection, WAF, or API-key enforcement.

## 2. Values used in this runbook

Set these locally while following the steps:

```text
REPO_DIR      absolute path to the clone
MCP_ENDPOINT  https://lxyiewf9z7.execute-api.us-east-1.amazonaws.com/demo/mcp
API_KEY       the privately issued judge key; never record it
```

The endpoint URL is public configuration, not a credential. The current
exposure ID and expiry are deliberately not hard-coded here because every
judge window must use a new ID and a maximum 72-hour expiry.

## 3. Install prerequisites

Required software:

- Claude Desktop for macOS
- Git
- Python 3.11, 3.12, or 3.13
- `uv`

In Claude Desktop, open **Settings -> Extensions -> Advanced settings** and
confirm that local developer MCP servers are permitted. Team and Enterprise
administrators can disable local developer MCP through managed policy. If the
setting is unavailable or the organization requires signed `.dxt` packages,
stop and ask the administrator; this repository does not currently ship a
signed Desktop Extension.

Confirm the command-line prerequisites:

```bash
git --version
python3 --version
uv --version
```

If a command is unavailable, use only the company-approved installation
method. Do not bypass device-management restrictions.

## 4. Clone and prepare the bridge

After PR #10 is merged, clone the default branch. If the repository is already
present, fetch and fast-forward it instead of making an unrelated local edit.

```bash
git clone https://github.com/yoonsoo-park/cape-fear-surf-guide.git
cd cape-fear-surf-guide
git status --short
git log -1 --oneline
uv sync --project mcp_runtime --frozen
```

`git status --short` should be empty. Confirm the bridge tests before putting
the code in Claude Desktop's execution path:

```bash
uv run --project mcp_runtime pytest mcp_runtime/tests/test_claude_desktop_bridge.py
```

Expected result: all bridge tests pass. A dependency-download or certificate
failure is a company-network issue; follow the troubleshooting section rather
than weakening TLS validation.

## 5. Put the API key in the GUI login environment

Claude Desktop launched from Finder does not reliably inherit variables from a
terminal shell. Use `launchctl` so a newly launched Claude process inherits the
key. The following commands hide keyboard input and do not put the literal key
in shell history:

```bash
read -s "CAPE_FEAR_MCP_API_KEY?Paste the private Cape Fear API key: "
echo
export CAPE_FEAR_MCP_API_KEY
launchctl setenv CAPE_FEAR_MCP_API_KEY "$CAPE_FEAR_MCP_API_KEY"
unset CAPE_FEAR_MCP_API_KEY
```

Confirm only presence; never print the value:

```bash
launchctl getenv CAPE_FEAR_MCP_API_KEY | awk '
  length { found=1 }
  END {
    if (found) print "Cape Fear API key is available to newly launched GUI apps"
    else print "Cape Fear API key is missing; stop here"
    exit found ? 0 : 1
  }'
```

The key remains in the user's launch environment until logout, restart, or the
cleanup step below. Other processes running as the same local user may be able
to read that environment. Use a dedicated, short-lived judge key and remove it
immediately after verification.

## 6. Configure Claude Desktop

Quit Claude Desktop completely before editing its configuration. In Finder,
use **Go -> Go to Folder** and open:

```text
~/Library/Application Support/Claude/
```

Create or edit `claude_desktop_config.json`. Preserve every existing MCP server
entry. Add `cape_fear_surf_guide` inside the existing `mcpServers` object,
replacing every `/ABSOLUTE/PATH/...` value with the actual clone path:

```json
{
  "mcpServers": {
    "cape_fear_surf_guide": {
      "command": "/ABSOLUTE/PATH/cape-fear-surf-guide/mcp_runtime/.venv/bin/python",
      "args": [
        "-m",
        "mcp_runtime.claude_desktop_bridge",
        "--endpoint",
        "https://lxyiewf9z7.execute-api.us-east-1.amazonaws.com/demo/mcp",
        "--api-key-env-var",
        "CAPE_FEAR_MCP_API_KEY"
      ],
      "cwd": "/ABSOLUTE/PATH/cape-fear-surf-guide/mcp_runtime",
      "env": {
        "PYTHONPATH": "/ABSOLUTE/PATH/cape-fear-surf-guide/mcp_runtime"
      }
    }
  }
}
```

Important boundaries:

- Do not add the API-key value to `env`, `args`, or any other JSON field.
- Do not add `x-api-key` as a literal header.
- Do not replace the whole file if it already contains other MCP servers.
- Use straight JSON quotes and absolute paths. `~` is not an absolute path.

Validate the JSON without displaying secrets:

```bash
python3 -m json.tool \
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
  >/dev/null && echo "Claude Desktop JSON is valid"
```

Launch Claude Desktop again. Open its MCP/tool settings and confirm that
`cape_fear_surf_guide` is running and exposes exactly:

- `find_surf_windows`
- `explain_surf_window`

If Claude asks for tool permission, approve only these two read-only tools for
this test.

## 7. Run the live `find` test

Start a new conversation. Replace `YYYY-MM-DD` with a date from today through
six days ahead in the `America/New_York` calendar, then send:

```text
Cape Fear Surf Guide MCP만 사용해 YYYY-MM-DD 오전 Wrightsville Beach의
초보자용 서핑 가능 창을 찾아줘. 웹 검색이나 다른 도구를 사용하지 말고,
find_surf_windows를 실제 호출해. party_profile은
{"skill_level":"beginner","ages":[],"accessibility_needs":[]}로 사용해.
도구를 호출할 수 없으면 일반 지식으로 답하지 말고 오류를 그대로 알려줘.
```

Open the tool result and verify all of the following:

- Tool name is `find_surf_windows`.
- `resultType` is `complete`.
- `retrieval.mode` is `live`.
- A non-empty random `window_id` is present.
- `decision.state` is a deterministic state such as `recommended_window`,
  `caution`, or `do_not_recommend`.
- Source URLs and freshness labels are present.
- The safety limitation says the result is a planning aid, not a safety
  guarantee.

`recommended_window` is not required for the test to pass. The current official
evidence may legitimately produce a caution, veto, or insufficient-data result.
Never change the prompt to force a favorable recommendation.

Copy only the returned `window_id` into a temporary local note. Do not copy the
API key, complete request body, model chain of thought, or personal information.

## 8. Run the independent `explain` replay

Start a second new conversation so the verification does not rely on Claude's
chat memory. Replace `WINDOW_ID` and send:

```text
Cape Fear Surf Guide MCP의 explain_surf_window를 실제 호출해서
window_id WINDOW_ID를 초보자 수준으로 설명해줘. 웹 검색이나
find_surf_windows 재호출은 하지 마. 찾을 수 없으면 일반 지식으로
재구성하지 말고 오류를 그대로 알려줘.
```

Verify:

- Tool name is `explain_surf_window`.
- `resultType` is `complete`.
- The returned `window_id` exactly matches the first call.
- Decision state and evidence match the stored first result.
- The response is a stored replay; it does not claim a new source refresh.

The replay record expires after 24 hours. An expired or unknown ID is an
expected error and must not be treated as a successful replay.

## 9. Capture sanitized judge evidence

Capture one screenshot for tool discovery and one for each successful tool
call. Before saving or sharing them, verify that they contain none of the
following:

- API-key value or an `x-api-key` header
- company account, proxy, device, employee, or internal network information
- terminal environment output
- private chat, notification, browser tab, or unrelated MCP server content

The evidence note may contain only:

```text
Test date and timezone:
Claude Desktop version:
Operating system version:
MCP server name: cape_fear_surf_guide
find_surf_windows: pass/fail
explain_surf_window: pass/fail
window_id:
decision state:
retrieval mode:
HTTP status if an error occurred:
```

Mark Claude Desktop **verified** only when discovery plus both live calls have
passed. A visible server registration by itself is not verification.

## 10. Troubleshooting without exhausting the circuit breaker

Make at most two diagnostic calls before stopping and contacting the demo
owner. Repeated startup or tool retries can trigger the 30-requests-per-IP WAF
limit or consume the 120-request exposure budget.

| Symptom | Likely cause | Safe action |
| --- | --- | --- |
| Server is absent or failed | Invalid JSON, wrong absolute path, or missing virtual environment | Quit Claude, validate JSON, confirm the command exists, and rerun the bridge test. |
| `environment_token_unavailable` | Claude was launched before `launchctl setenv`, or the key was removed | Quit Claude completely, restore the launch environment privately, and relaunch once. |
| HTTP 403 on the first call | Invalid/disabled key, expired exposure, or WAF block | Stop. Ask the owner to check the key, exposure state, request count, and WAF metrics. Never remove authentication. |
| HTTP 403 after repeated attempts | Per-IP WAF rate rule | Stop for at least five minutes and ask the owner to confirm metrics before one retry. |
| HTTP 429 or intermittent rejection | API Gateway usage-plan throttle | Stop retrying and wait for owner guidance. |
| `invalid_party_profile` | Claude sent the wrong field, such as `experience` | Retry once with the exact synthetic `skill_level` JSON from step 7. |
| `insufficient_data` | A required public source failed or was stale | Record the deterministic result. Do not substitute a web answer or cached fixture. |
| Unknown or expired `window_id` | Wrong ID or the 24-hour record expired | Repeat `find` once only if the exposure owner approves the additional request. |
| Certificate or proxy error | Company TLS inspection or proxy policy | Use an IT-approved PEM bundle with `--ca-bundle /approved/path/company-ca.pem`, or stop. Never disable TLS verification. |

For startup errors, inspect the newest matching file under:

```text
~/Library/Logs/Claude/
```

The bridge's own audit line contains only endpoint, tool name, and HTTP status.
Do not paste full corporate logs into the public repository.

## 11. Cleanup

After the screenshots and sanitized evidence note are complete:

1. Quit Claude Desktop.
2. Remove the key from the GUI login environment:

   ```bash
   launchctl unsetenv CAPE_FEAR_MCP_API_KEY
   ```

3. Confirm only that the value is gone:

   ```bash
   launchctl getenv CAPE_FEAR_MCP_API_KEY | awk '
     length { found=1 }
     END {
       if (found) print "Key still present; stop and investigate"
       else print "Cape Fear API key removed from launch environment"
       exit found ? 1 : 0
     }'
   ```

4. Remove the `cape_fear_surf_guide` JSON block if this was a one-time company
   laptop test, then validate the remaining JSON again.
5. Delete temporary screenshots that were not selected as sanitized evidence.
6. Ask the demo owner to disable or delete the individual API key after the
   test. Only the owner performs AWS changes.

Do not delete the public AWS stack as part of client cleanup. The exposure's
scheduled circuit breaker independently sets the judge Lambda concurrency to
zero at expiry; stack deletion requires separate approval.

## Official Claude Desktop references

- [Getting started with local MCP servers on Claude Desktop](https://support.anthropic.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [Building custom connectors via remote MCP servers](https://support.anthropic.com/en/articles/11503834-building-custom-connectors-via-remote-mcp-servers)

Anthropic's current guidance distinguishes local Desktop extensions from
remote connectors and documents organization-level controls for local
developer MCP. The remote connector path supports authless or OAuth servers;
this demo instead requires an `x-api-key`, which is why this runbook uses the
local stdio bridge.
