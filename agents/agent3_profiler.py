"""
Agent 3: Profile Card Builder.

Takes the top-ranked FitScores from Agent 2 and builds rich, structured
profile cards that a Streamlit dashboard can render directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent1_matcher import StudentProfile
from .agent2_scorer import CATEGORIES, BIG_METRO_CITIES, STATE_CLIMATE, FitScore

CATEGORY_LABELS = {
    "academic_fit": "Academic Fit",
    "affordability": "Affordability",
    "location_fit": "Location",
    "weather_fit": "Weather",
    "vibe_fit": "Campus Vibe",
}

OWNERSHIP_LABEL = {1: "public", 2: "private nonprofit", 3: "for-profit"}

CLIMATE_SUMMARY = {
    "warm":     "Warm year-round — think t-shirt weather most of the calendar.",
    "mild":     "Mild climate with moderate winters and comfortable summers.",
    "cold":     "Cold winters with real snow; pack a serious coat.",
    "seasonal": "Full four seasons — hot summers, cold snowy winters, crisp falls.",
}

# Derived from admission-rate buckets. Honest guess, not a published stat.
GPA_BANDS: list[tuple[float, tuple[float, float]]] = [
    (0.10, (3.85, 4.00)),
    (0.25, (3.70, 3.95)),
    (0.50, (3.50, 3.85)),
    (0.75, (3.20, 3.70)),
    (1.01, (2.80, 3.50)),
]


@dataclass
class ProfileCard:
    school_id: Any
    name: str
    classification: str           # Reach / Match / Safety
    overall_fit: float            # 0-100
    category_scores: dict[str, float]
    category_labels: dict[str, str]
    description: str              # 2-3 sentence
    tuition_in_state: int | None
    tuition_out_of_state: int | None
    cost_of_attendance: int | None
    acceptance_rate: float | None # 0-1
    sat_avg: int | None
    sat_range: tuple[int, int] | None
    act_range: tuple[int, int] | None
    gpa_range: tuple[float, float] | None
    gpa_note: str
    city: str
    state: str
    location_summary: str
    climate: str
    climate_summary: str
    winter_temp_f: float | None = None
    summer_temp_f: float | None = None
    annual_precip_in: float | None = None
    precip_level: str | None = None
    graduation_rate: float | None = None   # 0-1, 4yr 150% completion (Scorecard C150_4)
    median_debt: int | None = None         # median debt of completers (Scorecard DEBT_MDN)
    international_pct: float | None = None # 0-1, non-resident-alien undergrad share
    vibe_tags: list[str] = field(default_factory=list)
    vibe_campus_setting: str | None = None
    vibe_political_leaning: str | None = None
    vibe_athletics_culture: str | None = None
    vibe_greek_life: str | None = None
    vibe_party_scene: int | None = None
    vibe_academic_intensity: int | None = None
    vibe_diversity_score: int | None = None
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    url: str | None = None


def _size_bucket(size: int | None) -> str:
    if not size:
        return "mid-sized"
    if size < 2000:
        return "very small"
    if size < 5000:
        return "small"
    if size < 15000:
        return "mid-sized"
    if size < 30000:
        return "large"
    return "very large"


def _selectivity_phrase(admit: float | None) -> str:
    if admit is None:
        return "an institution"
    if admit < 0.15:
        return "a highly selective institution"
    if admit < 0.35:
        return "a selective institution"
    if admit < 0.65:
        return "a moderately selective institution"
    return "an accessible institution"


def _location_summary(city: str | None, state: str | None, size: int | None) -> str:
    city = city or ""
    state = state or ""
    in_metro = city.lower() in BIG_METRO_CITIES
    if in_metro:
        return f"Urban campus in {city}, {state}."
    if size and size >= 20000:
        return f"Large campus in {city}, {state}."
    if size and size < 3000:
        return f"Small college town feel in {city}, {state}."
    return f"{city}, {state}."


def _climate(school: dict[str, Any]) -> tuple[str, str]:
    """Prefer measured climate from Open-Meteo; fall back to state map."""
    label = school.get("climate_label")
    if not label or label == "unknown":
        label = STATE_CLIMATE.get((school.get("state") or "").upper(), "unknown")

    base = CLIMATE_SUMMARY.get(label, "Climate varies — check local conditions.")

    winter = school.get("winter_temp_f")
    summer = school.get("summer_temp_f")
    precip = school.get("annual_precip_in")
    precip_level = school.get("precip_level")

    stats: list[str] = []
    if winter is not None:
        stats.append(f"winter avg {winter:.0f}°F")
    if summer is not None:
        stats.append(f"summer avg {summer:.0f}°F")
    if precip is not None and precip_level:
        stats.append(f"{precip:.0f} in/yr rainfall ({precip_level})")

    if stats:
        return label, f"{base} ({', '.join(stats)})"
    return label, base


def _gpa_range(admit: float | None) -> tuple[tuple[float, float] | None, str]:
    if admit is None:
        return None, "GPA not published and no admission rate available."
    for ceiling, band in GPA_BANDS:
        if admit < ceiling:
            return band, "Estimated middle 50% based on selectivity (Scorecard does not publish GPA)."
    return None, "GPA not published."


def _sat_range(school: dict[str, Any]) -> tuple[int, int] | None:
    lo = school.get("sat_25")
    hi = school.get("sat_75")
    if lo and hi:
        return int(lo), int(hi)
    avg = school.get("sat_avg")
    if avg:
        return int(avg - 60), int(avg + 60)   # ±60 as rough fallback
    return None


def _act_range(school: dict[str, Any]) -> tuple[int, int] | None:
    lo = school.get("act_25")
    hi = school.get("act_75")
    if lo and hi:
        return int(lo), int(hi)
    mid = school.get("act_mid")
    if mid:
        return int(mid - 2), int(mid + 2)
    return None


def _describe(school: dict[str, Any], profile: StudentProfile) -> str:
    size = school.get("size")
    admit = school.get("admission_rate")
    ownership = OWNERSHIP_LABEL.get(school.get("ownership"), "")
    city = school.get("city") or ""
    state = school.get("state") or ""
    size_word = _size_bucket(size)
    selectivity = _selectivity_phrase(admit)

    s1 = f"{school.get('name')} is a {size_word} {ownership} institution in {city}, {state}.".strip()

    if admit is not None:
        s2 = f"{selectivity.capitalize()} ({int(admit * 100)}% admission rate)"
        if size:
            s2 += f" with around {size:,} undergraduates"
        s2 += "."
    else:
        s2 = f"{selectivity.capitalize()}."

    # Sentence 3: who thrives, composed from context cues.
    phrases: list[str] = []
    if admit is not None and admit < 0.25:
        phrases.append("academically driven students who come prepared for rigorous coursework")
    elif size and size >= 20000:
        phrases.append("students who enjoy a broad, varied academic offering and lots of activity")
    elif size and size < 3000:
        phrases.append("students who value close faculty relationships and a tight-knit community")

    if (city or "").lower() in BIG_METRO_CITIES:
        phrases.append("people who want to take advantage of a major city's internships and culture")

    if profile.intended_major and any(
        profile.intended_major.lower() in (p or "").lower()
        for p in school.get("programs", [])
    ):
        phrases.append(f"students focused on {profile.intended_major}")

    if phrases:
        s3 = "It tends to suit " + _join_with_and(phrases[:2]) + "."
    else:
        s3 = "A good option for students whose priorities line up with what this school offers."

    return " ".join([s1, s2, s3])


def _join_with_and(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{items[0]} and {items[1]}"


def _user_priorities(weights: dict[str, float], top_n: int = 3) -> list[str]:
    ranked = sorted(weights.items(), key=lambda kv: -kv[1])
    return [c for c, w in ranked if w > 0][:top_n]


def _strengths_weaknesses(
    fs: FitScore, profile: StudentProfile, weights: dict[str, float]
) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    priorities = _user_priorities(weights)
    school = fs.school

    for cat in priorities:
        score = fs.categories[cat]
        label = CATEGORY_LABELS[cat]
        if score >= 80:
            strengths.append(f"{label} matches your priorities ({score:.0f}/100).")
        elif score <= 55:
            weaknesses.append(f"{label} falls short of what you asked for ({score:.0f}/100).")

    # Concrete budget detail — always useful if data is present.
    coa = school.get("cost_of_attendance")
    if profile.budget and coa:
        if coa < profile.budget * 0.75:
            strengths.append(f"Well under budget: ${coa:,} vs your ${profile.budget:,} cap.")
        elif coa > profile.budget:
            weaknesses.append(f"Above budget by ${coa - profile.budget:,}/year.")

    # Academic stretch/reach reality check.
    if fs.classification == "Reach":
        weaknesses.append("Classified as a Reach — admission is unlikely even for strong applicants.")
    elif fs.classification == "Safety":
        strengths.append("Classified as a Safety — a realistic admit based on your stats.")

    if school.get("admission_rate") is not None and school["admission_rate"] < 0.10:
        weaknesses.append(
            f"Extremely low admission rate ({int(school['admission_rate']*100)}%) — apply, but don't count on it."
        )

    # Fallbacks so cards are never empty.
    if not strengths:
        best_cat, best_score = max(fs.categories.items(), key=lambda kv: kv[1])
        strengths.append(f"Strongest dimension: {CATEGORY_LABELS[best_cat]} ({best_score:.0f}/100).")
    if not weaknesses:
        worst_cat, worst_score = min(fs.categories.items(), key=lambda kv: kv[1])
        if worst_score < 70:
            weaknesses.append(f"Weakest dimension: {CATEGORY_LABELS[worst_cat]} ({worst_score:.0f}/100).")

    return strengths, weaknesses


def build_profile_cards(
    scored: list[FitScore],
    profile: StudentProfile,
    weights: dict[str, float],
    top_n: int = 15,
) -> list[ProfileCard]:
    cards: list[ProfileCard] = []

    for fs in scored[:top_n]:
        school = fs.school
        climate, climate_summary = _climate(school)
        gpa_range, gpa_note = _gpa_range(school.get("admission_rate"))
        strengths, weaknesses = _strengths_weaknesses(fs, profile, weights)

        # Compose vibe tags from the vibe dataset, plus auto-inject
        # "international friendly" for schools with >10% international.
        vibe_tags = list((school.get("vibe") or {}).get("vibe_tags") or [])
        intl_pct = school.get("international_pct")
        if intl_pct is not None and intl_pct > 0.10 and "international friendly" not in vibe_tags:
            vibe_tags.append("international friendly")

        url = school.get("url")
        if url and not url.startswith("http"):
            url = f"https://{url}"

        cards.append(ProfileCard(
            school_id=fs.school_id,
            name=fs.name,
            classification=fs.classification,
            overall_fit=fs.overall,
            category_scores=fs.categories,
            category_labels=CATEGORY_LABELS,
            description=_describe(school, profile),
            tuition_in_state=school.get("in_state_tuition"),
            tuition_out_of_state=school.get("out_of_state_tuition"),
            cost_of_attendance=school.get("cost_of_attendance"),
            acceptance_rate=school.get("admission_rate"),
            sat_avg=school.get("sat_avg"),
            sat_range=_sat_range(school),
            act_range=_act_range(school),
            gpa_range=gpa_range,
            gpa_note=gpa_note,
            city=school.get("city") or "",
            state=school.get("state") or "",
            location_summary=_location_summary(
                school.get("city"), school.get("state"), school.get("size")
            ),
            climate=climate,
            climate_summary=climate_summary,
            winter_temp_f=school.get("winter_temp_f"),
            summer_temp_f=school.get("summer_temp_f"),
            annual_precip_in=school.get("annual_precip_in"),
            precip_level=school.get("precip_level"),
            graduation_rate=school.get("graduation_rate"),
            median_debt=school.get("median_debt"),
            international_pct=school.get("international_pct"),
            vibe_tags=vibe_tags,
            vibe_campus_setting=(school.get("vibe") or {}).get("campus_setting"),
            vibe_political_leaning=(school.get("vibe") or {}).get("political_leaning"),
            vibe_athletics_culture=(school.get("vibe") or {}).get("athletics_culture"),
            vibe_greek_life=(school.get("vibe") or {}).get("greek_life"),
            vibe_party_scene=(school.get("vibe") or {}).get("party_scene"),
            vibe_academic_intensity=(school.get("vibe") or {}).get("academic_intensity"),
            vibe_diversity_score=(school.get("vibe") or {}).get("diversity_score"),
            strengths=strengths,
            weaknesses=weaknesses,
            url=url,
        ))

    return cards
