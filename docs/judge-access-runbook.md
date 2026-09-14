# Judge access activation runbook

Use this only after a hackathon judge asks to test Cape Fear Surf Guide. It
opens a new, individually keyed, short-lived exposure. It does not make
AgentCore anonymous and it never reuses an expired exposure.

## Outcome and hard limits

The operator confirms the judge request and personal AWS identity, generates a
new `ExposureId` and `PublicUntilUtc`, updates the existing CloudFormation
stack, restores bounded Lambda concurrency, creates one judge API key, verifies
a live call plus replay, and confirms shutdown at expiry.

The exposure stops at the earliest of 120 valid MCP POST requests, the approved
expiry (no more than 72 hours), or a volume alarm. Expiry and request-budget
stops are terminal for that exposure. A `volume_alarm` stop may be manually
re-enabled only with fresh approval and before expiry or budget exhaustion.

## 1. Capture explicit approval

Keep this in a private operator note. Never record an API-key value.

```text
Judge request received at (UTC):
Judge contact verified by:
Requested test window:
AWS profile, account ID, and role ARN:
AWS region:
CloudFormation stack name:
AgentCore Runtime ARN:
Monthly $10 budget email confirmed:
Log retention: 7 days
Decision-record retention: 24 hours
Rollback owner:
Smoke-test owner:
Approval statement and timestamp:
```

A previous exposure approval does not authorize a new exposure.

## 2. Generate fresh inputs offline

From a clean checkout of the release commit:

```bash
uv run python scripts/prepare_judge_exposure.py > /tmp/cape-fear-judge-exposure.json
cat /tmp/cape-fear-judge-exposure.json
```

This performs no AWS operation. Use `--hours 24` or `--hours 48` for a shorter
window; values above 72 are rejected. Copy the non-secret output values:

```bash
export CAPE_EXPOSURE_ID="<exposure_id>"
export CAPE_PUBLIC_UNTIL_UTC="<public_until_utc>"
export CAPE_AWS_PROFILE="<approved-personal-profile>"
export CAPE_AWS_REGION="us-east-1"
export CAPE_STACK_NAME="<existing-external-mcp-stack>"
```

## 3. Read-only preflight

```bash
aws sts get-caller-identity \
  --profile "$CAPE_AWS_PROFILE" \
  --region "$CAPE_AWS_REGION"

aws cloudformation describe-stacks \
  --profile "$CAPE_AWS_PROFILE" \
  --region "$CAPE_AWS_REGION" \
  --stack-name "$CAPE_STACK_NAME" \
  --query 'Stacks[0].{Status:StackStatus,Parameters:Parameters,Outputs:Outputs}'

uv run python scripts/package_external_mcp_lambda.py
uv run pytest
uv run python -m compileall -q main.py surf scripts
uv run --directory mcp_runtime pytest
```

Stop if the identity is not the approved personal account and role, the stack
is unhealthy, the Runtime ARN differs, a test fails, or the budget email is
unconfirmed.

## 4. Activate the exposure

The following commands change AWS. Immediately before running them, re-state
the account, role, region, exposure ID, expiry, 120-request limit, retention,
and rollback owner, and obtain explicit approval.

```bash
aws cloudformation deploy \
  --profile "$CAPE_AWS_PROFILE" \
  --region "$CAPE_AWS_REGION" \
  --stack-name "$CAPE_STACK_NAME" \
  --template-file infra/external-mcp-demo/runtime.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ExposureId="$CAPE_EXPOSURE_ID" \
    PublicUntilUtc="$CAPE_PUBLIC_UNTIL_UTC"

export CAPE_PUBLIC_FUNCTION_NAME="$(aws cloudformation describe-stack-resource \
  --profile "$CAPE_AWS_PROFILE" \
  --region "$CAPE_AWS_REGION" \
  --stack-name "$CAPE_STACK_NAME" \
  --logical-resource-id DemoFunction \
  --query 'StackResourceDetail.PhysicalResourceId' \
  --output text)"

aws lambda put-function-concurrency \
  --profile "$CAPE_AWS_PROFILE" \
  --region "$CAPE_AWS_REGION" \
  --function-name "$CAPE_PUBLIC_FUNCTION_NAME" \
  --reserved-concurrent-executions 2
```

A stack update alone is not proof that requests can run: a previous circuit
breaker may have left reserved concurrency at zero. Verify it is exactly two:

```bash
aws lambda get-function-concurrency \
  --profile "$CAPE_AWS_PROFILE" \
  --region "$CAPE_AWS_REGION" \
  --function-name "$CAPE_PUBLIC_FUNCTION_NAME"
```

## 5. Issue one judge key

Resolve the endpoint and usage plan:

```bash
export CAPE_MCP_ENDPOINT="$(aws cloudformation describe-stacks \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --stack-name "$CAPE_STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`McpEndpoint`].OutputValue' --output text)"

export CAPE_USAGE_PLAN_ID="$(aws cloudformation describe-stacks \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --stack-name "$CAPE_STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`JudgeAccessUsagePlanId`].OutputValue' --output text)"
```

The next response contains the secret. Do not run it in a recorded terminal or
copy its output into logs:

```bash
CAPE_KEY_FILE="$(mktemp /tmp/cape-fear-judge-key.XXXXXX)"
chmod 600 "$CAPE_KEY_FILE"
aws apigateway create-api-key \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --name "${CAPE_EXPOSURE_ID}-judge" --enabled --output json > "$CAPE_KEY_FILE"
export CAPE_API_KEY_ID="$(jq -r '.id' "$CAPE_KEY_FILE")"

aws apigateway create-usage-plan-key \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --usage-plan-id "$CAPE_USAGE_PLAN_ID" \
  --key-id "$CAPE_API_KEY_ID" --key-type API_KEY
```

Send the endpoint, `x-api-key` header value, UTC expiry, two tool names, and
planning-aid limitation to the verified judge through the agreed private
channel. Then remove the local secret file:

```bash
rm -f "$CAPE_KEY_FILE"
unset CAPE_KEY_FILE
```

## 6. Smoke test and evidence

Follow [`claude-desktop-mcp.md`](claude-desktop-mcp.md). Run one English
`find_surf_windows` request, then call `explain_surf_window` with the returned
`window_id` in a separate request. Registration, authentication status, or
tool discovery alone is not a pass.

Suggested judge prompts:

```text
Use Cape Fear Surf Guide to find a beginner-friendly morning surf window at
Wrightsville Beach for tomorrow. Return window_id, decision.state,
retrieval.mode, source freshness, and warnings.

Explain the saved Cape Fear Surf Guide recommendation for window_id
<WINDOW_ID>. Do not perform a new live retrieval. Confirm the returned
window_id and decision.state.
```

Record only:

```text
ExposureId and PublicUntilUtc:
Client and version:
Test time (UTC):
Endpoint host (no API key):
Discovered tools:
find_surf_windows HTTP result, retrieval.mode, decision.state, window_id:
explain_surf_window HTTP result:
Replay window_id and decision.state matched: yes/no
Budget email subscription confirmed: yes/no
Reserved concurrency after activation: 2
```

## 7. Expiry and cleanup

At or after `PublicUntilUtc`, verify reserved concurrency is zero and read the
exposure control record:

```bash
aws lambda get-function-concurrency \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --function-name "$CAPE_PUBLIC_FUNCTION_NAME"

export CAPE_EXPOSURE_TABLE="$(aws cloudformation describe-stacks \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --stack-name "$CAPE_STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`ExposureControlTableName`].OutputValue' --output text)"

aws dynamodb get-item \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --table-name "$CAPE_EXPOSURE_TABLE" \
  --key "{\"exposure_id\":{\"S\":\"$CAPE_EXPOSURE_ID\"}}" --consistent-read

aws apigateway delete-api-key \
  --profile "$CAPE_AWS_PROFILE" --region "$CAPE_AWS_REGION" \
  --api-key "$CAPE_API_KEY_ID"
```

Expected control state is `disabled`, with reason `scheduled_expiry` or
`request_budget_exhausted`. Stack deletion is separate and destructive; obtain
separate approval. Until then, keep reserved concurrency at zero.

## Response template

> Thanks for requesting access to Cape Fear Surf Guide. I issue individual,
> time-limited credentials rather than leaving my personal AWS endpoint
> permanently public. I am opening a fresh access window and will send the MCP
> endpoint, API key, expiry time, and two English test prompts through this private
> channel. The service is a planning aid and does not replace posted flags,
> lifeguards, or local officials.
