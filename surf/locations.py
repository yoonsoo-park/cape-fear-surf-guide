from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BeachLocation:
    id: str
    name: str
    latitude: float
    longitude: float
    timezone: str
    nws_zone: str | None
    noaa_station: str | None
    noaa_station_reason: str
    deq_site: str | None
    deq_site_reason: str


BEACHES: dict[str, BeachLocation] = {
    "wrightsville-beach": BeachLocation(
        id="wrightsville-beach", name="Wrightsville Beach", latitude=34.2085, longitude=-77.7964,
        timezone="America/New_York", nws_zone="NCZ108",
        noaa_station="8658163", noaa_station_reason="Official NOAA Wrightsville Beach station; proxy suitability still requires source-note review.",
        deq_site=None, deq_site_reason="NC DEQ machine-readable site mapping is not verified.",
    ),
    "carolina-beach": BeachLocation(
        id="carolina-beach", name="Carolina Beach", latitude=34.0352, longitude=-77.8936,
        timezone="America/New_York", nws_zone=None, noaa_station=None,
        noaa_station_reason="No official or reviewed proxy mapping has been verified.",
        deq_site=None, deq_site_reason="NC DEQ machine-readable site mapping is not verified.",
    ),
    "kure-beach": BeachLocation(
        id="kure-beach", name="Kure Beach", latitude=33.9968, longitude=-77.9072,
        timezone="America/New_York", nws_zone=None, noaa_station=None,
        noaa_station_reason="No official or reviewed proxy mapping has been verified.",
        deq_site=None, deq_site_reason="NC DEQ machine-readable site mapping is not verified.",
    ),
    "fort-fisher": BeachLocation(
        id="fort-fisher", name="Fort Fisher", latitude=33.9716, longitude=-77.9186,
        timezone="America/New_York", nws_zone=None, noaa_station=None,
        noaa_station_reason="No official or reviewed proxy mapping has been verified.",
        deq_site=None, deq_site_reason="NC DEQ machine-readable site mapping is not verified.",
    ),
}
