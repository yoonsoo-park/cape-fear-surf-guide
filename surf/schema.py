from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FreshnessState(StrEnum):
    current = "current"
    stale = "stale"
    unavailable = "unavailable"


class DecisionState(StrEnum):
    recommended_window = "recommended_window"
    experienced_only = "experienced_only"
    not_recommended = "not_recommended"
    official_advisory_present = "official_advisory_present"
    insufficient_data = "insufficient_data"
    stale_data = "stale_data"
    conflicting_evidence = "conflicting_evidence"


class EvidenceItem(FrozenModel):
    source_name: str
    source_url: str
    source_kind: str
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    retrieved_at: datetime
    location: str
    facts: dict[str, Any]
    freshness_state: FreshnessState
    original_timezone: str
    raw_reference: str

    @model_validator(mode="after")
    def require_aware_times(self) -> "EvidenceItem":
        fields = (self.issued_at, self.valid_from, self.valid_until, self.retrieved_at)
        if any(value.tzinfo is None or value.utcoffset() is None for value in fields):
            raise ValueError("evidence timestamps must include a timezone or UTC offset")
        return self


class PartyProfile(FrozenModel):
    skill_level: str
    ages: tuple[int, ...] = ()
    accessibility_needs: tuple[str, ...] = ()


class IntakeDecision(FrozenModel):
    questions: tuple[str, ...] = Field(max_length=2)
    profile: PartyProfile | None = None


class BeachWindow(FrozenModel):
    beach_id: str
    starts_at: datetime
    ends_at: datetime
    wave_height_m: float | None = None
    swell_period_s: float | None = None
    wind_kmh: float | None = None

    @model_validator(mode="after")
    def require_valid_interval(self) -> "BeachWindow":
        if any(value.tzinfo is None or value.utcoffset() is None for value in (self.starts_at, self.ends_at)):
            raise ValueError("window timestamps must include a timezone or UTC offset")
        if self.ends_at <= self.starts_at:
            raise ValueError("window end must be after its start")
        return self


class PolicyDecision(FrozenModel):
    state: DecisionState
    reasons: tuple[str, ...]
    vetoes: tuple[str, ...] = ()


class RecommendationRecord(FrozenModel):
    schema_version: str = "1"
    window_id: str
    snapshot_id: str
    profile: PartyProfile
    window: BeachWindow
    decision: PolicyDecision
    evidence: tuple[EvidenceItem, ...]


class SurfBrief(FrozenModel):
    window_id: str
    decision_state: DecisionState
    headline: str
    explanation: tuple[str, ...] = Field(min_length=1, max_length=3)
    warnings: tuple[str, ...]
    source_urls: tuple[str, ...]
    recheck_guidance: str
