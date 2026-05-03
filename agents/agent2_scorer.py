"""
Agent 2: Fit Scorer.

Takes a StudentProfile and the list of candidate schools from Agent 1,
scores each across five categories (0-100), computes a weighted overall
score, and classifies each school as Reach / Match / Safety.

Weights come from the user (what matters most). Categories the user
doesn't care about can be zero-weighted and they drop out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent1_matcher import StudentProfile

CATEGORIES = ["academic_fit", "affordability", "location_fit", "weather_fit", "vibe_fit"]

DEFAULT_WEIGHTS: dict[str, float] = {c: 1.0 for c in CATEGORIES}

# Rough state -> climate buckets. Simplification — California really has
# multiple climates, but for a one-line-per-state mapping this is workable.
STATE_CLIMATE: dict[str, str] = {
    # warm / hot
    **{s: "warm" for s in ["HI", "FL", "TX", "AZ", "NM", "LA", "MS", "AL", "GA", "SC", "NV"]},
    # mild
    **{s: "mild" for s in ["CA", "OR", "WA", "NC", "VA", "TN", "KY", "MD", "DC", "AR", "OK"]},
    # cold
    **{s: "cold" for s in ["AK", "ME", "VT", "NH", "MN", "ND", "SD", "WI", "MI", "MT", "WY", "ID"]},
    # seasonal (4-season)
    **{s: "seasonal" for s in ["NY", "PA", "NJ", "MA", "CT", "RI", "OH", "IN", "IL", "IA",
                                "MO", "KS", "NE", "WV", "DE", "CO", "UT"]},
}

# Regional grouping for partial-credit location scoring.
STATE_REGION: dict[str, str] = {
    **{s: "West" for s in ["CA", "OR", "WA", "NV", "AZ", "ID", "UT", "MT", "WY", "CO", "NM", "AK", "HI"]},
    **{s: "Midwest" for s in ["IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"]},
    **{s: "Northeast" for s in ["CT", "ME", "MA", "NH", "NJ", "NY", "PA", "RI", "VT"]},
    **{s: "South" for s in ["AL", "AR", "DE", "DC", "FL", "GA", "KY", "LA", "MD", "MS", "NC",
                             "OK", "SC", "TN", "TX", "VA", "WV"]},
}

# Big-metro lookup for the "big-city" vibe.
BIG_METRO_CITIES = {
    "new york", "brooklyn", "los angeles", "chicago", "houston", "phoenix",
    "philadelphia", "san antonio", "san diego", "dallas", "austin",
    "san francisco", "seattle", "denver", "boston", "washington", "atlanta",
    "miami", "minneapolis", "detroit", "portland", "las vegas",
}


@dataclass
class FitScore:
    school_id: Any
    name: str
    overall: float                       # 0-100
    categories: dict[str, float]         # per-category 0-100
    classification: str                  # Reach / Match / Safety
    notes: list[str] = field(default_factory=list)
    school: dict[str, Any] = field(default_factory=dict)  # passthrough


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def normalize_gpa(gpa: float | None, scale: float) -> float | None:
    """
    Convert a raw GPA on the student's chosen scale to a 4.0-equivalent so
    every downstream comparison against school averages happens on the same
    scale.

    - 4.0 scale: passthrough when gpa <= 4.0; divide by 1.25 above 4.0 so a
      weighted 5.0 (AP/honors max) lands at 4.0 and 4.5 lands at 3.6.
    - 5.0 scale: always multiply by 0.8 so 5.0 → 4.0 and 4.0 → 3.2.

    Returns None when gpa is None so existing None-checks keep working.
    """
    if gpa is None:
        return None
    if scale == 4.0:
        return gpa / 1.25 if gpa > 4.0 else gpa
    if scale == 5.0:
        return gpa * 0.8
    return gpa  # Unknown scale — passthrough rather than mis-normalize.


def _academic_fit(profile: StudentProfile, school: dict[str, Any]) -> tuple[float, list[str]]:
    """
    How academically appropriate is this school for the student?

    At or above the school's level -> high score (100 at par, easing to ~85
    when the student is way above — still a strong fit, just not a
    stretch). Below the school's level -> drops off linearly.
    Reach/Match/Safety classification is handled separately.
    """
    notes: list[str] = []
    parts: list[float] = []

    student_sat = profile.effective_sat()
    school_sat = school.get("sat_avg")
    if student_sat and school_sat:
        diff = student_sat - school_sat
        if diff >= 0:
            # 100 at par, gently easing toward ~85 as the student floats above.
            score = max(85.0, 100 - max(0, diff - 50) * 0.1)
        else:
            # 100 just below par, down to floor of 20 for very-below students.
            score = max(20.0, 100 + diff * 0.4)
        parts.append(_clamp(score))
    elif student_sat and not school_sat:
        notes.append("No published SAT avg for this school.")

    admit = school.get("admission_rate")
    student_gpa = normalize_gpa(profile.gpa, profile.gpa_scale)
    if admit is not None and student_gpa is not None:
        # Implied school GPA from admission rate:
        # admit=0.05 -> 3.95, admit=0.5 -> 3.5, admit=0.9 -> 3.1
        implied_gpa = 3.0 + (1 - admit) * 1.0
        gpa_diff = student_gpa - implied_gpa
        if gpa_diff >= 0:
            score = max(85.0, 100 - max(0, gpa_diff - 0.1) * 30)
        else:
            score = max(20.0, 100 + gpa_diff * 80)
        parts.append(_clamp(score))

    if not parts:
        notes.append("Not enough data to compute academic fit; defaulting to 60.")
        return 60.0, notes

    return sum(parts) / len(parts), notes


def _affordability(profile: StudentProfile, school: dict[str, Any]) -> tuple[float, list[str]]:
    coa = school.get("cost_of_attendance")
    if not profile.budget:
        return 70.0, ["No budget specified; neutral affordability."]
    if coa is None:
        return 50.0, ["No published cost of attendance; neutral."]

    ratio = coa / profile.budget
    # 100 at ratio<=0.6, 80 at 0.9, 60 at 1.0, 30 at 1.3, 0 beyond 1.5.
    if ratio <= 0.6:
        base = 100.0
    elif ratio <= 1.0:
        base = _clamp(100 - (ratio - 0.6) * 100)
    elif ratio <= 1.5:
        base = _clamp(60 - (ratio - 1.0) * 120)
    else:
        base = 0.0

    notes: list[str] = []
    if ratio > 1.0:
        notes.append(f"COA is {int((ratio-1)*100)}% over budget.")

    # IPEDS bonus — schools that hand out generous institutional aid get a
    # small lift for budget-constrained students. Only applies when the
    # student set a real budget under $50k AND avg aid >= $10k.
    avg_aid = school.get("ipeds_avg_institutional_aid")
    if profile.budget and profile.budget < 50_000 and avg_aid and avg_aid >= 10_000:
        bonus = min(8.0, avg_aid / 5_000)   # ~2 pts per $10k aid, max +8
        base = _clamp(base + bonus)
        notes.append(
            f"Generous institutional aid (~${avg_aid:,}/recipient) lifts "
            f"affordability for tighter budgets."
        )

    return base, notes


def _location_fit(profile: StudentProfile, school: dict[str, Any]) -> tuple[float, list[str]]:
    pref = (profile.state or "").upper()
    sch_state = (school.get("state") or "").upper()
    if not pref:
        return 70.0, ["No location preference; neutral."]
    if not sch_state:
        return 50.0, []
    if pref == sch_state:
        return 100.0, []
    if STATE_REGION.get(pref) and STATE_REGION.get(pref) == STATE_REGION.get(sch_state):
        return 70.0, [f"Same region ({STATE_REGION[pref]}), different state."]
    return 30.0, ["Different region than preferred."]


def _weather_fit(profile: StudentProfile, school: dict[str, Any]) -> tuple[float, list[str]]:
    pref = (profile.weather_pref or "").lower()
    if not pref or pref == "no preference":
        return 100.0, []

    # Prefer measured climate from Open-Meteo; fall back to the state map
    # when we don't have coordinates or the API call failed.
    climate = school.get("climate_label")
    if not climate or climate == "unknown":
        sch_state = (school.get("state") or "").upper()
        climate = STATE_CLIMATE.get(sch_state)

    if not climate:
        return 60.0, ["No climate data available; neutral."]

    if climate == pref:
        return 100.0, []

    adjacency = {
        ("warm", "mild"): 70, ("mild", "warm"): 70,
        ("mild", "seasonal"): 70, ("seasonal", "mild"): 70,
        ("seasonal", "cold"): 70, ("cold", "seasonal"): 70,
    }
    return adjacency.get((climate, pref), 30.0), [f"School climate is {climate}, you prefer {pref}."]


def _vibe_fit(profile: StudentProfile, school: dict[str, Any]) -> tuple[float, list[str]]:
    prefs = [v for v in (profile.vibe_prefs or []) if v]
    if not prefs:
        return 100.0, []

    # Imported locally to avoid a hard cycle between agent2 and vibe modules.
    from .vibe import score_vibe_preference

    vibe = school.get("vibe")  # populated by agents.vibe.enrich_schools_with_vibes
    scored: list[float] = []
    notes: list[str] = []
    for pref in prefs:
        score, note = score_vibe_preference(pref, vibe, school)
        scored.append(score)
        if note:
            notes.append(note)

    base = sum(scored) / len(scored)

    # IPEDS bonuses — applied on top of the existing vibe scoring.
    pref_tokens = {v.lower() for v in prefs}

    sfr = school.get("ipeds_student_faculty_ratio")
    if sfr and sfr <= 12 and any(p in pref_tokens for p in ("small-town", "rural")):
        base = _clamp(base + 5.0)
        notes.append(f"Low student/faculty ratio ({sfr}:1) suits a tight-knit feel.")

    ath_div = school.get("ipeds_athletics_division")
    if ath_div in ("NCAA", "NAIA") and any(
        ("sporty" in p) or ("athletic" in p) for p in pref_tokens
    ):
        bump = 4.0 if ath_div == "NCAA" else 2.0
        base = _clamp(base + bump)
        notes.append(f"{ath_div} athletics aligns with your sporty preference.")

    return base, notes


def _classify(profile: StudentProfile, school: dict[str, Any]) -> str:
    """
    Reach / Match / Safety classifier.

    Rules, in order:
      1. Acceptance rate < 10% → always Reach (elite schools are reaches for
         everyone, regardless of stats).
      2. Acceptance rate 10%–20% → Reach unless the student's SAT is above
         the school's 75th percentile (then fall through to normal eval).
      3. Acceptance rate > 20% (or the SAT-above-75 exception) → normal eval:
           Safety = SAT > school 75th AND GPA comfortably above school avg
           Match  = SAT within 25th–75th AND GPA near average
           Reach  = SAT < 25th OR GPA clearly below average
      4. If SAT data is missing, fall back to acceptance rate only:
           < 20% → Reach, 20%–50% → Match, > 50% → Safety.
    """
    admit = school.get("admission_rate")
    student_sat = profile.effective_sat()
    student_gpa = normalize_gpa(profile.gpa, profile.gpa_scale)
    sat_25 = school.get("sat_25")
    sat_75 = school.get("sat_75")

    # Rule 1: very-selective schools are always a Reach.
    if admit is not None and admit < 0.10:
        return "Reach"

    # Rule 2: 10%–20% admit — Reach unless SAT clears the 75th percentile.
    if admit is not None and admit < 0.20:
        if not (student_sat and sat_75 and student_sat > sat_75):
            return "Reach"
        # else fall through to the normal SAT/GPA evaluation below.

    # Normal evaluation. Prefer the SAT percentile path when we have it.
    if student_sat and sat_25 and sat_75:
        above_75 = student_sat > sat_75
        below_25 = student_sat < sat_25

        if admit is not None and student_gpa is not None:
            implied_gpa = 3.0 + (1 - admit) * 1.0
            gpa_comfortably_above = student_gpa >= implied_gpa + 0.10
            gpa_clearly_below     = student_gpa < implied_gpa - 0.15

            if above_75 and gpa_comfortably_above:
                return "Safety"
            if below_25 or gpa_clearly_below:
                return "Reach"
            # Strong SAT + OK GPA, or SAT in-range + OK GPA → Match.
            return "Match"

        # GPA missing — classify on SAT percentile alone.
        if above_75:
            return "Safety"
        if below_25:
            return "Reach"
        return "Match"

    # Rule 4 fallback: no SAT data → use acceptance rate only.
    if admit is not None:
        if admit < 0.20:
            return "Reach"
        if admit < 0.50:
            return "Match"
        return "Safety"

    # No SAT, no admit rate, no GPA relationship — default to Match.
    return "Match"


def _normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    w = dict(weights or DEFAULT_WEIGHTS)
    for c in CATEGORIES:
        w.setdefault(c, 0.0)
    total = sum(max(0.0, w[c]) for c in CATEGORIES)
    if total <= 0:
        # All zeros — fall back to equal weights so we still produce a score.
        return {c: 1.0 / len(CATEGORIES) for c in CATEGORIES}
    return {c: max(0.0, w[c]) / total for c in CATEGORIES}


def score_schools(
    profile: StudentProfile,
    schools: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> list[FitScore]:
    """Score every school and return sorted highest-overall first."""
    w = _normalize_weights(weights)
    out: list[FitScore] = []

    for s in schools:
        cat_scores: dict[str, float] = {}
        notes: list[str] = []

        for name, fn in [
            ("academic_fit", _academic_fit),
            ("affordability", _affordability),
            ("location_fit", _location_fit),
            ("weather_fit", _weather_fit),
            ("vibe_fit", _vibe_fit),
        ]:
            score, n = fn(profile, s)
            cat_scores[name] = round(score, 1)
            notes.extend(n)

        overall = sum(cat_scores[c] * w[c] for c in CATEGORIES)

        out.append(FitScore(
            school_id=s.get("id"),
            name=s.get("name") or "Unknown",
            overall=round(overall, 1),
            categories=cat_scores,
            classification=_classify(profile, s),
            notes=notes,
            school=s,
        ))

    out.sort(key=lambda x: x.overall, reverse=True)
    return out
