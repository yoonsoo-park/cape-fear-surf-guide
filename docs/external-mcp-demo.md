# External MCP frozen-demo deployment

## Scope

This is a short-lived, public HTTPS demonstration endpoint for a reviewed
frozen snapshot. It is a Lambda Function URL, meaning AWS provides HTTPS and
starts the function only when a request arrives. The stack creates no VPC, NAT
Gateway, EC2 instance, live-source fetcher, or model invocation.

Every successful tool response includes `retrieval.mode: frozen_snapshot`.
The endpoint does not describe current conditions and does not guarantee that
ocean activity is safe. The deterministic result still instructs people to
check posted flags, lifeguards, and local officials.

The public endpoint accepts standard stateless MCP JSON-RPC on `POST /mcp`.
It validates JSON-RPC 2.0, `MCP-Protocol-Version: 2026-07-28`, the request
metadata version, and the two reviewed tool names. It does not require the
AgentCore-only `Mcp-Method` or `Mcp-Name` headers. The isolated AgentCore app
continues to require those headers.

## Deployment approval gate

Do not deploy from this document alone. Before creating a change set, a human
must explicitly confirm the personal AWS account, role, region, profile,
budget, seven-day log retention, rollback path, and smoke-test owner. The
deployment creates a public URL whose access control is the short-lived bearer
token, so share the URL and bearer token through separate approved channels.

The CloudFormation templates are
[`infra/external-mcp-demo/artifact-bucket.yaml`](../infra/external-mcp-demo/artifact-bucket.yaml)
and [`infra/external-mcp-demo/runtime.yaml`](../infra/external-mcp-demo/runtime.yaml).
The artifact bucket is dedicated to this public demo, versioned, private, and
expires artifacts after seven days; it is not the AgentCore spike bucket. The
runtime pins the exact uploaded S3 object version.
It stores the deployment input in one dedicated SSM Parameter Store
`SecureString`. CloudFormation's normal SSM resource cannot create a
`SecureString`, so a no-log custom resource receives the NoEcho input and is
limited to creating and deleting that exact parameter. The Lambda environment
contains only the parameter's name, not its value. The demo execution role can
read only that one parameter and write only its own service log group. The
application never logs request bodies or `Authorization` headers.

The template fixes these operational limits:

| Control | Default | Purpose |
| --- | ---: | --- |
| Reserved Lambda concurrency | 2 | Bounds simultaneous demo execution. |
| Request body | 65,536 bytes | Rejects oversized JSON before it reaches MCP. |
| Browser origins | `https://claude.ai`, `https://chatgpt.com` | Applies only when an `Origin` header is supplied. |
| Log retention | 7 days | Minimum short-lived demo retention. |
| Lambda timeout | 30 seconds | Matches the agentic-path latency ceiling without authorizing model calls. |

AWS generates the Function URL host name after creating the function. For that
reason the Lambda adapter disables the SDK's static Host allowlist, which
cannot be configured without a circular CloudFormation dependency. The
adapter still enforces the explicit Origin allowlist and bearer authentication
for every request. It caches the authorized bearer value only in a warm Lambda
execution environment and creates a fresh stateless MCP ASGI lifespan per
request. This exception is limited to the Function URL adapter; the local
runtime retains its Host protection.

## Build and pre-deployment checks

Build the upload artifact only after the approval gate. The packaging command
uses the locked isolated MCP runtime and includes only the frozen service,
shared deterministic policy modules, reviewed fixtures, and Linux runtime
dependencies:

```bash
uv run python scripts/package_external_mcp_lambda.py
```

Run the offline checks before making an AWS change set:

```bash
uv run pytest
uv run python -m compileall -q main.py surf scripts
uv run --directory mcp_runtime pytest
git grep -n -I -E '(AKIA[0-9A-Z]{16}|aws_secret_access_key|BEGIN (RSA |OPENSSH )?PRIVATE KEY)' -- .
rg -n 'AWS::EC2::|AWS::NATGateway|Bearer [A-Za-z0-9_-]{20,}' infra/external-mcp-demo README.md docs
```

Review the CloudFormation change set before executing it. Confirm that it
contains only the demo Function URL, Lambda, dedicated role, dedicated log
group, and dedicated SecureString; that it contains no NAT or EC2 resource;
and that the bearer-token parameter value is absent from the change-set output.

## Post-deployment smoke matrix

Use a local secret store or protected shell environment for the bearer token;
do not paste it into a terminal transcript, source file, image, request log,
or README. Run each check against the published URL and record only HTTP
status, result code, fixture name, `window_id`, and `retrieval.mode`.

1. A request with no `Authorization` header and a request with a wrong bearer
   value both return HTTP 401.
2. A request with the configured bearer value returns `tools/list`, then a
   normal `find_surf_windows` result with `retrieval.mode: frozen_snapshot`.
3. Send `explain_surf_window` in a new request using that `window_id`; its
   deterministic record exactly matches the first response.
4. Call the reviewed hazard `window_id`; its result retains the deterministic
   veto and cannot be changed by the client.
5. Verify that GET returns 405, malformed JSON or a wrong protocol version
   returns 400, and a body above the configured limit returns 413.
6. Inspect the dedicated log group for the smoke time range. It must contain no
   request body, `Authorization` header, or bearer value.

Before recording, re-check the current official Claude and ChatGPT MCP
connector documentation. Record a product only when its current connector can
send a bearer token to this endpoint. If a client cannot do that, record it as
**not verified**, rather than claiming support. The five-minute sequence is:
tool discovery, normal fixture, independent `window_id` explanation, hazard
veto, then the frozen-data and safety-limit disclosure.

## Token rotation and teardown

To rotate a bearer token, update the stack with a newly generated short-lived
`DemoBearerToken` input and a new non-secret `TokenRotationId`. The changed
rotation identifier updates the Lambda configuration, replacing warm execution
environments so the new cold starts read the new SecureString. Re-run the
unauthorized and authorized smoke checks, then stop accepting the old token.

Immediately after the recording, delete the same CloudFormation stack. Stack
deletion removes the Function URL, Lambda function, dedicated log group, and
dedicated SecureString. Confirm the deletion events before treating access as
revoked. This deletion is a human-approved operational action, not an
automated test step.

## Live data and OAuth are deferred

Live NWS, marine, and water-quality contracts must each be verified for
freshness, failure behavior, policy effect, cost, and reproducible captures
before a separate change introduces them. OAuth 2.1 belongs to that later,
verified live-data design. This frozen fixture demo remains independent of
live sources and OAuth.
