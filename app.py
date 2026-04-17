"""College Fit Finder — Streamlit entry point."""

import streamlit as st

from agents.agent1_matcher import (
    ScorecardError,
    StudentProfile,
    find_matching_schools,
)
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards
from agents.vibe import enrich_schools_with_vibes
from agents.weather import enrich_schools_with_climate

US_STATES = [
    "", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY", "DC",
]

WEATHER_OPTIONS = ["No preference", "Warm", "Cold", "Mild", "Seasonal"]
VIBE_OPTIONS = [
    "Big-city", "Small-town", "Suburban", "Rural",
    "Sporty", "Artsy", "Academic / nerdy", "Greek life",
    "Outdoorsy", "Diverse", "Liberal", "Conservative",
]

CLASS_BADGE = {
    "Reach":  ("🔴", "Reach"),
    "Match":  ("🟡", "Match"),
    "Safety": ("🟢", "Safety"),
}

st.set_page_config(page_title="College Fit Finder", page_icon="🎓", layout="wide")
st.title("🎓 College Fit Finder")
st.caption("Tell us about you — we'll surface schools that fit.")

with st.sidebar:
    st.header("Your profile")
    gpa = st.number_input("Unweighted GPA", min_value=0.0, max_value=4.0, value=3.5, step=0.1)
    test_type = st.radio("Test score", ["SAT", "ACT", "None"], horizontal=True)
    sat = act = None
    if test_type == "SAT":
        sat = st.number_input("SAT (400–1600)", min_value=400, max_value=1600, value=1200, step=10)
    elif test_type == "ACT":
        act = st.number_input("ACT (1–36)", min_value=1, max_value=36, value=25, step=1)

    major = st.text_input("Intended major", placeholder="e.g. Computer Science")
    budget = st.number_input(
        "Max annual cost of attendance (USD)",
        min_value=0, max_value=120_000, value=40_000, step=1_000,
    )
    state = st.selectbox("Preferred state (optional)", US_STATES)
    weather = st.selectbox("Weather preference", WEATHER_OPTIONS)
    vibes = st.multiselect("Campus vibe", VIBE_OPTIONS)

    st.divider()
    st.subheader("What matters most?")
    w_academic = st.slider("Academic fit", 0, 10, 5)
    w_affordability = st.slider("Affordability", 0, 10, 5)
    w_location = st.slider("Location fit", 0, 10, 5)
    w_weather = st.slider("Weather fit", 0, 10, 3)
    w_vibe = st.slider("Campus vibe fit", 0, 10, 3)

    search = st.button("Find my schools", type="primary", use_container_width=True)

if not search:
    st.info("Fill out your profile on the left, then click **Find my schools**.")
    st.stop()

profile = StudentProfile(
    gpa=gpa,
    sat=sat,
    act=act,
    intended_major=major or None,
    budget=int(budget) if budget else None,
    state=state or None,
    weather_pref=None if weather == "No preference" else weather,
    vibe_prefs=vibes,
)

weights = {
    "academic_fit": w_academic,
    "affordability": w_affordability,
    "location_fit": w_location,
    "weather_fit": w_weather,
    "vibe_fit": w_vibe,
}

with st.spinner("Searching the College Scorecard..."):
    try:
        schools = find_matching_schools(profile)
    except ScorecardError as e:
        st.error(str(e))
        st.stop()

if not schools:
    st.warning("No schools matched. Try widening your budget or clearing the state filter.")
    st.stop()

with st.spinner("Matching vibe profiles..."):
    schools = enrich_schools_with_vibes(schools)

with st.spinner("Fetching climate data from Open-Meteo..."):
    schools = enrich_schools_with_climate(schools)

with st.spinner("Scoring fit..."):
    scored = score_schools(profile, schools, weights=weights)

with st.spinner("Building profile cards..."):
    cards = build_profile_cards(scored, profile, weights, top_n=15)

buckets = {"Safety": 0, "Match": 0, "Reach": 0}
for c in cards:
    buckets[c.classification] = buckets.get(c.classification, 0) + 1

hdr = st.columns(4)
hdr[0].metric("Schools shown", len(cards))
hdr[1].metric("🟢 Safety", buckets["Safety"])
hdr[2].metric("🟡 Match", buckets["Match"])
hdr[3].metric("🔴 Reach", buckets["Reach"])

st.divider()

for card in cards:
    icon, label = CLASS_BADGE.get(card.classification, ("", card.classification))

    with st.container(border=True):
        top = st.columns([4, 1, 1])
        top[0].markdown(f"### {card.name}")
        top[0].caption(f"{icon} **{label}**  ·  {card.location_summary}")
        top[1].metric("Overall fit", f"{card.overall_fit:.0f}")
        if card.cost_of_attendance:
            top[2].metric("Cost / yr", f"${card.cost_of_attendance:,}")

        st.write(card.description)

        if card.vibe_tags:
            st.markdown("**Vibe:** " + " · ".join(f"`{t}`" for t in card.vibe_tags))

        # Category bars
        st.caption("**Category breakdown**")
        cat_cols = st.columns(len(card.category_scores))
        for i, (cat, score) in enumerate(card.category_scores.items()):
            cat_cols[i].progress(
                int(score),
                text=f"{card.category_labels[cat]}: {score:.0f}",
            )

        # Key stats
        fact_cols = st.columns(4)
        if card.acceptance_rate is not None:
            fact_cols[0].markdown(f"**Acceptance rate**\n\n{card.acceptance_rate*100:.0f}%")
        else:
            fact_cols[0].markdown("**Acceptance rate**\n\n—")

        if card.sat_range:
            fact_cols[1].markdown(f"**SAT (25–75%)**\n\n{card.sat_range[0]}–{card.sat_range[1]}")
        elif card.act_range:
            fact_cols[1].markdown(f"**ACT (25–75%)**\n\n{card.act_range[0]}–{card.act_range[1]}")
        else:
            fact_cols[1].markdown("**SAT / ACT**\n\n—")

        if card.gpa_range:
            fact_cols[2].markdown(
                f"**GPA (est.)**\n\n{card.gpa_range[0]:.2f}–{card.gpa_range[1]:.2f}"
            )
        else:
            fact_cols[2].markdown("**GPA**\n\n—")

        if card.winter_temp_f is not None and card.summer_temp_f is not None:
            fact_cols[3].markdown(
                f"**Climate**\n\n{card.climate.title()}  \n"
                f"❄ {card.winter_temp_f:.0f}°F · ☀ {card.summer_temp_f:.0f}°F"
            )
        else:
            fact_cols[3].markdown(f"**Climate**\n\n{card.climate.title()}")

        # Tuition detail
        if card.tuition_in_state or card.tuition_out_of_state:
            parts = []
            if card.tuition_in_state:
                parts.append(f"In-state tuition: ${card.tuition_in_state:,}")
            if card.tuition_out_of_state and card.tuition_out_of_state != card.tuition_in_state:
                parts.append(f"Out-of-state tuition: ${card.tuition_out_of_state:,}")
            st.caption("  ·  ".join(parts))

        if card.gpa_range:
            st.caption(f"_{card.gpa_note}_")

        st.caption(f"_{card.climate_summary}_")

        # Strengths / weaknesses
        sw = st.columns(2)
        with sw[0]:
            st.markdown("**✅ Strengths for you**")
            for s in card.strengths:
                st.markdown(f"- {s}")
        with sw[1]:
            st.markdown("**⚠️ Watch-outs**")
            if card.weaknesses:
                for w in card.weaknesses:
                    st.markdown(f"- {w}")
            else:
                st.markdown("- _No major concerns given your priorities._")

        if card.url:
            st.markdown(f"[{card.url}]({card.url})")
