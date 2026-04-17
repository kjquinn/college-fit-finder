"""Verify pagination + MIT/Harvard discovery for high-stat MA/CS profile."""

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import score_schools

profile = StudentProfile(
    gpa=4.0, sat=1550, intended_major="Computer Science",
    budget=100000, state="MA",
    weather_pref="Cold", vibe_prefs=["Academic / nerdy"],
)

print("=== High-stat MA/CS profile with pagination ===")
schools = find_matching_schools(profile)
print(f"Agent 1 returned {len(schools)} matching schools")

targets = ["Massachusetts Institute of Technology", "Harvard", "Tufts", "Amherst", "Williams", "Boston"]
hits = {t: [] for t in targets}
for s in schools:
    for t in targets:
        if t.lower() in (s["name"] or "").lower():
            hits[t].append(s["name"])

print("\nElite MA schools found:")
for t, names in hits.items():
    flag = "[YES]" if names else "[no] "
    print(f"  {flag} {t}: {names}")

print("\nTop 10 by Agent 2 fit score:")
scored = score_schools(profile, schools, weights={
    "academic_fit": 10, "affordability": 3,
    "location_fit": 5, "weather_fit": 3, "vibe_fit": 3,
})
for fs in scored[:10]:
    sat = fs.school.get("sat_avg")
    admit = fs.school.get("admission_rate")
    admit_s = f"{admit*100:.0f}%" if admit is not None else "?"
    print(f"  [{fs.classification:6}] {fs.overall:5.1f}  "
          f"{fs.name[:45]:45}  SAT={sat}  admit={admit_s}")
