"""Live smoke test for Agent 1 against the College Scorecard API."""

import json

from agents.agent1_matcher import StudentProfile, find_matching_schools


def run_case(label: str, profile: StudentProfile) -> None:
    print(f"\n=== {label} ===")
    print(f"profile: sat={profile.effective_sat()} state={profile.state} "
          f"budget={profile.budget} major={profile.intended_major}")
    schools = find_matching_schools(profile, limit=5)
    print(f"got {len(schools)} schools")
    for s in schools:
        print(f"  - {s['name']} ({s['city']}, {s['state']}) "
              f"SAT={s['sat_avg']} COA=${s['cost_of_attendance']}")


if __name__ == "__main__":
    run_case(
        "CS in CA, SAT 1300, $75k budget",
        StudentProfile(
            gpa=3.7, sat=1300, intended_major="Computer Science",
            budget=75000, state="CA",
        ),
    )

    run_case(
        "Business, ACT 25, no state, $30k budget",
        StudentProfile(
            gpa=3.5, act=25, intended_major="Business",
            budget=30000,
        ),
    )

    run_case(
        "No test scores, NY, $60k budget",
        StudentProfile(gpa=3.8, budget=60000, state="NY"),
    )
