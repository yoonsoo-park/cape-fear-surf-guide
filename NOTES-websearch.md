# AgentCore Web Search implementation notes

## Architecture and current status

The offline stage is complete. `get_web_context` is registered only in the
explanation agent when `WebContextSettings.enabled` is true. The retrieval
agent still has exactly the original six fact tools. Normalized results carry
`source_kind=web_context`, title, URL, text, `published_at`, and a recency label
derived from `publishedDate`; they are attached to `SurfBrief.context` only.
The live Gateway create/call/delete stage is intentionally pending its explicit
AWS approval and has not run in this checkout.

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

No live query count, AWS cost, Gateway ARN, or Web Search result is claimed
until the approved private smoke is executed and torn down. No public MCP
endpoint or API-key behavior changes in this stage.
