# AgentCore live Strands agent

This is the current AgentCore score-booster path. It is separate from the
historical MCP v2 compatibility spike and from the public API Gateway MCP
endpoint. The runtime uses the same live-source normalization and deterministic
policy as the public path, then invokes one bounded Strands agent only to
retrieve facts and explain the immutable `RecommendationRecord`.

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

## Approval gate

No deployment is authorized by this document. Before any AWS action, confirm
the `personal` account `831597648506`, region `us-east-1`, caller identity,
Nova Lite inference profile `us.amazon.nova-lite-v1:0`, a budget ceiling,
retention, rollback, and smoke-test owner. This runtime has public egress only
to retrieve public marine sources; it has no public anonymous judge endpoint.

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
