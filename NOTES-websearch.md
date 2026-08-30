# AgentCore Web Search implementation notes

## Architecture and current status

The offline stage is complete. `get_web_context` is registered only in the
explanation agent when `WebContextSettings.enabled` is true. The retrieval
agent still has exactly the original six fact tools. Normalized results carry
`source_kind=web_context`, title, URL, text, `published_at`, and a recency label
derived from `publishedDate`; they are attached to `SurfBrief.context` only.
The live Gateway create/call/delete stage was held behind an explicit AWS
approval gate and is now complete; the resources were torn down after the
single smoke query.

## Offline evidence

- The Web Search tool contract test passed with the connector ID `web-search`,
  target configuration `WebSearch`, connector version `1.1.0`, and
  `GATEWAY_IAM_ROLE`.
- The default-off test passed: an injected adapter received zero calls and the
  tool returned `status=disabled`, an empty result list, and
  `policy_signal=false`.
- The guardrail test passed with an untrusted “The water is safe” result: the
  `official_advisory_present` policy decision and veto remained unchanged.
- The query budget is one call per request by default; the second call returns
  `query_cap_reached` without invoking the adapter.

## Actual pitfalls encountered

1. Botocore exposes Gateway APIs through the separate
   `bedrock-agentcore-control` service. Looking up a lower-case operation in
   the service model produced the actual
   `OperationNotFoundError: create_gateway`; the script uses the boto3 client
   method (which maps the operation correctly).
2. The managed connector requires the nested target shape, not a generic HTTP
   URL. The offline contract test catches the exact `connector -> source ->
   configurations` shape and the `GATEWAY_IAM_ROLE` credential provider.
3. A missing or malformed `publishedDate` cannot be treated as current. The
   normalizer labels it `freshness_state=unavailable` and still keeps it out of
   policy; an old timestamp is labeled `stale`.
4. Running the mutating script with an unapproved account produced the actual
   guard message `refusing non-approved or nCino account; --account must be the
   approved personal account`. Running `--action apply` without the explicit
   flag produced `apply requires --confirm-live after human AWS approval`.
5. The first private `tools/list` returned the namespaced wire tool
   `web-search-tool___WebSearch`, not the unqualified `WebSearchTool` assumed
   by the initial adapter. The adapter now resolves that target-name suffix;
   this was a real Gateway integration mismatch, not a policy change.

## Approved private smoke evidence

The live gate was then approved for one query in account `831597648506`,
profile `aws-dimly`, region `us-east-1`. Gateway
`capefearwebsearchgateway-45po1miaah` and target `GLIUUFMJ44` reached `READY`.
The 43-character query returned three results. All three were labeled
`source_kind=web_context`; all had `policy_signal=false`, and all lacked a
`publishedDate`, so the normalizer correctly reported
`freshness_state=unavailable`. The sanitized evidence is in
`dist/agentcore-web-search-evidence.json` (kept out of the commit if the
repository ignores generated `dist` evidence).

The first teardown attempt surfaced the actual asynchronous-delete error:
`ValidationException: Gateway with ID: capefearwebsearchgateway-45po1miaah has
targets associated with it. Delete all targets before deleting the gateway.`
After the target disappeared (`ResourceNotFoundException` on a read-only
follow-up), the retry deleted the Gateway and role. A final describe returned
`gateway: null`, and `iam get-role` returned `NoSuchEntity`; no Web Search
resource remains.

AWS cost was not measured as an invoice; the one-query count, Gateway ARN, and
sanitized result metadata above are the recorded smoke evidence. No public MCP
endpoint or API-key behavior changed.
