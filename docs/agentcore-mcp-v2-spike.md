# AgentCore MCP v2 compatibility spike

Verified: 2026-08-22

## Problem

Cape Fear Surf Guide's MCP service targets Python SDK v2 and protocol
`2026-07-28`. Current AgentCore MCP documentation instead demonstrates the
older `FastMCP`, `ClientSession.initialize()`, and `Mcp-Session-Id` API. Those
examples do not prove that AgentCore will pass through the v2 stateless request
metadata and HTTP headers unchanged.

## Local contract already proved

`mcp_runtime/Dockerfile` starts the isolated SDK v2 service at
`0.0.0.0:8000/mcp`, which is the AgentCore container path. The local test suite
proves all of the following without AWS:

- `MCPServer` from `mcp==2.0.0` registers only `find_surf_windows` and
  `explain_surf_window`.
- A second fresh server reconstructs the same frozen record from `window_id`.
- The endpoint requires bearer authorization, validates allowed `Origin`, and
  rejects mismatched `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`, and
  request metadata.
- The endpoint is POST-only and has no GET event stream or protocol session.
- Responses contain structured evidence and deterministic decision data.

## AWS gate before the real spike

The following values were explicitly approved for this isolated spike on
2026-08-22:

1. AWS profile `personal`, account ID `831597648506`, region `us-east-1`, and
   caller `yopa-study` were verified immediately before deployment.
2. The entrypoint is a new, dedicated CloudFormation runtime named
   `CapeFearMcpV2Spike`; no existing AgentCore runtime, role, or repository is
   reused.
3. Budget ceiling is $50 in promotional credits. The runtime stack is deleted
   after the spike. The versioned artifact bucket expires objects after seven
   days; its retained empty bucket can be deleted after that retention period.
4. AgentCore IAM/SigV4 is the inbound authorization boundary. The app uses no
   bearer secret and makes no external authenticated call, so no Parameter
   Store secret is created. If a later dependency needs one, CloudFormation
   must create an `AWS::SSM::Parameter` `SecureString` and grant only that
   parameter's `ssm:GetParameter` permission to this runtime role.
5. `infra/agentcore-spike/*.yaml` is the only provisioning path. The smoke
   script is `uv run python scripts/run_agentcore_mcp_v2_spike.py` with the
   CloudFormation RuntimeArn output. It invokes a fresh runtime session for
   `find_surf_windows`, then another for `explain_surf_window`.

The runtime has no model calls, no datastore, no VPC attachment, and no
application AWS SDK permissions. Its execution role trusts only the AgentCore
service from this account and has only the CloudWatch Logs permissions that
AgentCore requires to create and write its own runtime log path. AgentCore's
control plane reads the immutable S3 artifact version during deployment; the
application itself never reads S3.

AgentCore's current MCP contract was rechecked during the live spike. It
requires `Accept: application/json, text/event-stream` at its data-plane API,
adds its own `Mcp-Session-Id` for microVM routing, and requires the server to
accept that header in stateless mode. The application does not read, persist,
or require that identifier; the fresh-session test therefore remains valid.

### Deployment sequence

```bash
aws cloudformation deploy --profile personal --region us-east-1 \
  --stack-name CapeFearMcpV2ArtifactSpike \
  --template-file infra/agentcore-spike/artifact-bucket.yaml

uv run python scripts/package_agentcore_spike.py
aws s3api put-object --profile personal --region us-east-1 \
  --bucket "$(aws cloudformation describe-stacks --profile personal --region us-east-1 --stack-name CapeFearMcpV2ArtifactSpike --query 'Stacks[0].Outputs[?OutputKey==`ArtifactBucketName`].OutputValue' --output text)" \
  --key agentcore/cape-fear-mcp-v2-spike.zip --body dist/cape-fear-mcp-v2-spike.zip
```

The deployer records the returned object `VersionId` and supplies it to
`runtime.yaml`. This makes the tested runtime artifact immutable. The runtime
stack must be deleted with CloudFormation after the evidence file is captured;
do not use imperative AgentCore deletion.

## Pass criteria for the real AgentCore spike

The deployed runtime passes only if AgentCore preserves this v2 contract:

| Check | Required evidence |
| --- | --- |
| Endpoint | Request reaches container `POST /mcp` on port 8000 |
| Version | `MCP-Protocol-Version: 2026-07-28` reaches the service unchanged |
| Metadata | Required `params._meta` protocol and client-capability envelope reaches the service |
| Routing headers | `Mcp-Method` and `Mcp-Name` match the JSON-RPC request |
| Statelessness | A second invoke can land on a fresh process and explain the first `window_id` |
| Safety data | Returned record retains evidence, freshness, and deterministic veto state |
| Old session surface | No `initialize()` or `Mcp-Session-Id` dependency is introduced |
| Negative cases | Mismatched headers and an unknown `window_id` fail deterministically |

If any check fails, preserve the returned request/response metadata with secrets
redacted, document the incompatibility, and retain the standalone MCP v2
runtime. Do not downgrade MCP or add session coupling merely to fit the current
AgentCore examples.

## Live spike result

Run on 2026-08-22 against the dedicated `personal`/`us-east-1` runtime:

- Pass: `find_surf_windows` returned the full structured deterministic record
  for protocol `2026-07-28`.
- Pass: a separate runtime session resolved that returned `window_id` through
  `explain_surf_window`; no process or protocol-session state was needed.
- Pass: an unknown `window_id` returned the structured `unknown_window_id`
  tool error.
- Pass with AgentCore adaptation: a mismatched `Mcp-Method` reached the
  container and was rejected with HTTP 400. AgentCore returned it to the data
  plane as MCP JSON-RPC error `-32010` with HTTP 200, so the smoke assertion
  checks that documented wrapper instead of expecting a raw HTTP 400.

The latest AgentCore contract also sends health-check `ping` and `initialize`
requests that the 2026-07-28 service correctly rejects. AgentCore logs this as
an expected new-version MCP condition and treats the service as healthy. The
runtime ignores the platform's `Mcp-Session-Id`; it remains a stateless service
whose records are reconstructed from `window_id` and frozen evidence.

For the source-code artifact path, AgentCore executed the zip directly and did
not install `requirements.txt`. `scripts/package_agentcore_spike.py` therefore
vendors the lockfile-resolved Python 3.11/Linux ARM64 dependencies into the
ephemeral artifact. It never copies the host virtual environment. This is a
deployment packaging requirement, not a change to the MCP protocol contract.

All dedicated Cape Fear runtime stacks were deleted through CloudFormation
after the successful run. The private versioned artifact bucket remains only
until its seven-day lifecycle expires its uploaded artifacts; unrelated
AgentCore resources were not changed.

## Sources

- https://modelcontextprotocol.io/specification/2026-07-28
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- https://py.sdk.modelcontextprotocol.io/whats-new/
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html
