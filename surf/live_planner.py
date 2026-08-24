"""Live, deterministic planning path used by the public MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from .brief import template_brief
from .live_sources import fetch_live_evidence
from .policy import decide
from .schema import BeachWindow, PartyProfile, RecommendationRecord, SurfBrief


@dataclass(frozen=True)
class LivePlanningResult:
    record: RecommendationRecord
    brief: SurfBrief
    brief_source: str = "template"


def validate_live_request(requested_date: str, party_profile: dict[str, Any], preferred_area: str | None,
                          time_range: str | None, *, today: date | None = None) -> tuple[date, PartyProfile, str] | tuple[str, str, dict[str, Any]]:
    try:
        requested = date.fromisoformat(requested_date)
    except ValueError:
        return "invalid_date", "date must use ISO-8601 YYYY-MM-DD", {"date": requested_date}
    eastern_today = today or datetime.now(ZoneInfo("America/New_York")).date()
    if requested < eastern_today or requested > eastern_today + timedelta(days=6):
        return "date_out_of_range", "date must be from today through six days ahead in America/New_York", {"date": requested_date, "today": eastern_today.isoformat()}
    if preferred_area not in (None, "wrightsville-beach"):
        return "unsupported_area", "The public live demo supports Wrightsville Beach only.", {"preferred_area": preferred_area}
    if time_range not in (None, "morning", "afternoon"):
        return "invalid_time_range", "time_range must be morning or afternoon when supplied.", {"time_range": time_range}
    try:
        profile = PartyProfile.model_validate(party_profile)
    except ValueError as error:
        return "invalid_party_profile", "party_profile does not satisfy the shared schema", {"reason": str(error)}
    return requested, profile, time_range or "morning"


def plan_live(requested_date: str, party_profile: dict[str, Any], preferred_area: str | None = None,
              time_range: str | None = None, *, now: datetime | None = None, today: date | None = None,
              fetcher: Any = fetch_live_evidence) -> LivePlanningResult | tuple[str, str, dict[str, Any]]:
    validated = validate_live_request(requested_date, party_profile, preferred_area, time_range, today=today)
    if isinstance(validated[0], str):
        return validated
    requested, profile, resolved_range = validated
    evidence = fetcher(requested, now=now)
    conditions = next((item.facts.get("hours", {}) for item in evidence if item.source_kind == "marine_forecast"), {})
    selected_time = _select_hour(requested, resolved_range, conditions)
    values = conditions.get(selected_time, {})
    zone = ZoneInfo("America/New_York")
    starts = datetime.combine(requested, time.fromisoformat(selected_time.split("T", 1)[1]), tzinfo=zone)
    window = BeachWindow(
        beach_id="wrightsville-beach", starts_at=starts, ends_at=starts + timedelta(hours=1),
        wave_height_m=values.get("wave_height_m"), swell_period_s=values.get("swell_period_s"), wind_kmh=values.get("wind_kmh"),
    )
    deterministic = decide(f"live:{requested.isoformat()}", profile, window, evidence)
    record = deterministic.model_copy(update={"window_id": uuid4().hex})
    return LivePlanningResult(record=record, brief=template_brief(record))


def _select_hour(requested: date, time_range: str, conditions: dict[str, Any]) -> str:
    preferred_hour = 9 if time_range == "morning" else 15
    prefix = requested.isoformat()
    candidates = sorted(key for key in conditions if key.startswith(prefix))
    if not candidates:
        # Missing required Open-Meteo data is already an insufficient-data policy state.
        return f"{prefix}T{preferred_hour:02d}:00"
    return min(candidates, key=lambda value: abs(int(value[11:13]) - preferred_hour))
