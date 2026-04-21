"""
Agent 1: College Matcher.

Casts a wide net against the College Scorecard API using only the
hard constraints: major, location (state), and budget. Academic fit
and Reach/Match/Safety classification are Agent 2's job — Agent 1
just surfaces the candidate pool.

Weather and campus-vibe preferences are not available from Scorecard
and are passed through untouched for downstream agents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

SCORECARD_URL = "https://api.data.gov/ed/collegescorecard/v1/schools"

# Hard ceilings to keep pipeline latency bounded.
MIN_RESULTS_CAP = 150   # even if a caller asks for more, we stop at this
MAX_PAGES       = 3     # three 100-result pages = 300 raw rows max per query
REQUEST_TIMEOUT = 30    # seconds per Scorecard call

FIELDS = ",".join([
    "id",
    "school.name",
    "school.city",
    "school.state",
    "school.school_url",
    "school.ownership",
    "location.lat",
    "location.lon",
    "latest.student.size",
    "latest.admissions.admission_rate.overall",
    "latest.admissions.sat_scores.average.overall",
    "latest.admissions.sat_scores.25th_percentile.overall",
    "latest.admissions.sat_scores.75th_percentile.overall",
    "latest.admissions.act_scores.midpoint.cumulative",
    "latest.admissions.act_scores.25th_percentile.cumulative",
    "latest.admissions.act_scores.75th_percentile.cumulative",
    "latest.cost.attendance.academic_year",
    "latest.cost.tuition.in_state",
    "latest.cost.tuition.out_of_state",
    "latest.completion.completion_rate_4yr_150nt",   # C150_4 — grad rate
    "latest.aid.median_debt.completers.overall",     # DEBT_MDN — median debt at graduation
    "latest.student.demographics.race_ethnicity.non_resident_alien",  # % international
    "latest.programs.cip_4_digit.title",
])

# Rough ACT -> SAT concordance (College Board / ACT joint table, abbreviated).
ACT_TO_SAT = {
    36: 1590, 35: 1540, 34: 1500, 33: 1460, 32: 1430, 31: 1400,
    30: 1370, 29: 1340, 28: 1310, 27: 1280, 26: 1240, 25: 1210,
    24: 1180, 23: 1140, 22: 1110, 21: 1080, 20: 1040, 19: 1010,
    18: 970, 17: 930, 16: 890, 15: 850, 14: 800, 13: 760, 12: 710,
}


@dataclass
class StudentProfile:
    gpa: float | None = None
    sat: int | None = None
    act: int | None = None
    intended_major: str | None = None
    budget: int | None = None           # max annual tuition (USD)
    state: str | None = None            # 2-letter code used for the Scorecard
                                        # query (may be comma-separated for
                                        # region-level multi-state filters)
    weather_pref: str | None = None     # passthrough for later agents
    vibe_prefs: list[str] = field(default_factory=list)
    home_state: str | None = None       # 2-letter code of the student's own
                                        # home state (distinct from `state`);
                                        # used to pick in- vs out-of-state
                                        # tuition for the budget filter.
    tuition_preference: str | None = None  # "in_state" | "out_of_state" | None
    student_status: str | None = None   # "domestic" | "international" | "permanent_resident"

    def effective_sat(self) -> int | None:
        if self.sat:
            return self.sat
        if self.act and self.act in ACT_TO_SAT:
            return ACT_TO_SAT[self.act]
        return None


class ScorecardError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.getenv("COLLEGE_SCORECARD_API_KEY")
    if not key:
        raise ScorecardError(
            "COLLEGE_SCORECARD_API_KEY not set. Add it to .env."
        )
    return key


def _build_params(profile: StudentProfile) -> dict[str, Any]:
    params: dict[str, Any] = {
        "api_key": _api_key(),
        "fields": FIELDS,
        "school.operating": 1,
        "school.degrees_awarded.predominant__range": "3..4",  # bachelor's+
    }

    if profile.state:
        params["school.state"] = profile.state.upper()

    return params


def _relevant_tuition(school: dict[str, Any], profile: StudentProfile) -> int | None:
    """
    Pick the tuition amount that would apply to this student at this school.
      - International / permanent resident → always out-of-state (they pay
        OOS rates at every US school, home-state logic doesn't apply)
      - tuition_preference="in_state"      → in-state rate
      - tuition_preference="out_of_state"  → out-of-state rate
      - None / anything else (domestic)    → in-state if the school is in
                                             the student's home state, else OOS
    """
    if profile.student_status in ("international", "permanent_resident"):
        return school.get("out_of_state_tuition") or school.get("in_state_tuition")

    pref = profile.tuition_preference
    if pref == "in_state":
        return school.get("in_state_tuition")
    if pref == "out_of_state":
        return school.get("out_of_state_tuition")

    home = (profile.home_state or "").upper()
    sch_state = (school.get("state") or "").upper()
    if home and sch_state and home == sch_state:
        return school.get("in_state_tuition")
    # Attending out of state — fall back to in-state if OOS is unpublished.
    return school.get("out_of_state_tuition") or school.get("in_state_tuition")


def _passes_budget(school: dict[str, Any], profile: StudentProfile) -> bool:
    """
    Budget filter. Rules:
      - International / permanent resident: compare OOS tuition; do not
        scope by state (no "home" state applies).
      - Domestic + "in_state only":     restrict pool to home-state schools,
                                        compare in-state tuition.
      - Domestic + "out_of_state only": exclude home-state schools,
                                        compare out-of-state tuition.
      - Otherwise:                      compare the relevant tuition only.
    """
    if profile.budget is None:
        return True

    if profile.student_status in ("international", "permanent_resident"):
        tuition = _relevant_tuition(school, profile)
        return True if tuition is None else tuition <= profile.budget

    pref = profile.tuition_preference
    home = (profile.home_state or "").upper()
    sch_state = (school.get("state") or "").upper()

    if pref == "in_state" and home and sch_state and home != sch_state:
        return False
    if pref == "out_of_state" and home and sch_state and home == sch_state:
        return False

    tuition = _relevant_tuition(school, profile)
    if tuition is None:
        # Keep schools whose tuition isn't published rather than silently drop.
        return True
    return tuition <= profile.budget


def _apply_local_filters(
    schools: list[dict[str, Any]], profile: StudentProfile
) -> list[dict[str, Any]]:
    """Post-filters for columns the Scorecard API doesn't let us filter on."""
    out = schools

    if profile.budget is not None:
        out = [s for s in out if _passes_budget(s, profile)]

    if profile.intended_major:
        out = [s for s in out if _matches_major(s, profile.intended_major)]

    return out


def _flatten(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Scorecard result into a simpler dict for downstream agents."""
    # Scorecard returns programs as a list under the parent key, even when
    # we asked for .title specifically — each item is {"title": "..."}.
    programs_raw = raw.get("latest.programs.cip_4_digit") or []
    programs = [
        p["title"] for p in programs_raw
        if isinstance(p, dict) and p.get("title")
    ]

    return {
        "id": raw.get("id"),
        "name": raw.get("school.name"),
        "city": raw.get("school.city"),
        "state": raw.get("school.state"),
        "url": raw.get("school.school_url"),
        "ownership": raw.get("school.ownership"),  # 1=public, 2=private nonprofit, 3=for-profit
        "lat": raw.get("location.lat"),
        "lon": raw.get("location.lon"),
        "size": raw.get("latest.student.size"),
        "admission_rate": raw.get("latest.admissions.admission_rate.overall"),
        "sat_avg": raw.get("latest.admissions.sat_scores.average.overall"),
        "sat_25": raw.get("latest.admissions.sat_scores.25th_percentile.overall"),
        "sat_75": raw.get("latest.admissions.sat_scores.75th_percentile.overall"),
        "act_mid": raw.get("latest.admissions.act_scores.midpoint.cumulative"),
        "act_25": raw.get("latest.admissions.act_scores.25th_percentile.cumulative"),
        "act_75": raw.get("latest.admissions.act_scores.75th_percentile.cumulative"),
        "cost_of_attendance": raw.get("latest.cost.attendance.academic_year"),
        "in_state_tuition": raw.get("latest.cost.tuition.in_state"),
        "out_of_state_tuition": raw.get("latest.cost.tuition.out_of_state"),
        "graduation_rate": raw.get("latest.completion.completion_rate_4yr_150nt"),
        "median_debt": raw.get("latest.aid.median_debt.completers.overall"),
        "international_pct": raw.get(
            "latest.student.demographics.race_ethnicity.non_resident_alien"
        ),
        "programs": programs,
    }


def _matches_major(school: dict[str, Any], major: str) -> bool:
    if not major:
        return True
    needle = major.lower().strip()
    return any(needle in (p or "").lower() for p in school.get("programs", []))


def find_matching_schools(
    profile: StudentProfile,
    min_results: int = 100,
    max_fetched: int = 500,
    per_page: int = 100,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Query Scorecard with pagination and return the candidate pool.

    Keeps requesting pages until one of:
      - we have at least `min_results` schools passing budget/major filters
      - we've fetched `max_fetched` raw results from the API
      - the server has no more results to return

    `limit` optionally caps the returned list.
    """
    # Global cap so callers can't make the pipeline hang by asking for a huge
    # pool — 150 has always been plenty for Agent 2 to rank from.
    effective_min = min(min_results, MIN_RESULTS_CAP)

    params = _build_params(profile)
    params["per_page"] = per_page   # defaults to 100 (the Scorecard max)

    collected: list[dict[str, Any]] = []
    fetched = 0
    page = 0

    while (
        page < MAX_PAGES
        and fetched < max_fetched
        and len(collected) < effective_min
    ):
        params["page"] = page

        # Print the outgoing URL (with the API key redacted) so the
        # exact query is visible in the server log for debugging.
        prep = requests.Request("GET", SCORECARD_URL, params=params).prepare()
        safe_url = prep.url.replace(params["api_key"], "***") if prep.url else ""
        print(f"[Agent 1 page {page}] {safe_url}", flush=True)

        try:
            resp = requests.get(SCORECARD_URL, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.Timeout:
            # Don't hang the pipeline — return whatever we've collected so far.
            print(f"[Agent 1] Scorecard timeout on page {page}; "
                  f"returning {len(collected)} collected so far.", flush=True)
            break
        except requests.RequestException as e:
            raise ScorecardError(f"Scorecard request failed: {e}") from e

        payload = resp.json()
        raw = payload.get("results", [])
        if not raw:
            break  # no more pages

        fetched += len(raw)
        collected.extend(_apply_local_filters([_flatten(r) for r in raw], profile))

        total = payload.get("metadata", {}).get("total", 0)
        if fetched >= total:
            break  # exhausted the server-side result set

        page += 1

    return collected[:limit] if limit else collected
