"""College Fit Finder — onboarding survey + tabbed results dashboard."""

from __future__ import annotations

import time
from typing import Any, Iterable

import streamlit as st

from agents.agent1_matcher import (
    ScorecardError,
    StudentProfile,
    find_matching_schools,
)
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import ProfileCard, build_profile_cards
from agents.vibe import enrich_schools_with_vibes
from agents.weather import enrich_schools_with_climate


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
US_STATES_FULL = [
    ("", ""),
    ("Alabama", "AL"), ("Alaska", "AK"), ("Arizona", "AZ"), ("Arkansas", "AR"),
    ("California", "CA"), ("Colorado", "CO"), ("Connecticut", "CT"), ("Delaware", "DE"),
    ("Florida", "FL"), ("Georgia", "GA"), ("Hawaii", "HI"), ("Idaho", "ID"),
    ("Illinois", "IL"), ("Indiana", "IN"), ("Iowa", "IA"), ("Kansas", "KS"),
    ("Kentucky", "KY"), ("Louisiana", "LA"), ("Maine", "ME"), ("Maryland", "MD"),
    ("Massachusetts", "MA"), ("Michigan", "MI"), ("Minnesota", "MN"), ("Mississippi", "MS"),
    ("Missouri", "MO"), ("Montana", "MT"), ("Nebraska", "NE"), ("Nevada", "NV"),
    ("New Hampshire", "NH"), ("New Jersey", "NJ"), ("New Mexico", "NM"), ("New York", "NY"),
    ("North Carolina", "NC"), ("North Dakota", "ND"), ("Ohio", "OH"), ("Oklahoma", "OK"),
    ("Oregon", "OR"), ("Pennsylvania", "PA"), ("Rhode Island", "RI"), ("South Carolina", "SC"),
    ("South Dakota", "SD"), ("Tennessee", "TN"), ("Texas", "TX"), ("Utah", "UT"),
    ("Vermont", "VT"), ("Virginia", "VA"), ("Washington", "WA"), ("West Virginia", "WV"),
    ("Wisconsin", "WI"), ("Wyoming", "WY"),
]
STATE_NAME_TO_CODE = {n: c for n, c in US_STATES_FULL}

REGION_TO_STATES: dict[str, set[str]] = {
    "Northeast": {"CT", "ME", "MA", "NH", "NJ", "NY", "PA", "RI", "VT"},
    "Southeast": {"AL", "AR", "DE", "FL", "GA", "KY", "LA", "MD", "MS", "NC",
                  "SC", "TN", "VA", "WV", "DC"},
    "Midwest":   {"IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"},
    "Southwest": {"AZ", "NM", "OK", "TX"},
    "West Coast": {"CA", "OR", "WA", "AK", "HI", "NV"},
}

CLIMATE_OPTIONS = ["Warm and sunny", "Mild and seasonal", "Cold and snowy", "No preference"]
CLIMATE_TO_BACKEND = {
    "Warm and sunny": "Warm",
    "Mild and seasonal": "Mild",
    "Cold and snowy": "Cold",
}

REGION_OPTIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West Coast", "No preference"]
DISTANCE_OPTIONS = ["No preference", "Within 500 miles", "Within 1000 miles", "Anywhere"]

CAMPUS_SIZE_OPTIONS = [
    "Small (under 5,000 students)",
    "Medium (5,000–15,000)",
    "Large (over 15,000)",
    "No preference",
]
SIZE_TO_VIBE = {
    "Small (under 5,000 students)": "small-town",
    "Medium (5,000–15,000)": "suburban",
    "Large (over 15,000)": "big-city",
}

VIBE_OPTIONS = [
    "Academic & research focused",
    "Balanced",
    "Social & party",
    "Strong athletics",
    "Artsy & creative",
    "Pre-professional",
]
VIBE_TO_BACKEND = {
    "Academic & research focused": "academic",
    "Strong athletics": "sporty",
    "Artsy & creative": "artsy",
    "Social & party": "greek",
}

CLASSIFICATION_FILTERS = ["All", "Reach", "Match", "Safety"]
STACK_FILTERS = [
    ("under_30k",   "Under $30k"),
    ("warm",        "Warm climate"),
    ("cold",        "Cold climate"),
    ("small",       "Small school"),
    ("large",       "Large school"),
]
STACK_FILTER_LABELS = [label for _, label in STACK_FILTERS]
STACK_FILTER_LABEL_TO_KEY = {label: key for key, label in STACK_FILTERS}

LOADING_MESSAGES = [
    "Searching thousands of colleges...",
    "Analyzing your academic fit...",
    "Checking weather and climate data...",
    "Scoring campus vibes...",
    "Building your personalized list...",
]

ACCENT = "#185FA5"

# School-initial square palette — cycled by initial letter so different
# schools get different colors without any per-school mapping.
INITIAL_PALETTE = ["#185FA5", "#2E7D32", "#C2410C", "#6A1B9A", "#00838F", "#AD1457", "#4527A0"]


# -----------------------------------------------------------------------------
# CSS
# -----------------------------------------------------------------------------
CSS = f"""
<style>
/* ── Page ────────────────────────────────────────────────────────────── */
.stApp {{ background: #f5f6f8; }}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}

/* ── Typography ─────────────────────────────────────────────────────── */
.cff-title {{
    font-weight: 700; font-size: 1.75rem; color: #1a1a1a;
    text-align: center; margin: 0.25rem 0 0.5rem;
}}
.cff-subtitle {{ text-align: center; color: #555; margin-bottom: 1rem; }}
.cff-step-title {{ font-weight: 600; font-size: 1.25rem; color: #1a1a1a; margin: 1.25rem 0 0.25rem; }}
.cff-step-hint  {{ color: #666; font-size: 0.9rem; margin-bottom: 1rem; }}

/* Narrow the container only while in the survey flow */
.cff-narrow .block-container {{ max-width: 760px; }}

/* ── Progress indicator ─────────────────────────────────────────────── */
.cff-progress {{
    display: flex; align-items: center; justify-content: center;
    padding: 1rem 0 1.5rem; max-width: 480px; margin: 0 auto;
}}
.cff-progress .step {{
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 600; font-size: 0.95rem; flex-shrink: 0; background: white;
    transition: all 0.2s ease;
}}
.cff-progress .step.completed {{ background: {ACCENT}; color: white; border: 2px solid {ACCENT}; }}
.cff-progress .step.current   {{ background: white;   color: {ACCENT}; border: 2px solid {ACCENT}; }}
.cff-progress .step.future    {{ background: white;   color: #b0b0b0; border: 2px solid #d8d8d8; }}
.cff-progress .line {{
    flex: 1; height: 2px; background: #d8d8d8; margin: 0 6px; max-width: 90px;
}}
.cff-progress .line.completed {{ background: {ACCENT}; }}

/* ── Buttons / inputs ───────────────────────────────────────────────── */
.stButton > button {{
    border-radius: 8px; font-weight: 500;
    box-shadow: none !important; transition: all 0.15s ease;
}}
.stButton > button[kind="primary"] {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: white;
}}
.stButton > button[kind="primary"]:hover {{ background: #124a83; border-color: #124a83; }}
.stButton > button[kind="secondary"] {{
    background: white; border: 1px solid #d8d8d8; color: #333;
}}

input[type="number"], input[type="text"], textarea,
.stTextInput input, .stNumberInput input,
.stSelectbox > div > div {{
    border-radius: 8px !important;
    border: 1px solid #d8d8d8 !important;
    box-shadow: none !important;
}}
input:focus, textarea:focus,
.stTextInput input:focus, .stNumberInput input:focus {{
    border-color: {ACCENT} !important;
}}

.stSlider [data-baseweb="slider"] [role="slider"] {{
    background: {ACCENT} !important; box-shadow: none !important;
}}

/* Pills (chip) look */
[data-testid="stPills"] button {{
    border-radius: 999px !important;
    border: 1px solid #d8d8d8 !important;
    background: white !important;
    box-shadow: none !important;
}}
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stPills"] button[data-selected="true"] {{
    background: {ACCENT} !important; color: white !important; border-color: {ACCENT} !important;
}}

/* Native progress bar → blue */
.stProgress > div > div > div > div {{ background: {ACCENT} !important; }}

/* ── Loading screen ─────────────────────────────────────────────────── */
.cff-loading {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 4rem 1rem; text-align: center;
}}
.cff-spinner {{
    width: 56px; height: 56px;
    border: 4px solid #e5e7eb; border-top-color: {ACCENT};
    border-radius: 50%; animation: cff-spin 1s linear infinite;
    margin: 1.5rem 0 1.5rem;
}}
@keyframes cff-spin {{ to {{ transform: rotate(360deg); }} }}
.cff-loading-msg {{ font-size: 1.05rem; color: #333; margin-top: 0.5rem; font-weight: 500; }}

/* Hide default chrome */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

/* ── Toolbar (search + school count) ────────────────────────────────── */
.cff-toolbar {{
    display: flex; align-items: center; justify-content: space-between;
    background: white; border: 1px solid #e5e7eb; border-radius: 10px;
    padding: 0.75rem 1rem; margin-bottom: 0.75rem;
}}
.cff-count {{ color: #555; font-weight: 500; font-size: 0.95rem; }}
.cff-count strong {{ color: #1a1a1a; }}

/* ── Cards (grid view) ──────────────────────────────────────────────── */
.cff-card-body {{
    min-height: 340px;
    display: flex; flex-direction: column;
}}
.cff-card-header {{
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 0.5rem; margin-bottom: 0.5rem;
}}
.cff-initial {{
    width: 40px; height: 40px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    color: white; font-weight: 700; font-size: 1.15rem;
    flex-shrink: 0;
}}
.cff-class-badge {{
    font-size: 0.75rem; font-weight: 600; padding: 3px 10px;
    border-radius: 999px; white-space: nowrap;
}}
.cff-class-badge.reach  {{ background: #fde7e9; color: #b42318; border: 1px solid #fca5a5; }}
.cff-class-badge.match  {{ background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }}
.cff-class-badge.safety {{ background: #dcfce7; color: #166534; border: 1px solid #86efac; }}

.cff-card-name {{ font-weight: 600; font-size: 1.05rem; color: #1a1a1a; line-height: 1.25; margin: 0; }}
.cff-card-sub  {{ font-size: 0.85rem; color: #666; margin: 0.1rem 0 0.4rem; }}
.cff-fit {{ font-size: 2rem; font-weight: 700; color: {ACCENT}; line-height: 1.1; margin: 0.3rem 0 0.1rem; }}
.cff-fit-label {{ font-size: 0.75rem; color: #666; margin-bottom: 0.4rem; letter-spacing: 0.03em; }}

.cff-thin-bar {{
    width: 100%; height: 4px; background: #eef0f3; border-radius: 2px; overflow: hidden;
    margin-bottom: 0.75rem;
}}
.cff-thin-bar > div {{ height: 100%; background: {ACCENT}; border-radius: 2px; }}

.cff-mini-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; margin-bottom: 0.6rem;
}}
.cff-mini-cell {{
    border: 1px solid #eef0f3; border-radius: 8px; padding: 0.4rem 0.55rem;
}}
.cff-mini-cell .label {{ font-size: 0.7rem; color: #666; letter-spacing: 0.03em; }}
.cff-mini-cell .value {{ font-size: 0.95rem; font-weight: 600; color: #1a1a1a; margin-top: 2px; }}

.cff-vibe-chips {{
    display: flex; flex-wrap: wrap; gap: 4px; margin-top: auto; padding-top: 0.4rem;
}}
.cff-vibe-chip {{
    font-size: 0.72rem; padding: 2px 8px; border-radius: 999px;
    background: #f0f2f5; color: #333; border: 1px solid #e5e7eb;
}}

/* ── School profile page ────────────────────────────────────────────── */
.cff-profile-header {{
    display: flex; align-items: center; justify-content: space-between; gap: 1rem;
    padding-bottom: 0.5rem;
}}
.cff-profile-name {{ font-size: 1.75rem; font-weight: 700; color: #1a1a1a; margin: 0; }}
.cff-profile-sub  {{ color: #555; margin: 0.25rem 0 0.25rem; }}
.cff-profile-fit  {{
    text-align: right; font-size: 3rem; font-weight: 700;
    color: {ACCENT}; line-height: 1;
}}
.cff-profile-fit-lbl {{ color: #666; font-size: 0.8rem; text-align: right; }}

.cff-section-title {{
    font-weight: 600; font-size: 1.05rem; color: #1a1a1a;
    margin: 1rem 0 0.5rem;
}}
.cff-stat-grid {{
    display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 0.5rem;
}}
.cff-stat-grid.two {{ grid-template-columns: 1fr 1fr; }}
.cff-stat-cell {{
    background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.6rem 0.75rem;
}}
.cff-stat-cell .label {{ font-size: 0.72rem; color: #666; letter-spacing: 0.03em; }}
.cff-stat-cell .value {{ font-size: 1rem; font-weight: 600; color: #1a1a1a; margin-top: 2px; }}

.cff-bar-row {{ margin-bottom: 0.5rem; }}
.cff-bar-label {{
    display: flex; justify-content: space-between;
    font-size: 0.85rem; color: #333; margin-bottom: 3px;
}}

/* Map placeholder */
.cff-map-placeholder {{
    background: white; border: 1px solid #e5e7eb; border-radius: 10px;
    padding: 4rem 2rem; text-align: center; color: #555;
}}
.cff-map-placeholder h3 {{ margin: 0 0 0.5rem; color: #1a1a1a; font-weight: 600; }}
</style>
"""


# -----------------------------------------------------------------------------
# Streamlit bootstrap
# -----------------------------------------------------------------------------
st.set_page_config(page_title="College Fit Finder", page_icon="🎓", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------------
def _default_survey() -> dict[str, Any]:
    return {
        "gpa": 3.5, "sat": None, "act": None, "major": "",
        "home_state_name": "", "max_distance": "No preference",
        "climates": [], "regions": [],
        "budget": 40_000, "campus_size": "No preference", "vibes": [],
        "weights": {
            "academic_fit": 3, "affordability": 3,
            "location_fit": 3, "weather_fit": 3, "vibe_fit": 3,
        },
    }


def _init_session() -> None:
    ss = st.session_state
    ss.setdefault("phase", "survey")          # survey | running | results | school_profile
    ss.setdefault("step", 1)
    ss.setdefault("survey", _default_survey())
    ss.setdefault("results", None)            # list[ProfileCard]
    ss.setdefault("schools_by_id", {})        # id -> raw enriched school dict
    ss.setdefault("last_error", None)
    # Results-page state
    ss.setdefault("main_tab", "results")      # profile | results | list
    ss.setdefault("sub_view", "List view")    # List view | Map view
    ss.setdefault("filter_class", "All")
    ss.setdefault("filter_flags", [])         # list of stack-filter labels currently active
    ss.setdefault("saved_schools", [])        # list of school ids
    ss.setdefault("selected_school_id", None) # set when viewing a profile page
    ss.setdefault("display_limit", 50)        # how many filtered cards to show in list view


_init_session()


# -----------------------------------------------------------------------------
# Profile construction (shared between the survey and the profile tab)
# -----------------------------------------------------------------------------
def _survey_to_profile_and_backend(survey: dict[str, Any]) -> tuple[StudentProfile, list[str] | None, str | None]:
    home_code = STATE_NAME_TO_CODE.get(survey["home_state_name"]) or None

    weather_pref = None
    for c in survey["climates"]:
        if c != "No preference":
            weather_pref = CLIMATE_TO_BACKEND.get(c)
            break

    vibes: list[str] = []
    for v in survey["vibes"]:
        mapped = VIBE_TO_BACKEND.get(v)
        if mapped:
            vibes.append(mapped)
    size_vibe = SIZE_TO_VIBE.get(survey["campus_size"])
    if size_vibe:
        vibes.append(size_vibe)

    profile = StudentProfile(
        gpa=survey["gpa"] or None,
        sat=survey["sat"], act=survey["act"],
        intended_major=(survey["major"] or None),
        budget=int(survey["budget"]) if survey["budget"] else None,
        state=home_code,
        weather_pref=weather_pref,
        vibe_prefs=vibes,
    )
    return profile, _allowed_state_codes(survey), home_code


def _allowed_state_codes(survey: dict[str, Any]) -> list[str] | None:
    regions = [r for r in survey["regions"] if r and r != "No preference"]
    if not regions:
        return None
    allowed: set[str] = set()
    for r in regions:
        allowed |= REGION_TO_STATES.get(r, set())
    return sorted(allowed) if allowed else None


# -----------------------------------------------------------------------------
# Progress indicator (survey)
# -----------------------------------------------------------------------------
def render_progress(current: int, total: int = 4) -> None:
    parts: list[str] = ['<div class="cff-progress">']
    for i in range(1, total + 1):
        cls = "step completed" if i < current else "step current" if i == current else "step future"
        parts.append(f'<div class="{cls}">{i}</div>')
        if i < total:
            parts.append(f'<div class="{"line completed" if i < current else "line"}"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Survey steps
# -----------------------------------------------------------------------------
def render_step_1() -> None:
    s = st.session_state.survey
    st.markdown("<div class='cff-step-title'>Step 1 · Academic profile</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-step-hint'>We'll use these to gauge academic fit. Test scores are optional.</div>",
                unsafe_allow_html=True)

    s["gpa"] = st.number_input(
        "Unweighted GPA *", min_value=0.0, max_value=4.0, step=0.01,
        value=float(s["gpa"]) if s["gpa"] is not None else 3.5,
        help="Required. Enter on a 0.0–4.0 scale.",
    )

    c1, c2 = st.columns(2)
    with c1:
        sat_in = st.number_input("SAT score (optional)", min_value=0, max_value=1600, step=10,
                                 value=int(s["sat"]) if s["sat"] else 0)
        s["sat"] = int(sat_in) if sat_in >= 400 else None
    with c2:
        act_in = st.number_input("ACT score (optional)", min_value=0, max_value=36, step=1,
                                 value=int(s["act"]) if s["act"] else 0)
        s["act"] = int(act_in) if act_in >= 1 else None

    s["major"] = st.text_input("Intended major", value=s["major"], placeholder="e.g. Computer Science")

    st.write("")
    _, right = st.columns([3, 1])
    with right:
        disabled = s["gpa"] is None or s["gpa"] <= 0.0
        if st.button("Next →", type="primary", use_container_width=True, disabled=disabled):
            st.session_state.step = 2
            st.rerun()


def render_step_2() -> None:
    s = st.session_state.survey
    st.markdown("<div class='cff-step-title'>Step 2 · Location & weather</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-step-hint'>Where do you want to be? Pick as many climates or regions as feel right.</div>",
                unsafe_allow_html=True)

    names = [n for n, _ in US_STATES_FULL]
    s["home_state_name"] = st.selectbox(
        "Home state", names,
        index=names.index(s["home_state_name"]) if s["home_state_name"] in names else 0,
    )
    s["max_distance"] = st.selectbox(
        "Max distance from home", DISTANCE_OPTIONS,
        index=DISTANCE_OPTIONS.index(s["max_distance"]) if s["max_distance"] in DISTANCE_OPTIONS else 0,
    )

    st.markdown("**Preferred climate**")
    climates = st.pills("climate", CLIMATE_OPTIONS, selection_mode="multi",
                        default=s["climates"], label_visibility="collapsed", key="pills_climate")
    s["climates"] = list(climates or [])

    st.markdown("**Preferred region**")
    regions = st.pills("region", REGION_OPTIONS, selection_mode="multi",
                       default=s["regions"], label_visibility="collapsed", key="pills_region")
    s["regions"] = list(regions or [])

    st.write("")
    left, _, right = st.columns([1, 2, 1])
    with left:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 1; st.rerun()
    with right:
        if st.button("Next →", type="primary", use_container_width=True):
            st.session_state.step = 3; st.rerun()


def render_step_3() -> None:
    s = st.session_state.survey
    st.markdown("<div class='cff-step-title'>Step 3 · Budget & campus vibe</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-step-hint'>Cost is the annual all-in figure (tuition plus room, board, and fees).</div>",
                unsafe_allow_html=True)

    s["budget"] = st.slider(f"Max annual cost: ${int(s['budget']):,}",
                            min_value=0, max_value=100_000, step=1_000, value=int(s["budget"]))

    st.markdown("**Campus size**")
    size = st.pills("size", CAMPUS_SIZE_OPTIONS, selection_mode="single",
                    default=s["campus_size"] if s["campus_size"] in CAMPUS_SIZE_OPTIONS else "No preference",
                    label_visibility="collapsed", key="pills_size")
    s["campus_size"] = size or "No preference"

    st.markdown("**Campus vibe** *(pick any that fit)*")
    vibes = st.pills("vibes", VIBE_OPTIONS, selection_mode="multi",
                     default=s["vibes"], label_visibility="collapsed", key="pills_vibes")
    s["vibes"] = list(vibes or [])

    st.write("")
    left, _, right = st.columns([1, 2, 1])
    with left:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 2; st.rerun()
    with right:
        if st.button("Next →", type="primary", use_container_width=True):
            st.session_state.step = 4; st.rerun()


def render_step_4() -> None:
    s = st.session_state.survey
    st.markdown("<div class='cff-step-title'>Step 4 · What matters most?</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-step-hint'>These sliders weight how the overall fit score is calculated. "
                "Drag higher for dimensions that matter most to you.</div>", unsafe_allow_html=True)

    for key, label in [
        ("academic_fit",   "Academic quality"),
        ("affordability",  "Affordability"),
        ("location_fit",   "Location"),
        ("weather_fit",    "Weather"),
        ("vibe_fit",       "Campus vibe"),
    ]:
        current = int(s["weights"].get(key, 3))
        s["weights"][key] = st.slider(f"{label} — **{current}**", 1, 5, current, 1, key=f"w_{key}")

    st.write("")
    left, _, right = st.columns([1, 1.5, 1.5])
    with left:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 3; st.rerun()
    with right:
        if st.button("Find my colleges", type="primary", use_container_width=True):
            st.session_state.phase = "running"
            st.session_state.last_error = None
            st.rerun()


def render_survey() -> None:
    # Narrow container during the survey only.
    st.markdown("<script>document.querySelector('body').classList.add('cff-narrow');</script>",
                unsafe_allow_html=True)
    st.markdown("<div class='cff-title'>🎓 College Fit Finder</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-subtitle'>Tell us about you — we'll surface schools that fit.</div>",
                unsafe_allow_html=True)
    render_progress(st.session_state.step)

    step = st.session_state.step
    if step == 1: render_step_1()
    elif step == 2: render_step_2()
    elif step == 3: render_step_3()
    else: render_step_4()

    if st.session_state.last_error:
        st.error(st.session_state.last_error)


# -----------------------------------------------------------------------------
# Loading screen + pipeline
# -----------------------------------------------------------------------------
def render_running() -> None:
    st.markdown("<div class='cff-title'>🎓 College Fit Finder</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-loading'>", unsafe_allow_html=True)
    st.markdown("<div class='cff-spinner'></div>", unsafe_allow_html=True)
    msg_slot = st.empty()
    msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[0]}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    survey = st.session_state.survey
    profile, allowed_states, home_code = _survey_to_profile_and_backend(survey)

    matcher_profile = profile
    if survey["max_distance"] != "Within 500 miles":
        matcher_profile = StudentProfile(
            gpa=profile.gpa, sat=profile.sat, act=profile.act,
            intended_major=profile.intended_major, budget=profile.budget,
            state=None, weather_pref=profile.weather_pref, vibe_prefs=profile.vibe_prefs,
        )

    try:
        schools = find_matching_schools(matcher_profile)
    except ScorecardError as e:
        st.session_state.last_error = f"Scorecard API error: {e}"
        st.session_state.phase = "survey"; st.rerun(); return

    if allowed_states:
        schools = [s for s in schools if (s.get("state") or "").upper() in allowed_states]
    if not schools:
        st.session_state.last_error = (
            "No schools matched those filters. Try widening your budget, "
            "loosening your regions, or clearing your major."
        )
        st.session_state.phase = "survey"; st.rerun(); return

    msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[1]}</div>", unsafe_allow_html=True)
    schools = enrich_schools_with_vibes(schools)

    msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[2]}</div>", unsafe_allow_html=True)
    schools = enrich_schools_with_climate(schools)

    msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[3]}</div>", unsafe_allow_html=True)
    scored = score_schools(profile, schools, weights=survey["weights"])

    msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[4]}</div>", unsafe_allow_html=True)
    cards = build_profile_cards(scored, profile, survey["weights"], top_n=100)

    time.sleep(0.25)
    st.session_state.results = cards
    st.session_state.schools_by_id = {s["id"]: s for s in schools if s.get("id") is not None}
    st.session_state.phase = "results"
    st.session_state.main_tab = "results"
    st.session_state.display_limit = 50  # reset on every new search
    st.rerun()


# -----------------------------------------------------------------------------
# Filtering + lookups
# -----------------------------------------------------------------------------
def _school_size(card: ProfileCard) -> int | None:
    info = st.session_state.schools_by_id.get(card.school_id) or {}
    return info.get("size")


def _apply_filters(cards: Iterable[ProfileCard]) -> list[ProfileCard]:
    cls = st.session_state.filter_class
    flag_keys = {STACK_FILTER_LABEL_TO_KEY[f] for f in st.session_state.filter_flags
                 if f in STACK_FILTER_LABEL_TO_KEY}

    out: list[ProfileCard] = []
    for c in cards:
        if cls != "All" and c.classification != cls:
            continue
        if "under_30k" in flag_keys:
            coa = c.cost_of_attendance
            if not (coa is not None and coa < 30_000):
                continue
        if "warm" in flag_keys and c.climate != "warm":
            continue
        if "cold" in flag_keys and c.climate != "cold":
            continue
        if "small" in flag_keys:
            size = _school_size(c)
            if not (size is not None and size < 5_000):
                continue
        if "large" in flag_keys:
            size = _school_size(c)
            if not (size is not None and size > 15_000):
                continue
        out.append(c)
    return out


# -----------------------------------------------------------------------------
# Results phase — main nav, toolbar, list view, map view, profile page
# -----------------------------------------------------------------------------
def _render_main_nav() -> None:
    tabs = [("profile", "👤 My Profile"), ("results", "🎯 Results"), ("list", "💾 My List")]
    cols = st.columns(len(tabs))
    for i, (key, label) in enumerate(tabs):
        with cols[i]:
            is_active = st.session_state.main_tab == key
            if st.button(
                label,
                key=f"nav_{key}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state.main_tab = key
                st.rerun()


def _render_toolbar(all_cards: list[ProfileCard], filtered: list[ProfileCard]) -> None:
    # Row 1: searchable selectbox + count
    left, right = st.columns([4, 1])
    with left:
        chosen = st.selectbox(
            "school_search",
            options=[c.name for c in all_cards],
            index=None,
            placeholder="Search for a school...",
            label_visibility="collapsed",
            key="school_search_select",
        )
        if chosen:
            # Find the matching card and navigate to its profile.
            for c in all_cards:
                if c.name == chosen:
                    st.session_state.selected_school_id = c.school_id
                    st.session_state.phase = "school_profile"
                    # Clear the selectbox state so a "back" return to the
                    # results page doesn't re-trigger navigation.
                    if "school_search_select" in st.session_state:
                        del st.session_state["school_search_select"]
                    st.rerun()
                    break
    with right:
        st.markdown(
            f"<div style='text-align:right; padding-top: 0.5rem;' class='cff-count'>"
            f"<strong>{len(filtered)}</strong> of {len(all_cards)} schools</div>",
            unsafe_allow_html=True,
        )

    # Row 2: classification pills + stackable filter pills
    c1, c2 = st.columns([1, 2])
    with c1:
        cls = st.pills(
            "class_filter", CLASSIFICATION_FILTERS, selection_mode="single",
            default=st.session_state.filter_class,
            label_visibility="collapsed", key="filter_class_pills",
        )
        st.session_state.filter_class = cls or "All"
    with c2:
        flags = st.pills(
            "stack_filters", STACK_FILTER_LABELS, selection_mode="multi",
            default=st.session_state.filter_flags,
            label_visibility="collapsed", key="filter_flags_pills",
        )
        st.session_state.filter_flags = list(flags or [])


def _initial_color(letter: str) -> str:
    letter = (letter or "?").upper()[0]
    return INITIAL_PALETTE[ord(letter) % len(INITIAL_PALETTE)]


def _class_css(classification: str) -> str:
    return {"Reach": "reach", "Match": "match", "Safety": "safety"}.get(classification, "")


def _fmt_currency(v: int | None) -> str:
    return f"${v:,}" if v is not None else "—"


def _fmt_pct(v: float | None) -> str:
    return f"{v*100:.0f}%" if v is not None else "—"


def _fmt_size(v: int | None) -> str:
    if v is None: return "—"
    if v >= 1000: return f"{v/1000:.1f}k" if v < 10000 else f"{v:,}"
    return f"{v}"


def _card_tuition(card: ProfileCard) -> int | None:
    # Prefer out-of-state tuition for "tuition" summary; fall back to in-state or COA.
    return card.tuition_out_of_state or card.tuition_in_state or card.cost_of_attendance


def _render_card(card: ProfileCard) -> None:
    initial = (card.name or "?")[0]
    color = _initial_color(initial)
    badge_cls = _class_css(card.classification)
    fit_pct = max(0, min(100, int(card.overall_fit)))
    size = _school_size(card)
    tuition = _card_tuition(card)

    # Top HTML block — card header through vibe chips.
    tags_html = ""
    if card.vibe_tags:
        chips = "".join(f"<span class='cff-vibe-chip'>{t}</span>" for t in card.vibe_tags[:4])
        tags_html = f"<div class='cff-vibe-chips'>{chips}</div>"

    location_line = f"{card.city}, {card.state}  ·  {card.climate.title()}"

    body_html = f"""
<div class='cff-card-body'>
  <div class='cff-card-header'>
    <div class='cff-initial' style='background:{color};'>{initial.upper()}</div>
    <span class='cff-class-badge {badge_cls}'>{card.classification}</span>
  </div>
  <div class='cff-card-name'>{card.name}</div>
  <div class='cff-card-sub'>{location_line}</div>

  <div class='cff-fit-label'>OVERALL FIT</div>
  <div class='cff-fit'>{fit_pct}</div>
  <div class='cff-thin-bar'><div style='width:{fit_pct}%;'></div></div>

  <div class='cff-mini-grid'>
    <div class='cff-mini-cell'>
      <div class='label'>TUITION</div>
      <div class='value'>{_fmt_currency(tuition)}</div>
    </div>
    <div class='cff-mini-cell'>
      <div class='label'>SIZE</div>
      <div class='value'>{_fmt_size(size)}</div>
    </div>
    <div class='cff-mini-cell'>
      <div class='label'>ACCEPTANCE</div>
      <div class='value'>{_fmt_pct(card.acceptance_rate)}</div>
    </div>
    <div class='cff-mini-cell'>
      <div class='label'>MEDIAN DEBT</div>
      <div class='value'>{_fmt_currency(card.median_debt)}</div>
    </div>
  </div>

  {tags_html}
</div>
"""
    st.markdown(body_html, unsafe_allow_html=True)

    # Action buttons (native so they're clickable).
    saved = card.school_id in st.session_state.saved_schools
    left, right = st.columns(2)
    with left:
        if saved:
            if st.button("✓ Saved", key=f"save_{card.school_id}", use_container_width=True):
                st.session_state.saved_schools.remove(card.school_id)
                st.rerun()
        else:
            if st.button("Save", key=f"save_{card.school_id}", use_container_width=True):
                st.session_state.saved_schools.append(card.school_id)
                st.rerun()
    with right:
        if st.button("View profile", key=f"view_{card.school_id}",
                     type="primary", use_container_width=True):
            st.session_state.selected_school_id = card.school_id
            st.session_state.phase = "school_profile"
            st.rerun()


def _render_card_grid(cards: list[ProfileCard]) -> None:
    if not cards:
        st.info("No schools match those filters. Try clearing some.")
        return

    limit = int(st.session_state.display_limit)
    visible = cards[:limit]

    for row_start in range(0, len(visible), 3):
        row = visible[row_start:row_start + 3]
        cols = st.columns(3, gap="medium")
        for i, card in enumerate(row):
            with cols[i]:
                with st.container(border=True):
                    _render_card(card)
        # If fewer than 3 cards in this row, leave the rest empty for consistent grid.

    # Show-more footer: only if there are hidden matches.
    hidden = len(cards) - len(visible)
    if hidden > 0:
        st.write("")
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            if st.button(
                f"Show {min(25, hidden)} more  ·  {hidden} remaining",
                type="secondary",
                use_container_width=True,
                key="show_more",
            ):
                st.session_state.display_limit = limit + 25
                st.rerun()


def _render_map_view_placeholder(cards: list[ProfileCard]) -> None:
    st.markdown(
        f"""<div class='cff-map-placeholder'>
  <h3>🗺️  Interactive map coming soon</h3>
  <p>We'll show all {len(cards)} schools here as color-coded pins —
     blue for Match, green for Safety, red for Reach — with a hover card
     showing fit score and quick stats.</p>
</div>""",
        unsafe_allow_html=True,
    )


def _render_results_content() -> None:
    all_cards = st.session_state.results or []
    if not all_cards:
        st.info("No results yet. Go back and run the survey.")
        if st.button("← Back to survey"):
            st.session_state.phase = "survey"; st.session_state.step = 1; st.rerun()
        return

    # Compute filtered list once for the toolbar count and the render path.
    # (toolbar sets session state synchronously, then we refilter.)
    filtered_preview = _apply_filters(all_cards)
    _render_toolbar(all_cards, filtered_preview)

    # Re-apply after the toolbar potentially updated session_state.
    filtered = _apply_filters(all_cards)

    # Sub-view toggle (list / map)
    st.write("")
    st.session_state.sub_view = st.segmented_control(
        "view", ["List view", "Map view"],
        default=st.session_state.sub_view,
        label_visibility="collapsed", key="sub_view_toggle",
    ) or "List view"

    if st.session_state.sub_view == "Map view":
        _render_map_view_placeholder(filtered)
    else:
        _render_card_grid(filtered)


def _render_my_list_placeholder() -> None:
    saved_count = len(st.session_state.saved_schools)
    st.markdown(
        f"""<div class='cff-map-placeholder'>
  <h3>💾  My List coming soon</h3>
  <p>You've saved <strong>{saved_count}</strong> school{'s' if saved_count != 1 else ''} so far.
     A full comparison view with side-by-side stats is next.</p>
</div>""",
        unsafe_allow_html=True,
    )


def _render_profile_tab() -> None:
    s = st.session_state.survey
    st.markdown("Edit any field, then click **Re-run search** to refresh your list.")

    s["gpa"] = st.number_input("GPA", min_value=0.0, max_value=4.0, step=0.01,
                                value=float(s["gpa"]) if s["gpa"] is not None else 3.5, key="prof_gpa")

    c1, c2 = st.columns(2)
    with c1:
        sat_in = st.number_input("SAT", min_value=0, max_value=1600, step=10,
                                  value=int(s["sat"]) if s["sat"] else 0, key="prof_sat")
        s["sat"] = int(sat_in) if sat_in >= 400 else None
    with c2:
        act_in = st.number_input("ACT", min_value=0, max_value=36, step=1,
                                  value=int(s["act"]) if s["act"] else 0, key="prof_act")
        s["act"] = int(act_in) if act_in >= 1 else None

    s["major"] = st.text_input("Intended major", value=s["major"], key="prof_major")
    s["budget"] = st.slider(f"Budget: ${int(s['budget']):,}", 0, 100_000, int(s["budget"]),
                             step=1_000, key="prof_budget")

    names = [n for n, _ in US_STATES_FULL]
    s["home_state_name"] = st.selectbox(
        "Home state", names,
        index=names.index(s["home_state_name"]) if s["home_state_name"] in names else 0,
        key="prof_state",
    )

    st.markdown("**Climate**")
    climates = st.pills("climate2", CLIMATE_OPTIONS, selection_mode="multi",
                         default=s["climates"], label_visibility="collapsed", key="prof_climates")
    s["climates"] = list(climates or [])

    st.markdown("**Regions**")
    regions = st.pills("regions2", REGION_OPTIONS, selection_mode="multi",
                        default=s["regions"], label_visibility="collapsed", key="prof_regions")
    s["regions"] = list(regions or [])

    st.markdown("**Campus vibe**")
    vibes = st.pills("vibes2", VIBE_OPTIONS, selection_mode="multi",
                      default=s["vibes"], label_visibility="collapsed", key="prof_vibes")
    s["vibes"] = list(vibes or [])

    st.markdown("**Weights**")
    for key, label in [("academic_fit", "Academic"), ("affordability", "Affordability"),
                        ("location_fit", "Location"), ("weather_fit", "Weather"),
                        ("vibe_fit", "Vibe")]:
        s["weights"][key] = st.slider(f"{label}", 1, 5,
                                       int(s["weights"].get(key, 3)), key=f"prof_w_{key}")

    if st.button("Re-run search", type="primary", use_container_width=True):
        st.session_state.phase = "running"; st.rerun()


def render_results_phase() -> None:
    st.markdown("<div class='cff-title'>College Fit Finder</div>", unsafe_allow_html=True)
    _render_main_nav()
    st.write("")

    if st.session_state.main_tab == "profile":
        _render_profile_tab()
    elif st.session_state.main_tab == "list":
        _render_my_list_placeholder()
    else:
        _render_results_content()


# -----------------------------------------------------------------------------
# School profile page
# -----------------------------------------------------------------------------
def _bar_row(label: str, value: float, fmt: str = "{:.0f}") -> None:
    pct = max(0, min(100, int(value)))
    st.markdown(
        f"""<div class='cff-bar-row'>
  <div class='cff-bar-label'><span>{label}</span><span>{fmt.format(value)}</span></div>
  <div class='cff-thin-bar'><div style='width:{pct}%;'></div></div>
</div>""",
        unsafe_allow_html=True,
    )


def _stat_cell(label: str, value: str) -> str:
    return (
        f"<div class='cff-stat-cell'>"
        f"<div class='label'>{label}</div>"
        f"<div class='value'>{value}</div>"
        f"</div>"
    )


def render_school_profile() -> None:
    card: ProfileCard | None = None
    for c in (st.session_state.results or []):
        if c.school_id == st.session_state.selected_school_id:
            card = c
            break
    if not card:
        st.error("School not found. It may have been filtered out or a new search was run.")
        if st.button("← Back to results"):
            st.session_state.phase = "results"; st.rerun()
        return

    if st.button("← Back to results", key="school_back"):
        st.session_state.phase = "results"
        st.session_state.selected_school_id = None
        st.rerun()

    badge_cls = _class_css(card.classification)
    header_html = f"""
<div class='cff-profile-header'>
  <div>
    <div class='cff-profile-name'>{card.name}</div>
    <div class='cff-profile-sub'>{card.location_summary}  ·
      <span class='cff-class-badge {badge_cls}'>{card.classification}</span>
    </div>
  </div>
  <div>
    <div class='cff-profile-fit'>{int(card.overall_fit)}</div>
    <div class='cff-profile-fit-lbl'>OVERALL FIT</div>
  </div>
</div>
"""
    st.markdown(header_html, unsafe_allow_html=True)

    st.write(card.description)

    # Fit breakdown
    st.markdown("<div class='cff-section-title'>Fit breakdown</div>", unsafe_allow_html=True)
    for cat, score in card.category_scores.items():
        _bar_row(card.category_labels[cat], score)

    # Key stats grid
    size = _school_size(card)
    tuition = _card_tuition(card)
    sat = f"{card.sat_range[0]}–{card.sat_range[1]}" if card.sat_range else "—"
    winter = f"{card.winter_temp_f:.0f}°F" if card.winter_temp_f is not None else "—"
    summer = f"{card.summer_temp_f:.0f}°F" if card.summer_temp_f is not None else "—"

    st.markdown("<div class='cff-section-title'>Key stats</div>", unsafe_allow_html=True)
    stat_html = "<div class='cff-stat-grid'>" + "".join([
        _stat_cell("TUITION", _fmt_currency(tuition)),
        _stat_cell("ACCEPTANCE RATE", _fmt_pct(card.acceptance_rate)),
        _stat_cell("SAT RANGE (25–75%)", sat),
        _stat_cell("MEDIAN DEBT", _fmt_currency(card.median_debt)),
        _stat_cell("ENROLLMENT", _fmt_size(size)),
        _stat_cell("GRADUATION RATE", _fmt_pct(card.graduation_rate)),
        _stat_cell("WINTER TEMP", winter),
        _stat_cell("SUMMER TEMP", summer),
    ]) + "</div>"
    st.markdown(stat_html, unsafe_allow_html=True)

    # Strengths + weaknesses
    sw = st.columns(2)
    with sw[0]:
        st.markdown("<div class='cff-section-title'>✅ Strengths for you</div>", unsafe_allow_html=True)
        for x in card.strengths:
            st.markdown(f"- {x}")
    with sw[1]:
        st.markdown("<div class='cff-section-title'>⚠️ Watch-outs</div>", unsafe_allow_html=True)
        if card.weaknesses:
            for x in card.weaknesses:
                st.markdown(f"- {x}")
        else:
            st.markdown("- _No major concerns given your priorities._")

    # Campus vibe
    st.markdown("<div class='cff-section-title'>Campus vibe</div>", unsafe_allow_html=True)
    ath_score_map = {"dominant": 100, "high": 80, "medium": 55, "low": 25}
    _bar_row("Academic intensity", float(card.vibe_academic_intensity or 0))
    _bar_row("Party scene",        float(card.vibe_party_scene or 0))
    _bar_row("Diversity",          float(card.vibe_diversity_score or 0))
    _bar_row("Athletics",          float(ath_score_map.get(card.vibe_athletics_culture or "", 0)))

    if card.vibe_tags:
        chips = "".join(f"<span class='cff-vibe-chip'>{t}</span>" for t in card.vibe_tags)
        st.markdown(f"<div class='cff-vibe-chips'>{chips}</div>", unsafe_allow_html=True)

    if card.url:
        st.write("")
        st.markdown(f"[{card.url}]({card.url})")

    st.write("")

    # Action buttons
    saved = card.school_id in st.session_state.saved_schools
    c1, c2 = st.columns(2)
    with c1:
        if saved:
            if st.button("✓ Saved", key="profile_save", use_container_width=True):
                st.session_state.saved_schools.remove(card.school_id); st.rerun()
        else:
            if st.button("Save school", key="profile_save",
                         type="primary", use_container_width=True):
                st.session_state.saved_schools.append(card.school_id); st.rerun()
    with c2:
        st.button("Add to compare", key="profile_compare",
                  use_container_width=True, disabled=True,
                  help="Compare view is coming soon.")


# -----------------------------------------------------------------------------
# Phase routing
# -----------------------------------------------------------------------------
phase = st.session_state.phase
if phase == "survey":
    render_survey()
elif phase == "running":
    render_running()
elif phase == "school_profile":
    render_school_profile()
else:
    render_results_phase()
