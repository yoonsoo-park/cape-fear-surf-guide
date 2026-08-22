# Cape Fear source verification

Reviewed: 2026-08-22

| Source or mapping | Status | Contract |
| --- | --- | --- |
| NWS API | Live point, alert, and forecast-zone captures verified | On 2026-08-22, official point discovery for Wrightsville Beach (`34.2085,-77.7964`) returned forecast zone `NCZ108` and office `ILM`. The active-alerts capture is `fixtures/captured/nws-alerts-NCZ108-2026-08-22.json`; the ten-period zone forecast capture is `fixtures/captured/nws-zone-forecast-NCZ108-2026-08-22.json`. Both replay without a network call. The endpoints require an identifying `User-Agent`; the capture used the public project URL as its contact route. |
| NOAA `8658163` | Verified as Wrightsville Beach station | Do not reuse it for another beach without a documented proxy rationale. |
| NC DEQ machine-readable feed | Unverified | Preserve `no_advisory_found`, `out_of_season`, and `feed_unavailable`; only `advisory_active` is a veto. |
| Carolina Beach, Kure Beach, Fort Fisher tide proxies | Unverified | Store `None`; never guess. |
| Municipal surfing and closure rules | Unverified | Community knowledge cannot become a veto. |

Official references are recorded in `docs/plan-review-decisions.md`. Live endpoint verification is intentionally deferred and does not authorize an AWS call or deployment.
