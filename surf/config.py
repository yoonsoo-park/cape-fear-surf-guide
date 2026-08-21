from __future__ import annotations

import os
from dataclasses import dataclass


BEACHES = {
    "Seal Beach": {"latitude": 33.7414, "longitude": -118.1048, "timezone": "America/Los_Angeles"},
}

EXPECTED_PATH = [
    "conditions_agent",
    "weather_agent",
    "availability_agent",
    "safety_agent",
    "pricing_agent",
]


@dataclass(frozen=True)
class Settings:
    region: str
    model_id: str
    snapshot_dir: str = "snapshots"
    run_log: str = "runs/log.jsonl"

    @classmethod
    def from_env(cls) -> "Settings":
        region = os.getenv("AWS_REGION", "")
        model_id = os.getenv("BEDROCK_MODEL_ID", "")
        if not region or not model_id:
            raise RuntimeError("AWS_REGION and BEDROCK_MODEL_ID must both be set")
        return cls(region=region, model_id=model_id)
