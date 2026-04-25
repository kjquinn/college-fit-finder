"""End-to-end: U Arizona's IPEDS data flows through Agent 1 → ipeds.py → Agent 3."""

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.ipeds import enrich_schools_with_ipeds
from agents.vibe import enrich_schools_with_vibes
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards


# Profile narrowly targeting AZ to ensure we get U Arizona in the pool.
profile = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major=None, budget=None,
    state="AZ", home_state="AZ",
    tuition_preference=None, student_status="domestic",
)
schools = find_matching_schools(profile)
print(f"Agent 1 returned {len(schools)} schools")

ua = next((s for s in schools if s.get("id") == 104179), None)
print(f"University of Arizona in pool: {bool(ua)}")

# Enrich just the AZ pool with IPEDS
enrich_schools_with_vibes(schools)
enrich_schools_with_ipeds(schools)

ua = next((s for s in schools if s.get("id") == 104179), None)
if ua:
    print("\nU Arizona raw IPEDS fields:")
    for k in sorted(ua.keys()):
        if k.startswith("ipeds_"):
            print(f"  {k}: {ua[k]}")

# Score and build cards
weights = {"academic_fit": 3, "affordability": 3, "location_fit": 3,
           "weather_fit": 3, "vibe_fit": 3}
scored = score_schools(profile, schools, weights=weights)
cards = build_profile_cards(scored, profile, weights, top_n=50)

ua_card = next((c for c in cards if c.school_id == 104179), None)
if ua_card:
    print("\nU Arizona ProfileCard IPEDS fields:")
    for attr in ("student_faculty_ratio", "housing_capacity", "housing_guaranteed",
                 "avg_institutional_aid", "pct_receiving_aid", "athletics_division",
                 "religious_affiliation", "pct_on_campus", "num_programs"):
        print(f"  {attr}: {getattr(ua_card, attr)}")
    print(f"\n  classification: {ua_card.classification}, overall_fit: {ua_card.overall_fit}")
else:
    print("\nU Arizona did NOT make it into the cards.")
