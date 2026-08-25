# AgentCore live Strands agent

This is the current AgentCore score-booster path. It is separate from the
historical MCP v2 compatibility spike and from the public API Gateway MCP
endpoint. The deployed runtime uses the same live-source normalization and
deterministic policy as the public path, then invokes one bounded Strands agent
only to retrieve facts and explain the immutable `RecommendationRecord`.
The public MCP endpoint remains API Gateway and Lambda; Lambda invokes this
runtime, so the runtime is not an anonymous judge endpoint.

The direct-code ZIP implements AgentCore's HTTP contract: `GET /ping` and `POST
/invocations` on port 8080. Its invocation body accepts only this structured
shape:

```json
{
  "input": {
    "date": "YYYY-MM-DD",
    "party_profile": {"skill_level": "beginner", "ages": [12, 40]},
    "preferred_area": "wrightsville-beach",
    "time_range": "morning"
  }
}
```

The runtime never accepts a model-generated policy decision. Live NWS, NOAA,
Open-Meteo, and explicit NC DEQ coverage evidence are normalized before
`policy.decide`; a model failure or invariant violation returns the template
brief with the same record.

## Current deployment and future approval gate

The current runtime was deployed after explicit approval using the personal
AWS account and `us-east-1`; the live smoke returned a structured record and
brief with `brief_source: agent`. It has public egress only to retrieve public
marine sources and has no public anonymous judge endpoint. Before any future
AWS change, reconfirm the caller identity, Nova Lite inference profile,
budget, retention, rollback, and smoke-test owner.

## Build and deploy after approval

Build a ZIP with Linux ARM64 dependencies, upload it to the private versioned
artifact bucket, and pass its bucket, key, and immutable S3 `VersionId` to
`infra/agentcore-live-agent/runtime.yaml`. No Docker build, ECR repository, or
container image is used by this Runtime. The runtime role is limited to reading
that exact ZIP, AgentCore logging, and invoking the fixed Nova Lite inference
profile.

```bash
uv run python scripts/package_agentcore_live_agent.py
```

After CloudFormation reports success, invoke the output `RuntimeArn` with:

```bash
uv run python scripts/run_agentcore_live_agent_smoke.py --runtime-arn '<RuntimeArn>'
```

The smoke passes only when AgentCore returns a record and brief, the agent has
called facts tools, output schema validation is true, and no immutable-policy
invariant is violated. Preserve the small evidence JSON, stop the runtime
session, and obtain separate approval before deleting the runtime stack.
