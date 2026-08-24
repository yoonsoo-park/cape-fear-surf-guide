# Public live MCP demo

## Scope

The judge-facing endpoint is an API-key-gated, read-only HTTPS MCP service.
It supports only Wrightsville Beach and dates from today through six days ahead
in `America/New_York`. It accepts stateless JSON-RPC on `POST /mcp`, protocol
`2026-07-28`, and exposes only `find_surf_windows` and
`explain_surf_window`.

Each `find_surf_windows` call retrieves NWS `NCZ108` alerts and forecast,
NOAA station `8658163` tide predictions, and Open-Meteo marine and weather
data in parallel. It returns `retrieval.mode: live`, source URLs, retrieval
times, freshness labels, the deterministic decision, and the safety limit.
The service never uses a frozen fixture to replace a failed live source. A
failed or unnormalizable required source produces `insufficient_data`.

NC DEQ does not yet have a verified machine-readable Wrightsville mapping. The
result labels that state `feed_unavailable` with the official direct-check URL;
it is not evidence that the water is safe. An active confirmed DEQ advisory is
a deterministic veto.

`find_surf_windows` writes the exact decision payload under a random
`window_id` to encrypted DynamoDB storage with a 24-hour TTL. A later
`explain_surf_window` only reads that record: it never performs a second live
retrieval. Unknown and expired identifiers return explicit structured errors.

This is a planning aid, not a guarantee that ocean activity is safe. Posted
flags, lifeguards, local officials, and current conditions take priority.

## Judge access, controls, and hard stop

The CloudFormation template is
[`infra/external-mcp-demo/runtime.yaml`](../infra/external-mcp-demo/runtime.yaml).
It creates API Gateway REST `POST /mcp`, Lambda, two DynamoDB tables, and a
regional AWS WAF web ACL. WAF blocks an IP after 30 requests in five minutes
and blocks all clients together after 60 `POST /mcp` requests in five minutes.
API Gateway also targets 0.2 requests per second with a burst of two. Its
`POST /mcp` method requires the `x-api-key` header before Lambda is invoked.
The stack creates a usage plan but deliberately creates no API key value: when
a judge requests access at `yoonsoo@duck.com`, create a distinct API Gateway
key manually, associate it with this usage plan, and deliver it out of band.
Never put a key in Git, CloudFormation parameters or outputs, a Devpost page,
or a demo recording. That throttle smooths bursts but is not a cost guarantee.

The application grants at most 120 valid MCP POST permits for one exposure. It
consumes each permit with a DynamoDB conditional update after protocol
validation and before any tool, source lookup, or decision record write. The
121st valid request receives HTTP 429 with `demo_request_budget_exhausted`.

A private Circuit Breaker sets public Lambda reserved concurrency to zero when
the 120th permit is observed, when Lambda starts reach 40 in five minutes, or
when the required `PublicUntilUtc` arrives. `PublicUntilUtc` is UTC and must
be no more than 72 hours after the approved deployment time. Only a
human-approved manual invocation can re-enable a `volume_alarm` stop;
request-budget and scheduled-expiry stops are terminal for that exposure.
Every new public window must use a new required `ExposureId`; it never reuses
an expired or exhausted control record.

The stack sends a monthly AWS Budget email at $10. This alert provides
visibility; the request-budget and circuit-breaker controls provide shutdown.
Lambda has reserved concurrency 2, a 30-second timeout, a bounded request
body, no VPC, and narrowly scoped record-table and exposure-control-table IAM.

The API and application do not log request bodies, party profiles, or API-key
values. API Gateway method execution logging is disabled. There is no Lambda
Function URL, bearer token, SecureString, token-rotation path, Cognito
configuration, Google credential, OAuth 2.1 implementation, or local Keychain
dependency in this deployment.

## Approval and release gate

No AWS resource creation or deployment is authorized by this document. Before
creating a change set, a human must explicitly approve the personal AWS
account, role, region, budget, log and data retention, rollback path,
smoke-test owner, `BudgetAlertEmail`, exact `PublicUntilUtc`, the AgentCore
Runtime ARN, and the judge-access operating responsibility. The approver must
also provide a new `ExposureId` for this access window.

After that approval, package and validate the exact artifact:

```bash
uv run python scripts/package_external_mcp_lambda.py
uv run pytest
uv run python -m compileall -q main.py surf scripts
uv run --directory mcp_runtime pytest
```

Review the change set to confirm that it contains API Gateway REST, WAF,
Lambda, DynamoDB, SNS, CloudWatch alarm, Scheduler, and dedicated roles and
log groups only. It must contain no
Function URL, SSM parameter, Cognito resource, VPC, NAT gateway, or EC2
resource.

At expiry, record the circuit-breaker reason and verify judge-access Lambda reserved
concurrency is zero. Preserve only sanitized evidence, then obtain separate
human approval to delete the CloudFormation stack. Disabling stops workload
execution; stack deletion removes API Gateway, WAF, DynamoDB, and continuing
fixed charges.

## Manual judge-client evidence

Claude Desktop and ChatGPT Desktop/Codex are the manual demonstration routes.
Use the remote MCP connector UI or the local Codex MCP configuration with the
approved `POST /mcp` URL and supplied `x-api-key`, discover
the two tools, call a valid live Wrightsville request, then call
`explain_surf_window` from its returned `window_id` in a new request. Record
the client version, date, endpoint, tool names, HTTP result, decision state,
retrieval mode, and `window_id`; do not record prompt content or model prose.

For the ChatGPT Desktop/Codex setup, use the environment-backed
`env_http_headers` configuration in
[`docs/claude-desktop-mcp.md`](claude-desktop-mcp.md). If either product cannot
make the request, record it as not verified rather than adding OAuth or
weakening the public controls.

The old frozen MCP and Keychain bridge remain local regression evidence only.
They are not a judge access path.

## Deferred authentication

OAuth 2.1 is a later product phase. It needs a separately reviewed identity,
consent, token-storage, rotation, and client-compatibility design. API Gateway
API keys are an access gate and usage meter, not a full identity system.
