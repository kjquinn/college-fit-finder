"""
Build data/school_vibes.json.

Strategy:
  1. Fetch ~500 schools from Scorecard (selective + large) so we have
     accurate unit IDs.
  2. For ~50 well-known schools, use hand-curated vibe data based on
     reputation (Princeton Review-style priors).
  3. For the rest, derive vibe scores heuristically from size, ownership,
     admission rate, state, city type.
  4. Write the first 400 deduped entries to data/school_vibes.json.

Run once: `py scripts/generate_vibes.py`
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("COLLEGE_SCORECARD_API_KEY")
URL = "https://api.data.gov/ed/collegescorecard/v1/schools"
FIELDS = ",".join([
    "id", "school.name", "school.city", "school.state", "school.ownership",
    "latest.student.size",
    "latest.admissions.admission_rate.overall",
    "latest.admissions.sat_scores.average.overall",
])

TARGET = 400

BIG_METROS = {
    "new york", "brooklyn", "bronx", "queens", "los angeles", "chicago",
    "houston", "phoenix", "philadelphia", "san antonio", "san diego",
    "dallas", "austin", "san francisco", "seattle", "denver", "boston",
    "washington", "atlanta", "miami", "minneapolis", "detroit", "portland",
    "las vegas", "baltimore", "milwaukee", "oakland", "newark",
}

COLLEGE_TOWN_STATES_BIAS = {"VT", "NH", "ME", "MT", "WY", "ID", "IA", "KS", "WV", "ND", "SD"}

SEC_LIKE = {"AL", "AR", "FL", "GA", "KY", "LA", "MS", "MO", "SC", "TN", "TX"}
BIG10_LIKE = {"IN", "IA", "MI", "MN", "NE", "OH", "PA", "IL", "WI", "MD", "NJ"}

LIBERAL_STATES = {"MA", "CA", "NY", "VT", "OR", "WA", "CT", "RI", "NJ", "MD", "IL", "CO", "MN", "HI", "DC", "DE"}
CONSERVATIVE_STATES = {"AL", "MS", "AR", "OK", "ID", "WY", "UT", "ND", "SD", "KY", "TN", "SC", "MT", "WV", "IN", "LA", "NE"}

OUTDOORSY_STATES = {"CO", "VT", "UT", "MT", "WY", "ID", "WA", "OR", "NH", "ME", "AK", "NM"}


# -----------------------------------------------------------------------------
# Curated data for well-known schools. Keys are the exact Scorecard school.name
# we expect to see (case-insensitive match). Values override the heuristics.
# -----------------------------------------------------------------------------
CURATED: dict[str, dict[str, Any]] = {
    # Ivies + peers
    "harvard university": dict(party_scene=35, academic_intensity=98, greek_life="low",
        campus_setting="urban", political_leaning="liberal", athletics_culture="medium",
        diversity_score=82, vibe_tags=["research focused", "pre-professional", "elite", "intellectual"]),
    "yale university": dict(party_scene=40, academic_intensity=96, greek_life="low",
        campus_setting="urban", political_leaning="very liberal", athletics_culture="medium",
        diversity_score=80, vibe_tags=["intellectual", "artsy", "tight knit", "elite"]),
    "princeton university": dict(party_scene=45, academic_intensity=97, greek_life="medium",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="high",
        diversity_score=75, vibe_tags=["preppy", "research focused", "elite", "tight knit"]),
    "columbia university in the city of new york": dict(party_scene=45, academic_intensity=96,
        greek_life="low", campus_setting="urban", political_leaning="very liberal", athletics_culture="low",
        diversity_score=88, vibe_tags=["intellectual", "pre-professional", "artsy", "activist"]),
    "university of pennsylvania": dict(party_scene=70, academic_intensity=94, greek_life="high",
        campus_setting="urban", political_leaning="liberal", athletics_culture="medium",
        diversity_score=80, vibe_tags=["pre-professional", "social", "elite", "career-driven"]),
    "brown university": dict(party_scene=55, academic_intensity=92, greek_life="low",
        campus_setting="urban", political_leaning="very liberal", athletics_culture="low",
        diversity_score=78, vibe_tags=["open curriculum", "artsy", "progressive", "laid back"]),
    "cornell university": dict(party_scene=65, academic_intensity=93, greek_life="high",
        campus_setting="college town", political_leaning="liberal", athletics_culture="medium",
        diversity_score=78, vibe_tags=["rigorous", "outdoorsy", "social", "preppy"]),
    "dartmouth college": dict(party_scene=75, academic_intensity=92, greek_life="high",
        campus_setting="college town", political_leaning="liberal", athletics_culture="high",
        diversity_score=70, vibe_tags=["outdoorsy", "greek life", "tight knit", "preppy"]),

    # Top privates
    "stanford university": dict(party_scene=50, academic_intensity=96, greek_life="medium",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="high",
        diversity_score=82, vibe_tags=["research focused", "pre-professional", "entrepreneurial", "outdoorsy"]),
    "massachusetts institute of technology": dict(party_scene=30, academic_intensity=100,
        greek_life="medium", campus_setting="urban", political_leaning="liberal", athletics_culture="low",
        diversity_score=80, vibe_tags=["nerdy", "research focused", "intense", "quirky"]),
    "california institute of technology": dict(party_scene=20, academic_intensity=100,
        greek_life="low", campus_setting="suburban", political_leaning="liberal", athletics_culture="low",
        diversity_score=75, vibe_tags=["nerdy", "research focused", "intense", "small"]),
    "university of chicago": dict(party_scene=25, academic_intensity=98, greek_life="low",
        campus_setting="urban", political_leaning="liberal", athletics_culture="low",
        diversity_score=78, vibe_tags=["intellectual", "quirky", "intense", "nerdy"]),
    "duke university": dict(party_scene=75, academic_intensity=94, greek_life="high",
        campus_setting="suburban", political_leaning="moderate", athletics_culture="dominant",
        diversity_score=78, vibe_tags=["sports culture", "preppy", "greek life", "pre-professional"]),
    "northwestern university": dict(party_scene=60, academic_intensity=93, greek_life="high",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="medium",
        diversity_score=78, vibe_tags=["pre-professional", "artsy", "type-A", "spirited"]),
    "johns hopkins university": dict(party_scene=40, academic_intensity=95, greek_life="medium",
        campus_setting="urban", political_leaning="liberal", athletics_culture="low",
        diversity_score=80, vibe_tags=["research focused", "pre-med", "intense", "career-driven"]),
    "vanderbilt university": dict(party_scene=70, academic_intensity=92, greek_life="high",
        campus_setting="urban", political_leaning="moderate", athletics_culture="high",
        diversity_score=72, vibe_tags=["greek life", "preppy", "southern", "social"]),
    "rice university": dict(party_scene=50, academic_intensity=94, greek_life="none",
        campus_setting="urban", political_leaning="moderate", athletics_culture="medium",
        diversity_score=82, vibe_tags=["residential college system", "tight knit", "quirky", "intellectual"]),
    "notre dame university": dict(party_scene=65, academic_intensity=90, greek_life="none",
        campus_setting="college town", political_leaning="conservative", athletics_culture="dominant",
        diversity_score=68, vibe_tags=["faith-based", "sports culture", "tight knit", "spirited"]),
    "university of notre dame": dict(party_scene=65, academic_intensity=90, greek_life="none",
        campus_setting="college town", political_leaning="conservative", athletics_culture="dominant",
        diversity_score=68, vibe_tags=["faith-based", "sports culture", "tight knit", "spirited"]),
    "washington university in st louis": dict(party_scene=50, academic_intensity=93, greek_life="medium",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="low",
        diversity_score=75, vibe_tags=["pre-med", "research focused", "type-A", "laid back"]),
    "emory university": dict(party_scene=55, academic_intensity=91, greek_life="high",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="low",
        diversity_score=80, vibe_tags=["pre-med", "pre-professional", "diverse", "type-A"]),
    "georgetown university": dict(party_scene=60, academic_intensity=92, greek_life="low",
        campus_setting="urban", political_leaning="moderate", athletics_culture="medium",
        diversity_score=76, vibe_tags=["pre-professional", "politically engaged", "preppy", "international"]),
    "carnegie mellon university": dict(party_scene=35, academic_intensity=96, greek_life="medium",
        campus_setting="urban", political_leaning="liberal", athletics_culture="low",
        diversity_score=80, vibe_tags=["nerdy", "artsy", "intense", "techy"]),
    "new york university": dict(party_scene=55, academic_intensity=85, greek_life="low",
        campus_setting="urban", political_leaning="very liberal", athletics_culture="low",
        diversity_score=90, vibe_tags=["urban", "artsy", "pre-professional", "diverse"]),
    "university of southern california": dict(party_scene=75, academic_intensity=85, greek_life="high",
        campus_setting="urban", political_leaning="liberal", athletics_culture="dominant",
        diversity_score=82, vibe_tags=["preppy", "sports culture", "greek life", "career-driven"]),

    # Top liberal arts
    "williams college": dict(party_scene=50, academic_intensity=96, greek_life="none",
        campus_setting="rural", political_leaning="liberal", athletics_culture="high",
        diversity_score=72, vibe_tags=["outdoorsy", "tight knit", "intellectual", "athletic"]),
    "amherst college": dict(party_scene=50, academic_intensity=95, greek_life="none",
        campus_setting="college town", political_leaning="very liberal", athletics_culture="medium",
        diversity_score=75, vibe_tags=["intellectual", "tight knit", "open curriculum", "progressive"]),
    "swarthmore college": dict(party_scene=30, academic_intensity=97, greek_life="low",
        campus_setting="suburban", political_leaning="very liberal", athletics_culture="low",
        diversity_score=78, vibe_tags=["intellectual", "intense", "progressive", "quirky"]),
    "pomona college": dict(party_scene=50, academic_intensity=94, greek_life="none",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="medium",
        diversity_score=78, vibe_tags=["laid back", "intellectual", "tight knit", "consortium"]),
    "middlebury college": dict(party_scene=55, academic_intensity=93, greek_life="low",
        campus_setting="rural", political_leaning="liberal", athletics_culture="high",
        diversity_score=70, vibe_tags=["outdoorsy", "tight knit", "athletic", "environmental"]),
    "wellesley college": dict(party_scene=25, academic_intensity=94, greek_life="none",
        campus_setting="suburban", political_leaning="very liberal", athletics_culture="low",
        diversity_score=80, vibe_tags=["women's college", "intellectual", "pre-professional", "tight knit"]),
    "bowdoin college": dict(party_scene=55, academic_intensity=94, greek_life="none",
        campus_setting="college town", political_leaning="liberal", athletics_culture="high",
        diversity_score=72, vibe_tags=["outdoorsy", "quality of life", "foodie", "athletic"]),
    "carleton college": dict(party_scene=40, academic_intensity=94, greek_life="none",
        campus_setting="rural", political_leaning="liberal", athletics_culture="low",
        diversity_score=72, vibe_tags=["quirky", "intellectual", "tight knit", "nerdy"]),
    "harvey mudd college": dict(party_scene=30, academic_intensity=98, greek_life="none",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="low",
        diversity_score=70, vibe_tags=["nerdy", "intense", "stem focused", "tight knit"]),
    "reed college": dict(party_scene=50, academic_intensity=96, greek_life="none",
        campus_setting="urban", political_leaning="very liberal", athletics_culture="low",
        diversity_score=72, vibe_tags=["intellectual", "quirky", "counterculture", "intense"]),
    "oberlin college": dict(party_scene=45, academic_intensity=88, greek_life="none",
        campus_setting="rural", political_leaning="very liberal", athletics_culture="low",
        diversity_score=78, vibe_tags=["artsy", "progressive", "activist", "quirky"]),
    "wesleyan university": dict(party_scene=55, academic_intensity=91, greek_life="low",
        campus_setting="college town", political_leaning="very liberal", athletics_culture="low",
        diversity_score=78, vibe_tags=["artsy", "progressive", "activist", "intellectual"]),
    "grinnell college": dict(party_scene=45, academic_intensity=92, greek_life="none",
        campus_setting="rural", political_leaning="very liberal", athletics_culture="low",
        diversity_score=75, vibe_tags=["progressive", "tight knit", "intellectual", "activist"]),

    # Top publics
    "university of california-berkeley": dict(party_scene=55, academic_intensity=94, greek_life="medium",
        campus_setting="urban", political_leaning="very liberal", athletics_culture="high",
        diversity_score=90, vibe_tags=["activist", "research focused", "diverse", "intellectual"]),
    "university of california-los angeles": dict(party_scene=65, academic_intensity=91, greek_life="high",
        campus_setting="urban", political_leaning="liberal", athletics_culture="dominant",
        diversity_score=90, vibe_tags=["big school energy", "sports culture", "diverse", "career-driven"]),
    "university of michigan-ann arbor": dict(party_scene=75, academic_intensity=92, greek_life="high",
        campus_setting="college town", political_leaning="liberal", athletics_culture="dominant",
        diversity_score=75, vibe_tags=["sports culture", "big school energy", "spirited", "pre-professional"]),
    "university of virginia-main campus": dict(party_scene=75, academic_intensity=90, greek_life="high",
        campus_setting="college town", political_leaning="moderate", athletics_culture="high",
        diversity_score=70, vibe_tags=["preppy", "greek life", "southern", "tradition"]),
    "university of north carolina at chapel hill": dict(party_scene=70, academic_intensity=89, greek_life="high",
        campus_setting="college town", political_leaning="liberal", athletics_culture="dominant",
        diversity_score=70, vibe_tags=["sports culture", "southern charm", "big school energy", "spirited"]),
    "georgia institute of technology-main campus": dict(party_scene=40, academic_intensity=93, greek_life="high",
        campus_setting="urban", political_leaning="moderate", athletics_culture="high",
        diversity_score=78, vibe_tags=["nerdy", "stem focused", "intense", "career-driven"]),
    "the university of texas at austin": dict(party_scene=80, academic_intensity=85, greek_life="high",
        campus_setting="urban", political_leaning="moderate", athletics_culture="dominant",
        diversity_score=80, vibe_tags=["big school energy", "sports culture", "spirited", "greek life"]),
    "university of illinois urbana-champaign": dict(party_scene=75, academic_intensity=88, greek_life="high",
        campus_setting="college town", political_leaning="moderate", athletics_culture="high",
        diversity_score=75, vibe_tags=["party focused", "greek life", "big school energy", "stem focused"]),
    "university of wisconsin-madison": dict(party_scene=90, academic_intensity=87, greek_life="high",
        campus_setting="college town", political_leaning="liberal", athletics_culture="dominant",
        diversity_score=72, vibe_tags=["party focused", "sports culture", "big school energy", "spirited"]),
    "university of washington-seattle campus": dict(party_scene=55, academic_intensity=88, greek_life="medium",
        campus_setting="urban", political_leaning="liberal", athletics_culture="high",
        diversity_score=80, vibe_tags=["outdoorsy", "big school energy", "techy", "career-driven"]),
    "university of california-san diego": dict(party_scene=40, academic_intensity=88, greek_life="low",
        campus_setting="suburban", political_leaning="liberal", athletics_culture="low",
        diversity_score=85, vibe_tags=["stem focused", "chill", "laid back", "outdoorsy"]),
    "ohio state university-main campus": dict(party_scene=85, academic_intensity=82, greek_life="high",
        campus_setting="urban", political_leaning="moderate", athletics_culture="dominant",
        diversity_score=70, vibe_tags=["sports culture", "party focused", "big school energy", "spirited"]),
    "pennsylvania state university-main campus": dict(party_scene=90, academic_intensity=82, greek_life="high",
        campus_setting="college town", political_leaning="moderate", athletics_culture="dominant",
        diversity_score=65, vibe_tags=["party focused", "sports culture", "big school energy", "greek life"]),
    "purdue university-main campus": dict(party_scene=60, academic_intensity=84, greek_life="high",
        campus_setting="college town", political_leaning="moderate", athletics_culture="high",
        diversity_score=70, vibe_tags=["stem focused", "sports culture", "greek life", "career-driven"]),
    "university of florida": dict(party_scene=80, academic_intensity=84, greek_life="high",
        campus_setting="college town", political_leaning="moderate", athletics_culture="dominant",
        diversity_score=75, vibe_tags=["sports culture", "greek life", "big school energy", "party focused"]),
    "university of alabama": dict(party_scene=90, academic_intensity=75, greek_life="high",
        campus_setting="college town", political_leaning="conservative", athletics_culture="dominant",
        diversity_score=60, vibe_tags=["sports culture", "greek life", "southern", "party focused"]),
    "louisiana state university and agricultural & mechanical college": dict(party_scene=90, academic_intensity=72,
        greek_life="high", campus_setting="urban", political_leaning="conservative", athletics_culture="dominant",
        diversity_score=65, vibe_tags=["sports culture", "party focused", "greek life", "southern"]),

    # Known party / outdoorsy / specialty
    "tulane university of louisiana": dict(party_scene=95, academic_intensity=85, greek_life="high",
        campus_setting="urban", political_leaning="liberal", athletics_culture="medium",
        diversity_score=72, vibe_tags=["party focused", "greek life", "urban", "social"]),
    "university of colorado boulder": dict(party_scene=80, academic_intensity=80, greek_life="medium",
        campus_setting="college town", political_leaning="liberal", athletics_culture="high",
        diversity_score=70, vibe_tags=["outdoorsy", "party focused", "counterculture", "athletic"]),
    "university of vermont": dict(party_scene=65, academic_intensity=78, greek_life="medium",
        campus_setting="college town", political_leaning="very liberal", athletics_culture="medium",
        diversity_score=62, vibe_tags=["outdoorsy", "progressive", "environmental", "chill"]),
    "syracuse university": dict(party_scene=85, academic_intensity=80, greek_life="high",
        campus_setting="urban", political_leaning="liberal", athletics_culture="high",
        diversity_score=72, vibe_tags=["party focused", "sports culture", "greek life", "spirited"]),

    # Religious
    "brigham young university": dict(party_scene=10, academic_intensity=80, greek_life="none",
        campus_setting="college town", political_leaning="conservative", athletics_culture="high",
        diversity_score=40, vibe_tags=["faith-based", "conservative", "tight knit", "family values"]),
    "liberty university": dict(party_scene=10, academic_intensity=70, greek_life="none",
        campus_setting="suburban", political_leaning="conservative", athletics_culture="medium",
        diversity_score=55, vibe_tags=["faith-based", "conservative", "evangelical"]),
    "baylor university": dict(party_scene=60, academic_intensity=82, greek_life="high",
        campus_setting="suburban", political_leaning="conservative", athletics_culture="high",
        diversity_score=70, vibe_tags=["faith-based", "southern", "sports culture", "tight knit"]),

    # HBCUs
    "howard university": dict(party_scene=65, academic_intensity=82, greek_life="high",
        campus_setting="urban", political_leaning="liberal", athletics_culture="medium",
        diversity_score=65, vibe_tags=["hbcu", "activist", "pre-professional", "spirited"]),
    "spelman college": dict(party_scene=45, academic_intensity=86, greek_life="medium",
        campus_setting="urban", political_leaning="liberal", athletics_culture="low",
        diversity_score=55, vibe_tags=["hbcu", "women's college", "tight knit", "empowering"]),
    "morehouse college": dict(party_scene=50, academic_intensity=84, greek_life="medium",
        campus_setting="urban", political_leaning="liberal", athletics_culture="medium",
        diversity_score=55, vibe_tags=["hbcu", "men's college", "pre-professional", "brotherhood"]),

    # Military
    "united states military academy": dict(party_scene=10, academic_intensity=90, greek_life="none",
        campus_setting="rural", political_leaning="conservative", athletics_culture="high",
        diversity_score=62, vibe_tags=["military", "disciplined", "tradition", "athletic"]),
    "united states naval academy": dict(party_scene=10, academic_intensity=90, greek_life="none",
        campus_setting="suburban", political_leaning="conservative", athletics_culture="high",
        diversity_score=60, vibe_tags=["military", "disciplined", "tradition", "athletic"]),
}


def _canon(name: str) -> str:
    return (name or "").strip().lower()


def _curated(name: str) -> dict[str, Any] | None:
    key = _canon(name)
    if key in CURATED:
        return CURATED[key]
    # Permissive substring fallback: Princeton matches "princeton university"
    for k, v in CURATED.items():
        if key == k or key.replace("the ", "").strip() == k:
            return v
    return None


# -----------------------------------------------------------------------------
# Heuristic scoring
# -----------------------------------------------------------------------------
def _is_religious(name: str) -> bool:
    n = name.lower()
    markers = ["christian", "baptist", "catholic", "jesuit", "lutheran", "methodist",
               "theological", "seminary", "bible", "wesleyan", "mennonite", "adventist",
               "pentecostal", "evangelical", "covenant", "divinity", "brigham young",
               "latter-day", "yeshiva", "hebrew", "trinity college of",
               "liberty university", "oral roberts", "franciscan", "dominican"]
    return any(m in n for m in markers)


def _campus_setting(city: str, size: int | None, state: str) -> str:
    c = (city or "").lower()
    if c in BIG_METROS:
        return "urban"
    if size and size >= 20000:
        return "urban"
    if size and size < 3000:
        return "college town" if state not in COLLEGE_TOWN_STATES_BIAS else "rural"
    if state in COLLEGE_TOWN_STATES_BIAS and (size or 0) < 10000:
        return "college town"
    return "suburban"


def _heuristic(school: dict[str, Any]) -> dict[str, Any]:
    name = school.get("school.name", "")
    size = school.get("latest.student.size") or 0
    admit = school.get("latest.admissions.admission_rate.overall")
    state = (school.get("school.state") or "").upper()
    city = (school.get("school.city") or "")
    ownership = school.get("school.ownership")
    is_public = ownership == 1
    is_religious = _is_religious(name)

    campus_setting = _campus_setting(city, size, state)

    # Academic intensity: mostly admission selectivity.
    if admit is None:
        academic = 55
    elif admit < 0.15:
        academic = 92
    elif admit < 0.30:
        academic = 82
    elif admit < 0.50:
        academic = 68
    elif admit < 0.75:
        academic = 55
    else:
        academic = 45

    # Party scene
    party = 45
    if is_public and state in SEC_LIKE and size > 10000:
        party += 30
    elif is_public and state in BIG10_LIKE and size > 15000:
        party += 25
    elif is_public and size > 20000:
        party += 15
    if size > 25000:
        party += 5
    if campus_setting == "urban":
        party += 5
    if is_religious:
        party = 15
    if state == "UT":
        party -= 10
    if academic >= 90 and size < 8000:
        party -= 10
    party = max(5, min(95, party))

    # Greek life
    if is_religious:
        greek = "none"
    elif state in SEC_LIKE and is_public and size > 10000:
        greek = "high"
    elif is_public and size > 15000:
        greek = "medium"
    elif not is_public and size < 2500:
        greek = "low"
    elif size < 3000:
        greek = "low"
    else:
        greek = "medium" if academic < 80 else "low"

    # Political leaning
    if is_religious:
        political = "conservative"
    elif state in LIBERAL_STATES:
        political = "liberal" if not is_public or size < 15000 else "moderate"
        if campus_setting == "urban" and not is_public:
            political = "very liberal"
    elif state in CONSERVATIVE_STATES:
        political = "conservative" if not is_public else "moderate"
    else:
        political = "moderate"

    # Athletics culture
    if is_public and state in SEC_LIKE and size > 20000:
        athletics = "dominant"
    elif is_public and state in BIG10_LIKE and size > 20000:
        athletics = "dominant"
    elif is_public and size > 15000:
        athletics = "high"
    elif size > 8000:
        athletics = "medium"
    else:
        athletics = "low"

    # Diversity score
    diversity = 55
    if campus_setting == "urban":
        diversity += 15
    if is_public:
        diversity += 5
    if is_religious:
        diversity -= 12
    if state in {"CA", "NY", "NJ", "TX", "FL", "HI", "NM", "MD", "DC", "GA"}:
        diversity += 10
    if state in {"ND", "SD", "WV", "ID", "WY", "MT", "VT", "NH", "ME"}:
        diversity -= 10
    if size and size > 20000:
        diversity += 5
    diversity = max(20, min(95, diversity))

    # Vibe tags — compose a list from the signals above.
    tags: list[str] = []
    if academic >= 88:
        tags.append("intellectual")
    if academic >= 85 and size < 4000:
        tags.append("intense")
    if size > 20000 and is_public:
        tags.append("big school energy")
    if is_religious:
        tags.append("faith-based")
    if campus_setting == "urban" and not is_religious:
        tags.append("pre-professional")
    if campus_setting == "college town":
        tags.append("college town vibes")
    if campus_setting == "rural":
        tags.append("tight knit")
    if size < 2500 and not is_public:
        tags.append("tight knit")
    if state in OUTDOORSY_STATES and size < 15000:
        tags.append("outdoorsy")
    if athletics in ("high", "dominant"):
        tags.append("sports culture")
    if party >= 75:
        tags.append("party focused")
    if political == "very liberal":
        tags.append("progressive")
    if political == "conservative" and not is_religious:
        tags.append("traditional")
    if diversity >= 80:
        tags.append("diverse")
    if admit is not None and admit < 0.20:
        tags.append("selective")
    if is_public and size > 25000:
        tags.append("rah-rah")
    if not tags:
        tags = ["mainstream"]
    # Dedupe while preserving order
    seen = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]

    return dict(
        party_scene=party,
        academic_intensity=academic,
        greek_life=greek,
        campus_setting=campus_setting,
        political_leaning=political,
        athletics_culture=athletics,
        diversity_score=diversity,
        vibe_tags=tags,
    )


# -----------------------------------------------------------------------------
# Fetching from Scorecard
# -----------------------------------------------------------------------------
def _fetch(page: int, params_extra: dict[str, Any]) -> dict[str, Any]:
    params = {
        "api_key": API_KEY,
        "per_page": 100,
        "page": page,
        "fields": FIELDS,
        "school.operating": 1,
        "school.degrees_awarded.predominant__range": "3..4",
    }
    params.update(params_extra)
    r = requests.get(URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_schools(target: int = TARGET) -> list[dict[str, Any]]:
    """Two passes: most selective first, then largest. Dedupe by unit id."""
    seen: dict[int, dict[str, Any]] = {}

    # Pass 1: selective schools (admit rate known, ascending)
    for page in range(4):
        data = _fetch(page, {
            "latest.admissions.admission_rate.overall__range": "0..0.6",
            "sort": "latest.admissions.admission_rate.overall:asc",
        })
        for s in data.get("results", []):
            if s.get("id") and s["id"] not in seen:
                seen[s["id"]] = s
        if not data.get("results") or len(seen) >= target:
            break

    # Pass 2: largest schools (for well-known publics that aren't highly selective)
    for page in range(4):
        if len(seen) >= target:
            break
        data = _fetch(page, {
            "latest.student.size__range": "5000..100000",
            "sort": "latest.student.size:desc",
        })
        for s in data.get("results", []):
            if s.get("id") and s["id"] not in seen:
                seen[s["id"]] = s
        if not data.get("results"):
            break

    return list(seen.values())[:target]


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> int:
    if not API_KEY:
        print("COLLEGE_SCORECARD_API_KEY missing from .env", file=sys.stderr)
        return 1

    print(f"Fetching up to {TARGET} schools from Scorecard...")
    schools = fetch_schools(TARGET)
    print(f"  got {len(schools)} schools")

    entries: list[dict[str, Any]] = []
    curated_hits = 0
    for s in schools:
        name = s.get("school.name") or ""
        curated = _curated(name)
        if curated:
            base = curated
            curated_hits += 1
        else:
            base = _heuristic(s)

        entries.append({
            "name": name,
            "unit_id": s.get("id"),
            **base,
        })

    out_path = Path(__file__).resolve().parent.parent / "data" / "school_vibes.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, indent=2))
    print(f"Wrote {len(entries)} entries to {out_path}")
    print(f"  curated: {curated_hits},  heuristic: {len(entries) - curated_hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
