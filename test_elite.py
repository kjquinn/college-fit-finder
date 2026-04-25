"""Verify elite injection — Harvard / MIT must appear and classify as Reach
   for a 3.5/1200 student; state schools land as Match or Safety."""

from collections import Counter

from agents.agent1_matcher import StudentProfile, find_matching_schools_national
from agents.agent2_scorer import score_schools


profile = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major=None, budget=None,
    state=None, home_state="CA",
    tuition_preference=None, student_status="domestic",
)

schools = find_matching_schools_national(profile)
print(f"\nAgent 1 returned {len(schools)} schools")

# Quick state diversity sanity check.
states = Counter((s.get("state") or "?").upper() for s in schools)
print(f"Distinct states: {len(states)}")

# Elite presence checks.
TARGET_ELITE = [
    "Harvard University",
    "Massachusetts Institute of Technology",
    "Stanford University",
    "Yale University",
    "Princeton University",
    "University of California-Berkeley",
    "University of Chicago",
    "Williams College",
]
by_name = {(s.get("name") or "").lower(): s for s in schools}
print("\nElite presence:")
for name in TARGET_ELITE:
    sid = by_name.get(name.lower())
    print(f"  [{'YES' if sid else 'no '}] {name}")

# State-school sanity — pick a few common state flagships
STATE_FLAGSHIPS = [
    "University of Massachusetts-Amherst",
    "University of California-Riverside",
    "University of Florida",
    "The University of Texas at Austin",
]
print("\nState flagships:")
for name in STATE_FLAGSHIPS:
    sid = by_name.get(name.lower())
    print(f"  [{'YES' if sid else 'no '}] {name}")

# Score with default weights and check classifications.
weights = {"academic_fit": 3, "affordability": 3, "location_fit": 3,
           "weather_fit": 3, "vibe_fit": 3}
scored = score_schools(profile, schools, weights=weights)
scored_by_name = {(fs.name or "").lower(): fs for fs in scored}

print("\nClassifications for elite (expect Reach):")
for name in TARGET_ELITE:
    fs = scored_by_name.get(name.lower())
    if fs:
        print(f"  {name[:42]:42}  {fs.classification:6}  fit={fs.overall:.1f}")

print("\nClassifications for state flagships (expect Match/Safety):")
for name in STATE_FLAGSHIPS:
    fs = scored_by_name.get(name.lower())
    if fs:
        print(f"  {name[:42]:42}  {fs.classification:6}  fit={fs.overall:.1f}")
