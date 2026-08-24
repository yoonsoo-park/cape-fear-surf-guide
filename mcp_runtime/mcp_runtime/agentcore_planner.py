"""Typed Lambda-to-AgentCore adapter for the judge-facing MCP service."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from surf.schema import PartyProfile, RecommendationRecord, SurfBrief


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentCorePlanningResult:
    record: RecommendationRecord
    brief: SurfBrief
    brief_source: str


class AgentCorePlanner:
    """Invoke one isolated AgentCore Runtime session per `find` request."""

    def __init__(self, runtime_arn: str, *, client: Any, qualifier: str = "DEFAULT") -> None:
        if not runtime_arn:
            raise ValueError("AgentCore runtime ARN is required")
        self.runtime_arn = runtime_arn
        self.client = client
        self.qualifier = qualifier

    @classmethod
    def from_environment(cls) -> "AgentCorePlanner":
        runtime_arn = os.environ.get("MCP_AGENTCORE_RUNTIME_ARN", "")
        region = os.environ.get("AWS_REGION", "us-east-1")
        try:
            import boto3
        except ImportError as error:  # pragma: no cover - Lambda supplies boto3
            raise RuntimeError("boto3 is required to invoke AgentCore Runtime") from error
        return cls(runtime_arn, client=boto3.client("bedrock-agentcore", region_name=region))

    def __call__(self, date: str, party_profile: dict[str, Any], preferred_area: str | None = None,
                 time_range: str | None = None) -> AgentCorePlanningResult | tuple[str, str, dict[str, Any]]:
        canonical_profile = _canonical_party_profile(party_profile)
        if isinstance(canonical_profile, tuple):
            return canonical_profile
        canonical_area = _canonical_preferred_area(preferred_area)
        if isinstance(canonical_area, tuple):
            return canonical_area
        payload = {"input": {"date": date, "party_profile": canonical_profile,
                               "preferred_area": canonical_area, "time_range": time_range}}
        try:
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.runtime_arn,
                qualifier=self.qualifier,
                runtimeSessionId=f"cape-fear-mcp-{uuid.uuid4().hex}",
                contentType="application/json",
                accept="application/json",
                payload=json.dumps(payload).encode(),
            )
            if response.get("statusCode", 200) != 200 or response.get("contentType") != "application/json":
                return "agentcore_unavailable", "The AgentCore planner did not return a valid response.", {}
            raw_body = response["response"].read()
            body = json.loads(raw_body)
        except Exception as error:
            LOGGER.warning("AgentCore invocation failed: %s", type(error).__name__)
            return "agentcore_unavailable", "The AgentCore planner is temporarily unavailable.", {}
        return _validated_result(body)


def _canonical_party_profile(party_profile: dict[str, Any]) -> dict[str, Any] | tuple[str, str, dict[str, Any]]:
    """Validate and normalize the public tool's profile before AgentCore.

    Some standard MCP hosts infer the generic ``dict`` schema as ``skill``
    instead of the canonical ``skill_level`` field. Accept that harmless alias
    at this adapter boundary, then send only the shared PartyProfile schema to
    AgentCore. Invalid input fails closed without spending a runtime call.
    """
    if not isinstance(party_profile, dict):
        return "invalid_party_profile", "party_profile must be an object.", {}
    candidate = dict(party_profile)
    if "skill_level" not in candidate and isinstance(candidate.get("skill"), str):
        candidate["skill_level"] = candidate.pop("skill")
    try:
        return PartyProfile.model_validate(candidate).model_dump(mode="json")
    except ValueError:
        return "invalid_party_profile", "party_profile does not satisfy the shared schema.", {}


def _canonical_preferred_area(preferred_area: str | None) -> str | None | tuple[str, str, dict[str, Any]]:
    """Accept the human-facing Wrightsville name but send the stable beach ID."""
    if preferred_area is None:
        return None
    if not isinstance(preferred_area, str):
        return "unsupported_area", "The public live demo supports Wrightsville Beach only.", {}
    normalized = "-".join(preferred_area.strip().lower().replace("_", " ").split())
    if normalized in {"wrightsville-beach", "wrightsville"}:
        return "wrightsville-beach"
    return "unsupported_area", "The public live demo supports Wrightsville Beach only.", {"preferred_area": preferred_area}


def _validated_result(body: Any) -> AgentCorePlanningResult | tuple[str, str, dict[str, Any]]:
    if not isinstance(body, dict) or not isinstance(body.get("output"), dict):
        return "agentcore_invalid_response", "The AgentCore planner returned an invalid response.", {}
    output = body["output"]
    if output.get("model_schema_valid") is not True or output.get("invariant_violations"):
        return "agentcore_policy_validation_failed", "The AgentCore planner response did not pass policy validation.", {}
    try:
        record = RecommendationRecord.model_validate(output["record"])
        brief = SurfBrief.model_validate(output["brief"])
    except Exception:
        return "agentcore_invalid_response", "The AgentCore planner returned an invalid response.", {}
    canonical_urls = tuple(item.source_url for item in record.evidence)
    if brief.window_id != record.window_id or brief.decision_state != record.decision.state:
        return "agentcore_policy_validation_failed", "The AgentCore planner changed immutable policy fields.", {}
    if brief.source_urls != canonical_urls or any(veto not in brief.warnings for veto in record.decision.vetoes):
        return "agentcore_policy_validation_failed", "The AgentCore planner changed immutable evidence.", {}
    brief_source = output.get("brief_source")
    if brief_source not in {"agent", "template"}:
        return "agentcore_invalid_response", "The AgentCore planner returned an invalid response.", {}
    return AgentCorePlanningResult(record=record, brief=brief, brief_source=brief_source)
