from __future__ import annotations

from strands import Agent

from .schema import IntakeDecision


def resolve_intake(agent: Agent, request: str, answers: tuple[str, ...] = ()) -> IntakeDecision:
    prompt = (
        f"INTAKE_REQUEST={request}\nANSWERS={' | '.join(answers)}\n"
        "Resolve a PartyProfile. Ask at most two questions. Do not guess a missing safety-relevant field."
    )
    result = agent(prompt, structured_output_model=IntakeDecision)
    decision = result.structured_output
    if not isinstance(decision, IntakeDecision):
        raise ValueError("agent did not return the IntakeDecision schema")
    if decision.profile is None and not decision.questions:
        raise ValueError("unresolved intake must ask a question")
    return decision
