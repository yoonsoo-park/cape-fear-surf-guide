from __future__ import annotations

from .schema import RecommendationRecord


def audit_record(record: RecommendationRecord) -> tuple[str, ...]:
    findings: list[str] = []
    marine = [item for item in record.evidence if item.source_kind == "marine_forecast"]
    if record.window.wave_height_m is not None:
        observed = {item.facts.get("wave_height_m") for item in marine}
        if record.window.wave_height_m not in observed:
            findings.append("unverifiable_slot:wave_height_m")
    if record.window.swell_period_s is not None:
        observed = {item.facts.get("swell_period_s") for item in marine}
        if record.window.swell_period_s not in observed:
            findings.append("unverifiable_slot:swell_period_s")
    if record.window.wind_kmh is not None:
        observed = {item.facts.get("wind_kmh") for item in marine}
        if record.window.wind_kmh not in observed:
            findings.append("unverifiable_slot:wind_kmh")
    if any(not item.source_url.startswith("https://") for item in record.evidence):
        findings.append("invalid_source_url")
    return tuple(findings)
