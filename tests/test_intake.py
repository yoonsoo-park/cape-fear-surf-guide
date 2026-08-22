from strands import Agent

from surf.intake import resolve_intake
from surf.replay_model import FixturePlannerModel


def test_intake_asks_no_more_than_two_questions_without_guessing():
    agent = Agent(model=FixturePlannerModel(), callback_handler=None)
    result = resolve_intake(agent, "This weekend with my kid")
    assert result.profile is None
    assert result.questions == ("What are the surfers' skill levels and ages?",)
