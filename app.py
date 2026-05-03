"""College Fit Finder — onboarding survey + tabbed results dashboard."""

from __future__ import annotations

import copy
import time
from typing import Any, Iterable

import folium
import streamlit as st
from streamlit_folium import st_folium

from agents.agent1_matcher import (
    ScorecardError,
    StudentProfile,
    find_matching_schools,
    find_matching_schools_national,
)
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import ProfileCard, build_profile_cards
from agents.ipeds import enrich_schools_with_ipeds
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
    "Northeast":     {"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"},
    "Mid-Atlantic":  {"NY", "NJ", "PA", "MD", "DE"},
    "Southeast":     {"VA", "WV", "NC", "SC", "GA", "FL", "AL", "MS", "TN",
                      "KY", "AR", "LA"},
    "Midwest":       {"OH", "IN", "IL", "MI", "WI", "MN", "IA", "MO",
                      "ND", "SD", "NE", "KS"},
    "Southwest":     {"TX", "OK", "NM", "AZ"},
    "West Coast":    {"CA", "OR", "WA"},
    "Mountain West": {"CO", "UT", "NV", "ID", "MT", "WY"},
}

CLIMATE_OPTIONS = ["Hot", "Warm", "Mild", "Seasonal", "Chilly", "Cold"]
CLIMATE_TO_BACKEND = {
    "Hot":      "Warm",
    "Warm":     "Warm",
    "Mild":     "Mild",
    "Seasonal": "Seasonal",
    "Chilly":   "Cold",
    "Cold":     "Cold",
}

REGION_OPTIONS = [
    "Northeast", "Mid-Atlantic", "Southeast", "Midwest",
    "Southwest", "West Coast", "Mountain West", "No preference",
]
DISTANCE_OPTIONS = ["No preference", "Within 500 miles", "Within 1000 miles", "Anywhere"]

TUITION_OPTIONS = ["In-state only", "Out-of-state only", "No preference"]
TUITION_LABEL_TO_KEY = {
    "In-state only": "in_state",
    "Out-of-state only": "out_of_state",
    "No preference": "no_preference",
}
TUITION_KEY_TO_LABEL = {v: k for k, v in TUITION_LABEL_TO_KEY.items()}

STATUS_OPTIONS = ["Domestic", "International", "Permanent Resident"]
STATUS_LABEL_TO_KEY = {
    "Domestic": "domestic",
    "International": "international",
    "Permanent Resident": "permanent_resident",
}
STATUS_KEY_TO_LABEL = {v: k for k, v in STATUS_LABEL_TO_KEY.items()}
INTERNATIONAL_LIKE = ("international", "permanent_resident")

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
    "Greek life",
    "Artsy & creative",
    "Pre-professional",
]
VIBE_TO_BACKEND = {
    "Academic & research focused": "academic",
    "Strong athletics": "sporty",
    "Greek life": "greek",
    "Artsy & creative": "artsy",
    "Social & party": "greek",
}

MAJOR_OPTIONS = [
    "Undecided",
    "Business",
    "Computer Science",
    "Engineering",
    "Biology and Life Sciences",
    "Psychology",
    "Communications",
    "Nursing and Health",
    "Economics",
    "Political Science",
    "Mathematics",
    "Education",
    "Art and Design",
    "History",
    "English and Literature",
    "Sociology",
    "Environmental Science",
    "Criminal Justice",
    "Philosophy",
]

CLASSIFICATION_FILTERS = ["All", "Reach", "Match", "Safety"]

LOADING_MESSAGES = [
    "Searching thousands of colleges...",
    "Analyzing your academic fit...",
    "Checking weather and climate data...",
    "Scoring campus vibes...",
    "Building your personalized list...",
]

# Brand palette (hex values kept in sync with the CSS :root variables).
ACCENT = "#4A8574"   # --sage — used where inline f-strings need a hex literal

# School-initial square — brand spec calls for a single --ink background for
# every school, so the "palette" is just that one color.
INITIAL_PALETTE = ["#0A1F3D"]


# -----------------------------------------------------------------------------
# CSS
# -----------------------------------------------------------------------------
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,800;0,9..144,900;1,9..144,400;1,9..144,600&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
  --ink: #0A1F3D;
  --ink-soft: #142D52;
  --sage: #4A8574;
  --sage-deep: #2F5F4F;
  --sky: #5B8DB8;
  --paper: #F5F1E8;
  --paper-warm: #EDE6D3;
  --cream: #F0EADA;
  --rule: #D8D1BC;
  --mist: #B8C8D0;
  --text: #1A1A1A;
  --text-soft: #5C5C5C;
  --text-mute: #8A8A8A;
  --reach: #C0392B;
  --match: #B7860B;
  --safety: #2F5F4F;
}}

/* ── Base typography: Inter as the default, Fraunces + JetBrains Mono as
   targeted overrides for headings and data labels respectively. ─────── */
html, body, .stApp, .stApp *,
button, input, textarea, select, [class*="st-"], [class*="css-"] {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}}
.stApp {{ background: var(--paper) !important; color: var(--text); }}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}
.cff-narrow .block-container {{ max-width: 760px; }}

/* Fraunces (display serif) for headings, school names, fit scores, section
   titles, and the logo wordmark. */
h1, h2, h3, h4,
.cff-title, .cff-step-title, .cff-section-title,
.cff-card-name, .cff-fit, .cff-saved-row-fit,
.cff-profile-name, .cff-profile-fit,
.cff-profile-header h2,
.cff-logo, .cff-logo *,
.cff-compare-col-name,
.cff-map-placeholder h3 {{
  font-family: 'Fraunces', Georgia, 'Times New Roman', serif !important;
}}

/* JetBrains Mono for data labels, badges, and metadata. */
.cff-class-badge,
.cff-fit-label, .cff-saved-row-fit-lbl, .cff-profile-fit-lbl,
.cff-mini-cell .label, .cff-stat-cell .label,
.cff-compare-label,
.cff-count, .cff-count strong,
.cff-search-suggest-label {{
  font-family: 'JetBrains Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace !important;
}}

/* ── Titles / page chrome ────────────────────────────────────────────── */
.cff-title {{
  font-weight: 800; font-size: 2.1rem; color: var(--ink);
  text-align: center; margin: 0.25rem 0 0.5rem;
  letter-spacing: -0.01em;
}}
.cff-subtitle {{ text-align: center; color: var(--text-soft); margin-bottom: 1rem; }}
.cff-step-title {{
  font-weight: 700; font-size: 1.4rem; color: var(--ink);
  margin: 1.25rem 0 0.25rem; letter-spacing: -0.005em;
}}
.cff-step-hint {{ color: var(--text-soft); font-size: 0.9rem; margin-bottom: 1rem; }}
.cff-section-title {{
  font-weight: 700; font-size: 1.2rem; color: var(--ink);
  margin: 1rem 0 0.5rem; letter-spacing: -0.005em;
}}

/* ── Main navigation bar ─────────────────────────────────────────────── */
.st-key-cff_main_nav {{
  background: var(--ink) !important;
  padding: 0.85rem 1.1rem !important;
  border-radius: 12px !important;
  margin-bottom: 1rem !important;
  border: 0 !important;
}}
.st-key-cff_main_nav div[data-testid="stButton"] button {{
  background: transparent !important;
  border: 0 !important;
  color: rgba(255,255,255,0.6) !important;
  font-weight: 500 !important;
  box-shadow: none !important;
}}
.st-key-cff_main_nav div[data-testid="stButton"] button:hover {{
  background: rgba(255,255,255,0.06) !important;
  color: white !important;
}}
.st-key-cff_main_nav div[data-testid="stButton"] button[kind="primary"] {{
  background: rgba(74,133,116,0.24) !important;
  color: white !important;
  font-weight: 600 !important;
}}
.st-key-cff_main_nav div[data-testid="stButton"] button[kind="primary"]:hover {{
  background: rgba(74,133,116,0.34) !important;
}}

/* ── Logo wordmark ───────────────────────────────────────────────────── */
.cff-logo {{
  display: inline-flex; align-items: center; gap: 0.5rem;
  font-size: 1.35rem; line-height: 1;
}}
.cff-logo-cap {{ color: var(--sage); flex-shrink: 0; }}
.cff-logo .college, .cff-logo .finder {{ font-weight: 900; letter-spacing: -0.005em; }}
.cff-logo .fit {{ font-style: italic; font-weight: 600; color: var(--sage); margin: 0 0.05rem; }}
.cff-logo.dark .college, .cff-logo.dark .finder {{ color: var(--paper); }}
.cff-logo.light .college, .cff-logo.light .finder {{ color: var(--ink); }}

/* ── Progress dots ───────────────────────────────────────────────────── */
.cff-progress {{ display: none; }}  /* legacy — replaced by button-based dots */
.st-key-cff_progress_dots div[data-testid="stButton"] button {{
  border-radius: 50% !important;
  width: 42px; height: 42px;
  padding: 0 !important;
  font-weight: 600 !important;
  min-width: 0;
}}
.st-key-cff_progress_dots div[data-testid="stButton"] button[kind="secondary"] {{
  background: var(--sage) !important;
  border: 2px solid var(--sage) !important;
  color: var(--paper) !important;
}}
.st-key-cff_progress_dots div[data-testid="stButton"] button[kind="secondary"]:hover {{
  background: var(--sage-deep) !important;
  border-color: var(--sage-deep) !important;
}}
.st-key-cff_progress_dots div[data-testid="stButton"] button[disabled] {{
  background: var(--paper-warm) !important;
  color: var(--text-mute) !important;
  border: 2px solid var(--rule) !important;
  opacity: 1 !important;
  cursor: not-allowed !important;
}}
.cff-progress-dot-current {{
  width: 42px; height: 42px; border-radius: 50%;
  background: var(--ink); color: var(--paper); border: 2px solid var(--ink);
  display: flex; align-items: center; justify-content: center;
  font-weight: 600; font-size: 0.95rem;
  margin: 0 auto;
  box-shadow: 0 0 0 4px rgba(10,31,61,0.15);
}}
.cff-step-line {{ height: 2px; width: 100%; border-radius: 1px; }}

/* ── Buttons ─────────────────────────────────────────────────────────── */
.stButton > button {{
  border-radius: 8px; font-weight: 500;
  box-shadow: none !important; transition: all 0.15s ease;
}}
.stButton > button[kind="primary"] {{
  background: var(--sage); border: 1px solid var(--sage); color: var(--paper);
}}
.stButton > button[kind="primary"]:hover {{
  background: var(--sage-deep); border-color: var(--sage-deep); color: var(--paper);
}}
.stButton > button[kind="secondary"] {{
  background: transparent; border: 1px solid var(--rule); color: var(--text-soft);
}}
.stButton > button[kind="secondary"]:hover {{
  border-color: var(--ink); color: var(--ink); background: rgba(10,31,61,0.03);
}}

/* ── Inputs ──────────────────────────────────────────────────────────── */
input[type="number"], input[type="text"], textarea,
.stTextInput input, .stNumberInput input {{
  border-radius: 8px !important;
  border: 1px solid var(--rule) !important;
  background: var(--cream) !important;
  color: var(--text) !important;
  box-shadow: none !important;
}}
.stSelectbox > div > div {{
  border-radius: 8px !important;
  border: 1px solid var(--rule) !important;
  background: var(--cream) !important;
  box-shadow: none !important;
}}
input:focus, textarea:focus,
.stTextInput input:focus, .stNumberInput input:focus {{
  border-color: var(--sage) !important;
}}
.stSlider [data-baseweb="slider"] [role="slider"] {{
  background: var(--sage) !important; box-shadow: none !important;
}}
.stSlider [data-baseweb="slider"] > div > div {{
  background: var(--sage) !important;
}}

/* ── Pills ───────────────────────────────────────────────────────────── */
[data-testid="stPills"] button {{
  border-radius: 999px !important;
  border: 1px solid var(--rule) !important;
  background: var(--paper) !important;
  color: var(--text) !important;
  box-shadow: none !important;
  font-weight: 500 !important;
}}
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stPills"] button[data-selected="true"] {{
  background: var(--ink) !important; color: var(--paper) !important;
  border-color: var(--ink) !important;
}}

/* ── Sub-tabs (segmented control) ────────────────────────────────────── */
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {{
  color: var(--sage-deep) !important;
  border-bottom-color: var(--sage) !important;
  border-bottom-width: 2px !important;
}}

/* Native progress bar fill */
.stProgress > div > div > div > div {{ background: var(--sage) !important; }}

/* ── Loading screen ──────────────────────────────────────────────────── */
.st-key-cff_loading_screen {{
  background: var(--ink) !important;
  color: var(--paper) !important;
  padding: 4rem 2rem !important;
  border-radius: 16px !important;
  text-align: center;
  border: 0 !important;
  min-height: 420px;
}}
.st-key-cff_loading_screen * {{ color: var(--paper); }}
.st-key-cff_loading_screen .cff-logo-cap {{ color: var(--sage); }}
.st-key-cff_loading_screen .cff-logo .fit {{ color: var(--sage); }}
.cff-spinner {{
  width: 56px; height: 56px;
  border: 4px solid rgba(255,255,255,0.15); border-top-color: var(--sage);
  border-radius: 50%; animation: cff-spin 1s linear infinite;
  margin: 1.5rem auto;
}}
@keyframes cff-spin {{ to {{ transform: rotate(360deg); }} }}
.cff-loading-msg {{
  font-size: 1.05rem; color: var(--paper); margin-top: 0.5rem; font-weight: 500;
}}

/* Hide default Streamlit chrome */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

/* ── Toolbar ─────────────────────────────────────────────────────────── */
.cff-toolbar {{
  display: flex; align-items: center; justify-content: space-between;
  background: var(--cream); border: 1px solid var(--rule); border-radius: 12px;
  padding: 0.75rem 1rem; margin-bottom: 0.75rem;
}}
.cff-count {{
  color: var(--text-soft); font-weight: 500; font-size: 0.78rem;
  text-transform: uppercase; letter-spacing: 0.12em;
}}
.cff-count strong {{ color: var(--ink); }}

/* ── Bordered containers (cards) ─────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--cream) !important;
  border: 1px solid var(--rule) !important;
  border-radius: 12px !important;
}}

/* ── Grid-view cards ─────────────────────────────────────────────────── */
.cff-card-body {{
  min-height: 400px;
  display: flex; flex-direction: column;
}}
.cff-card-header {{
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 0.5rem; margin-bottom: 0.6rem;
}}
.cff-initial {{
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: var(--paper) !important;
  background: var(--ink) !important;
  font-weight: 900 !important; font-size: 1.25rem;
  flex-shrink: 0;
}}

/* Classification badges (light-bg variant) */
.cff-class-badge {{
  font-size: 0.68rem; font-weight: 600;
  padding: 4px 10px; border-radius: 999px; white-space: nowrap;
  letter-spacing: 0.12em; text-transform: uppercase;
  border: 1px solid transparent;
}}
.cff-class-badge.reach  {{ background: #fde8e6; color: var(--reach);  border-color: rgba(192,57,43,0.25); }}
.cff-class-badge.match  {{ background: #f5eddb; color: var(--match);  border-color: rgba(183,134,11,0.3); }}
.cff-class-badge.safety {{ background: #e0ede8; color: var(--safety); border-color: rgba(74,133,116,0.3); }}

.cff-card-name {{
  font-weight: 700; font-size: 1.15rem; color: var(--ink);
  line-height: 1.2; margin: 0;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; min-height: 2.5em; letter-spacing: -0.005em;
}}
.cff-card-sub {{ font-size: 0.85rem; color: var(--text-soft); margin: 0.15rem 0 0.5rem; }}
.cff-fit {{
  font-weight: 900; font-size: 2.6rem; color: var(--sage-deep);
  line-height: 1.05; margin: 0.3rem 0 0.1rem; letter-spacing: -0.02em;
}}
.cff-fit-label {{
  font-size: 0.62rem; color: var(--text-mute);
  margin-bottom: 0.4rem; letter-spacing: 0.15em; text-transform: uppercase;
}}

.cff-thin-bar {{
  width: 100%; height: 4px; background: var(--rule); border-radius: 2px;
  overflow: hidden; margin-bottom: 0.75rem;
}}
.cff-thin-bar > div {{ height: 100%; background: var(--sage); border-radius: 2px; }}

/* Mini-grid stat cells on cards */
.cff-mini-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.45rem; margin-bottom: 0.6rem;
}}
.cff-mini-cell {{
  border: 1px solid var(--rule); border-radius: 8px; padding: 0.5rem 0.65rem;
  background: var(--paper);
}}
.cff-mini-cell .label {{
  font-size: 0.6rem; color: var(--text-mute);
  letter-spacing: 0.15em; text-transform: uppercase; font-weight: 500;
}}
.cff-mini-cell .value {{
  font-size: 0.95rem; font-weight: 600; color: var(--ink); margin-top: 3px;
}}
.cff-mini-cell .qual {{ font-size: 0.7rem; color: var(--text-mute); font-weight: 400; margin-left: 4px; }}
.cff-mini-cell.full {{ grid-column: 1 / -1; }}

.cff-vibe-chips {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: auto; padding-top: 0.4rem; }}
.cff-vibe-chip {{
  font-size: 0.72rem; padding: 2px 8px; border-radius: 999px;
  background: var(--paper-warm); color: var(--text); border: 1px solid var(--rule);
}}

/* Search suggestion buttons */
.st-key-cff_search_suggestions div[data-testid="stButton"] button {{
  text-align: left !important;
  justify-content: flex-start !important;
}}
.cff-search-suggest-label {{
  font-size: 0.7rem; color: var(--text-mute); margin: 0.4rem 0 0.25rem;
  letter-spacing: 0.12em; text-transform: uppercase;
}}

/* ── School profile page ─────────────────────────────────────────────── */
/* Distinguish school-profile header (dark card) from My Profile header
   (plain light section) via :has() on the children that are unique to each. */
.cff-profile-header {{
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  margin-bottom: 0.75rem;
}}
.cff-profile-header:has(.cff-profile-name) {{
  background: var(--ink); color: var(--paper);
  padding: 1.5rem 1.75rem; border-radius: 14px;
  align-items: flex-start;
}}
.cff-profile-name {{
  font-size: 2rem; font-weight: 800; color: var(--paper); margin: 0;
  letter-spacing: -0.01em;
}}
.cff-profile-sub {{ color: rgba(245,241,232,0.78); margin: 0.3rem 0 0.25rem; }}
.cff-profile-fit {{
  text-align: right; font-size: 3.25rem; font-weight: 900;
  color: var(--sage); line-height: 1; letter-spacing: -0.02em;
}}
.cff-profile-fit-lbl {{
  color: rgba(245,241,232,0.65); font-size: 0.7rem; text-align: right;
  letter-spacing: 0.15em; text-transform: uppercase;
}}
/* Classification badges inside the dark profile card — semi-transparent tints. */
.cff-profile-header .cff-class-badge.reach  {{ background: rgba(192,57,43,0.18);  color: #F5B7AE; border-color: rgba(192,57,43,0.4); }}
.cff-profile-header .cff-class-badge.match  {{ background: rgba(183,134,11,0.18); color: #E8CE85; border-color: rgba(183,134,11,0.4); }}
.cff-profile-header .cff-class-badge.safety {{ background: rgba(74,133,116,0.22); color: #9AC7B6; border-color: rgba(74,133,116,0.45); }}

.cff-stat-grid {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem;
}}
.cff-stat-grid.two {{ grid-template-columns: 1fr 1fr; }}
.cff-stat-grid.three {{ grid-template-columns: repeat(3, 1fr); }}
.cff-stat-cell {{
  background: var(--paper); border: 1px solid var(--rule); border-radius: 8px;
  padding: 0.7rem 0.85rem;
}}
.cff-stat-cell .label {{
  font-size: 0.6rem; color: var(--text-mute);
  letter-spacing: 0.15em; text-transform: uppercase; font-weight: 500;
}}
.cff-stat-cell .value {{
  font-size: 1rem; font-weight: 600; color: var(--ink); margin-top: 4px;
}}

.cff-bar-row {{ margin-bottom: 0.55rem; }}
.cff-bar-label {{
  display: flex; justify-content: space-between;
  font-size: 0.88rem; color: var(--text); margin-bottom: 3px;
}}

/* Map placeholder */
.cff-map-placeholder {{
  background: var(--cream); border: 1px solid var(--rule); border-radius: 12px;
  padding: 4rem 2rem; text-align: center; color: var(--text-soft);
}}
.cff-map-placeholder h3 {{ margin: 0 0 0.5rem; color: var(--ink); font-weight: 700; }}

/* ── My Profile tab header (matches via :has on h2) ──────────────────── */
.cff-profile-header:has(> h2) {{
  background: transparent; color: var(--ink); padding: 0;
  margin-bottom: 0.5rem;
  flex-direction: column; align-items: flex-start;
}}
.cff-profile-header h2 {{
  margin: 0 0 0.25rem; color: var(--ink); font-weight: 700; font-size: 1.7rem;
  letter-spacing: -0.005em;
}}
.cff-profile-header .sub {{ color: var(--text-soft); font-size: 0.95rem; }}

.cff-success-flash {{
  background: #e0ede8; color: var(--safety);
  border: 1px solid rgba(74,133,116,0.35); border-radius: 10px;
  padding: 0.7rem 1rem; margin: 0.25rem 0 1rem;
  font-weight: 500; font-size: 0.95rem;
  animation: cff-flash-fade 0.5s ease-in 3s forwards;
  overflow: hidden;
}}
@keyframes cff-flash-fade {{
  0%   {{ opacity: 1; max-height: 60px; }}
  99%  {{ opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0;
          margin: 0; border-width: 0; }}
  100% {{ display: none; }}
}}

/* ── My List — saved rows ────────────────────────────────────────────── */
.cff-saved-row-body {{
  display: flex; flex-direction: column; justify-content: center; gap: 0.15rem;
  min-height: 110px;
}}
.cff-saved-row-fit {{
  font-size: 2.3rem; font-weight: 900; color: var(--sage-deep);
  line-height: 1; text-align: center; letter-spacing: -0.02em;
}}
.cff-saved-row-fit-lbl {{
  font-size: 0.62rem; color: var(--text-mute); text-align: center;
  letter-spacing: 0.15em; text-transform: uppercase;
}}

/* Add-more-schools card */
.st-key-ml_add_more_card {{ margin-top: 0.75rem; }}
.st-key-ml_add_more_card div[data-testid="stButton"] button {{
  min-height: 150px;
  border: 2px dashed var(--rule) !important;
  background: transparent !important;
  color: var(--text-soft) !important;
  font-size: 1.05rem !important;
  font-weight: 500 !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}}
.st-key-ml_add_more_card div[data-testid="stButton"] button:hover {{
  border-color: var(--sage) !important;
  color: var(--sage-deep) !important;
  background: rgba(74,133,116,0.05) !important;
}}

/* ── Compare table ───────────────────────────────────────────────────── */
.cff-compare-col {{
  background: var(--ink);
  border: 1px solid var(--ink);
  border-radius: 10px;
  padding: 0.7rem 0.8rem; margin-bottom: 0.35rem;
  text-align: center;
}}
.cff-compare-col-initial {{
  width: 32px; height: 32px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  color: var(--paper) !important; font-weight: 900; font-size: 0.95rem;
  margin: 0 auto 0.35rem;
  background: rgba(245,241,232,0.12);
}}
.cff-compare-col-name {{
  font-size: 0.92rem; font-weight: 700; color: var(--paper);
  line-height: 1.2; min-height: 2.2em; letter-spacing: -0.005em;
}}
.cff-compare-cell {{
  padding: 0.45rem 0.5rem; text-align: center;
  font-size: 0.88rem; color: var(--text);
  border-radius: 6px;
  background: var(--paper);
}}
.cff-compare-cell.best {{
  background: #e0ede8; color: var(--sage-deep); font-weight: 600;
}}
.cff-compare-cell.tie {{
  background: #f5eddb; color: var(--match); font-weight: 600;
}}
.cff-compare-label {{
  padding: 0.45rem 0.75rem;
  font-size: 0.68rem; color: var(--text-soft); font-weight: 500;
  letter-spacing: 0.12em; text-transform: uppercase;
  background: var(--cream); border-radius: 6px;
}}

/* ── Welcome / landing page ──────────────────────────────────────────── */
.st-key-cff_welcome_nav {{
  background: var(--ink) !important;
  padding: 0.85rem 1.1rem !important;
  border-radius: 12px !important;
  margin-bottom: 2.5rem !important;
  border: 0 !important;
}}
.cff-welcome-hero {{
  text-align: center;
  max-width: 720px;
  margin: 1.5rem auto 1rem;
  padding: 0 1rem;
}}
.cff-welcome-headline {{
  font-family: 'Fraunces', Georgia, 'Times New Roman', serif !important;
  font-weight: 800;
  font-size: 3rem;
  color: var(--ink);
  letter-spacing: -0.015em;
  line-height: 1.1;
  margin: 0.5rem 0 1.25rem;
}}
.cff-welcome-headline em {{
  font-style: italic; font-weight: 600; color: var(--sage-deep);
}}
.cff-welcome-lede {{
  font-family: 'Inter', sans-serif !important;
  font-size: 1.1rem;
  color: var(--text-soft);
  line-height: 1.6;
  margin: 0 auto 2.5rem;
  max-width: 580px;
}}
.cff-welcome-features-label {{
  font-family: 'JetBrains Mono', ui-monospace, monospace !important;
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-mute);
  text-align: center;
  margin: 0 0 1rem;
}}
.cff-welcome-features {{
  text-align: left;
  display: flex; flex-direction: column;
  gap: 0.85rem;
  max-width: 540px;
  margin: 0 auto 2.5rem;
}}
.cff-welcome-feature {{
  display: flex; align-items: flex-start; gap: 0.85rem;
  font-family: 'Inter', sans-serif !important;
  font-size: 1rem;
  color: var(--text);
  line-height: 1.5;
}}
.cff-welcome-feature::before {{
  content: '';
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--sage);
  margin-top: 0.55rem;
  flex-shrink: 0;
}}
.st-key-cff_welcome_cta div[data-testid="stButton"] button {{
  font-size: 1.05rem !important;
  padding: 0.85rem 1.5rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em !important;
}}
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
        "gpa": 3.00, "gpa_scale": 4.0,
        "sat": None, "act": None, "major": "Undecided",
        "student_status": "domestic",
        "home_state_name": "", "max_distance": 0,           # 0 miles = "No preference"
        "tuition_preference": "no_preference",
        "climates": [], "regions": ["No preference"],
        "budget": 0,                                         # 0 = "No preference"
        "campus_size": "No preference", "vibes": [],
        "weights": {
            "academic_fit": 3, "affordability": 3,
            "location_fit": 3, "weather_fit": 3, "vibe_fit": 3,
        },
    }


def _init_session() -> None:
    ss = st.session_state
    ss.setdefault("phase", "welcome")         # welcome | survey | running | results | school_profile
    ss.setdefault("step", 1)
    ss.setdefault("max_step_reached", 1)      # highest step the user has visited
    ss.setdefault("survey", _default_survey())
    # Step-1 N/A toggles and step-2/3 collapse flags.
    ss.setdefault("sat_not_applicable", False)
    ss.setdefault("act_not_applicable", False)
    ss.setdefault("distance_collapsed", False)
    ss.setdefault("budget_collapsed", False)
    # Remember the last non-zero slider values so Change restores them.
    ss.setdefault("distance_last_value", 0)
    ss.setdefault("budget_last_value", 0)
    ss.setdefault("results", None)            # list[ProfileCard]
    ss.setdefault("schools_by_id", {})        # id -> raw enriched school dict
    ss.setdefault("preserved_cards_by_id", {}) # ProfileCards for saves that
                                                # dropped out of the latest pool
    ss.setdefault("last_error", None)
    # Results-page state
    ss.setdefault("main_tab", "results")      # profile | results | list
    ss.setdefault("sub_view", "List view")    # List view | Map view
    ss.setdefault("filter_class", "All")
    # (filter_flags / my_list_filter_flags state was used by stackable
    #  pill filters; both pill rows have been removed and the keys are gone.)
    ss.setdefault("saved_schools", [])        # list of school ids
    ss.setdefault("compare_schools", [])      # list of school ids in the Compare table
    ss.setdefault("selected_school_id", None) # set when viewing a profile page
    ss.setdefault("display_limit", 50)        # how many filtered cards to show in list view
    ss.setdefault("map_selected_id", None)    # school id currently highlighted on the map
    # Filter state for My List tab (independent from the Results page's filters)
    ss.setdefault("my_list_filter_class", "All")
    ss.setdefault("pending_unsave_id", None)  # inline two-click unsave confirmation
    # Snapshot of the survey that produced the current results — used by
    # My Profile's change-detection to enable/disable Refresh Results.
    ss.setdefault("baseline_survey", None)
    ss.setdefault("profile_refreshed", False)


_init_session()


# -----------------------------------------------------------------------------
# Background IPEDS preload for the curated elite schools — runs once per
# Streamlit session so the most commonly viewed schools are already cached
# by the time the user finishes the survey.
# -----------------------------------------------------------------------------
def _preload_elite_ipeds() -> None:
    try:
        from agents.agent1_matcher import _load_elite_unit_ids
        from agents.ipeds import enrich_schools_with_ipeds
        ids = _load_elite_unit_ids()
        if not ids:
            return
        # Synthetic minimal school dicts — enrich_schools_with_ipeds only
        # needs the "id" key. Cache hits skip the API entirely.
        synthetic = [{"id": uid} for uid in ids]
        enrich_schools_with_ipeds(synthetic)
        print(f"[IPEDS preload] {len(ids)} elite schools warmed", flush=True)
    except Exception as e:
        print(f"[IPEDS preload] failed: {e}", flush=True)


if not st.session_state.get("_elite_ipeds_preload_started"):
    st.session_state["_elite_ipeds_preload_started"] = True
    import threading as _bg_thread
    _bg_thread.Thread(target=_preload_elite_ipeds, daemon=True).start()


def _diversify_by_state(scored: list, top_per_state: int = 3,
                        target_count: int = 100) -> list:
    """
    Build a geographically diverse top-N pool from a fit-sorted list.

    1. Group all scored results by school state.
    2. Tier 1: take the top `top_per_state` highest-fit schools from each
       state (gives at most num_states * top_per_state schools — usually ~150
       for the national pool when most states have ≥3 schools).
    3. If tier 1 already contains `target_count` or more, sort by fit desc
       and cut to `target_count`.
    4. Otherwise top off with the next-highest-fit schools that aren't in
       tier 1, then sort the final list by fit desc.

    Used only on the national-no-filter path so the user sees schools from
    a broad set of states even when raw fit scores cluster a few states at
    the top of the leaderboard. Region-filtered and state-restricted
    searches skip this step (they're already geographically narrow by
    construction).
    """
    if not scored:
        return []

    by_state: dict[str, list] = {}
    for fs in scored:
        state = ((fs.school.get("state") if fs.school else "") or "?").upper()
        by_state.setdefault(state, []).append(fs)

    for state in by_state:
        by_state[state].sort(key=lambda fs: fs.overall, reverse=True)

    tier1: list = []
    tier1_ids: set = set()
    for state, lst in by_state.items():
        for fs in lst[:top_per_state]:
            tier1.append(fs)
            tier1_ids.add(fs.school_id)

    if len(tier1) >= target_count:
        tier1.sort(key=lambda fs: fs.overall, reverse=True)
        return tier1[:target_count]

    remaining = [fs for fs in scored if fs.school_id not in tier1_ids]
    remaining.sort(key=lambda fs: fs.overall, reverse=True)
    needed = target_count - len(tier1)
    final = tier1 + remaining[:needed]
    final.sort(key=lambda fs: fs.overall, reverse=True)
    return final


def _wants_home_state_only(survey: dict[str, Any]) -> bool:
    """
    True if the user wants to narrow the Scorecard query to their home state.
    Handles both the new slider (int miles, > 0 and <= 500) and the legacy
    string form still used by the untouched My Profile tab.
    """
    md = survey.get("max_distance")
    if isinstance(md, int):
        return 0 < md <= 500
    if isinstance(md, str):
        return md == "Within 500 miles"
    return False


def _survey_for_compare(s: dict[str, Any]) -> dict[str, Any]:
    """Stable representation of the survey for change detection.
    Sorts multi-select chip lists so chip re-order isn't a false positive."""
    out = dict(s or {})
    for k in ("climates", "regions", "vibes"):
        v = out.get(k)
        if isinstance(v, list):
            out[k] = sorted(v)
    return out


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

    tuition_pref_raw = survey.get("tuition_preference") or "no_preference"
    tuition_pref = tuition_pref_raw if tuition_pref_raw in ("in_state", "out_of_state") else None
    student_status = survey.get("student_status") or "domestic"

    # Bug 3 — "Undecided" (the survey's default major sentinel) means the
    # student hasn't picked a major; we must NOT send it to Scorecard as a
    # CIP-title substring filter (no school has a program literally titled
    # "Undecided" so the result would be 0 schools).
    major_raw = (survey.get("major") or "").strip()
    intended_major = None if major_raw.lower() in ("", "undecided") else major_raw

    # Bug 5 — budget of 0 (the slider's "No preference" sentinel) means
    # no cap; coerce to None so Agent 1's budget filter is skipped entirely.
    budget_raw = survey.get("budget")
    try:
        budget_int = int(budget_raw) if budget_raw is not None else 0
    except (TypeError, ValueError):
        budget_int = 0
    budget = budget_int if budget_int > 0 else None

    # Bug 6 — GPA is passed through untouched; Agent 1 never filters on it.
    # A GPA as low as 1.0 still produces a full pool — only Agent 2's
    # classifier skews toward Reach.
    gpa_val = survey.get("gpa")
    gpa = float(gpa_val) if gpa_val else None
    try:
        gpa_scale = float(survey.get("gpa_scale", 4.0))
    except (TypeError, ValueError):
        gpa_scale = 4.0
    if gpa_scale not in (4.0, 5.0):
        gpa_scale = 4.0

    profile = StudentProfile(
        gpa=gpa,
        gpa_scale=gpa_scale,
        # Bug 4 — sat/act stay None when the student toggled "Not applicable";
        # Agent 1 has no SAT/ACT filter at the API level, so None is safe.
        sat=survey["sat"], act=survey["act"],
        intended_major=intended_major,
        budget=budget,
        # `state` is the *scoring* profile's home state used by Agent 2's
        # location_fit. The matcher built in render_running gets a separate
        # `state=matcher_state` that the Scorecard query actually sees.
        state=home_code,
        weather_pref=weather_pref,
        vibe_prefs=vibes,
        home_state=home_code,
        tuition_preference=tuition_pref,
        student_status=student_status,
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
    """
    Clickable progress dots at the top of the survey.
    Visited steps (<= max_step_reached) are clickable; future steps are
    visible but disabled. Clicking the current step is a no-op.
    """
    max_reached = int(st.session_state.get("max_step_reached", 1))

    with st.container(key="cff_progress_dots"):
        # Alternating dot / connector columns: 4 dots + 3 lines = 7 cells.
        widths: list[float] = []
        for i in range(total):
            widths.append(1)        # dot column (narrow)
            if i < total - 1:
                widths.append(2)    # connector column
        cols = st.columns(widths, gap="small")

        for i in range(total):
            step_num = i + 1
            col = cols[i * 2]
            with col:
                if step_num == current:
                    # Non-clickable visual marker for the current step —
                    # looks the same as visited primary buttons.
                    st.markdown(
                        f"<div class='cff-progress-dot-current'>{step_num}</div>",
                        unsafe_allow_html=True,
                    )
                elif step_num <= max_reached:
                    if st.button(
                        str(step_num),
                        key=f"progress_dot_{step_num}",
                        type="secondary",
                        use_container_width=False,
                    ):
                        st.session_state.step = step_num
                        st.rerun()
                else:
                    # Disabled future step.
                    st.button(
                        str(step_num),
                        key=f"progress_dot_{step_num}",
                        disabled=True,
                        use_container_width=False,
                    )

            if i < total - 1:
                line_col = cols[i * 2 + 1]
                # Line is completed up to (but not including) the current step.
                completed = (step_num < current)
                bg = ACCENT if completed else "#d8d8d8"
                line_col.markdown(
                    f"<div class='cff-step-line' "
                    f"style='background:{bg}; margin-top:1.35rem;'></div>",
                    unsafe_allow_html=True,
                )


# -----------------------------------------------------------------------------
# Survey steps
# -----------------------------------------------------------------------------
def render_step_1() -> None:
    s = st.session_state.survey
    st.markdown("<div class='cff-step-title'>Step 1 · Academic profile</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-step-hint'>We'll use these to gauge academic fit. Test scores are optional.</div>",
                unsafe_allow_html=True)

    # ── GPA scale toggle ────────────────────────────────────────────────
    st.markdown("**GPA scale**")
    current_scale = float(s.get("gpa_scale", 4.0))
    scale_label = "5.0 Scale" if current_scale == 5.0 else "4.0 Scale"
    chosen_scale = st.pills(
        "gpa_scale", ["4.0 Scale", "5.0 Scale"], selection_mode="single",
        default=scale_label, label_visibility="collapsed",
        key="pills_gpa_scale",
    )
    s["gpa_scale"] = 5.0 if chosen_scale == "5.0 Scale" else 4.0

    # GPA input — same 0.0–5.0 / 0.1 step regardless of scale; the helper
    # caption below explains how to interpret it.
    raw_gpa = float(s["gpa"]) if s["gpa"] is not None else 3.0
    s["gpa"] = st.number_input(
        "GPA *", min_value=0.0, max_value=5.0, step=0.1,
        value=min(5.0, max(0.0, raw_gpa)),
        key="step1_gpa_input",
    )
    if s["gpa_scale"] == 5.0:
        st.caption("Enter your GPA on a 5.0 scale — we'll convert it for comparison.")
    else:
        st.caption("Weighted GPA from AP or honors classes may exceed 4.0.")

    c1, c2 = st.columns(2)

    # ── SAT with Not-applicable toggle ──────────────────────────────────
    with c1:
        sat_na = st.session_state.sat_not_applicable
        hdr1, hdr2 = st.columns([2, 1.4])
        hdr1.markdown("**SAT score**")
        with hdr2:
            if st.button(
                "Not applicable",
                key="sat_na_btn",
                type="primary" if sat_na else "secondary",
                use_container_width=True,
            ):
                st.session_state.sat_not_applicable = not sat_na
                # Pop the widget key so when the input reappears it resets
                # to the value= default instead of the user's last entry.
                st.session_state.pop("sat_score_input", None)
                st.rerun()

        if not sat_na:
            # Pre-fill from the survey dict so a value entered here (or in
            # the My Profile tab) survives navigation between contexts.
            sat_default = int(s["sat"]) if s.get("sat") is not None else 400
            sat_in = st.number_input(
                "SAT score",
                min_value=400, max_value=1600, step=10,
                value=sat_default, label_visibility="collapsed",
                key="sat_score_input",
            )
            s["sat"] = int(sat_in) if sat_in > 400 else None
        else:
            s["sat"] = None

    # ── ACT with Not-applicable toggle ──────────────────────────────────
    with c2:
        act_na = st.session_state.act_not_applicable
        hdr1, hdr2 = st.columns([2, 1.4])
        hdr1.markdown("**ACT score**")
        with hdr2:
            if st.button(
                "Not applicable",
                key="act_na_btn",
                type="primary" if act_na else "secondary",
                use_container_width=True,
            ):
                st.session_state.act_not_applicable = not act_na
                st.session_state.pop("act_score_input", None)
                st.rerun()

        if not act_na:
            # Same pre-fill pattern as SAT.
            act_default = int(s["act"]) if s.get("act") is not None else 1
            act_in = st.number_input(
                "ACT score",
                min_value=1, max_value=36, step=1,
                value=act_default, label_visibility="collapsed",
                key="act_score_input",
            )
            # 1 (the minimum) is treated as "no score entered" — real ACT=1
            # is practically unseen.
            s["act"] = int(act_in) if act_in > 1 else None
        else:
            s["act"] = None

    # Major is now a fixed-list selectbox.
    major_val = s.get("major") or "Undecided"
    major_idx = MAJOR_OPTIONS.index(major_val) if major_val in MAJOR_OPTIONS else 0
    s["major"] = st.selectbox("Intended major", MAJOR_OPTIONS, index=major_idx, key="major_select")

    st.write("")
    _, right = st.columns([3, 1])
    with right:
        disabled = s["gpa"] is None or s["gpa"] <= 0.0
        if st.button("Next →", type="primary", use_container_width=True, disabled=disabled):
            st.session_state.step = 2
            st.session_state.max_step_reached = max(
                st.session_state.max_step_reached, 2
            )
            st.rerun()


def render_step_2() -> None:
    s = st.session_state.survey
    # Reconcile: a non-zero distance coming in from outside (e.g., the
    # My Profile tab) should uncollapse the slider so it's visible.
    md = s.get("max_distance")
    if isinstance(md, int) and md > 0 and st.session_state.distance_collapsed:
        st.session_state.distance_collapsed = False
    st.markdown("<div class='cff-step-title'>Step 2 · Location & weather</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-step-hint'>Where do you want to be? Pick as many climates or regions as feel right.</div>",
                unsafe_allow_html=True)

    # ── Student status (moved here from Step 1) ─────────────────────────
    st.markdown("**Student status**")
    current_status_label = STATUS_KEY_TO_LABEL.get(s.get("student_status", "domestic"), "Domestic")
    status_choice = st.pills(
        "student_status", STATUS_OPTIONS, selection_mode="single",
        default=current_status_label,
        label_visibility="collapsed", key="pills_status",
    )
    s["student_status"] = STATUS_LABEL_TO_KEY.get(status_choice or "Domestic", "domestic")

    is_intl = s.get("student_status") in INTERNATIONAL_LIKE

    # ── Home state + distance + location preference (domestic only) ─────
    if is_intl:
        st.markdown(
            "<div style='font-style: italic; color: #555; margin: 0.5rem 0 0.75rem;'>"
            "International and permanent resident students are shown "
            "out-of-state tuition for all schools.</div>",
            unsafe_allow_html=True,
        )
        s["tuition_preference"] = "no_preference"
    else:
        names = [n for n, _ in US_STATES_FULL]
        s["home_state_name"] = st.selectbox(
            "Home state", names,
            index=names.index(s["home_state_name"]) if s["home_state_name"] in names else 0,
        )

        # Max distance: slider by default; "No preference" collapses it.
        if st.session_state.distance_collapsed:
            col_txt, col_btn = st.columns([3, 1])
            col_txt.markdown("**Max distance from home:**  No preference")
            with col_btn:
                if st.button("Change", key="distance_change_btn",
                             type="secondary", use_container_width=True):
                    restored = int(st.session_state.get("distance_last_value") or 0)
                    s["max_distance"] = restored
                    st.session_state.distance_collapsed = False
                    st.session_state.pop("distance_slider", None)
                    st.rerun()
            s["max_distance"] = 0
        else:
            raw_dist = s.get("max_distance", 0)
            if not isinstance(raw_dist, int):
                raw_dist = 0
            s["max_distance"] = st.slider(
                f"Max distance from home: **{int(raw_dist):,} miles**",
                min_value=0, max_value=3000, step=100, value=int(raw_dist),
                key="distance_slider",
            )
            _, col_btn = st.columns([3, 1])
            with col_btn:
                if st.button("No preference", key="distance_no_pref_btn",
                             type="secondary", use_container_width=True):
                    if int(s["max_distance"]) > 0:
                        st.session_state.distance_last_value = int(s["max_distance"])
                    s["max_distance"] = 0
                    st.session_state.distance_collapsed = True
                    st.session_state.pop("distance_slider", None)
                    st.rerun()

        st.markdown("**Location preference**")
        current_label = TUITION_KEY_TO_LABEL.get(
            s.get("tuition_preference", "no_preference"), "No preference"
        )
        loc_choice = st.pills(
            "location_pref", TUITION_OPTIONS, selection_mode="single",
            default=current_label,
            label_visibility="collapsed", key="pills_location_pref",
        )
        s["tuition_preference"] = TUITION_LABEL_TO_KEY.get(
            loc_choice or "No preference", "no_preference"
        )

    # ── Climate + region chips (shown for everyone) ─────────────────────
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
            st.session_state.step = 3
            st.session_state.max_step_reached = max(
                st.session_state.max_step_reached, 3
            )
            st.rerun()


def render_step_3() -> None:
    s = st.session_state.survey
    # Reconcile: non-zero budget from outside uncollapses the slider.
    if int(s.get("budget") or 0) > 0 and st.session_state.budget_collapsed:
        st.session_state.budget_collapsed = False
    st.markdown("<div class='cff-step-title'>Step 3 · Budget & campus vibe</div>", unsafe_allow_html=True)
    st.markdown("<div class='cff-step-hint'>Cost is the annual tuition figure. Leave at $0 for no budget cap.</div>",
                unsafe_allow_html=True)

    # Budget: slider by default; "No preference" collapses it.
    if st.session_state.budget_collapsed:
        col_txt, col_btn = st.columns([3, 1])
        col_txt.markdown("**Max annual tuition:**  No preference")
        with col_btn:
            if st.button("Change", key="budget_change_btn",
                         type="secondary", use_container_width=True):
                restored = int(st.session_state.get("budget_last_value") or 0)
                s["budget"] = restored
                st.session_state.budget_collapsed = False
                st.session_state.pop("budget_slider", None)
                st.rerun()
        s["budget"] = 0
    else:
        budget_val = int(s.get("budget") or 0)
        s["budget"] = st.slider(
            f"Max annual tuition: **${budget_val:,}**",
            min_value=0, max_value=100_000, step=5_000, value=budget_val,
            key="budget_slider",
        )
        _, col_btn = st.columns([3, 1])
        with col_btn:
            if st.button("No preference", key="budget_no_pref_btn",
                         type="secondary", use_container_width=True):
                if int(s["budget"]) > 0:
                    st.session_state.budget_last_value = int(s["budget"])
                s["budget"] = 0
                st.session_state.budget_collapsed = True
                st.session_state.pop("budget_slider", None)
                st.rerun()

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
            st.session_state.step = 4
            st.session_state.max_step_reached = max(
                st.session_state.max_step_reached, 4
            )
            st.rerun()


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


def render_welcome() -> None:
    """Landing page shown before the survey on first load."""
    # Top dark nav bar — same ink-block styling as the main results nav.
    with st.container(key="cff_welcome_nav"):
        st.markdown(_logo_html("dark"), unsafe_allow_html=True)

    st.markdown(
        """<div class='cff-welcome-hero'>
  <h1 class='cff-welcome-headline'>Find the college that <em>actually</em> fits you</h1>
  <p class='cff-welcome-lede'>
    College Fit Finder ranks U.S. four-year colleges across academic fit,
    affordability, location, weather, and campus vibe — using your real
    profile, not a generic ranking. Tell us about you, and we'll surface
    the schools that match.
  </p>
  <div class='cff-welcome-features-label'>What you get</div>
  <div class='cff-welcome-features'>
    <div class='cff-welcome-feature'>Personalized fit scores based on your academic profile</div>
    <div class='cff-welcome-feature'>Schools ranked from a national pool of 800+ colleges</div>
    <div class='cff-welcome-feature'>Interactive map with color-coded reach, match, and safety schools</div>
    <div class='cff-welcome-feature'>Side-by-side school comparison tool</div>
    <div class='cff-welcome-feature'>Real data from College Scorecard, IPEDS, and weather APIs</div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.container(key="cff_welcome_cta"):
            if st.button(
                "Get Started",
                type="primary",
                use_container_width=True,
                key="welcome_get_started_btn",
            ):
                st.session_state.phase = "survey"
                st.rerun()


def render_survey() -> None:
    # Narrow container during the survey only.
    st.markdown("<script>document.querySelector('body').classList.add('cff-narrow');</script>",
                unsafe_allow_html=True)
    st.markdown(
        f"<div style='text-align:center; margin: 0.25rem 0 0.75rem;'>{_logo_html('light')}</div>",
        unsafe_allow_html=True,
    )
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
    # Dark brand container; the logo + spinner + cycling message all live
    # inside the same st.container so the CSS background paints one block.
    with st.container(key="cff_loading_screen"):
        st.markdown(
            f"<div style='text-align:center;'>{_logo_html('dark')}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='cff-spinner'></div>", unsafe_allow_html=True)
        msg_slot = st.empty()
        msg_slot.markdown(
            f"<div class='cff-loading-msg'>{LOADING_MESSAGES[0]}</div>",
            unsafe_allow_html=True,
        )

    survey = st.session_state.survey

    # Snapshot the prior run's saved-school context BEFORE the pipeline
    # overwrites session state. Used at the end to keep saves alive across
    # My-Profile refreshes (a "Start a new search" doesn't carry these
    # because a new survey wipes saved/compare on the way in).
    is_profile_refresh = st.session_state.get("_refresh_source") == "profile"
    prev_saved      = list(st.session_state.get("saved_schools") or [])
    prev_compare    = list(st.session_state.get("compare_schools") or [])
    prev_results    = st.session_state.get("results") or []
    prev_cards_by_id = {c.school_id: c for c in prev_results}
    # Carry forward already-preserved cards so a save survives multiple
    # consecutive profile refreshes (not just one).
    prev_cards_by_id.update(st.session_state.get("preserved_cards_by_id") or {})
    prev_schools_by_id = dict(st.session_state.get("schools_by_id") or {})

    # Bug 1 debug — log the raw survey state before any transformation.
    print(
        f"[survey state]      sat={survey.get('sat')!r}  "
        f"act={survey.get('act')!r}  "
        f"sat_not_applicable={st.session_state.get('sat_not_applicable')!r}  "
        f"act_not_applicable={st.session_state.get('act_not_applicable')!r}  "
        f"profile_refresh={is_profile_refresh}",
        flush=True,
    )
    profile, allowed_states, home_code = _survey_to_profile_and_backend(survey)

    # Build the matcher's state filter from the user's choices. Priority:
    #   1. If specific regions are selected → Agent 1 queries all states
    #      in those regions (server-side filtering).
    #   2. Else if distance is "Within 500 miles" → narrow to home state.
    #   3. Else → no state filter (all 50 states).
    if allowed_states:
        matcher_state: str | None = ",".join(allowed_states)
    elif _wants_home_state_only(survey) and home_code:
        matcher_state = home_code
    else:
        matcher_state = None

    matcher_profile = StudentProfile(
        gpa=profile.gpa, gpa_scale=profile.gpa_scale,
        sat=profile.sat, act=profile.act,
        intended_major=profile.intended_major, budget=profile.budget,
        state=matcher_state,
        weather_pref=profile.weather_pref, vibe_prefs=profile.vibe_prefs,
        home_state=profile.home_state,
        tuition_preference=profile.tuition_preference,
        student_status=profile.student_status,
    )

    # National 50-state fan-out unless the user explicitly opted into
    # in-state-only (which restricts the pool to their home state).
    # Out-of-state and no-preference both still get full national coverage —
    # tuition_preference only affects which tuition figure is displayed and
    # how the budget cap is applied, never the geographic search scope.
    # NB: assigned BEFORE the debug print below so the log line can read it.
    is_national_search = (
        matcher_state is None
        and matcher_profile.tuition_preference != "in_state"
    )

    # Bug 1 debug — confirm the SAT/ACT carry-through end-to-end. Logged on
    # every search so you can grep the Streamlit console for `[scoring profile]`.
    print(
        f"[scoring profile]   sat={profile.sat!r}  act={profile.act!r}  "
        f"gpa={profile.gpa!r}  major={profile.intended_major!r}",
        flush=True,
    )
    print(
        f"[matcher profile]   sat={matcher_profile.sat!r}  "
        f"act={matcher_profile.act!r}  state={matcher_profile.state!r}  "
        f"tuition_pref={matcher_profile.tuition_preference!r}  "
        f"national_search={is_national_search}",
        flush=True,
    )

    try:
        if is_national_search:
            schools = find_matching_schools_national(matcher_profile)
        else:
            schools = find_matching_schools(matcher_profile)
    except ScorecardError as e:
        st.session_state.last_error = f"Scorecard API error: {e}"
        st.session_state.phase = "survey"; st.rerun(); return

    if not schools:
        st.session_state.last_error = (
            "No schools matched those filters. Try widening your budget, "
            "loosening your regions, or clearing your major."
        )
        st.session_state.phase = "survey"; st.rerun(); return

    msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[1]}</div>", unsafe_allow_html=True)
    schools = enrich_schools_with_vibes(schools)

    # ── Climate enrichment + scoring ────────────────────────────────────
    # National pools can be ~1000 schools; enriching every one with the
    # Open-Meteo Archive API would take ~1-2 minutes. Instead we pre-score
    # using state-level climate fallback, take the top 100, enrich climate
    # only for those, and re-score that top slice. For non-national pools
    # (≤150 schools) we keep the existing single-pass flow.
    if is_national_search and len(schools) > 200:
        msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[3]}</div>", unsafe_allow_html=True)
        pre_scored = score_schools(profile, schools, weights=survey["weights"])
        pre_scored.sort(key=lambda x: x.overall, reverse=True)   # defensive

        # Geographic diversity guarantee: take the top 3 highest-fit schools
        # from each state first so the final 100 isn't dominated by whichever
        # 2-3 states happen to have the most highly-scored schools.
        diversified = _diversify_by_state(
            pre_scored, top_per_state=3, target_count=100,
        )
        top_ids = {fs.school_id for fs in diversified}
        schools_top = [s for s in schools if s.get("id") in top_ids]

        # Climate for the full top-100 (display data); IPEDS only for the
        # top 50 by pre-score since those are the schools the user is most
        # likely to drill into. Both cache to disk.
        msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[2]}</div>", unsafe_allow_html=True)
        enrich_schools_with_climate(schools_top)
        top_50_ids = {fs.school_id for fs in diversified[:50]}
        schools_top_50 = [s for s in schools_top if s.get("id") in top_50_ids]
        enrich_schools_with_ipeds(schools_top_50)

        # Re-score with real climate + IPEDS data so weather_fit, vibe_fit,
        # and affordability incorporate the new bonuses for the displayed pool.
        scored = score_schools(profile, schools_top, weights=survey["weights"])
    else:
        msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[2]}</div>", unsafe_allow_html=True)
        schools = enrich_schools_with_climate(schools)
        # IPEDS only for the top 50 by a quick pre-score (skips the long
        # tail of schools nobody will look at in detail).
        pre_scored_for_ipeds = score_schools(profile, schools, weights=survey["weights"])
        pre_scored_for_ipeds.sort(key=lambda x: x.overall, reverse=True)
        top_50_ids = {fs.school_id for fs in pre_scored_for_ipeds[:50]}
        schools_top_50 = [s for s in schools if s.get("id") in top_50_ids]
        enrich_schools_with_ipeds(schools_top_50)
        msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[3]}</div>", unsafe_allow_html=True)
        scored = score_schools(profile, schools, weights=survey["weights"])

    # Fix 2 — make absolutely sure the list is sorted by overall_fit desc
    # before Agent 3 builds cards. score_schools already sorts, but a
    # defensive resort here costs nothing and guards against future changes.
    scored.sort(key=lambda x: x.overall, reverse=True)

    msg_slot.markdown(f"<div class='cff-loading-msg'>{LOADING_MESSAGES[4]}</div>", unsafe_allow_html=True)
    cards = build_profile_cards(scored, profile, survey["weights"], top_n=100)
    # Defensive resort on the card list too — guards Agent 3's iteration order.
    cards.sort(key=lambda c: c.overall_fit, reverse=True)

    time.sleep(0.25)
    st.session_state.results = cards

    # Build the new schools_by_id from the freshly-fetched pool.
    new_schools_by_id = {s["id"]: s for s in schools if s.get("id") is not None}
    new_card_ids = {c.school_id for c in cards}

    if is_profile_refresh:
        # Carry forward saved + compare entries. Drop any whose ID is
        # neither in the new card pool nor recoverable from the previous
        # run's cards. For preserved (dropped-out) saves, also rescue the
        # raw school dict so My List size lookups still work.
        preserved_cards: dict = {}
        surviving_saved: list = []
        for sid in prev_saved:
            if sid in new_card_ids:
                surviving_saved.append(sid)
            elif sid in prev_cards_by_id:
                surviving_saved.append(sid)
                preserved_cards[sid] = prev_cards_by_id[sid]
                if sid in prev_schools_by_id and sid not in new_schools_by_id:
                    new_schools_by_id[sid] = prev_schools_by_id[sid]
            # else: silently drop (no card data to fall back on).

        surviving_compare = [sid for sid in prev_compare if sid in surviving_saved]

        st.session_state.saved_schools = surviving_saved
        st.session_state.compare_schools = surviving_compare
        st.session_state.preserved_cards_by_id = preserved_cards
    else:
        # New survey from scratch — wipe saved/compare so the user starts clean.
        st.session_state.saved_schools = []
        st.session_state.compare_schools = []
        st.session_state.preserved_cards_by_id = {}

    st.session_state.schools_by_id = new_schools_by_id
    st.session_state.phase = "results"
    st.session_state.main_tab = "results"
    st.session_state.display_limit = 50  # reset on every new search
    # Freeze the survey that produced these results. My Profile uses this
    # to decide whether "Refresh Results" should be enabled.
    st.session_state.baseline_survey = copy.deepcopy(st.session_state.survey)
    # If the user kicked this run from the My Profile tab, let the tab
    # show the success banner on their next visit.
    if st.session_state.pop("_refresh_source", None) == "profile":
        st.session_state.profile_refreshed = True
    st.rerun()


# -----------------------------------------------------------------------------
# Filtering + lookups
# -----------------------------------------------------------------------------
def _school_size(card: ProfileCard) -> int | None:
    info = st.session_state.schools_by_id.get(card.school_id) or {}
    return info.get("size")


def _apply_filters(
    cards: Iterable[ProfileCard],
    *,
    filter_class: str | None = None,
    # Kept for callsite compatibility (My List used to pass `filter_flags=[]`)
    # but stackable filters were removed from both the Results toolbar and
    # the My List filter bar. This argument is now ignored.
    filter_flags: Any = None,
) -> list[ProfileCard]:
    """Filter cards by classification only (Results + My List both)."""
    cls = filter_class if filter_class is not None else st.session_state.filter_class
    if cls == "All":
        return list(cards)
    return [c for c in cards if c.classification == cls]


def _fetch_school_on_demand(name: str) -> ProfileCard | None:
    """
    Look up a single school by name from Scorecard and run it through the
    enrich → score → build_card pipeline using the user's current survey.

    Used by the search bar when the requested school isn't in the current
    top-100 pool. The resulting card is stashed in `preserved_cards_by_id`
    (so render_school_profile's fallback finds it and the Results grid
    isn't polluted) and the raw enriched school dict is added to
    `schools_by_id` so size lookups continue to work.

    Returns the ProfileCard or None if no school matches the name.
    """
    name = (name or "").strip()
    if not name:
        return None

    survey = st.session_state.survey
    profile, _, _ = _survey_to_profile_and_backend(survey)
    weights = survey["weights"]

    # Relaxed matcher profile — drop state, budget, and major so the
    # requested school is never filtered out before it surfaces. The
    # *scoring* profile keeps everything intact so the fit score reflects
    # the user's actual preferences.
    matcher_profile = StudentProfile(
        gpa=profile.gpa, gpa_scale=profile.gpa_scale,
        sat=profile.sat, act=profile.act,
        intended_major=None, budget=None,
        state=None,
        weather_pref=profile.weather_pref, vibe_prefs=profile.vibe_prefs,
        home_state=profile.home_state,
        tuition_preference=None,
        student_status=profile.student_status,
    )

    try:
        results = find_matching_schools(
            matcher_profile, name=name,
            min_results=10, max_fetched=30, per_page=20,
        )
    except ScorecardError as e:
        print(f"[on-demand] Scorecard error: {e}", flush=True)
        return None

    if not results:
        return None

    # Prefer an exact case-insensitive name match, otherwise the first hit
    # (Scorecard returns alphabetically by default).
    needle = name.lower()
    school = next(
        (s for s in results if (s.get("name") or "").lower() == needle),
        results[0],
    )

    enrich_schools_with_vibes([school])
    enrich_schools_with_climate([school])

    scored = score_schools(profile, [school], weights=weights)
    cards = build_profile_cards(scored, profile, weights, top_n=1)
    if not cards:
        return None

    card = cards[0]
    sid = card.school_id
    if sid is None:
        return None

    preserved = dict(st.session_state.get("preserved_cards_by_id") or {})
    preserved[sid] = card
    st.session_state.preserved_cards_by_id = preserved
    st.session_state.schools_by_id[sid] = school

    return card


# -----------------------------------------------------------------------------
# Results phase — main nav, toolbar, list view, map view, profile page
# -----------------------------------------------------------------------------
def _logo_html(variant: str = "dark") -> str:
    """
    Return the brand wordmark HTML.
      variant="dark"  → white "College"/"Finder" (use on --ink backgrounds)
      variant="light" → --ink "College"/"Finder" (use on --paper backgrounds)
    "Fit" is always italic --sage.
    """
    return (
        f"<div class='cff-logo {variant}'>"
        "<svg class='cff-logo-cap' viewBox='0 0 24 24' width='26' height='26' "
        "xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>"
        "<path d='M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm0 11.72"
        "L5.18 11 12 7.28 18.82 11 12 14.72z' fill='currentColor'/>"
        "</svg>"
        "<span class='college'>College</span>"
        "<span class='fit'>Fit</span>"
        "<span class='finder'>Finder</span>"
        "</div>"
    )


def _render_main_nav() -> None:
    tabs = [("profile", "My Profile"), ("results", "Results"), ("list", "My List")]
    with st.container(key="cff_main_nav"):
        cols = st.columns([2.2, 1, 1, 1], vertical_alignment="center")
        with cols[0]:
            st.markdown(_logo_html("dark"), unsafe_allow_html=True)
        for i, (key, label) in enumerate(tabs):
            with cols[i + 1]:
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
    # Row 1: text-input search + count
    left, right = st.columns([4, 1])
    with left:
        st.text_input(
            "school_search",
            placeholder="Search for a school by name...",
            label_visibility="collapsed",
            key="school_search_text",
        )
    with right:
        st.markdown(
            f"<div style='text-align:right; padding-top: 0.5rem;' class='cff-count'>"
            f"<strong>{len(filtered)}</strong> of {len(all_cards)} schools</div>",
            unsafe_allow_html=True,
        )

    # Suggestion area — only once the user types 3+ characters.
    query = (st.session_state.get("school_search_text") or "").strip()
    if len(query) >= 3:
        q = query.lower()
        matches = [c for c in all_cards if q in (c.name or "").lower()][:8]
        with st.container(key="cff_search_suggestions"):
            if matches:
                st.markdown(
                    "<div class='cff-search-suggest-label'>Jump to a school:</div>",
                    unsafe_allow_html=True,
                )
                for c in matches:
                    if st.button(
                        f"🎓 {c.name}",
                        key=f"search_suggest_{c.school_id}",
                        use_container_width=True,
                        help=f"{c.classification} · {int(c.overall_fit)}% fit",
                    ):
                        st.session_state.selected_school_id = c.school_id
                        st.session_state.phase = "school_profile"
                        # Clear the search text so returning here is a fresh start.
                        if "school_search_text" in st.session_state:
                            del st.session_state["school_search_text"]
                        st.rerun()
                st.markdown(
                    "<div class='cff-search-suggest-label' "
                    "style='margin-top: 0.6rem;'>"
                    "Looking for a school not in your top-100?"
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div class='cff-search-suggest-label'>"
                    f'"{query}" isn\'t in your top-100 results — '
                    "fetch it from the College Scorecard:"
                    "</div>",
                    unsafe_allow_html=True,
                )

            # On-demand Scorecard lookup. Always offered when the user has
            # typed 3+ chars so they can pull any school by name regardless
            # of what's in the current pool.
            if st.button(
                f'Fetch "{query}" from the College Scorecard',
                key="search_ondemand_btn",
                use_container_width=True,
            ):
                with st.spinner("Fetching school profile..."):
                    fetched = _fetch_school_on_demand(query)
                if fetched is not None:
                    st.session_state.selected_school_id = fetched.school_id
                    st.session_state.phase = "school_profile"
                    if "school_search_text" in st.session_state:
                        del st.session_state["school_search_text"]
                    st.rerun()
                else:
                    st.error(
                        f'Couldn\'t find a school matching "{query}" in the '
                        f'College Scorecard. Try a different spelling.'
                    )

    # Row 2: classification pills only (stackable filters removed per spec).
    cls = st.pills(
        "class_filter", CLASSIFICATION_FILTERS, selection_mode="single",
        default=st.session_state.filter_class,
        label_visibility="collapsed", key="filter_class_pills",
    )
    st.session_state.filter_class = cls or "All"


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


def _card_tuition(card: ProfileCard) -> tuple[int | None, str]:
    """
    Returns (amount, short_label) for the tuition rate the student would
    actually pay at this school, per the display rules:
      - "in_state only"     → in-state rate
      - "out_of_state only" → out-of-state rate
      - "no preference"     → in-state if school is in the student's home
                              state, else out-of-state
    The short_label ("in-state" / "out-of-state") is shown as muted text
    next to the amount on cards.
    """
    survey = st.session_state.survey
    status = survey.get("student_status") or "domestic"
    pref = survey.get("tuition_preference") or "no_preference"
    home = STATE_NAME_TO_CODE.get(survey.get("home_state_name") or "") or ""
    sch_state = (card.state or "").upper()
    is_home = bool(home) and home == sch_state

    # International / permanent resident → always out-of-state tuition.
    if status in INTERNATIONAL_LIKE:
        return (card.tuition_out_of_state or card.tuition_in_state), "out-of-state"

    if pref == "in_state":
        return card.tuition_in_state, "in-state"
    if pref == "out_of_state":
        return card.tuition_out_of_state, "out-of-state"

    if is_home:
        return card.tuition_in_state, "in-state"
    if card.tuition_out_of_state is not None:
        return card.tuition_out_of_state, "out-of-state"
    return card.tuition_in_state, "in-state"


def _render_card(card: ProfileCard) -> None:
    initial = (card.name or "?")[0]
    color = _initial_color(initial)
    badge_cls = _class_css(card.classification)
    fit_pct = max(0, min(100, int(card.overall_fit)))
    size = _school_size(card)
    tuition, tuition_label = _card_tuition(card)

    # Fix 4 — always show enrollment as a full comma-formatted number.
    size_str = f"{size:,}" if size is not None else "—"

    # Fix 2 — climate label stays as plain text; Fix 6 — no vibe chips.
    location_line = f"{card.city}, {card.state}  ·  {card.climate.title()}"

    # Fix 5 — the International population stat shows only for international
    # and permanent-resident students.
    student_status = st.session_state.survey.get("student_status") or "domestic"
    intl_row_html = ""
    if student_status in INTERNATIONAL_LIKE:
        intl_row_html = (
            "<div class='cff-mini-cell full'>"
            "<div class='label'>INTERNATIONAL POPULATION</div>"
            f"<div class='value'>{_fmt_pct(card.international_pct)}</div>"
            "</div>"
        )

    body_html = f"""
<div class='cff-card-body'>
  <div class='cff-card-header'>
    <div class='cff-initial' style='background:{color};'>{initial.upper()}</div>
    <span class='cff-class-badge {badge_cls}'>{card.classification}</span>
  </div>
  <div class='cff-card-name'>{card.name}</div>
  <div class='cff-card-sub'>{location_line}</div>

  <div class='cff-fit-label'>OVERALL FIT</div>
  <div class='cff-fit'>{fit_pct}%</div>
  <div class='cff-thin-bar'><div style='width:{fit_pct}%;'></div></div>

  <div class='cff-mini-grid'>
    <div class='cff-mini-cell'>
      <div class='label'>TUITION</div>
      <div class='value'>{_fmt_currency(tuition)}<span class='qual'>{tuition_label}</span></div>
    </div>
    <div class='cff-mini-cell'>
      <div class='label'>SIZE</div>
      <div class='value'>{size_str}</div>
    </div>
    <div class='cff-mini-cell'>
      <div class='label'>ACCEPTANCE</div>
      <div class='value'>{_fmt_pct(card.acceptance_rate)}</div>
    </div>
    <div class='cff-mini-cell'>
      <div class='label'>AVG AID</div>
      <div class='value'>{_fmt_currency(card.avg_institutional_aid)}</div>
    </div>
    {intl_row_html}
  </div>
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


# Classification → pin color. Aligned with the list-view card badges:
#   Safety = green, Match = amber, Reach = red.
CLASS_COLOR = {
    "Reach":  "#E24B4A",   # red
    "Match":  "#BA7517",   # amber
    "Safety": "#639922",   # green
}


def _pins_data(cards: list[ProfileCard]) -> list[tuple[ProfileCard, float, float]]:
    """Return only the cards that have valid lat/lon in schools_by_id."""
    sbi = st.session_state.schools_by_id
    out: list[tuple[ProfileCard, float, float]] = []
    for c in cards:
        info = sbi.get(c.school_id) or {}
        lat, lon = info.get("lat"), info.get("lon")
        if lat is None or lon is None:
            continue
        try:
            out.append((c, float(lat), float(lon)))
        except (TypeError, ValueError):
            continue
    return out


def _build_folium_map(pins: list[tuple[ProfileCard, float, float]]) -> folium.Map:
    # Always center on the continental US with a zoom that frames CONUS and
    # excludes Hawaii / Alaska — regardless of where the filtered pins sit.
    m = folium.Map(
        location=[39.5, -98.35],
        zoom_start=4,
        tiles="CartoDB Positron",
        control_scale=False,
    )

    for card, lat, lon in pins:
        color = CLASS_COLOR.get(card.classification, "#555555")
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,
            color="#ffffff",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=f"{card.name} — {int(card.overall_fit)}",
        ).add_to(m)

    # Legend — fixed-position HTML injected into the map iframe.
    legend_html = f"""
<div style="position: absolute; bottom: 20px; left: 10px; z-index: 9999;
            background: white; padding: 8px 12px; border: 1px solid #d8d8d8;
            border-radius: 8px; font-size: 12px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);">
  <div style="margin-bottom: 3px;">
    <span style="display:inline-block; width:10px; height:10px; border-radius:50%;
                 background:{CLASS_COLOR['Reach']}; margin-right:6px;
                 vertical-align: middle;"></span>Reach
  </div>
  <div style="margin-bottom: 3px;">
    <span style="display:inline-block; width:10px; height:10px; border-radius:50%;
                 background:{CLASS_COLOR['Match']}; margin-right:6px;
                 vertical-align: middle;"></span>Match
  </div>
  <div>
    <span style="display:inline-block; width:10px; height:10px; border-radius:50%;
                 background:{CLASS_COLOR['Safety']}; margin-right:6px;
                 vertical-align: middle;"></span>Safety
  </div>
</div>
"""
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


def _render_map_detail_panel(card: ProfileCard) -> None:
    initial = (card.name or "?")[0]
    color = _initial_color(initial)
    badge_cls = _class_css(card.classification)

    size = _school_size(card)
    tuition, tuition_label = _card_tuition(card)

    # Fix 5 — enrollment always as a full comma-formatted number on the map panel.
    size_str = f"{size:,}" if size is not None else "—"

    # Fix 6 — International population row only renders for international /
    # permanent-resident students.
    student_status = st.session_state.survey.get("student_status") or "domestic"
    intl_row_html = ""
    if student_status in INTERNATIONAL_LIKE:
        intl_row_html = (
            "<div class='cff-mini-cell full'>"
            "<div class='label'>INTERNATIONAL POPULATION</div>"
            f"<div class='value'>{_fmt_pct(card.international_pct)}</div>"
            "</div>"
        )

    # Fix 3 — add "%" after the overall fit score in the side panel.
    header_html = f"""
<div style='display:flex; align-items:center; gap:0.75rem; margin-bottom:0.5rem;'>
  <div class='cff-initial' style='background:{color};'>{initial.upper()}</div>
  <div style='flex:1;'>
    <div class='cff-card-name'>{card.name}</div>
    <div class='cff-card-sub'>{card.city}, {card.state}  ·  {card.climate.title()}</div>
  </div>
</div>
<div style='margin-bottom:0.5rem;'>
  <span class='cff-class-badge {badge_cls}'>{card.classification}</span>
</div>
<div class='cff-fit-label'>OVERALL FIT</div>
<div class='cff-fit'>{int(card.overall_fit)}%</div>
<div class='cff-thin-bar'><div style='width:{int(card.overall_fit)}%;'></div></div>
"""
    st.markdown(header_html, unsafe_allow_html=True)

    # Category bars — Fix 4: append "%" via _bar_row's fmt parameter.
    short_labels = {
        "academic_fit": "Academic", "affordability": "Affordability",
        "location_fit": "Location", "weather_fit": "Weather", "vibe_fit": "Vibe",
    }
    for cat in ("academic_fit", "affordability", "location_fit", "weather_fit", "vibe_fit"):
        score = card.category_scores.get(cat, 0)
        _bar_row(short_labels[cat], float(score), fmt="{:.0f}%")

    # Fix 7 — no more vibe tag chips in the side panel.
    mini_html = f"""
<div class='cff-mini-grid' style='margin-top:0.5rem;'>
  <div class='cff-mini-cell'><div class='label'>TUITION</div>
    <div class='value'>{_fmt_currency(tuition)}<span class='qual'>{tuition_label}</span></div></div>
  <div class='cff-mini-cell'><div class='label'>ACCEPTANCE</div>
    <div class='value'>{_fmt_pct(card.acceptance_rate)}</div></div>
  <div class='cff-mini-cell'><div class='label'>ENROLLMENT</div>
    <div class='value'>{size_str}</div></div>
  <div class='cff-mini-cell'><div class='label'>MEDIAN DEBT</div>
    <div class='value'>{_fmt_currency(card.median_debt)}</div></div>
  {intl_row_html}
</div>
"""
    st.markdown(mini_html, unsafe_allow_html=True)

    # Actions
    saved = card.school_id in st.session_state.saved_schools
    c1, c2 = st.columns(2)
    with c1:
        if saved:
            if st.button("✓ Saved", key=f"map_save_{card.school_id}", use_container_width=True):
                st.session_state.saved_schools.remove(card.school_id); st.rerun()
        else:
            if st.button("Save school", key=f"map_save_{card.school_id}", use_container_width=True):
                st.session_state.saved_schools.append(card.school_id); st.rerun()
    with c2:
        if st.button("View full profile", key=f"map_view_{card.school_id}",
                     type="primary", use_container_width=True):
            st.session_state.selected_school_id = card.school_id
            st.session_state.phase = "school_profile"
            st.rerun()


def _render_map_view(cards: list[ProfileCard]) -> None:
    pins = _pins_data(cards)
    total_cards = len(cards)
    with_coords = len(pins)
    if with_coords < total_cards:
        st.caption(
            f"_Showing {with_coords} of {total_cards} filtered schools on the map "
            f"(rest are missing geographic coordinates)._"
        )

    left, right = st.columns([65, 35], gap="medium")

    with left:
        m = _build_folium_map(pins)
        # Stable key keeps pan/zoom across reruns; returned_objects limits
        # reruns to click events only.
        map_data = st_folium(
            m, height=600, use_container_width=True,
            returned_objects=["last_object_clicked"],
            key="cff_map",
        )

    # Resolve click → school id, via a rounded-coord lookup to survive float drift.
    clicked = (map_data or {}).get("last_object_clicked") if map_data else None
    if clicked and "lat" in clicked and "lng" in clicked:
        ck = (round(float(clicked["lat"]), 5), round(float(clicked["lng"]), 5))
        coord_index = {
            (round(lat, 5), round(lon, 5)): card for card, lat, lon in pins
        }
        matched = coord_index.get(ck)
        if matched and matched.school_id != st.session_state.map_selected_id:
            st.session_state.map_selected_id = matched.school_id
            st.rerun()

    with right:
        selected_card: ProfileCard | None = None
        if st.session_state.map_selected_id is not None:
            for c in cards:
                if c.school_id == st.session_state.map_selected_id:
                    selected_card = c
                    break

        if selected_card is None:
            st.markdown(
                """<div class='cff-map-placeholder' style='padding:2.5rem 1rem;'>
  <h3>Click a pin to see school details</h3>
  <p>Hover each pin for name and fit score.
     Click to load the school's breakdown here.</p>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            with st.container(border=True):
                _render_map_detail_panel(selected_card)


def _render_results_content() -> None:
    all_cards = st.session_state.results or []
    if not all_cards:
        st.info("No results yet. Go back and run the survey.")
        if st.button("← Back to survey"):
            st.session_state.phase = "survey"
            st.session_state.step = 1
            st.session_state.max_step_reached = 1
            st.rerun()
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
        _render_map_view(filtered)
    else:
        _render_card_grid(filtered)


COMPARE_LIMIT = 5


def _add_to_compare(school_id: Any) -> None:
    """Append a school to the comparison table, up to COMPARE_LIMIT."""
    cmp_list = st.session_state.compare_schools
    if school_id in cmp_list:
        st.toast("Already in your comparison.", icon="ℹ️")
        return
    if len(cmp_list) >= COMPARE_LIMIT:
        st.toast(f"You can compare up to {COMPARE_LIMIT} schools at a time.", icon="⚠️")
        return
    cmp_list.append(school_id)
    st.toast("Added to comparison.", icon="✅")


def _render_saved_row(card: ProfileCard) -> None:
    """One full-width row in the Saved Schools section."""
    initial = (card.name or "?")[0]
    color = _initial_color(initial)
    badge_cls = _class_css(card.classification)

    with st.container(border=True):
        # Layout: initial | body (name → location → badge) | fit | 3 action buttons
        cols = st.columns([1, 6, 1.5, 5], gap="small")

        with cols[0]:
            st.markdown(
                f"<div class='cff-initial' style='background:{color}; margin-top:0.25rem;'>"
                f"{initial.upper()}</div>",
                unsafe_allow_html=True,
            )

        with cols[1]:
            # Fix 3 — order is: name, location, badge. Vibe chips removed.
            st.markdown(
                f"""<div class='cff-saved-row-body'>
  <div class='cff-card-name'>{card.name}</div>
  <div class='cff-card-sub'>{card.city}, {card.state}  ·  {card.climate.title()}</div>
  <div style='margin-top:0.35rem;'>
    <span class='cff-class-badge {badge_cls}'>{card.classification}</span>
  </div>
</div>""",
                unsafe_allow_html=True,
            )

        with cols[2]:
            # Fix 4 — append "%" to the fit score.
            st.markdown(
                f"""<div class='cff-saved-row-fit'>{int(card.overall_fit)}%</div>
<div class='cff-saved-row-fit-lbl'>FIT</div>""",
                unsafe_allow_html=True,
            )

        with cols[3]:
            btn_cols = st.columns(3, gap="small")
            with btn_cols[0]:
                if st.button("View profile", key=f"ml_view_{card.school_id}",
                             type="primary", use_container_width=True):
                    st.session_state.selected_school_id = card.school_id
                    st.session_state.phase = "school_profile"
                    st.rerun()
            with btn_cols[1]:
                in_compare = card.school_id in st.session_state.compare_schools
                label = "In compare" if in_compare else "Add to compare"
                if st.button(label, key=f"ml_add_{card.school_id}",
                             use_container_width=True, disabled=in_compare):
                    _add_to_compare(card.school_id)
                    st.rerun()
            with btn_cols[2]:
                is_pending = st.session_state.pending_unsave_id == card.school_id
                if is_pending:
                    if st.button("Confirm?", key=f"ml_confirm_{card.school_id}",
                                 type="primary", use_container_width=True):
                        if card.school_id in st.session_state.saved_schools:
                            st.session_state.saved_schools.remove(card.school_id)
                        if card.school_id in st.session_state.compare_schools:
                            st.session_state.compare_schools.remove(card.school_id)
                        st.session_state.pending_unsave_id = None
                        st.rerun()
                else:
                    if st.button("Unsave", key=f"ml_unsave_{card.school_id}",
                                 use_container_width=True):
                        st.session_state.pending_unsave_id = card.school_id
                        st.rerun()


# -----------------------------------------------------------------------------
# Compare table
# -----------------------------------------------------------------------------
def _fmt_sat_range(card: ProfileCard) -> str:
    if card.sat_range:
        return f"{card.sat_range[0]}–{card.sat_range[1]}"
    if card.act_range:
        return f"ACT {card.act_range[0]}–{card.act_range[1]}"
    return "—"


def _fmt_temp(v: float | None) -> str:
    return f"{v:.0f}°F" if v is not None else "—"


def _fmt_score(v: float | None) -> str:
    return f"{v:.0f}" if v is not None else "—"


def _best_indices(values: list[Any], direction: str | None) -> list[int]:
    """
    Return every index sharing the best value in `values`.
      - "high" → all indices at the maximum non-None value
      - "low"  → all indices at the minimum non-None value
      - None   → empty list (no highlight)
    Exact equality on the raw value defines a tie.
    """
    if direction not in ("high", "low"):
        return []
    candidates = [(i, v) for i, v in enumerate(values) if v is not None]
    if not candidates:
        return []
    best_val = (max if direction == "high" else min)(v for _, v in candidates)
    return [i for i, v in candidates if v == best_val]


def _render_compare_table(cards: list[ProfileCard]) -> None:
    if not cards:
        st.markdown(
            """<div class='cff-map-placeholder'>
  <h3>Nothing in the comparison yet</h3>
  <p>Add schools to compare using the <strong>Add to compare</strong> button above.</p>
</div>""",
            unsafe_allow_html=True,
        )
        return

    n = len(cards)
    col_widths = [1.7] + [1.4] * n   # label column a bit wider

    # ── Header row: blank label cell + each school's initial/name/remove button.
    hdr = st.columns(col_widths, gap="small")
    hdr[0].markdown("")  # spacer
    for i, card in enumerate(cards):
        with hdr[i + 1]:
            initial = (card.name or "?")[0]
            color = _initial_color(initial)
            st.markdown(
                f"""<div class='cff-compare-col'>
  <div class='cff-compare-col-initial' style='background:{color};'>{initial.upper()}</div>
  <div class='cff-compare-col-name'>{card.name}</div>
</div>""",
                unsafe_allow_html=True,
            )
            if st.button("Remove", key=f"cmp_rm_{card.school_id}",
                         use_container_width=True):
                st.session_state.compare_schools.remove(card.school_id)
                st.rerun()

    # ── Metric rows. Each tuple: (label, extractor, direction, formatter).
    metrics: list[tuple[str, Any, str | None, Any]] = [
        ("Overall fit score",  lambda c: c.overall_fit,                   "high", _fmt_score),
        ("Classification",     lambda c: c.classification,                None,   lambda v: v or "—"),
        ("In-state tuition",   lambda c: c.tuition_in_state,              "low",  _fmt_currency),
        ("Out-of-state tuition", lambda c: c.tuition_out_of_state,        "low",  _fmt_currency),
        ("Acceptance rate",    lambda c: c.acceptance_rate,               "high", _fmt_pct),
        ("SAT range (25–75%)", lambda c: c,                               None,   _fmt_sat_range),
        ("Enrollment",         lambda c: _school_size(c),                 None,   _fmt_size),
        ("Graduation rate",    lambda c: c.graduation_rate,               "high", _fmt_pct),
        ("Median debt",        lambda c: c.median_debt,                   "low",  _fmt_currency),
        ("Academic fit",       lambda c: c.category_scores.get("academic_fit"),   "high", _fmt_score),
        ("Affordability",      lambda c: c.category_scores.get("affordability"),  "high", _fmt_score),
        ("Location",           lambda c: c.category_scores.get("location_fit"),   "high", _fmt_score),
        ("Weather",            lambda c: c.category_scores.get("weather_fit"),    "high", _fmt_score),
        ("Vibe",               lambda c: c.category_scores.get("vibe_fit"),       "high", _fmt_score),
        ("Winter temp",        lambda c: c.winter_temp_f,                 None,   _fmt_temp),
        ("Summer temp",        lambda c: c.summer_temp_f,                 None,   _fmt_temp),
    ]

    for label, extractor, direction, fmt in metrics:
        raw_values = [extractor(c) for c in cards]
        # For SAT range the extractor returns the card itself — skip highlight.
        if label == "SAT range (25–75%)":
            best: list[int] = []
        else:
            best = _best_indices(raw_values, direction)

        # Fix 6 — a tie (2+ schools share the best value) highlights yellow;
        # a single best highlights green.
        is_tie = len(best) > 1
        best_set = set(best)

        row = st.columns(col_widths, gap="small")
        row[0].markdown(f"<div class='cff-compare-label'>{label}</div>",
                         unsafe_allow_html=True)
        for i, v in enumerate(raw_values):
            if i in best_set:
                cell_cls = "cff-compare-cell tie" if is_tie else "cff-compare-cell best"
            else:
                cell_cls = "cff-compare-cell"
            row[i + 1].markdown(
                f"<div class='{cell_cls}'>{fmt(v)}</div>",
                unsafe_allow_html=True,
            )


# -----------------------------------------------------------------------------
# My List tab — filter toolbar, saved rows, divider, compare table
# -----------------------------------------------------------------------------
def _render_my_list_tab() -> None:
    all_cards: list[ProfileCard] = st.session_state.results or []
    cards_by_id = {c.school_id: c for c in all_cards}
    # Schools saved across a profile refresh that fell out of the new top
    # 100 still need to render here — fall back to their preserved cards.
    preserved = st.session_state.get("preserved_cards_by_id") or {}
    for sid, card in preserved.items():
        cards_by_id.setdefault(sid, card)
    saved_ids = st.session_state.saved_schools
    saved_cards = [cards_by_id[sid] for sid in saved_ids if sid in cards_by_id]

    # ── Filter toolbar (My List–scoped, classification only per Fix 1) ──
    cls = st.pills(
        "ml_class_filter", CLASSIFICATION_FILTERS, selection_mode="single",
        default=st.session_state.my_list_filter_class,
        label_visibility="collapsed", key="my_list_filter_class_pills",
    )
    st.session_state.my_list_filter_class = cls or "All"

    filtered_saved = _apply_filters(
        saved_cards,
        filter_class=st.session_state.my_list_filter_class,
    )

    # ── Saved Schools section.
    st.markdown(
        f"<div class='cff-section-title'>Saved schools "
        f"<span style='color:#888; font-weight:400;'>"
        f"({len(filtered_saved)} of {len(saved_cards)})</span></div>",
        unsafe_allow_html=True,
    )

    if not saved_cards:
        st.markdown(
            """<div class='cff-map-placeholder'>
  <h3>You haven't saved any schools yet</h3>
  <p>Browse your results and click <strong>Save</strong> on any school to add it here.</p>
</div>""",
            unsafe_allow_html=True,
        )
    elif not filtered_saved:
        st.info("No saved schools match the current filters. Try clearing some.")
    else:
        for card in filtered_saved:
            _render_saved_row(card)

    # Fix 5 — always-visible "Add more schools" card at the bottom of the
    # saved list, regardless of how many schools are saved. Clicking jumps
    # back to the Results tab.
    with st.container(key="ml_add_more_card"):
        if st.button(
            "＋  Add more schools",
            key="ml_add_more_btn",
            use_container_width=True,
        ):
            st.session_state.main_tab = "results"
            st.rerun()

    st.divider()

    # ── Compare Schools section.
    compare_cards = [cards_by_id[sid] for sid in st.session_state.compare_schools
                      if sid in cards_by_id]
    st.markdown(
        f"<div class='cff-section-title'>Compare schools "
        f"<span style='color:#888; font-weight:400;'>"
        f"(comparing {len(compare_cards)} "
        f"school{'s' if len(compare_cards) != 1 else ''})</span></div>",
        unsafe_allow_html=True,
    )
    _render_compare_table(compare_cards)


def _render_profile_tab() -> None:
    s = st.session_state.survey
    baseline = st.session_state.get("baseline_survey") or _default_survey()

    # Reconcile the collapse flags with actual stored values so that, e.g.,
    # a non-zero budget set in the survey doesn't display as "No preference"
    # on the profile side.
    md = s.get("max_distance")
    if isinstance(md, int) and md > 0 and st.session_state.distance_collapsed:
        st.session_state.distance_collapsed = False
    if int(s.get("budget") or 0) > 0 and st.session_state.budget_collapsed:
        st.session_state.budget_collapsed = False

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        """<div class='cff-profile-header'>
  <h2>My Profile</h2>
  <div class='sub'>Update your preferences below and click
    <strong>Refresh Results</strong> to update your matches.</div>
</div>""",
        unsafe_allow_html=True,
    )

    # ── Success banner — auto-fades after 3s via CSS animation ───────────
    if st.session_state.get("profile_refreshed"):
        st.markdown(
            "<div class='cff-success-flash'>✓ Your results have been updated</div>",
            unsafe_allow_html=True,
        )
        # Clear so it only appears once per refresh.
        st.session_state.profile_refreshed = False

    # ── Academic Profile card ────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='cff-section-title' style='margin-top:0;'>Academic Profile</div>",
            unsafe_allow_html=True,
        )

        # GPA scale toggle — mirrors Step 1 so changes round-trip.
        st.markdown("**GPA scale**")
        current_scale = float(s.get("gpa_scale", 4.0))
        scale_label = "5.0 Scale" if current_scale == 5.0 else "4.0 Scale"
        chosen_scale = st.pills(
            "gpa_scale", ["4.0 Scale", "5.0 Scale"], selection_mode="single",
            default=scale_label, label_visibility="collapsed",
            key="prof_pills_gpa_scale",
        )
        s["gpa_scale"] = 5.0 if chosen_scale == "5.0 Scale" else 4.0

        raw_gpa = float(s["gpa"]) if s["gpa"] is not None else 3.0
        s["gpa"] = st.number_input(
            "GPA", min_value=0.0, max_value=5.0, step=0.1,
            value=min(5.0, max(0.0, raw_gpa)),
            key="prof_gpa",
        )
        if s["gpa_scale"] == 5.0:
            st.caption("Enter your GPA on a 5.0 scale — we'll convert it for comparison.")
        else:
            st.caption("Weighted GPA from AP or honors classes may exceed 4.0.")

        c1, c2 = st.columns(2)

        # SAT with Not-applicable toggle
        with c1:
            sat_na = st.session_state.sat_not_applicable
            hdr1, hdr2 = st.columns([2, 1.4])
            hdr1.markdown("**SAT score**")
            with hdr2:
                if st.button(
                    "Not applicable",
                    key="prof_sat_na_btn",
                    type="primary" if sat_na else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.sat_not_applicable = not sat_na
                    # Pop both the survey-side and profile-side widget keys
                    # so the input genuinely resets on toggle, regardless of
                    # which tab the user toggled from.
                    st.session_state.pop("sat_score_input", None)
                    st.session_state.pop("prof_sat_input", None)
                    st.rerun()

            if not sat_na:
                # Pre-fill the widget from `survey["sat"]` so anything entered
                # in the survey carries over here (and vice versa). Distinct
                # widget key from the survey so Streamlit can't apply stale
                # widget state from the other tab and override the survey value.
                sat_default = int(s["sat"]) if s.get("sat") is not None else 400
                sat_in = st.number_input(
                    "SAT score",
                    min_value=400, max_value=1600, step=10,
                    value=sat_default, label_visibility="collapsed",
                    key="prof_sat_input",
                )
                s["sat"] = int(sat_in) if sat_in > 400 else None
            else:
                s["sat"] = None

        # ACT with Not-applicable toggle
        with c2:
            act_na = st.session_state.act_not_applicable
            hdr1, hdr2 = st.columns([2, 1.4])
            hdr1.markdown("**ACT score**")
            with hdr2:
                if st.button(
                    "Not applicable",
                    key="prof_act_na_btn",
                    type="primary" if act_na else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.act_not_applicable = not act_na
                    st.session_state.pop("act_score_input", None)
                    st.session_state.pop("prof_act_input", None)
                    st.rerun()

            if not act_na:
                act_default = int(s["act"]) if s.get("act") is not None else 1
                act_in = st.number_input(
                    "ACT score",
                    min_value=1, max_value=36, step=1,
                    value=act_default, label_visibility="collapsed",
                    key="prof_act_input",
                )
                s["act"] = int(act_in) if act_in > 1 else None
            else:
                s["act"] = None

        # Major as selectbox
        major_val = s.get("major") or "Undecided"
        major_idx = MAJOR_OPTIONS.index(major_val) if major_val in MAJOR_OPTIONS else 0
        s["major"] = st.selectbox(
            "Intended major", MAJOR_OPTIONS,
            index=major_idx, key="prof_major_select",
        )

    # ── Location and Weather card ────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='cff-section-title' style='margin-top:0;'>Location & Weather</div>",
            unsafe_allow_html=True,
        )

        # Student status chips at the very top (moved here from the Academic card).
        st.markdown("**Student status**")
        status_label = STATUS_KEY_TO_LABEL.get(
            s.get("student_status", "domestic"), "Domestic"
        )
        status_choice = st.pills(
            "student_status", STATUS_OPTIONS, selection_mode="single",
            default=status_label,
            label_visibility="collapsed", key="pills_status",
        )
        s["student_status"] = STATUS_LABEL_TO_KEY.get(
            status_choice or "Domestic", "domestic"
        )

        is_intl = s.get("student_status") in INTERNATIONAL_LIKE

        if is_intl:
            st.markdown(
                "<div style='font-style: italic; color: #555; margin: 0.5rem 0 0.75rem;'>"
                "International and permanent resident students are shown "
                "out-of-state tuition for all schools.</div>",
                unsafe_allow_html=True,
            )
            s["tuition_preference"] = "no_preference"
        else:
            names = [n for n, _ in US_STATES_FULL]
            s["home_state_name"] = st.selectbox(
                "Home state", names,
                index=names.index(s["home_state_name"]) if s["home_state_name"] in names else 0,
                key="prof_state",
            )

            # Max distance: slider by default; "No preference" collapses it.
            if st.session_state.distance_collapsed:
                col_txt, col_btn = st.columns([3, 1])
                col_txt.markdown("**Max distance from home:**  No preference")
                with col_btn:
                    if st.button("Change", key="prof_distance_change_btn",
                                 type="secondary", use_container_width=True):
                        restored = int(st.session_state.get("distance_last_value") or 0)
                        s["max_distance"] = restored
                        st.session_state.distance_collapsed = False
                        st.session_state.pop("distance_slider", None)
                        st.rerun()
                s["max_distance"] = 0
            else:
                raw_dist = s.get("max_distance", 0)
                if not isinstance(raw_dist, int):
                    raw_dist = 0
                s["max_distance"] = st.slider(
                    f"Max distance from home: **{int(raw_dist):,} miles**",
                    min_value=0, max_value=3000, step=100, value=int(raw_dist),
                    key="distance_slider",
                )
                _, col_btn = st.columns([3, 1])
                with col_btn:
                    if st.button("No preference", key="prof_distance_no_pref_btn",
                                 type="secondary", use_container_width=True):
                        if int(s["max_distance"]) > 0:
                            st.session_state.distance_last_value = int(s["max_distance"])
                        s["max_distance"] = 0
                        st.session_state.distance_collapsed = True
                        st.session_state.pop("distance_slider", None)
                        st.rerun()

            # Location preference (renamed from Tuition preference).
            st.markdown("**Location preference**")
            tlabel = TUITION_KEY_TO_LABEL.get(
                s.get("tuition_preference") or "no_preference", "No preference"
            )
            tchoice = st.pills(
                "location_pref", TUITION_OPTIONS, selection_mode="single",
                default=tlabel, label_visibility="collapsed", key="pills_location_pref",
            )
            s["tuition_preference"] = TUITION_LABEL_TO_KEY.get(
                tchoice or "No preference", "no_preference"
            )

        st.markdown("**Preferred climate**")
        climates = st.pills(
            "climate", CLIMATE_OPTIONS, selection_mode="multi",
            default=s["climates"], label_visibility="collapsed", key="pills_climate",
        )
        s["climates"] = list(climates or [])

        st.markdown("**Preferred region**")
        regions = st.pills(
            "region", REGION_OPTIONS, selection_mode="multi",
            default=s["regions"], label_visibility="collapsed", key="pills_region",
        )
        s["regions"] = list(regions or [])

    # ── Budget & Campus Vibe card ────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='cff-section-title' style='margin-top:0;'>Budget & Campus Vibe</div>",
            unsafe_allow_html=True,
        )

        # Budget: slider by default; "No preference" collapses it.
        if st.session_state.budget_collapsed:
            col_txt, col_btn = st.columns([3, 1])
            col_txt.markdown("**Max annual tuition:**  No preference")
            with col_btn:
                if st.button("Change", key="prof_budget_change_btn",
                             type="secondary", use_container_width=True):
                    restored = int(st.session_state.get("budget_last_value") or 0)
                    s["budget"] = restored
                    st.session_state.budget_collapsed = False
                    st.session_state.pop("budget_slider", None)
                    st.rerun()
            s["budget"] = 0
        else:
            budget_val = int(s.get("budget") or 0)
            s["budget"] = st.slider(
                f"Max annual tuition: **${budget_val:,}**",
                min_value=0, max_value=100_000, step=5_000, value=budget_val,
                key="budget_slider",
            )
            _, col_btn = st.columns([3, 1])
            with col_btn:
                if st.button("No preference", key="prof_budget_no_pref_btn",
                             type="secondary", use_container_width=True):
                    if int(s["budget"]) > 0:
                        st.session_state.budget_last_value = int(s["budget"])
                    s["budget"] = 0
                    st.session_state.budget_collapsed = True
                    st.session_state.pop("budget_slider", None)
                    st.rerun()

        st.markdown("**Campus size**")
        size = st.pills(
            "size", CAMPUS_SIZE_OPTIONS, selection_mode="single",
            default=s["campus_size"] if s["campus_size"] in CAMPUS_SIZE_OPTIONS else "No preference",
            label_visibility="collapsed", key="pills_size",
        )
        s["campus_size"] = size or "No preference"

        st.markdown("**Campus vibe**")
        vibes = st.pills(
            "vibes", VIBE_OPTIONS, selection_mode="multi",
            default=s["vibes"], label_visibility="collapsed", key="pills_vibes",
        )
        s["vibes"] = list(vibes or [])

    # ── Priority Weights card (unchanged) ────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='cff-section-title' style='margin-top:0;'>Priority Weights</div>",
            unsafe_allow_html=True,
        )
        for key, label in [
            ("academic_fit",  "Academic quality"),
            ("affordability", "Affordability"),
            ("location_fit",  "Location"),
            ("weather_fit",   "Weather"),
            ("vibe_fit",      "Campus vibe"),
        ]:
            current = int(s["weights"].get(key, 3))
            s["weights"][key] = st.slider(
                f"{label} — **{current}**",
                min_value=1, max_value=5, value=current, step=1,
                key=f"prof_w_{key}",
            )

    # ── Refresh button ───────────────────────────────────────────────────
    has_changes = _survey_for_compare(s) != _survey_for_compare(baseline)

    st.write("")
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if st.button(
            "Refresh Results",
            type="primary",
            use_container_width=True,
            disabled=(not has_changes),
            help="No changes to apply" if not has_changes else None,
            key="profile_refresh_btn",
        ):
            # Don't clear saved / compare here — render_running's profile-
            # refresh branch will intersect them with the new results and
            # preserve any saves whose card data we can still serve.
            st.session_state._refresh_source = "profile"
            st.session_state.phase = "running"
            st.rerun()


def render_results_phase() -> None:
    # Logo now lives inside the dark nav bar itself; no separate title above it.
    _render_main_nav()
    st.write("")

    if st.session_state.main_tab == "profile":
        _render_profile_tab()
    elif st.session_state.main_tab == "list":
        _render_my_list_tab()
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
    sid = st.session_state.selected_school_id
    for c in (st.session_state.results or []):
        if c.school_id == sid:
            card = c
            break
    # Fall back to preserved cards — covers saves dropped from a profile
    # refresh AND on-demand Scorecard lookups for schools outside the top-100.
    if card is None:
        preserved = st.session_state.get("preserved_cards_by_id") or {}
        card = preserved.get(sid)

    # Fix 1 — add explicit top padding so the Back button is never clipped
    # by the browser chrome / Streamlit header area.
    st.markdown(
        "<div style='padding-top: 1.25rem;'></div>",
        unsafe_allow_html=True,
    )

    if not card:
        st.error("School not found. It may have been filtered out or a new search was run.")
        if st.button("Back to results", key="school_back_missing"):
            st.session_state.phase = "results"; st.rerun()
        return

    if st.button("Back to results", key="school_back"):
        st.session_state.phase = "results"
        st.session_state.selected_school_id = None
        st.rerun()

    badge_cls = _class_css(card.classification)
    # Fix 2 — append "%" to the top-right overall fit score.
    header_html = f"""
<div class='cff-profile-header'>
  <div>
    <div class='cff-profile-name'>{card.name}</div>
    <div class='cff-profile-sub'>{card.location_summary}  ·
      <span class='cff-class-badge {badge_cls}'>{card.classification}</span>
    </div>
  </div>
  <div>
    <div class='cff-profile-fit'>{int(card.overall_fit)}%</div>
    <div class='cff-profile-fit-lbl'>OVERALL FIT</div>
  </div>
</div>
"""
    st.markdown(header_html, unsafe_allow_html=True)

    st.write(card.description)

    # Fix 5 — website link rendered right below the description, labeled.
    if card.url:
        st.markdown(f"**Website:** [{card.url}]({card.url})")

    # Fit breakdown — Fix 3: append "%" to each category score via _bar_row's
    # fmt parameter.
    st.markdown("<div class='cff-section-title'>Fit breakdown</div>", unsafe_allow_html=True)
    for cat, score in card.category_scores.items():
        _bar_row(card.category_labels[cat], score, fmt="{:.0f}%")

    # Key stats grid — always show both tuition rates on the profile page,
    # regardless of the survey's tuition preference.
    size = _school_size(card)
    sat = f"{card.sat_range[0]}–{card.sat_range[1]}" if card.sat_range else "—"
    winter = f"{card.winter_temp_f:.0f}°F" if card.winter_temp_f is not None else "—"
    summer = f"{card.summer_temp_f:.0f}°F" if card.summer_temp_f is not None else "—"

    st.markdown("<div class='cff-section-title'>Key stats</div>", unsafe_allow_html=True)
    sf_ratio = (
        f"{card.student_faculty_ratio}:1"
        if card.student_faculty_ratio is not None else "—"
    )
    cells = [
        _stat_cell("IN-STATE TUITION",      _fmt_currency(card.tuition_in_state)),
        _stat_cell("OUT-OF-STATE TUITION",  _fmt_currency(card.tuition_out_of_state)),
        _stat_cell("ACCEPTANCE RATE",       _fmt_pct(card.acceptance_rate)),
        _stat_cell("SAT RANGE (25–75%)",    sat),
        _stat_cell("AVG INSTITUTIONAL AID", _fmt_currency(card.avg_institutional_aid)),
        _stat_cell("% RECEIVING AID",       _fmt_pct(card.pct_receiving_aid)),
        _stat_cell("ENROLLMENT",            _fmt_size(size)),
        _stat_cell("GRADUATION RATE",       _fmt_pct(card.graduation_rate)),
        _stat_cell("STUDENT/FACULTY RATIO", sf_ratio),
        _stat_cell("ATHLETICS",             card.athletics_division or "—"),
        _stat_cell("INTERNATIONAL STUDENTS", _fmt_pct(card.international_pct)),
        _stat_cell("MEDIAN DEBT",           _fmt_currency(card.median_debt)),
        _stat_cell("WINTER TEMP",           winter),
        _stat_cell("SUMMER TEMP",           summer),
    ]
    # Religious affiliation cell only when applicable.
    if card.religious_affiliation:
        cells.append(_stat_cell("RELIGIOUS AFFILIATION", card.religious_affiliation))
    stat_html = "<div class='cff-stat-grid'>" + "".join(cells) + "</div>"
    st.markdown(stat_html, unsafe_allow_html=True)

    # Extra context for international / permanent-resident applicants.
    student_status = st.session_state.survey.get("student_status") or "domestic"
    if student_status in INTERNATIONAL_LIKE and card.international_pct is not None:
        st.caption(
            f"_This school enrolls {card.international_pct*100:.0f}% "
            f"international students._"
        )

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

    # Campus vibe — Fix 4: append "%" to each vibe score.
    st.markdown("<div class='cff-section-title'>Campus vibe</div>", unsafe_allow_html=True)
    ath_score_map = {"dominant": 100, "high": 80, "medium": 55, "low": 25}
    _bar_row("Academic intensity", float(card.vibe_academic_intensity or 0), fmt="{:.0f}%")
    _bar_row("Party scene",        float(card.vibe_party_scene or 0),        fmt="{:.0f}%")
    _bar_row("Diversity",          float(card.vibe_diversity_score or 0),    fmt="{:.0f}%")
    _bar_row("Athletics",
             float(ath_score_map.get(card.vibe_athletics_culture or "", 0)),
             fmt="{:.0f}%")

    if card.vibe_tags:
        chips = "".join(f"<span class='cff-vibe-chip'>{t}</span>" for t in card.vibe_tags)
        st.markdown(f"<div class='cff-vibe-chips'>{chips}</div>", unsafe_allow_html=True)

    # Fix 5 — the bare URL that used to live here has moved up under the
    # description as a labeled "Website:" line, so nothing renders here.

    st.write("")

    # ── Action buttons ──────────────────────────────────────────────────
    # Fix 6 — Add-to-compare is fully functional and independent of saved state.
    saved = card.school_id in st.session_state.saved_schools
    in_compare = card.school_id in st.session_state.compare_schools

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
        if in_compare:
            st.button("In compare", key="profile_compare",
                      use_container_width=True, disabled=True)
        else:
            if st.button("Add to compare", key="profile_compare",
                         use_container_width=True):
                if len(st.session_state.compare_schools) >= 5:
                    st.warning("You can compare up to 5 schools at a time.")
                else:
                    st.session_state.compare_schools.append(card.school_id)
                    st.rerun()


# -----------------------------------------------------------------------------
# Phase routing
# -----------------------------------------------------------------------------
phase = st.session_state.phase
if phase == "welcome":
    render_welcome()
elif phase == "survey":
    render_survey()
elif phase == "running":
    render_running()
elif phase == "school_profile":
    render_school_profile()
else:
    render_results_phase()
