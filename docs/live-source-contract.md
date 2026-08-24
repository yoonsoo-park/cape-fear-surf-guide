# Live source contract capture

Captured and checked: **2026-08-22**. The public requests used a ten-second
inspection timeout; the deployed adapters use a five-second timeout and treat
timeouts or schema failures as `insufficient_data`.

| Source | Live request and observed response contract | Policy use |
| --- | --- | --- |
| NWS active alerts | `GET https://api.weather.gov/alerts/active?zone=NCZ108`, with a project URL in `User-Agent`; response was a GeoJSON `FeatureCollection` with `features` (zero features in the capture). | A nonempty active official alert list is a veto. Failure normalizing either NWS alerts or forecast is insufficient data. |
| NWS forecast | `GET https://api.weather.gov/zones/forecast/NCZ108/forecast`; response was a GeoJSON feature whose `properties` contained `updated`, `zone`, and `periods`. | Required official forecast context and source freshness evidence. |
| NOAA tides | `GET https://api.tidesandcurrents.noaa.gov/api/prod/datagetter` with `product=predictions`, `station=8658163`, local tide time, metric units, and high/low interval; response contained `predictions`, each with `t`, `v`, and `type`. | Required tide evidence. Station `8658163` applies only to Wrightsville Beach. |
| Open-Meteo | Separate marine and weather hourly requests with `timezone=America/New_York` and `forecast_days=7`; marine response had hourly `time`, `wave_height`, `wave_direction`, `wave_period`; weather response had matching hourly `time`, `wind_speed_10m`, `precipitation_probability`, `weather_code`. | Required supplemental planning data. Mismatched or missing hourly ranges fail closed. |
| NC DEQ | No verified machine-readable location mapping was found. The public response retains the official recreational-water-quality page URL. | `feed_unavailable` is labeled, not safety evidence and not an automatic veto. Only a verified `advisory_active` is a veto. |

The code converts all internal timestamps to timezone-aware values, preserves
the original source timezone string, and displays request-range validation in
`America/New_York`. The live path has no response cache and does not use the
frozen fixture files as a replacement for any source.
