import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_LOG = ROOT / "runs" / "sample-log.jsonl"


def _run_json(script: str) -> dict:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), str(SAMPLE_LOG)],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_duckdb_analyzer_preserves_summarize_runs_contract():
    expected = _run_json("summarize_runs.py")
    actual = _run_json("analyze_runs_duckdb.py")

    # The analytics report is additive. Every pre-existing number must remain
    # byte-for-byte equivalent after JSON decoding.
    assert {key: actual[key] for key in expected} == expected


def test_duckdb_analyzer_reports_nested_and_grouped_evidence():
    report = _run_json("analyze_runs_duckdb.py")
    analytics = report["analytics"]

    assert analytics["node_token_distribution"]["availability_agent"]["runs"] == 33
    assert analytics["node_token_distribution"]["pricing_agent"]["failures"] == 1
    assert analytics["scenario_failure_rate"]["high-swell-and-gusts"] == {
        "runs": 3,
        "failures": 1,
        "failure_rate": 0.3333,
    }
    assert analytics["schema_field_presence"]["validation"] == {
        "present": 33,
        "presence_rate": 1.0,
    }
