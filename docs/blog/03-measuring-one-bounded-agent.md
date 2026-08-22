# Measuring one bounded agent

This project measures the agentic and deterministic paths separately. The deterministic path has no model call, must return byte-identical records for identical inputs, and has a two-second p95 latency limit. The agent path has a 30-second p95 limit and a $0.05 per-request limit.

The Phase 3 runner uses only the explicitly checked `personal` AWS profile, account `831597648506`, `us-east-1`, and `us.amazon.nova-lite-v1:0`. It runs two preflight requests before its 30-case fixture/profile matrix. A failed tool call, structured output, immutable policy field, latency limit, or cost limit prevents the matrix from continuing.

For each live run, the runner writes the provider-reported input and output token counters, tool-call record, structured brief, immutable record, and a price estimate. The estimate uses the official AWS Price List rates checked on 2026-08-22: $0.00006 per 1K input tokens and $0.00024 per 1K output tokens. The report labels the important limitation: token counters are evidence for a repeatable estimate, not an AWS invoice. Cost Explorer reconciliation remains an operating follow-up.
