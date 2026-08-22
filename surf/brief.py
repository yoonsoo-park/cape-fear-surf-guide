from __future__ import annotations

from .schema import DecisionState, RecommendationRecord, SurfBrief


def template_brief(record: RecommendationRecord) -> SurfBrief:
    positive = record.decision.state == DecisionState.recommended_window
    headline = "Planning window available" if positive else "We cannot recommend this window right now"
    warnings = record.decision.vetoes or (() if positive else record.decision.reasons)
    return SurfBrief(
        window_id=record.window_id, decision_state=record.decision.state, headline=headline,
        explanation=record.decision.reasons[:3], warnings=warnings,
        source_urls=tuple(dict.fromkeys(item.source_url for item in record.evidence)),
        recheck_guidance="Re-check official conditions, posted flags, lifeguards, and local officials before entering the water.",
    )
