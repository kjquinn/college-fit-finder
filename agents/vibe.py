"""
Vibe dataset loader and scoring helpers.

Reads data/school_vibes.json (produced by scripts/generate_vibes.py),
indexes entries by Scorecard unit ID, and exposes helpers for attaching
vibe data to school dicts and scoring user-preference matches.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

VIBE_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "school_vibes.json"

VIBE_FIELDS = [
    "party_scene", "academic_intensity", "greek_life", "campus_setting",
    "political_leaning", "athletics_culture", "diversity_score", "vibe_tags",
]


@lru_cache(maxsize=1)
def _index() -> dict[int, dict[str, Any]]:
    if not VIBE_DATA_PATH.exists():
        return {}
    try:
        raw = json.loads(VIBE_DATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {int(e["unit_id"]): e for e in raw if e.get("unit_id") is not None}


def get_vibe(unit_id: Any) -> dict[str, Any] | None:
    if unit_id is None:
        return None
    try:
        return _index().get(int(unit_id))
    except (TypeError, ValueError):
        return None


def enrich_schools_with_vibes(schools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach a `vibe` sub-dict to each school with a matching unit ID."""
    for s in schools:
        v = get_vibe(s.get("id"))
        if v:
            s["vibe"] = {k: v.get(k) for k in VIBE_FIELDS}
    return schools


# -----------------------------------------------------------------------------
# Scoring helpers — used by Agent 2's _vibe_fit.
# -----------------------------------------------------------------------------
GREEK_SCORES = {"high": 100, "medium": 70, "low": 35, "none": 10}
ATHLETICS_SCORES = {"dominant": 100, "high": 85, "medium": 60, "low": 25}
SETTING_SCORES = {
    "big-city": {"urban": 100, "suburban": 50, "college town": 30, "rural": 15},
    "small-town": {"college town": 100, "rural": 80, "suburban": 50, "urban": 20},
    "suburban": {"suburban": 100, "college town": 65, "urban": 45, "rural": 40},
    "rural": {"rural": 100, "college town": 70, "suburban": 35, "urban": 15},
}

POLITICAL_MATCH = {
    "liberal": {"very liberal": 95, "liberal": 100, "moderate": 50, "conservative": 10},
    "conservative": {"conservative": 100, "moderate": 55, "liberal": 15, "very liberal": 5},
}


def score_vibe_preference(
    pref: str, vibe: dict[str, Any] | None, school: dict[str, Any]
) -> tuple[float, str | None]:
    """
    Score one user-selected vibe against a school. Prefers the rich vibe
    dataset; falls back to observable school data (city, size) when the
    school isn't in the dataset.
    """
    p = pref.lower().strip()

    # Campus-setting family — has a fallback using city/size.
    setting_key = None
    if "big-city" in p or "big city" in p:
        setting_key = "big-city"
    elif "small-town" in p or "small town" in p:
        setting_key = "small-town"
    elif "suburban" in p:
        setting_key = "suburban"
    elif "rural" in p:
        setting_key = "rural"

    if setting_key:
        if vibe and vibe.get("campus_setting"):
            return SETTING_SCORES[setting_key].get(vibe["campus_setting"], 30), None
        # Fallback — coarse inference from observable data.
        from .agent2_scorer import BIG_METRO_CITIES  # local import avoids cycles
        city = (school.get("city") or "").lower()
        size = school.get("size") or 0
        is_big = city in BIG_METRO_CITIES or size >= 20000
        is_small = 0 < size < 3000 and not is_big
        if setting_key == "big-city":
            return (100 if is_big else 30), None
        if setting_key == "small-town":
            return (100 if is_small else 40), None
        if setting_key == "suburban":
            return (60 if not is_big and not is_small else 40), None
        if setting_key == "rural":
            return (80 if is_small else 25), None

    # Everything below requires the dataset.
    if not vibe:
        return 60.0, f"'{pref}' needs vibe data; this school isn't in the top-400 set."

    if "sporty" in p or "athletic" in p:
        return ATHLETICS_SCORES.get(vibe.get("athletics_culture"), 50), None

    if "greek" in p:
        return GREEK_SCORES.get(vibe.get("greek_life"), 50), None

    if "academic" in p or "nerdy" in p:
        ai = vibe.get("academic_intensity") or 50
        if ai >= 90: return 100.0, None
        if ai >= 80: return 85.0, None
        if ai >= 65: return 60.0, None
        return 30.0, None

    if "artsy" in p:
        tags = [t.lower() for t in (vibe.get("vibe_tags") or [])]
        if "artsy" in tags: return 100.0, None
        if "counterculture" in tags or "progressive" in tags: return 75.0, None
        return 40.0, None

    if "outdoorsy" in p:
        tags = [t.lower() for t in (vibe.get("vibe_tags") or [])]
        if "outdoorsy" in tags: return 100.0, None
        if "environmental" in tags: return 70.0, None
        return 35.0, None

    if "diverse" in p:
        d = vibe.get("diversity_score") or 50
        # Scale: 85+ → 100, 70 → 80, 50 → 50.
        return max(20.0, min(100.0, float(d))), None

    if "liberal" in p:
        return POLITICAL_MATCH["liberal"].get(vibe.get("political_leaning"), 40), None

    if "conservative" in p:
        return POLITICAL_MATCH["conservative"].get(vibe.get("political_leaning"), 40), None

    return 60.0, f"Unrecognized vibe preference: {pref}"
