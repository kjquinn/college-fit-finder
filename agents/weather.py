"""
Weather enrichment via Open-Meteo Archive API.

For each school with lat/lon, pull one year of daily historical weather
(ERA5 reanalysis), aggregate into winter/summer averages + annual
precipitation, and attach a climate label. Results are cached on disk
so repeated searches don't re-hit the API.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "weather.json"
CLIMATE_YEAR = 2023  # fully ingested, stable historical year

_cache_lock = threading.Lock()


@dataclass
class ClimateSummary:
    winter_temp_f: float | None       # avg daily temp over Dec/Jan/Feb
    summer_temp_f: float | None       # avg daily temp over Jun/Jul/Aug
    annual_precip_in: float | None    # total inches
    label: str                        # "warm" / "mild" / "seasonal" / "cold"
    precip_level: str                 # "low" / "moderate" / "high" / "very high"


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _cache_key(lat: float, lon: float) -> str:
    # ~1km precision is plenty for climate — nearby schools share weather.
    return f"{round(lat, 2)},{round(lon, 2)}"


def _classify_label(winter_f: float | None, summer_f: float | None) -> str:
    if winter_f is None:
        return "unknown"
    if winter_f >= 55:
        return "warm"
    if winter_f >= 40:
        return "mild"
    if winter_f >= 25:
        return "seasonal"
    return "cold"


def _classify_precip(annual_in: float | None) -> str:
    if annual_in is None:
        return "unknown"
    if annual_in < 20:
        return "low"
    if annual_in < 40:
        return "moderate"
    if annual_in < 60:
        return "high"
    return "very high"


def fetch_climate(lat: float, lon: float, timeout: int = 15) -> ClimateSummary:
    """Pull one year of daily weather and reduce to a ClimateSummary."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{CLIMATE_YEAR}-01-01",
        "end_date": f"{CLIMATE_YEAR}-12-31",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }
    r = requests.get(ARCHIVE_URL, params=params, timeout=timeout)
    r.raise_for_status()
    daily = r.json().get("daily", {}) or {}
    dates = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_sum") or []

    winter: list[float] = []
    summer: list[float] = []
    total_precip = 0.0
    had_precip = False

    for d, hi, lo, p in zip(dates, tmax, tmin, precip):
        if hi is not None and lo is not None:
            avg = (hi + lo) / 2
            month = int(d.split("-")[1])
            if month in (12, 1, 2):
                winter.append(avg)
            elif month in (6, 7, 8):
                summer.append(avg)
        if p is not None:
            total_precip += p
            had_precip = True

    winter_f = round(sum(winter) / len(winter), 1) if winter else None
    summer_f = round(sum(summer) / len(summer), 1) if summer else None
    annual_in = round(total_precip, 1) if had_precip else None

    return ClimateSummary(
        winter_temp_f=winter_f,
        summer_temp_f=summer_f,
        annual_precip_in=annual_in,
        label=_classify_label(winter_f, summer_f),
        precip_level=_classify_precip(annual_in),
    )


def _enrich_one(
    school: dict[str, Any], cache: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    lat, lon = school.get("lat"), school.get("lon")
    if lat is None or lon is None:
        return school, None, None

    key = _cache_key(lat, lon)
    with _cache_lock:
        cached = cache.get(key)
    if cached:
        return school, cached, key

    # One retry with a small backoff; Open-Meteo occasionally rate-limits
    # bursts of concurrent requests and a second try almost always succeeds.
    for attempt in range(2):
        try:
            summary = asdict(fetch_climate(lat, lon))
            return school, summary, key
        except requests.RequestException:
            if attempt == 0:
                time.sleep(0.5)

    return school, None, key


def enrich_schools_with_climate(
    schools: list[dict[str, Any]], max_workers: int = 6
) -> list[dict[str, Any]]:
    """
    Attach climate fields to each school in place:
      climate_label, winter_temp_f, summer_temp_f,
      annual_precip_in, precip_level

    Uses an on-disk cache (.cache/weather.json) keyed by rounded
    (lat, lon), so follow-up searches for overlapping pools are free.
    """
    cache = _load_cache()
    updated = False

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_enrich_one, s, cache) for s in schools]
        for fut in as_completed(futures):
            school, summary, key = fut.result()
            if summary is None:
                continue
            school["climate_label"] = summary["label"]
            school["winter_temp_f"] = summary["winter_temp_f"]
            school["summer_temp_f"] = summary["summer_temp_f"]
            school["annual_precip_in"] = summary["annual_precip_in"]
            school["precip_level"] = summary["precip_level"]
            if key is not None:
                with _cache_lock:
                    if cache.get(key) != summary:
                        cache[key] = summary
                        updated = True

    if updated:
        _save_cache(cache)

    return schools
