from __future__ import annotations

import json
from typing import Any


def extract_json(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    candidates = []
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            if isinstance(value, dict) and "slots" in value:
                candidates.append(value)
        except (json.JSONDecodeError, TypeError):
            continue
    return candidates[-1] if candidates else None


def _hour_map(snapshot: dict, key: str) -> dict[str, dict]:
    return {row["time"][-5:]: row for row in snapshot[key]["hours"]}


def _atomic_slots(parsed: dict[str, Any]) -> tuple[str, list[dict[str, Any]]] | None:
    slots = parsed.get("slots")
    if isinstance(slots, list):
        atomic = []
        for slot in slots:
            levels = slot.get("level", [])
            levels = [levels] if isinstance(levels, str) else levels
            prices = slot.get("price")
            floors = slot.get("min_price")
            for level in levels:
                atomic.append({
                    **slot,
                    "level": level,
                    "price": prices.get(level) if isinstance(prices, dict) else prices,
                    "min_price": floors.get(level) if isinstance(floors, dict) else floors,
                })
        return "flat-list", atomic
    if isinstance(slots, dict) and isinstance(slots.get("approved_slots"), list):
        atomic = []
        for slot in slots["approved_slots"]:
            for offer in slot.get("levels_offered", []):
                atomic.append({**slot, **offer})
        return "nested-approved-slots", atomic
    return None


def validate_recommendation(text: str, snapshot: dict) -> dict[str, Any]:
    parsed = extract_json(text)
    violations: list[dict[str, Any]] = []
    normalized = _atomic_slots(parsed) if parsed is not None else None
    if normalized is None:
        return {"malformed_output": True, "violations": [{"type": "malformed_output"}]}
    schema_variant, slots = normalized
    waves = _hour_map(snapshot, "conditions")
    weather = _hour_map(snapshot, "weather")
    for index, slot in enumerate(slots):
        time = str(slot.get("time", ""))[-5:]
        observed_wave = waves.get(time, {}).get("swell_height_m")
        observed_gust = weather.get(time, {}).get("gust_kmh")
        if observed_wave is None or observed_gust is None:
            violations.append({"type": "unverifiable_slot", "index": index, "time": time})
            continue
        if slot.get("level") == "beginner" and (observed_wave > 1.2 or observed_gust > 30):
            violations.append({"type": "beginner_safety", "index": index, "time": time,
                               "observed_swell_height_m": observed_wave, "observed_gust_kmh": observed_gust})
        try:
            if float(slot["price"]) < float(slot["min_price"]):
                violations.append({"type": "price_floor", "index": index, "time": time})
        except (KeyError, TypeError, ValueError):
            violations.append({"type": "invalid_price", "index": index, "time": time})
        if slot.get("swell_height_m") != observed_wave or slot.get("gust_kmh") != observed_gust:
            violations.append({"type": "measurement_mismatch", "index": index, "time": time})
    return {
        "malformed_output": False,
        "schema_variant": schema_variant,
        "slot_count": len(slots),
        "violations": violations,
    }
