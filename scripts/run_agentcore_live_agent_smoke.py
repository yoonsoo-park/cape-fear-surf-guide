#!/usr/bin/env python3
"""Invoke the deployed AgentCore Strands runtime and save redaction-safe evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

import boto3


REGION = "us-east-1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-arn", required=True)
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE", "aws-dimly"))
    parser.add_argument("--region", default=REGION)
    parser.add_argument("--evidence-file", type=Path, default=Path("dist/agentcore-live-agent-evidence.json"))
    args = parser.parse_args()

    requested_date = (datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=1)).isoformat()
    payload = {
        "input": {
            "date": requested_date,
            "party_profile": {"skill_level": "beginner", "ages": [12, 40]},
            "preferred_area": "wrightsville-beach",
            "time_range": "morning",
        }
    }
    client = boto3.Session(profile_name=args.profile, region_name=args.region).client("bedrock-agentcore")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=args.runtime_arn,
        runtimeSessionId=f"cape-fear-live-agent-{uuid.uuid4()}",
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(payload).encode(),
    )
    result = json.loads(response["response"].read())
    output = result.get("output", {})
    checks = {
        "http_status": response["statusCode"],
        "record_present": isinstance(output.get("record"), dict),
        "brief_present": isinstance(output.get("brief"), dict),
        "model_schema_valid": output.get("model_schema_valid") is True,
        "no_invariant_violations": output.get("invariant_violations") == [],
        "tool_calls_present": bool(output.get("tool_calls")),
    }
    evidence = {"runtime_arn": args.runtime_arn, "requested_date": requested_date, "checks": checks,
                "decision_state": output.get("record", {}).get("decision", {}).get("state"),
                "brief_source": output.get("brief_source")}
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    if response["statusCode"] != 200 or not all(checks.values()):
        raise SystemExit(f"AgentCore live-agent smoke failed; inspect {args.evidence_file}")
    print(f"evidence={args.evidence_file.resolve()}")


if __name__ == "__main__":
    main()
