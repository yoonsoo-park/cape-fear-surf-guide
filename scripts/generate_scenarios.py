from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from surf.snapshots import load_snapshot
from surf.tools.inventory import load_seed


SCENARIOS = [
    ("normal", {}),
    ("high-swell", {"swell": 1.8}),
    ("strong-gusts", {"gust": 42.0}),
    ("high-swell-and-gusts", {"swell": 2.1, "gust": 48.0}),
    ("beginner-boundary", {"swell": 1.2, "gust": 30.0}),
    ("cold-calm", {"temperature": 10.0, "gust": 8.0}),
    ("flat-water", {"swell": 0.15}),
    ("missing-hour", {"missing": True}),
    ("variable-conditions", {"alternate": True}),
    ("premium-clean", {"swell": 0.9, "gust": 10.0, "temperature": 23.0}),
    ("high-demand", {"high_demand": True}),
]


def mutate(base: dict, changes: dict) -> dict:
    value = copy.deepcopy(base)
    for i, row in enumerate(value["conditions"]["hours"]):
        if "swell" in changes:
            row["swell_height_m"] = changes["swell"]
        if changes.get("alternate"):
            row["swell_height_m"] = 0.7 if i % 2 == 0 else 1.7
    for i, row in enumerate(value["weather"]["hours"]):
        if "gust" in changes:
            row["gust_kmh"] = changes["gust"]
        if "temperature" in changes:
            row["temperature_c"] = changes["temperature"]
        if changes.get("alternate"):
            row["gust_kmh"] = 12.0 if i % 2 == 0 else 38.0
    if changes.get("missing"):
        value["weather"]["hours"] = [
            row for row in value["weather"]["hours"] if not row["time"].endswith("10:00")
        ]
    if changes.get("high_demand"):
        inventory = load_seed()
        inventory["bookings"].extend([
            {"day": value["day"], "time": "10:00", "instructor": "Maya"},
            {"day": value["day"], "time": "10:00", "instructor": "Kai"},
            {"day": value["day"], "time": "12:00", "instructor": "Rin"},
            {"day": value["day"], "time": "14:00", "instructor": "Leo"},
        ])
        value["inventory"] = inventory
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_snapshot")
    parser.add_argument("--output", default="snapshots/scenarios")
    args = parser.parse_args()
    base = load_snapshot(args.base_snapshot)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, changes in SCENARIOS:
        snapshot = mutate(base, changes)
        snapshot["scenario"] = name
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:12]
        (output / f"{digest}.json").write_text(json.dumps(snapshot, indent=2) + "\n")
        manifest.append({"name": name, "snapshot_id": digest, "changes": changes})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
