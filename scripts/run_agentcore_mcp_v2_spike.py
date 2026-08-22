#!/usr/bin/env python3
"""Invoke the deployed AgentCore MCP runtime and emit redaction-safe evidence."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

import boto3


PROTOCOL_VERSION = "2026-07-28"
PROFILE = "personal"
REGION = "us-east-1"


def request(name: str, arguments: dict[str, Any], request_id: int) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }


def invoke(client: Any, runtime_arn: str, body: dict[str, Any], *, method: str, name: str) -> tuple[int, Any]:
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=f"cape-fear-spike-{uuid.uuid4()}",
        contentType="application/json",
        # AgentCore's MCP service contract requires both response formats even
        # when this stateless server elects the JSON response path.
        accept="application/json, text/event-stream",
        mcpProtocolVersion=PROTOCOL_VERSION,
        mcpMethod=method,
        mcpName=name,
        payload=json.dumps(body).encode(),
    )
    payload = response["response"].read().decode()
    try:
        return response["statusCode"], json.loads(payload)
    except json.JSONDecodeError:
        return response["statusCode"], {"raw_response": payload[:2000]}


def _find_first_window_id(value: Any) -> str | None:
    if isinstance(value, dict):
        if isinstance(value.get("window_id"), str):
            return value["window_id"]
        for child in value.values():
            found = _find_first_window_id(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_first_window_id(child)
            if found:
                return found
    return None


def _is_agentcore_wrapped_protocol_error(status: int, value: Any) -> bool:
    """AgentCore maps the container's HTTP 400 to MCP JSON-RPC -32010/HTTP 200."""
    return (
        status == 200
        and isinstance(value, dict)
        and value.get("error", {}).get("code") == -32010
    )


def _is_unknown_window_tool_error(status: int, value: Any) -> bool:
    try:
        result = value["result"]
        return (
            status == 200
            and result["isError"] is True
            and result["structuredContent"]["error"]["code"] == "unknown_window_id"
        )
    except (KeyError, TypeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-arn", required=True)
    parser.add_argument("--evidence-file", type=Path, default=Path("dist/agentcore-mcp-v2-spike-evidence.json"))
    args = parser.parse_args()

    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    client = session.client("bedrock-agentcore")
    first_body = request(
        "find_surf_windows",
        {"date": "2026-08-29", "party_profile": {"skill_level": "beginner", "ages": [12, 40]}},
        1,
    )
    find_status, find_result = invoke(client, args.runtime_arn, first_body, method="tools/call", name="find_surf_windows")
    window_id = _find_first_window_id(find_result)
    if find_status != 200 or window_id is None:
        raise SystemExit(f"find_surf_windows failed: status={find_status}, response={json.dumps(find_result, sort_keys=True)}")

    explain_status, explain_result = invoke(
        client, args.runtime_arn, request("explain_surf_window", {"window_id": window_id}, 2),
        method="tools/call", name="explain_surf_window",
    )
    mismatch_status, mismatch_result = invoke(
        client, args.runtime_arn, first_body, method="tools/list", name="find_surf_windows",
    )
    unknown_status, unknown_result = invoke(
        client, args.runtime_arn, request("explain_surf_window", {"window_id": "does-not-exist"}, 3),
        method="tools/call", name="explain_surf_window",
    )

    evidence = {
        "runtime_arn": args.runtime_arn,
        "protocol_version": PROTOCOL_VERSION,
        "checks": {
            "find": {"status": find_status, "response": find_result},
            "explain_fresh_session": {"status": explain_status, "response": explain_result},
            "header_method_mismatch": {"status": mismatch_status, "response": mismatch_result},
            "unknown_window": {"status": unknown_status, "response": unknown_result},
        },
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    if not (
        explain_status == 200
        and _is_agentcore_wrapped_protocol_error(mismatch_status, mismatch_result)
        and _is_unknown_window_tool_error(unknown_status, unknown_result)
    ):
        raise SystemExit(f"compatibility spike failed; inspect {args.evidence_file}")
    print(f"evidence={args.evidence_file.resolve()}")


if __name__ == "__main__":
    main()
