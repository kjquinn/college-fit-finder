"""Verify Fix 1 (50-state fan-out) + Fix 2 (sort by fit desc) end-to-end."""

import time
from collections import Counter

from agents.agent1_matcher import (
    StudentProfile, find_matching_schools, find_matching_schools_national,
)
from agents.agent2_scorer import score_schools


def header(label: str) -> None:
    print(f"\n{'='*72}\n{label}\n{'='*72}")


# ── Profile A — true national, no filters ──────────────────────────────
header("Profile A — GPA 3.0, no scores, Undecided, CA home, no preferences")
profile_a = StudentProfile(
    gpa=3.0, sat=None, act=None,
    intended_major=None, budget=None,
    state=None, home_state="CA",
    tuition_preference=None, student_status="domestic",
)
t0 = time.time()
schools_a = find_matching_schools_national(profile_a)
print(f"Agent 1 (national): {len(schools_a)} schools in {time.time()-t0:.1f}s")
states_a = Counter((s.get("state") or "?").upper() for s in schools_a)
print(f"Distinct states: {len(states_a)}")
print(f"All states present: {sorted(states_a)}")
print(f"Counts: top 10 = {sorted(states_a.items(), key=lambda kv: -kv[1])[:10]}")

# Score and confirm sort
weights = {"academic_fit": 3, "affordability": 3, "location_fit": 3,
           "weather_fit": 3, "vibe_fit": 3}
scored_a = score_schools(profile_a, schools_a, weights=weights)
fits_a = [s.overall for s in scored_a]
print(f"Top 5 fit scores: {[round(s, 1) for s in fits_a[:5]]}")
print(f"Sorted desc: {fits_a == sorted(fits_a, reverse=True)}")
print(f"Top school: {scored_a[0].name}  ({scored_a[0].overall:.1f}) — {scored_a[0].school.get('state')}")
top_states_in_top10 = {s.school.get("state") for s in scored_a[:10]}
print(f"States in top 10 by fit: {sorted(top_states_in_top10)}")


# ── Profile B — Northeast region (single-query path) ───────────────────
header("Profile B — GPA 3.8, SAT 1400, CS, TX home, Northeast region, $60k")
NE_STATES = ["ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"]
profile_b = StudentProfile(
    gpa=3.8, sat=1400, act=None,
    intended_major="Computer Science", budget=60000,
    state=",".join(NE_STATES), home_state="TX",
    tuition_preference=None, student_status="domestic",
)
t0 = time.time()
schools_b = find_matching_schools(profile_b)
print(f"Agent 1 (single): {len(schools_b)} schools in {time.time()-t0:.1f}s")
states_b = Counter((s.get("state") or "?").upper() for s in schools_b)
print(f"Distinct states: {len(states_b)}  (all NE: {set(states_b).issubset(NE_STATES)})")

scored_b = score_schools(profile_b, schools_b, weights=weights)
fits_b = [s.overall for s in scored_b]
print(f"Top 5 fit scores: {[round(s, 1) for s in fits_b[:5]]}")
print(f"Sorted desc: {fits_b == sorted(fits_b, reverse=True)}")
print(f"Top school: {scored_b[0].name}  ({scored_b[0].overall:.1f}) — {scored_b[0].school.get('state')}")
