from __future__ import annotations

from dataclasses import dataclass

from .brief import template_brief
from .fixtures import load_fixture
from .policy import decide
from .schema import RecommendationRecord, SurfBrief


@dataclass(frozen=True)
class PlanningResult:
    record: RecommendationRecord
    brief: SurfBrief
    brief_source: str


def plan_fixture(name: str) -> PlanningResult:
    snapshot_id, profile, window, evidence = load_fixture(name)
    record = decide(snapshot_id, profile, window, evidence)
    return PlanningResult(record=record, brief=template_brief(record), brief_source="template")
