from __future__ import annotations

from dataclasses import dataclass
import json
import time
import uuid
from typing import Any

from strands import Agent
from strands.models import BedrockModel, Model

from .brief import template_brief
from .fixtures import load_fixture
from .intake import resolve_intake
from .planner_tools import PLANNER_TOOLS
from .policy import decide
from .schema import PartyProfile, RecommendationRecord, SurfBrief

MAX_RETRIEVAL_TURNS = 8
MAX_RETRIEVAL_TOTAL_TOKENS = 50_000


@dataclass(frozen=True)
class AgentPlanningResult:
    trace_id: str
    record: RecommendationRecord
    brief: SurfBrief
    brief_source: str
    tool_calls: tuple[dict[str, Any], ...]
    elapsed_ms: float
    estimated_cost_usd: float
    findings: tuple[str, ...]
    usage: dict[str, int]
    model_schema_valid: bool
    invariant_violations: tuple[str, ...]
    model_output_error: str | None


def bedrock_model(region: str, model_id: str, *, boto_session: Any | None = None) -> BedrockModel:
    config: dict[str, Any] = {"model_id": model_id, "temperature": 0, "max_tokens": 2_000}
    if boto_session is None:
        config["region_name"] = region
    else:
        # Strands reads the region from a supplied boto session and rejects a
        # second region argument, even when both values match.
        config["boto_session"] = boto_session
    return BedrockModel(**config)


def _usage(result: Any) -> dict[str, int]:
    """Preserve the provider-reported token counters without estimating them."""
    return {key: int(value) for key, value in result.metrics.accumulated_usage.items()}


def plan_fixture_with_agent(
    name: str, model: Model, *, profile_override: PartyProfile | None = None,
) -> AgentPlanningResult:
    started = time.perf_counter()
    snapshot_id, fixture_profile, window, fixture_evidence = load_fixture(name)
    profile = profile_override or fixture_profile
    state: dict[str, Any] = {
        "fixture_evidence": [item.model_dump(mode="json") for item in fixture_evidence],
        "tool_calls": [],
    }
    agent = Agent(
        name="surf_planner_agent", agent_id="surf_planner_agent", model=model, tools=PLANNER_TOOLS,
        callback_handler=None,
        system_prompt=(
            "Interpret the request and retrieve facts with tools. Tools return facts only. "
            "Never decide or claim safety, never alter measurements, and never invent a source URL."
        ),
    )
    intake_request = (
        f"Cape Fear reviewed profile: skill={profile.skill_level}; ages={','.join(map(str, profile.ages))}\n"
        "Return exactly this reviewed profile; do not infer, add, or remove fields. "
        f"PROFILE_JSON={profile.model_dump_json()}"
    )
    intake = resolve_intake(agent, intake_request)
    if intake.profile != profile:
        raise ValueError("agent intake profile does not match the reviewed fixture profile")
    retrieval_result = agent(
        "Retrieve the official hazard, water-quality, and supplemental marine facts for the fixture window. "
        "Call each tool name at most once. After you receive NWS hazards, water-quality status, and marine "
        "facts, reply RETRIEVAL_COMPLETE without another tool call. Do not retry, re-query, or loop; the "
        "reviewed policy receives the complete frozen evidence independently of tool selection.",
        invocation_state=state,
        # A tool loop is part of the billable agentic path. Cap it before a
        # repeated fact query can grow its own conversation context unboundedly.
        limits={"turns": MAX_RETRIEVAL_TURNS, "total_tokens": MAX_RETRIEVAL_TOTAL_TOKENS},
    )
    # The immutable record uses the complete frozen evidence set. Tool selection is
    # observable agent behavior, but it cannot select which facts reach policy.
    record = decide(snapshot_id, profile, window, fixture_evidence)
    fallback = template_brief(record)
    if retrieval_result.stop_reason != "end_turn":
        from .audit import audit_record
        return AgentPlanningResult(
            trace_id=str(uuid.uuid4()), record=record, brief=fallback, brief_source="template",
            tool_calls=tuple(state["tool_calls"]),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            estimated_cost_usd=0.0 if model.__class__.__name__ == "FixturePlannerModel" else -1.0,
            findings=audit_record(record), usage=_usage(retrieval_result), model_schema_valid=False,
            invariant_violations=(),
            model_output_error=f"retrieval_limit_reached:{retrieval_result.stop_reason}",
        )
    invariant_violations: list[str] = []
    model_output_error: str | None = None
    model_schema_valid = False
    try:
        canonical_urls = tuple(dict.fromkeys(item.source_url for item in record.evidence))
        canonical_warnings = record.decision.vetoes
        generated_result = agent(
            f"RECORD_JSON={record.model_dump_json()}\n"
            "Explain only this immutable record as SurfBrief. Copy `window_id`, "
            "`decision.state`, every URL in the evidence order, and every policy "
            "veto into the corresponding output field exactly, character for character. "
            "Do not paraphrase, omit, add, reorder, or infer any of those values.\n"
            f"REQUIRED_SOURCE_URLS_JSON={json.dumps(canonical_urls)}\n"
            f"REQUIRED_WARNINGS_JSON={json.dumps(canonical_warnings)}\n"
            "The `source_urls` and `warnings` fields MUST be exactly the two JSON arrays above.\n"
            "The explanation may be plain language, but it must not contradict the record.",
            structured_output_model=SurfBrief,
        )
        generated = generated_result.structured_output
        if not isinstance(generated, SurfBrief):
            raise ValueError("agent did not return the required SurfBrief schema")
        model_schema_valid = True
        if generated.window_id != record.window_id or generated.decision_state != record.decision.state:
            invariant_violations.append("immutable_policy_fields_changed")
        if generated.source_urls != canonical_urls:
            invariant_violations.append("source_urls_changed")
        if any(veto not in generated.warnings for veto in record.decision.vetoes):
            invariant_violations.append("deterministic_warning_removed")
        if invariant_violations:
            brief, source = fallback, "template"
        else:
            brief, source = generated, "agent"
    except Exception as error:
        model_output_error = f"{type(error).__name__}: {error}"
        brief, source = fallback, "template"
    from .audit import audit_record
    # Strands reports accumulated provider usage for the whole agent session on
    # the final result. Adding intermediate counters would double-count.
    usage = _usage(generated_result if "generated_result" in locals() else retrieval_result)
    return AgentPlanningResult(
        trace_id=str(uuid.uuid4()),
        record=record, brief=brief, brief_source=source, tool_calls=tuple(state["tool_calls"]),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        estimated_cost_usd=0.0 if model.__class__.__name__ == "FixturePlannerModel" else -1.0,
        findings=audit_record(record),
        usage=usage,
        model_schema_valid=model_schema_valid,
        invariant_violations=tuple(invariant_violations),
        model_output_error=model_output_error,
    )
