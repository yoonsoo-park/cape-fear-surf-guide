from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from strands import ToolContext, tool


SEED_PATH = Path(__file__).parents[1] / "data" / "seed.json"


def load_seed(path: Path = SEED_PATH) -> dict:
    return json.loads(path.read_text())


def availability_for_day(day: str, seed: dict | None = None) -> dict:
    datetime.strptime(day, "%Y-%m-%d")
    seed = seed or load_seed()
    booked = {(b["time"], b["instructor"]) for b in seed["bookings"] if b["day"] == day}
    slots = []
    for instructor in seed["instructors"]:
        current = datetime.strptime(instructor["shift"][0], "%H:%M")
        end = datetime.strptime(instructor["shift"][1], "%H:%M")
        while current < end:
            time = current.strftime("%H:%M")
            if (time, instructor["name"]) not in booked:
                slots.append({"time": time, "instructor": instructor["name"], "levels": instructor["levels"]})
            current += timedelta(minutes=seed["slot_minutes"])
    return {"day": day, "slots": slots}


@tool(context=True)
def get_instructor_availability(tool_context: ToolContext) -> dict:
    """Return open instructor slots and certified skill levels for the requested day."""
    invocation_state = tool_context.invocation_state
    if "day" not in invocation_state:
        raise ValueError("day is required in invocation_state")
    seed = invocation_state.get("inventory") or load_seed()
    return availability_for_day(invocation_state["day"], seed)


@tool(context=True)
def get_base_pricing(tool_context: ToolContext) -> dict:
    """Return base and minimum lesson prices for every skill level."""
    seed = tool_context.invocation_state.get("inventory") or load_seed()
    return seed["pricing"]
