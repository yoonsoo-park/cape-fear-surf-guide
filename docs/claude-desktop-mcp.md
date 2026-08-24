# Claude Desktop and ChatGPT MCP verification

Verified documentation date: **2026-08-22**. The public demo is a live,
unauthenticated, rate-limited MCP endpoint; it is not a safety guarantee.

## Claude Desktop primary route

After the approved API Gateway endpoint is deployed, add its exact HTTPS
`/mcp` URL in Claude Desktop's remote MCP connector UI. Do not use a local
bridge, Keychain item, bearer token, OAuth client credential, or environment
variable for this public route.

In a new conversation, verify the following in order:

1. Claude Desktop discovers exactly `find_surf_windows` and
   `explain_surf_window`.
2. Call `find_surf_windows` for Wrightsville Beach on a date inside the next
   seven local calendar days. Confirm `retrieval.mode: live`, the source URLs
   and freshness labels, a deterministic decision state, and the safety limit.
3. In an independent request, call `explain_surf_window` with the returned
   random `window_id`. Confirm the stored record is returned without a live
   source refresh.

Record only the client version, date, endpoint, tool name, HTTP result,
decision state, and `window_id`. Do not record a request body, party profile,
Authorization header, account identifier, secret, or model prose.

## ChatGPT Developer Mode compatibility route

On an account with Developer Mode and remote MCP enabled, repeat the same
three checks. This is an additional compatibility check. It does not guarantee
that every ChatGPT account, product tier, or future connector supports this
endpoint.

If the current UI cannot connect to the no-auth URL or send the required MCP
protocol request, mark the route **not verified**. Do not add Cognito, Google
login, OAuth 2.1, or a Keychain bridge merely to change that result.

## Local frozen evidence

The repository's previous frozen MCP fixture tests and Keychain bridge are
kept for local regression and historical evidence. They are deliberately not
described as public demo setup or a judge access method.
