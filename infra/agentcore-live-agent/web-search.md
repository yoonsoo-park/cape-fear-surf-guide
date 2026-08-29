# Private AgentCore Web Search target

This directory's existing Runtime templates are separate from the public MCP
API Gateway/Lambda path. `scripts/setup_web_search_target.py` manages a
dedicated, private AgentCore Gateway target for explanation context only; it
does not change the public endpoint.

## Verified connector contract (2026-08-29)

- Region: `us-east-1`.
- Gateway: MCP protocol with `AWS_IAM` inbound authorization.
- Target name: `web-search-tool`.
- Connector source: `connectorId: web-search`, pinned by default to `1.1.0`.
- Configuration: `name: WebSearch`, empty `parameterValues`.
- Credential provider: `GATEWAY_IAM_ROLE`.
- Gateway role actions: `bedrock-agentcore:InvokeGateway` on the dedicated
  gateway ARN and `bedrock-agentcore:InvokeWebSearch` on
  `arn:aws:bedrock-agentcore:us-east-1:aws:tool/web-search.v1`.

The Gateway exposes the managed connector as an MCP `WebSearchTool`. Its
results are normalized as `source_kind=web_context` and are never passed to
`policy.decide` or mapped to an advisory/veto.

## Guarded lifecycle

Inspect the private resources (read-only):

```bash
PYTHONPATH=. uv run python scripts/setup_web_search_target.py \
  --action describe --account 831597648506 --region us-east-1 --profile aws-dimly
```

After a separately recorded human approval for the live Web Search stage:

```bash
PYTHONPATH=. uv run python scripts/setup_web_search_target.py \
  --action apply --confirm-live --account 831597648506 \
  --region us-east-1 --profile aws-dimly
```

Capture only the sanitized JSON summary, run the private MCP `tools/list` and
one bounded `WebSearchTool` smoke, then tear down the target, Gateway, and
role:

```bash
PYTHONPATH=. uv run python scripts/setup_web_search_target.py \
  --action delete --confirm-live --account 831597648506 \
  --region us-east-1 --profile aws-dimly
```

The script refuses all other accounts, nCino/company profile names, regions
other than `us-east-1`, and mutating actions without `--confirm-live`.
