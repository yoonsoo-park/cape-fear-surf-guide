from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ..schema import EvidenceItem, FreshnessState


def normalize_hourly_marine(conditions: dict, weather: dict, *, location: str,
                            timezone_name: str, retrieved_at: datetime) -> tuple[EvidenceItem, ...]:
    """Normalize captured Open-Meteo arrays into auditable hourly evidence."""
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    weather_by_time = {item["time"]: item for item in weather.get("hours", [])}
    items: list[EvidenceItem] = []
    timezone = ZoneInfo(timezone_name)
    for marine in conditions.get("hours", []):
        if marine["time"] not in weather_by_time:
            raise ValueError(f"weather is missing the marine hour {marine['time']}")
        local_time = datetime.fromisoformat(marine["time"])
        if local_time.tzinfo is None:
            local_time = local_time.replace(tzinfo=timezone)
        weather_hour = weather_by_time[marine["time"]]
        facts = {**{key: value for key, value in marine.items() if key != "time"},
                 **{key: value for key, value in weather_hour.items() if key != "time"}}
        items.append(EvidenceItem(
            source_name="Open-Meteo Marine and Weather", source_url="https://open-meteo.com/",
            source_kind="marine_forecast", issued_at=retrieved_at,
            valid_from=local_time, valid_until=local_time.replace(minute=59, second=59),
            retrieved_at=retrieved_at, location=location, facts=facts,
            freshness_state=FreshnessState.current, original_timezone=timezone_name,
            raw_reference=f"open-meteo:{location}:{marine['time']}",
        ))
    return tuple(items)
