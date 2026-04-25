"""
IPEDS enrichment via the Urban Institute Education Data API.

Pulls four endpoints per school:
  - student-faculty-ratio/{year}             → student_faculty_ratio
  - institutional-characteristics/{year}     → housing capacity / required,
                                               religious affiliation,
                                               athletic association,
                                               degree levels offered
  - sfa-grants-and-net-price/{year}          → avg institutional aid + % aid
  - sfa-by-living-arrangement/{year}         → % of students living on campus

Mutates each school dict in place with `ipeds_*` keys. Caches per-school
results to .cache/ipeds.json so repeat runs hit the API only for new IDs.
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

BASE_URL = "https://educationdata.urban.org/api/v1/college-university/ipeds"
DATA_YEAR = 2020          # most recent year with all four endpoints populated
REQUEST_TIMEOUT = 25      # per-endpoint
CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "ipeds.json"

_cache_lock = threading.Lock()


# Partial IPEDS religious-affiliation code → display label. Codes outside
# this map but > 0 fall back to "Religious affiliation" (still flags the
# school as religious without naming the denomination).
RELIGION_NAMES = {
    22: "Catholic",
    30: "Catholic",
    35: "Methodist",
    40: "Quaker",
    51: "Lutheran",
    71: "Christian",
    77: "Christian",
    80: "Southern Baptist",
    91: "Catholic",
    92: "Christian",
    93: "Christian",
    94: "Latter-day Saints (LDS)",
    99: "Other religious",
    24: "Jewish",
}


@dataclass
class IpedsSummary:
    student_faculty_ratio: int | None = None
    housing_capacity: int | None = None
    housing_guaranteed: bool | None = None
    avg_institutional_aid: int | None = None
    pct_receiving_aid: float | None = None
    athletics_division: str | None = None
    religious_affiliation: str | None = None
    pct_on_campus: float | None = None
    num_programs: int | None = None


# -----------------------------------------------------------------------------
# Cache I/O
# -----------------------------------------------------------------------------
def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


# -----------------------------------------------------------------------------
# Single Urban-Institute call with one retry + backoff
# -----------------------------------------------------------------------------
def _api_get(endpoint: str, unit_id: int) -> list[dict[str, Any]]:
    url = f"{BASE_URL}/{endpoint}/?unitid={unit_id}"
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.json().get("results", [])
        except (requests.Timeout, requests.RequestException):
            if attempt == 0:
                time.sleep(0.5)
    return []


def fetch_ipeds(unit_id: int, year: int = DATA_YEAR) -> IpedsSummary:
    """Pull IPEDS data for one school across multiple endpoints."""
    summary = IpedsSummary()

    # 1. Student-faculty ratio (single value)
    sfr_rows = _api_get(f"student-faculty-ratio/{year}", unit_id)
    if sfr_rows:
        summary.student_faculty_ratio = sfr_rows[0].get("student_faculty_ratio")

    # 2. Institutional characteristics (one row, many fields)
    ic_rows = _api_get(f"institutional-characteristics/{year}", unit_id)
    if ic_rows:
        ic = ic_rows[0]

        cap = ic.get("dormitory_capacity")
        summary.housing_capacity = int(cap) if cap and cap > 0 else None

        req = ic.get("oncampus_required")
        summary.housing_guaranteed = bool(req == 1) if req is not None else None

        rel = ic.get("religious_affiliation")
        if rel and rel > 0:
            summary.religious_affiliation = RELIGION_NAMES.get(
                rel, "Religious affiliation"
            )

        # Athletic association — proxy for division (NCAA / NAIA / NJCAA).
        # Real NCAA Division I/II/III isn't a single IPEDS field, so we
        # surface the membership level here and note the caveat upstream.
        if ic.get("member_ncaa") == 1:
            summary.athletics_division = "NCAA"
        elif ic.get("member_naia") == 1:
            summary.athletics_division = "NAIA"
        elif ic.get("member_njcaa") == 1:
            summary.athletics_division = "NJCAA"
        else:
            summary.athletics_division = "Non-NCAA"

        # Programs offered = count of degree-level "*_offered" fields = 1.
        offered_fields = (
            "assoc_offered", "bach_offered", "masters_offered",
            "doctors_research_offered", "doctors_professional_offered",
            "doctors_other_offered", "postbac_cert_offered",
            "post_masters_cert_offered", "cert_0_1_offered",
            "cert_1_2_offered", "cert_2_4_offered",
        )
        offered = sum(1 for f in offered_fields if ic.get(f) == 1)
        summary.num_programs = offered if offered > 0 else None

    # 3. Aid grants — aggregate weighted average across all rows.
    sfa_rows = _api_get(f"sfa-grants-and-net-price/{year}", unit_id)
    if sfa_rows:
        total_grant = sum((r.get("total_grant") or 0) for r in sfa_rows)
        recipients  = sum((r.get("number_receiving_grants") or 0) for r in sfa_rows)
        students    = sum((r.get("number_of_students") or 0) for r in sfa_rows)
        if recipients > 0:
            summary.avg_institutional_aid = int(total_grant / recipients)
        if students > 0:
            summary.pct_receiving_aid = round(recipients / students, 3)

    # 4. % living on campus — derived from sfa-by-living-arrangement.
    living_rows = _api_get(f"sfa-by-living-arrangement/{year}", unit_id)
    if living_rows:
        # IPEDS living_arrangement codes: 1 = on-campus, 2 = with family,
        # 3 = off-campus not with family, 99 = total.
        on_campus = sum(
            (r.get("number_of_students") or 0)
            for r in living_rows if r.get("living_arrangement") == 1
        )
        all_arr = sum(
            (r.get("number_of_students") or 0)
            for r in living_rows if r.get("living_arrangement") != 99
        )
        if all_arr > 0:
            summary.pct_on_campus = round(on_campus / all_arr, 3)

    return summary


# -----------------------------------------------------------------------------
# Bulk enrichment with cache + thread pool
# -----------------------------------------------------------------------------
def _enrich_one(school: dict[str, Any], cache: dict[str, Any]) -> bool:
    """Fetch (or cache-hit) IPEDS for one school. Returns True if cache changed."""
    unit_id = school.get("id")
    if unit_id is None:
        return False
    key = str(unit_id)

    with _cache_lock:
        cached = cache.get(key)

    if cached is not None:
        for k, v in cached.items():
            school[f"ipeds_{k}"] = v
        return False

    try:
        summary = fetch_ipeds(int(unit_id))
    except Exception as e:
        print(f"[IPEDS] {unit_id} fetch failed: {e}", flush=True)
        return False

    data = asdict(summary)
    for k, v in data.items():
        school[f"ipeds_{k}"] = v

    with _cache_lock:
        cache[key] = data
    return True


def enrich_schools_with_ipeds(
    schools: list[dict[str, Any]], max_workers: int = 6
) -> list[dict[str, Any]]:
    """
    Attach IPEDS fields to each school in place. Uses 6-worker concurrent
    fetching against the Urban Institute API and caches by unit ID at
    .cache/ipeds.json so warm runs are near-instant.
    """
    cache = _load_cache()
    cache_dirty = False

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_enrich_one, s, cache) for s in schools]
        for fut in as_completed(futures):
            try:
                if fut.result():
                    cache_dirty = True
            except Exception as e:
                print(f"[IPEDS] worker raised: {e}", flush=True)

    if cache_dirty:
        _save_cache(cache)

    return schools
