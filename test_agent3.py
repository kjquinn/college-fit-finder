"""Live smoke test for the full Agent 1 -> 2 -> 3 pipeline."""

import json
from dataclasses import asdict

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards


def run(label, profile, weights):
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    schools = find_matching_schools(profile)
    scored = score_schools(profile, schools, weights=weights)
    cards = build_profile_cards(scored, profile, weights, top_n=15)
    print(f"Agent 1: {len(schools)} schools  ->  Agent 2 ranked  ->  Agent 3: {len(cards)} cards\n")

    for c in cards[:3]:
        print(f"--- {c.name} ({c.classification}) · overall {c.overall_fit:.0f} ---")
        print(f"  {c.description}")
        print(f"  Location: {c.location_summary}  |  Climate: {c.climate}")
        print(f"  Cost: ${c.cost_of_attendance}  |  Accept: "
              f"{c.acceptance_rate*100 if c.acceptance_rate else '?'}%"
              f"  |  SAT range: {c.sat_range}  |  GPA est: {c.gpa_range}")
        print("  Strengths:")
        for s in c.strengths:
            print(f"    + {s}")
        print("  Weaknesses:")
        for w in c.weaknesses:
            print(f"    - {w}")
        print()

    # Validate the shape of the structured output for one card.
    if cards:
        sample = asdict(cards[0])
        print(f"Structured card has {len(sample)} fields, JSON-serialisable: "
              f"{'yes' if _json_ok(sample) else 'no'}")


def _json_ok(d):
    try:
        json.dumps(d, default=str)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    run(
        "High-stat MA / CS / $100k — expect MIT-style reaches near the top",
        StudentProfile(
            gpa=4.0, sat=1550, intended_major="Computer Science",
            budget=100000, state="MA",
            weather_pref="Cold", vibe_prefs=["Academic / nerdy", "Small-town"],
        ),
        weights={
            "academic_fit": 10, "affordability": 3,
            "location_fit": 5, "weather_fit": 4, "vibe_fit": 5,
        },
    )

    run(
        "Budget-focused TX / Business / ACT 25 / $30k",
        StudentProfile(
            gpa=3.5, act=25, intended_major="Business",
            budget=30000, state="TX",
            weather_pref="Warm", vibe_prefs=["Big-city"],
        ),
        weights={
            "academic_fit": 3, "affordability": 10,
            "location_fit": 6, "weather_fit": 3, "vibe_fit": 4,
        },
    )
