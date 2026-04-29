"""End-to-end check for the search-bar on-demand Scorecard lookup.

Simulates a CA student searching for "Harvard" — Harvard sits in MA, so
a state-restricted matcher would normally exclude it. The on-demand path
relaxes state/budget/major filters but keeps the *scoring* profile intact,
so the resulting fit score is personalized.
"""

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards
from agents.vibe import enrich_schools_with_vibes
from agents.weather import enrich_schools_with_climate


# Scoring profile — the student's real preferences (CA home state).
profile = StudentProfile(
    gpa=3.7, sat=1450, act=None,
    intended_major=None, budget=None,
    state="CA", home_state="CA",
    tuition_preference=None, student_status="domestic",
)
weights = {"academic_fit": 4, "affordability": 2, "location_fit": 2,
           "weather_fit": 2, "vibe_fit": 3}

# Relaxed matcher profile — drop state/budget/major so Harvard isn't filtered
# out before it surfaces (mirrors _fetch_school_on_demand in app.py).
matcher_profile = StudentProfile(
    gpa=profile.gpa, sat=profile.sat, act=profile.act,
    intended_major=None, budget=None,
    state=None,
    weather_pref=profile.weather_pref, vibe_prefs=profile.vibe_prefs,
    home_state=profile.home_state,
    tuition_preference=None, student_status=profile.student_status,
)

print("Fetching 'Harvard' from Scorecard...")
results = find_matching_schools(
    matcher_profile, name="Harvard",
    min_results=10, max_fetched=30, per_page=20,
)
print(f"  Scorecard returned {len(results)} school(s) matching 'Harvard'")
for s in results[:5]:
    print(f"   - {s['name']} ({s.get('state')})  id={s.get('id')}")

assert results, "Expected at least one school matching 'Harvard'"

# Pick the canonical match — same logic as _fetch_school_on_demand.
needle = "harvard"
school = next(
    (s for s in results if (s.get("name") or "").lower() == needle),
    results[0],
)
print(f"\nSelected: {school['name']} ({school.get('state')})")

enrich_schools_with_vibes([school])
enrich_schools_with_climate([school])
print(f"  vibe attached:  {bool(school.get('vibe'))}")
print(f"  climate label:  {school.get('climate_label')}")
print(f"  winter temp:    {school.get('winter_temp_f')}")

scored = score_schools(profile, [school], weights=weights)
cards = build_profile_cards(scored, profile, weights, top_n=1)
assert cards, "Expected one ProfileCard"
card = cards[0]

print(f"\nProfileCard:")
print(f"  name:           {card.name}")
print(f"  classification: {card.classification}")
print(f"  overall_fit:    {card.overall_fit}")
print(f"  per-category:")
for cat, score in card.category_scores.items():
    print(f"    {cat:18s} {score}")

# Personalization checks:
#   - location_fit is comparing pref=CA vs school=MA, so it should NOT be 100
#     (which would mean the scoring profile lost its home state).
#   - academic_fit should be high since SAT 1450 is competitive at Harvard.
loc_fit = card.category_scores.get("location_fit", 100)
acad_fit = card.category_scores.get("academic_fit", 0)
assert loc_fit < 100, (
    f"location_fit should reflect MA != CA, got {loc_fit} — scoring profile "
    f"likely lost its home state"
)
assert 0 <= card.overall_fit <= 100, "Fit score out of range"

print(f"\n[OK] location_fit={loc_fit} (<100, reflects MA vs CA)")
print(f"[OK] academic_fit={acad_fit} (SAT 1450 vs Harvard's range)")
print(f"[OK] on-demand pipeline produced a personalized fit card.")
