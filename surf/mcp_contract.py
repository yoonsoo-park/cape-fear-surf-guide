"""Stateless, frozen-record lookup used by the MCP v2 runtime.

The MCP runtime deliberately rebuilds this registry on every request.  A
``window_id`` is a hash, so the frozen snapshot is the durable lookup source;
no process-local cache or protocol session is needed to explain a window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .application import PlanningResult, plan_fixture
from .schema import PartyProfile

FROZEN_MCP_FIXTURES = ("normal", "hazard", "stale", "conflict")


@dataclass(frozen=True)
class ContractError:
    code: str
    message: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"resultType": "error", "error": {"code": self.code, "message": self.message, "details": self.details}}


def _records() -> tuple[PlanningResult, ...]:
    """Rebuild the reviewed frozen records instead of retaining request state."""
    return tuple(plan_fixture(name) for name in FROZEN_MCP_FIXTURES)


def find_frozen_windows(
    requested_date: str,
    party_profile: dict[str, Any],
    preferred_area: str | None = None,
    time_range: str | None = None,
) -> tuple[PlanningResult, ...] | ContractError:
    """Find the reviewed normal snapshot matching a frozen-demo request.

    This is intentionally explicit about its scope.  The Phase 2 MCP demo
    never silently substitutes a different date, beach, or party profile for
    the caller's request.
    """
    try:
        parsed_date = date.fromisoformat(requested_date)
    except ValueError:
        return ContractError("invalid_date", "date must use ISO-8601 YYYY-MM-DD", {"date": requested_date})
    try:
        requested_profile = PartyProfile.model_validate(party_profile)
    except ValueError as error:
        return ContractError("invalid_party_profile", "party_profile does not satisfy the shared schema", {"reason": str(error)})

    normal = plan_fixture("normal")
    if parsed_date != normal.record.window.starts_at.date():
        return ContractError(
            "snapshot_unavailable",
            "No reviewed frozen snapshot covers the requested date.",
            {"date": requested_date, "available_date": normal.record.window.starts_at.date().isoformat()},
        )
    if preferred_area is not None and preferred_area != normal.record.window.beach_id:
        return ContractError(
            "snapshot_unavailable",
            "No reviewed frozen snapshot covers the requested beach.",
            {"preferred_area": preferred_area, "available_area": normal.record.window.beach_id},
        )
    if time_range not in (None, "morning", "12:00-14:00Z"):
        return ContractError(
            "snapshot_unavailable",
            "No reviewed frozen snapshot covers the requested time range.",
            {"time_range": time_range, "available_time_range": "12:00-14:00Z"},
        )
    if requested_profile != normal.record.profile:
        return ContractError(
            "snapshot_unavailable",
            "The reviewed frozen demo has no record for this party profile.",
            {"available_profile": normal.record.profile.model_dump(mode="json")},
        )
    return (normal,)


def explain_frozen_window(window_id: str) -> PlanningResult | ContractError:
    """Resolve a frozen record from disk-derived inputs on every call."""
    for result in _records():
        if result.record.window_id == window_id:
            return result
    return ContractError(
        "unknown_window_id",
        "window_id is not present in a reviewed frozen snapshot.",
        {"window_id": window_id},
    )
