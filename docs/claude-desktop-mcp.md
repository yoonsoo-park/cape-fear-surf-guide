# Claude Desktop local MCP bridge verification

Verified source date: **2026-08-22**. This document covers only the reviewed
frozen-fixture endpoint. It is not a live surf report and it does not make an
ocean-safety claim.

## Remote custom connector result

Claude's remote custom-connector flow documents OAuth configuration. The
deployed Cape Fear endpoint instead requires a dedicated bearer token on every
request. The connector UI has no safe field for this demo's bearer token, so
the direct remote route is recorded as **not verified: bearer authentication
unsupported for this configuration**. Do not enter OAuth client credentials,
do not add an OAuth implementation, and do not weaken endpoint authorization
to make that route appear to work.

Source checked: [Anthropic, Get started with custom connectors using remote
MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

If a future Claude Desktop release changes that authentication surface, recheck
the official source, record the version and date, and run this procedure again.
The local success below proves only `Claude Desktop -> local stdio bridge ->
HTTPS MCP`; it does not prove remote-connector compatibility.

## Local bridge

`mcp_runtime.mcp_runtime.claude_desktop_bridge` is a local standard-input and
standard-output MCP server. Standard input and standard output are the two
streams Claude Desktop uses to exchange JSON-RPC messages with a local process.
The bridge itself handles `initialize` and `tools/list`; it exposes exactly
`find_surf_windows` and `explain_surf_window`.

For each tool call, the bridge obtains the bearer value at runtime from this
dedicated macOS Keychain generic-password item:

| Field | Value |
| --- | --- |
| Service | `cape-fear-surf-guide-mcp` |
| Account | `claude-desktop` |

Create that item manually in Keychain Access. Put only the demo bearer value
in the password field. Do not put it in a repository file, Claude Desktop
configuration, environment variable, shell command, screenshot, or evidence
record. The bridge logs only its public endpoint URL, tool name, and HTTP status
to standard error; it never logs a request body or authorization value.

Back up the Claude Desktop configuration before editing it. Add only the
following server entry under `mcpServers`, replacing the executable path and
the public Function URL with their real non-secret values. The `endpoint` value
must end exactly in `/mcp`.

```json
{
  "mcpServers": {
    "cape-fear-surf-guide-local": {
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--directory",
        "/Users/yoonsoo.park/orca/workspaces/cape-fear-surf-guide/wentletrap/mcp_runtime",
        "python",
        "-m",
        "mcp_runtime.claude_desktop_bridge",
        "--endpoint",
        "https://public-function-url.example/mcp",
        "--ca-bundle",
        "/path/to/company-ca-bundle.pem"
      ]
    }
  }
}
```

Do not use a bearer token in `args`, `env`, or any other configuration field.
The CA bundle path is non-secret and is needed only when the host's HTTPS
inspection proxy has a private root certificate. Omit both CA arguments on a
host that does not need them. The sample URL is deliberately nonfunctional.
The repository example never contains a Keychain value or bearer token.

## Manual acceptance record

The user must restart Claude Desktop and begin a new conversation before this
check. In Connectors, enable only `cape-fear-surf-guide-local` and confirm that
the tool list contains only the two names above.

1. Call `find_surf_windows` with `date: 2026-08-29`,
   `party_profile: {"skill_level":"beginner","ages":[12,40]}`, and
   `preferred_area: wrightsville-beach`. Record the date, Claude Desktop
   version, connection path, tool name, HTTP status, snapshot ID, `window_id`,
   `retrieval.mode: frozen_snapshot`, and the safety-limit disclosure.
2. In a new request, pass that exact `window_id` to `explain_surf_window`.
   Record whether the deterministic record is reconstructed.
3. Call `explain_surf_window` with the reviewed hazard `window_id`
   `344fef82136e2bccd01b`. Record the `cape-fear-hazard-v1` snapshot ID, veto
   state `official_advisory_present`, and confirm that Claude did not change it
   into a safe claim.

Do not record a bearer token, Keychain screen, request body, authorization
header, account identifier, or model prose. After the demo, remove this one
`mcpServers.cape-fear-surf-guide-local` entry and the dedicated Keychain item.
Do not delete a CloudFormation stack without separate explicit approval.
