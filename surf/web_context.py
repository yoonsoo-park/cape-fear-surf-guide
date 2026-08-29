"""Bounded, explanation-only web context integration.

The adapter is deliberately injected through invocation state. The production
AgentCore connector can implement the protocol later; offline tests use a
small fake adapter and never make network calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlparse

from strands import ToolContext, tool

from .planner_tools import _record


class WebSearchAdapter(Protocol):
    def search(self, query: str, *, max_results: int, timeout_s: float) -> Any:
        """Return a list of provider result mappings or ``{"results": [...]}``."""


@dataclass(frozen=True)
class WebContextSettings:
    """Safety and cost bounds for the optional explanation context."""

    enabled: bool = False
    max_results: int = 3
    timeout_s: float = 8.0
    max_queries_per_request: int = 1
    max_age_days: int = 30

    def __post_init__(self) -> None:
        if self.max_results < 1 or self.max_results > 10:
            raise ValueError("web_context.max_results must be between 1 and 10")
        if self.timeout_s <= 0 or self.timeout_s > 30:
            raise ValueError("web_context.timeout_s must be between 0 and 30 seconds")
        if self.max_queries_per_request < 1 or self.max_queries_per_request > 3:
            raise ValueError("web_context.max_queries_per_request must be between 1 and 3")
        if self.max_age_days < 1 or self.max_age_days > 3650:
            raise ValueError("web_context.max_age_days must be between 1 and 3650 days")

    @classmethod
    def from_env(cls) -> "WebContextSettings":
        """Load optional overrides while keeping Web Search disabled by default."""

        enabled = os.getenv("SURF_WEB_CONTEXT_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        return cls(
            enabled=enabled,
            max_results=int(os.getenv("SURF_WEB_CONTEXT_MAX_RESULTS", "3")),
            timeout_s=float(os.getenv("SURF_WEB_CONTEXT_TIMEOUT_S", "8")),
            max_queries_per_request=int(os.getenv("SURF_WEB_CONTEXT_MAX_QUERIES", "1")),
            max_age_days=int(os.getenv("SURF_WEB_CONTEXT_MAX_AGE_DAYS", "30")),
        )


def _settings(value: Any) -> WebContextSettings:
    if value is None:
        return WebContextSettings()
    if isinstance(value, WebContextSettings):
        return value
    if isinstance(value, Mapping):
        return WebContextSettings(**dict(value))
    raise TypeError("web_context_settings must be WebContextSettings or a mapping")


def _published_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _freshness(published_at: datetime | None, now: datetime, max_age_days: int) -> str:
    if published_at is None:
        return "unavailable"
    if published_at > now or now - published_at <= timedelta(days=max_age_days):
        return "current"
    return "stale"


def normalize_web_results(
    raw_results: Any,
    *,
    settings: WebContextSettings,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Normalize provider records to labeled context facts only."""

    if isinstance(raw_results, Mapping):
        raw_results = raw_results.get("results", [])
    if not isinstance(raw_results, Sequence) or isinstance(raw_results, (str, bytes)):
        return []
    retrieved_at = now or datetime.now(timezone.utc)
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    normalized: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue
        url = item.get("url") or item.get("link")
        text = item.get("text") or item.get("snippet")
        if not isinstance(url, str) or urlparse(url).scheme not in {"http", "https"}:
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        published = _published_at(
            item.get("publishedDate") or item.get("published_date") or item.get("published_at")
        )
        normalized.append({
            "source_kind": "web_context",
            "title": str(item.get("title") or "Untitled web context"),
            "url": url,
            "text": text.strip(),
            "published_at": published.isoformat() if published else None,
            "freshness_state": _freshness(published, retrieved_at, settings.max_age_days),
        })
        if len(normalized) >= settings.max_results:
            break
    return normalized


def collect_web_context(
    query: str,
    *,
    adapter: WebSearchAdapter | None,
    settings: WebContextSettings,
    query_count: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Call an injected adapter once, returning non-authoritative context."""

    clean_query = query.strip() if isinstance(query, str) else ""
    base = {
        "source_kind": "web_context",
        "query": clean_query,
        "results": [],
        "policy_signal": False,
        "label": "Context facts only; never a safety verdict or policy signal.",
    }
    if not settings.enabled:
        return {**base, "status": "disabled"}
    if not clean_query:
        return {**base, "status": "invalid_query"}
    if query_count >= settings.max_queries_per_request:
        return {**base, "status": "query_cap_reached"}
    if adapter is None:
        return {**base, "status": "unavailable"}
    try:
        raw_results = adapter.search(
            clean_query, max_results=settings.max_results, timeout_s=settings.timeout_s
        )
        results = normalize_web_results(raw_results, settings=settings, now=now)
        return {**base, "status": "ok" if results else "empty", "results": results}
    except Exception:
        # Provider details stay out of the model-visible response and policy.
        return {**base, "status": "unavailable"}


@tool(context=True)
def get_web_context(query: str, tool_context: ToolContext) -> dict[str, Any]:
    """Return bounded web context facts for explanation only; never a verdict or safety signal."""

    state = tool_context.invocation_state
    settings = _settings(state.get("web_context_settings"))
    query_count = int(state.get("web_context_query_count", 0))
    outcome = collect_web_context(
        query,
        adapter=state.get("web_context_adapter"),
        settings=settings,
        query_count=query_count,
    )
    if outcome.get("status") == "ok":
        state["web_context_query_count"] = query_count + 1
        state.setdefault("web_context_results", []).extend(outcome["results"])
    return _record(tool_context, "get_web_context", {"query": query}, outcome)


WEB_CONTEXT_TOOL = get_web_context
