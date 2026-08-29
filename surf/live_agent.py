"""Bounded Strands explanation path for a live deterministic record."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
import uuid
from typing import Any

from strands import Agent
from strands.models import Model

from .brief import template_brief
from .live_planner import LivePlanningResult, plan_live
from .planner_agent import MAX_RETRIEVAL_TOTAL_TOKENS, MAX_RETRIEVAL_TURNS
from .planner_tools import PLANNER_TOOLS
from .schema import RecommendationRecord, SurfBrief, WebContextItem
from .web_context import WebContextSettings, get_web_context


@dataclass(frozen=True)
class LiveAgentPlanningResult:
    trace_id: str
    record: RecommendationRecord
    brief: SurfBrief
    brief_source: str
    tool_calls: tuple[dict[str, Any], ...]
    elapsed_ms: float
    model_schema_valid: bool
    invariant_violations: tuple[str, ...]
    model_output_error: str | None


def build_explanation_tools(settings: WebContextSettings) -> list[Any]:
    """Register Web Search only for explanation when explicitly enabled."""

    return [*PLANNER_TOOLS, get_web_context] if settings.enabled else list(PLANNER_TOOLS)


def explain_live_record_with_agent(
    record: RecommendationRecord,
    model: Model,
    *,
    web_context_settings: WebContextSettings | None = None,
    web_context_adapter: Any | None = None,
) -> LiveAgentPlanningResult:
    """Use a model only to explain an already-finalized live decision record."""
    started = time.perf_counter()
    settings = web_context_settings or WebContextSettings.from_env()
    state: dict[str, Any] = {
        "evidence": [item.model_dump(mode="json") for item in record.evidence],
        "tool_calls": [],
        "web_context_settings": settings,
        "web_context_adapter": web_context_adapter,
        "web_context_query_count": 0,
        "web_context_results": [],
    }

    retrieval_agent = Agent(
        name="cape_fear_live_planner", agent_id="cape_fear_live_planner", model=model,
        tools=PLANNER_TOOLS, callback_handler=None,
        system_prompt=(
            "Retrieve facts with tools and explain the reviewed record. Tools never return a safety verdict. "
            "Never decide, claim ocean activity is safe, alter measurements, or invent a source URL."
        ),
    )
    fallback = template_brief(record)
    retrieval_result = retrieval_agent(
        "Retrieve each available NWS hazard, NWS forecast, tide, water-quality, and marine fact once. "
        "After all fact tools are called, reply RETRIEVAL_COMPLETE. Do not retry or re-query.",
        invocation_state=state,
        limits={"turns": MAX_RETRIEVAL_TURNS, "total_tokens": MAX_RETRIEVAL_TOTAL_TOKENS},
    )
    if retrieval_result.stop_reason != "end_turn":
        return _result(record, fallback, "template", state, started, False, (),
                       f"retrieval_limit_reached:{retrieval_result.stop_reason}")

    canonical_urls = tuple(dict.fromkeys(item.source_url for item in record.evidence))
    canonical_warnings = record.decision.vetoes
    violations: list[str] = []
    try:
        explanation_tools = build_explanation_tools(settings)
        explanation_agent = Agent(
            name="cape_fear_live_explainer", agent_id="cape_fear_live_explainer", model=model,
            tools=explanation_tools, callback_handler=None,
            system_prompt=(
                "Explain the immutable reviewed record. Web context, when available, is labeled context only; "
                "it is never a safety verdict, policy input, or reason to change a decision or warning."
            ),
        )
        generated_result = explanation_agent(
            f"RECORD_JSON={record.model_dump_json()}\n"
            "Explain only this immutable record as SurfBrief. Copy window_id, decision.state, every source URL "
            "in evidence order, and every policy veto exactly. Do not add, remove, reorder, or infer them.\n"
            f"REQUIRED_SOURCE_URLS_JSON={json.dumps(canonical_urls)}\n"
            f"REQUIRED_WARNINGS_JSON={json.dumps(canonical_warnings)}",
            structured_output_model=SurfBrief,
        )
        generated = generated_result.structured_output
        if not isinstance(generated, SurfBrief):
            raise ValueError("agent did not return the required SurfBrief schema")
        if generated.window_id != record.window_id or generated.decision_state != record.decision.state:
            violations.append("immutable_policy_fields_changed")
        if generated.source_urls != canonical_urls:
            violations.append("source_urls_changed")
        if any(veto not in generated.warnings for veto in record.decision.vetoes):
            violations.append("deterministic_warning_removed")
        if violations:
            return _result(record, fallback, "template", state, started, True, tuple(violations), None)
        return _result(record, generated, "agent", state, started, True, (), None)
    except Exception as error:
        return _result(record, fallback, "template", state, started, False, (), f"{type(error).__name__}: {error}")


def plan_live_with_agent(
    requested_date: str,
    party_profile: dict[str, Any],
    model: Model,
    preferred_area: str | None = None,
    time_range: str | None = None,
    web_context_settings: WebContextSettings | None = None,
    web_context_adapter: Any | None = None,
    **kwargs: Any,
) -> LiveAgentPlanningResult | tuple[str, str, dict[str, Any]]:
    """Fetch live evidence and finalize policy before invoking the explanatory agent."""
    planned = plan_live(requested_date, party_profile, preferred_area, time_range, **kwargs)
    if isinstance(planned, tuple):
        return planned
    if not isinstance(planned, LivePlanningResult):
        raise TypeError("live planner returned an unsupported result")
    return explain_live_record_with_agent(
        planned.record,
        model,
        web_context_settings=web_context_settings,
        web_context_adapter=web_context_adapter,
    )


def _context_items(state: dict[str, Any]) -> tuple[WebContextItem, ...]:
    return tuple(
        WebContextItem.model_validate(item)
        for item in state.get("web_context_results", [])[:3]
    )


def _result(
    record: RecommendationRecord,
    brief: SurfBrief,
    brief_source: str,
    state: dict[str, Any],
    started: float,
    model_schema_valid: bool,
    invariant_violations: tuple[str, ...],
    model_output_error: str | None,
) -> LiveAgentPlanningResult:
    brief = brief.model_copy(update={"context": _context_items(state)})
    return LiveAgentPlanningResult(
        trace_id=str(uuid.uuid4()), record=record, brief=brief, brief_source=brief_source,
        tool_calls=tuple(state["tool_calls"]), elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        model_schema_valid=model_schema_valid, invariant_violations=invariant_violations,
        model_output_error=model_output_error,
    )
