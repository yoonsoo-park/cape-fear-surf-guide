from __future__ import annotations

import json
from pathlib import Path

from .schema import BeachWindow, EvidenceItem, PartyProfile


DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture(name: str, root: Path = DEFAULT_FIXTURE_ROOT) -> tuple[str, PartyProfile, BeachWindow, tuple[EvidenceItem, ...]]:
    payload = json.loads((root / f"{name}.json").read_text())
    return (
        payload["snapshot_id"],
        PartyProfile.model_validate(payload["profile"]),
        BeachWindow.model_validate(payload["window"]),
        tuple(EvidenceItem.model_validate(item) for item in payload["evidence"]),
    )
