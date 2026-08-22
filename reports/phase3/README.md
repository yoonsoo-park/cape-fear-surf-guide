# Phase 3 evidence index

The canonical passing Nova Lite evaluation is
[`20260822T210549Z/summary.json`](20260822T210549Z/summary.json), with its 32
redaction-safe raw records in
[`20260822T210549Z/raw-runs.jsonl`](20260822T210549Z/raw-runs.jsonl).

It contains two preflight requests and 30 matrix requests. The runner checked
the explicit `personal` account/profile/region/inference-profile boundary
before every evaluation run. It does not create, update, or delete AWS
resources.

Earlier timestamped directories are retained as engineering evidence of gates
working during this evaluation: a warning-preservation failure, a per-request
cost guard that stopped a tool loop, and a retrieval-turn guard. They are not
submission-pass evidence. The final run added exact immutable-field output
instructions and a bounded retrieval contract, then passed all Phase 3 gates.
