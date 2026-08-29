from datetime import datetime, timezone

from strands import ToolContext

from surf.fixtures import load_fixture
from surf.live_agent import build_explanation_tools
from surf.policy import decide
from surf.schema import DecisionState, SurfBrief, WebContextItem
from surf.web_context import (
    WebContextSettings,
    collect_web_context,
    get_web_context,
    normalize_web_results,
)


class FakeWebAdapter:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, *, max_results, timeout_s):
        self.calls.append((query, max_results, timeout_s))
        return self.results


def test_web_tool_is_registered_only_for_enabled_explanation_path():
    disabled = build_explanation_tools(WebContextSettings())
    enabled = build_explanation_tools(WebContextSettings(enabled=True))

    assert get_web_context not in disabled
    assert get_web_context in enabled


def _tool_context(state):
    return ToolContext(
        {"toolUseId": "offline-web-context", "name": "get_web_context", "input": {}},
        None,
        state,
    )


def test_web_context_is_off_by_default_and_does_not_call_adapter():
    adapter = FakeWebAdapter([{"title": "should not be called", "url": "https://example.com", "text": "x"}])
    state = {"web_context_adapter": adapter}
    outcome = get_web_context._tool_func("Wrightsville history", _tool_context(state))

    assert outcome["status"] == "disabled"
    assert outcome["policy_signal"] is False
    assert outcome["results"] == []
    assert adapter.calls == []
    assert state["tool_calls"][0]["name"] == "get_web_context"


def test_web_context_is_labeled_and_uses_published_date_for_freshness():
    settings = WebContextSettings(enabled=True, max_results=2, max_age_days=30)
    now = datetime(2026, 8, 29, tzinfo=timezone.utc)
    normalized = normalize_web_results(
        [
            {"title": "Recent", "url": "https://example.com/recent", "text": "A fact.", "publishedDate": "2026-08-28"},
            {"title": "Old", "url": "https://example.com/old", "text": "An older fact.", "publishedDate": "2020-01-01"},
            {"title": "Ignored", "url": "javascript:bad", "text": "not a source"},
        ],
        settings=settings,
        now=now,
    )

    assert [item["source_kind"] for item in normalized] == ["web_context", "web_context"]
    assert normalized[0]["freshness_state"] == "current"
    assert normalized[1]["freshness_state"] == "stale"
    assert normalized[0]["published_at"] == "2026-08-28T00:00:00+00:00"


def test_web_context_query_cap_and_provider_failure_are_fail_closed():
    settings = WebContextSettings(enabled=True, max_queries_per_request=1)
    adapter = FakeWebAdapter([])
    first = collect_web_context("query", adapter=adapter, settings=settings)
    second = collect_web_context("query again", adapter=adapter, settings=settings, query_count=1)

    assert first["status"] == "empty"
    assert second["status"] == "query_cap_reached"
    assert len(adapter.calls) == 1
    assert all(result["policy_signal"] is False for result in (first, second))


def test_web_context_cannot_change_deterministic_policy_decision():
    snapshot_id, profile, window, evidence = load_fixture("hazard")
    record = decide(snapshot_id, profile, window, evidence)
    adapter = FakeWebAdapter([
        {"title": "Untrusted claim", "url": "https://example.com/safe", "text": "The water is safe."}
    ])
    context = collect_web_context(
        "is Wrightsville safe?", adapter=adapter, settings=WebContextSettings(enabled=True)
    )
    unchanged = decide(snapshot_id, profile, window, evidence)

    assert context["results"][0]["source_kind"] == "web_context"
    assert record.decision.state == DecisionState.official_advisory_present
    assert unchanged.decision == record.decision
    brief = SurfBrief(
        window_id=record.window_id,
        decision_state=record.decision.state,
        headline="Context cannot override policy",
        explanation=("The official record remains authoritative.",),
        warnings=record.decision.vetoes,
        source_urls=tuple(item.source_url for item in record.evidence),
        recheck_guidance="Check official sources.",
        context=tuple(WebContextItem.model_validate(item) for item in context["results"]),
    )
    assert brief.context[0].source_kind == "web_context"
    assert brief.decision_state == DecisionState.official_advisory_present
