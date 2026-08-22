from __future__ import annotations

import html

from .application import PlanningResult


def render_html(result: PlanningResult) -> str:
    record_json = result.record.model_dump_json(indent=2).replace("<", "\\u003c")
    sources = "".join(
        f'<li><a href="{html.escape(url, quote=True)}">{html.escape(url)}</a></li>'
        for url in result.brief.source_urls
    )
    explanations = "".join(f"<li>{html.escape(line)}</li>" for line in result.brief.explanation)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Cape Fear Surf Guide</title></head>
<body><main><h1>{html.escape(result.brief.headline)}</h1>
<p>Decision: <strong>{html.escape(result.record.decision.state.value)}</strong></p>
<ul>{explanations}</ul><h2>Official and supplemental sources</h2><ul>{sources}</ul>
<p>{html.escape(result.brief.recheck_guidance)}</p>
<script id="recommendation-record" type="application/json">{record_json}</script>
</main></body></html>"""
