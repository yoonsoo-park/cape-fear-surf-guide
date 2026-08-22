from __future__ import annotations

import json
import re

from surf.planner_agent import plan_fixture_with_agent
from surf.render import render_html
from surf.replay_model import FixturePlannerModel


def test_html_embeds_the_exact_cli_record():
    result = plan_fixture_with_agent("normal", FixturePlannerModel())
    rendered = render_html(result)
    embedded = re.search(r'<script id="recommendation-record" type="application/json">(.*?)</script>', rendered, re.S)
    assert embedded
    assert json.loads(embedded.group(1)) == result.record.model_dump(mode="json")
