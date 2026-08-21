from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_run(record: dict[str, Any], path: Path = Path("runs/log.jsonl")) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
