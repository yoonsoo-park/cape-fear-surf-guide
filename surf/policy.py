from __future__ import annotations

import hashlib
import json

from .schema import (
    BeachWindow, DecisionState, EvidenceItem, FreshnessState, PartyProfile,
    PolicyDecision, RecommendationRecord,
)

REQUIRED_HAZARD_KIND = "nws_hazards"


def _window_id(snapshot_id: str, profile: PartyProfile, window: BeachWindow) -> str:
    value = {
        "version": 1, "snapshot_id": snapshot_id,
        "profile": profile.model_dump(mode="json"), "window": window.model_dump(mode="json"),
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:20]


def decide(snapshot_id: str, profile: PartyProfile, window: BeachWindow,
           evidence: tuple[EvidenceItem, ...]) -> RecommendationRecord:
    hazards = tuple(item for item in evidence if item.source_kind == REQUIRED_HAZARD_KIND)
    vetoes: list[str] = []
    for item in evidence:
        if item.source_kind in {"nws_hazards", "nws_alerts"} and item.facts.get("active_official_hazard"):
            vetoes.append(f"Active official hazard from {item.source_name}.")
        if item.source_kind == "nc_deq_water_quality" and item.facts.get("status") == "advisory_active":
            vetoes.append("Active NC DEQ recreational water-quality advisory.")
    if vetoes:
        decision = PolicyDecision(state=DecisionState.official_advisory_present,
                                  reasons=("An active official advisory overlaps this window.",), vetoes=tuple(vetoes))
    elif not hazards:
        decision = PolicyDecision(state=DecisionState.insufficient_data,
                                  reasons=("Required NWS hazard evidence is missing.",))
    elif any(item.freshness_state != FreshnessState.current for item in hazards):
        decision = PolicyDecision(state=DecisionState.stale_data,
                                  reasons=("Required NWS hazard evidence is stale or unavailable.",))
    elif any(item.facts.get("location_ambiguous") for item in evidence):
        decision = PolicyDecision(state=DecisionState.insufficient_data,
                                  reasons=("An official source cannot be mapped unambiguously to the beach.",))
    elif any(item.facts.get("safety_conflict") for item in evidence):
        decision = PolicyDecision(state=DecisionState.conflicting_evidence,
                                  reasons=("Official and supplemental evidence conflict in a safety-significant way.",))
    else:
        decision = PolicyDecision(state=DecisionState.recommended_window,
                                  reasons=("No deterministic veto is present in the reviewed evidence.",))
    return RecommendationRecord(
        window_id=_window_id(snapshot_id, profile, window), snapshot_id=snapshot_id,
        profile=profile, window=window, decision=decision, evidence=evidence,
    )
