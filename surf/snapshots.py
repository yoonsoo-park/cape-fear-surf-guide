from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import BEACHES
from .tools.signals import fetch_surf_conditions, fetch_weather


def capture_snapshot(beach: str, day: str, root: Path = Path("snapshots/live")) -> tuple[str, dict]:
    if beach not in BEACHES:
        raise ValueError(f"unsupported beach: {beach}")
    location = BEACHES[beach]
    datetime.strptime(day, "%Y-%m-%d")
    snapshot = {
        "beach": beach,
        "day": day,
        "timezone": location["timezone"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "conditions": fetch_surf_conditions(location["latitude"], location["longitude"], day, location["timezone"]),
        "weather": fetch_weather(location["latitude"], location["longitude"], day, location["timezone"]),
    }
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:12]
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{digest}.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    return digest, snapshot


def load_snapshot(snapshot_id: str, roots: tuple[Path, ...] = (Path("snapshots/live"), Path("snapshots/scenarios"))) -> dict:
    for root in roots:
        path = root / f"{snapshot_id}.json"
        if path.exists():
            return json.loads(path.read_text())
    raise FileNotFoundError(f"snapshot not found: {snapshot_id}")
