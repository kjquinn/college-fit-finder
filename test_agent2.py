"""Live smoke test: Agent 1 -> Agent 2 end-to-end."""

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import score_schools


def run(label, profile, weights):
    print(f"\n=== {label} ===")
    schools = find_matching_schools(profile, limit=15)
    print(f"Agent 1 returned {len(schools)} schools")
    scored = score_schools(profile, schools, weights=weights)

    counts = {"Safety": 0, "Match": 0, "Reach": 0}
    for s in scored:
        counts[s.classification] = counts.get(s.classification, 0) + 1
    print(f"classifications: {counts}")

    for fs in scored[:5]:
        cats = " | ".join(f"{k[:4]}:{v:.0f}" for k, v in fs.categories.items())
        coa = fs.school.get("cost_of_attendance")
        print(f"  [{fs.classification:6}] {fs.overall:5.1f}  {fs.name[:40]:40}  "
              f"COA=${coa}  {cats}")


if __name__ == "__main__":
    # Case A: affordability-focused out-of-stater
    run(
        "Business, ACT 25, GPA 3.5, $30k budget, prefers TX, warm weather, big-city",
        StudentProfile(
            gpa=3.5, act=25, intended_major="Business",
            budget=30000, state="TX",
            weather_pref="Warm", vibe_prefs=["Big-city"],
        ),
        weights={
            "academic_fit": 3, "affordability": 10,
            "location_fit": 6, "weather_fit": 4, "vibe_fit": 4,
        },
    )

    # Case B: strong student, academic-focused
    run(
        "CS, SAT 1450, GPA 3.9, $80k budget, MA, cold weather, small-town",
        StudentProfile(
            gpa=3.9, sat=1450, intended_major="Computer Science",
            budget=80000, state="MA",
            weather_pref="Cold", vibe_prefs=["Small-town", "Academic / nerdy"],
        ),
        weights={
            "academic_fit": 10, "affordability": 2,
            "location_fit": 6, "weather_fit": 3, "vibe_fit": 5,
        },
    )
