# Claude Desktop, ChatGPT Desktop, and Codex MCP verification

Verified documentation date: **2026-08-24**. The live demo is an API-key-gated,
rate-limited MCP endpoint; it is not a safety guarantee.

## Claude Desktop route

After the approved API Gateway endpoint is deployed, add its exact HTTPS
`/mcp` URL in Claude Desktop's remote MCP connector UI with the individually
issued `x-api-key`. Never put the key in the repository, a recording, or a
shared configuration file.

In a new conversation, verify the following in order:

1. Claude Desktop discovers exactly `find_surf_windows` and
   `explain_surf_window`.
2. Call `find_surf_windows` for Wrightsville Beach on a date inside the next
   seven local calendar days. Confirm `retrieval.mode: live`, source URLs and
   freshness labels, a deterministic decision state, and the safety limit.
3. In an independent request, call `explain_surf_window` with the returned
   random `window_id`. Confirm the stored record returns without source refresh.

## ChatGPT Desktop and Codex route

ChatGPT Desktop, Codex CLI, and the Codex IDE extension share local MCP
configuration on the same Mac. Configure this once on the personal laptop;
do not add a second endpoint or local proxy.

1. Store the individually issued API key in the local login session as
   `CAPE_FEAR_MCP_API_KEY`. Do not commit it or put the literal key in
   `config.toml`.
2. Add this entry to `~/.codex/config.toml`, replacing only the endpoint URL:

   ```toml
   [mcp_servers.cape_fear_surf_guide]
   url = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/demo/mcp"
   http_headers = { "User-Agent" = "cape-fear-codex/1.0" }
   env_http_headers = { "x-api-key" = "CAPE_FEAR_MCP_API_KEY" }
   enabled_tools = ["find_surf_windows", "explain_surf_window"]
   default_tools_approval_mode = "prompt"
   tool_timeout_sec = 45
   enabled = true
   ```

3. Restart ChatGPT Desktop after changing this file. The User-Agent is required
   because the public WAF rejects requests with no User-Agent header. In a new
   Codex chat, type `/mcp`, confirm `cape_fear_surf_guide` is connected, and
   repeat the three checks above.

The Desktop UI can add a Streamable HTTP URL, but this config-file route is
required here because it reads the API key from an environment variable rather
than saving a static secret header. ChatGPT web does not read this local file;
it needs a separately installed hosted app or plugin and is out of scope for
the judged demo.

Record only the client version, date, endpoint, tool name, HTTP result,
decision state, retrieval mode, and `window_id`. Do not record an API-key
value, request body, party profile, account identifier, secret, or model prose.
If either product cannot make the request, mark it **not verified** rather than
weakening the API-key, WAF, or request-budget controls.

## Local frozen evidence

The repository's previous frozen MCP fixture tests and Keychain bridge remain
local regression and historical evidence. They are not a judge access method.
