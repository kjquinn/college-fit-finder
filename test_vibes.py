"""End-to-end vibe pipeline test."""

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards
from agents.vibe import enrich_schools_with_vibes, get_vibe
from agents.weather import enrich_schools_with_climate


def run(label, profile, weights):
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    schools = find_matching_schools(profile, min_results=30, max_fetched=200)

    schools = enrich_schools_with_vibes(schools)
    with_vibe = [s for s in schools if s.get("vibe")]
    print(f"Agent 1: {len(schools)} schools  |  with vibe data: {len(with_vibe)}/{len(schools)}")

    # Skip weather for speed in this test — it's already proven.
    scored = score_schools(profile, schools, weights=weights)
    cards = build_profile_cards(scored, profile, weights, top_n=6)

    print(f"\nTop 6 cards:")
    for c in cards:
        vibe_bit = (", ".join(c.vibe_tags[:4])) if c.vibe_tags else "(no vibe data)"
        print(f"  [{c.classification:6}] {c.overall_fit:5.1f}  {c.name[:40]:40}  "
              f"vibe_fit={c.category_scores['vibe_fit']:.0f}  "
              f"setting={c.vibe_campus_setting or '-'}")
        print(f"             tags: {vibe_bit}")


if __name__ == "__main__":
    # Verify well-known schools look right in isolation first.
    print("Direct lookups:")
    for uid in [166027, 166683, 240444, 186131]:  # Harvard, MIT, UW-Madison, Princeton
        v = get_vibe(uid)
        if v:
            print(f"  id={uid}  {v['name']}  "
                  f"party={v['party_scene']} academic={v['academic_intensity']} "
                  f"tags={v['vibe_tags']}")

    # Profile who wants big-city + artsy + liberal — should favor NYU-type schools.
    run(
        "NY / Art / SAT 1350 / wants big-city + artsy + liberal",
        StudentProfile(
            gpa=3.7, sat=1350, intended_major="Fine Arts",
            budget=80000, state="NY",
            weather_pref=None, vibe_prefs=["Big-city", "Artsy", "Liberal"],
        ),
        weights={
            "academic_fit": 3, "affordability": 3,
            "location_fit": 5, "weather_fit": 1, "vibe_fit": 10,
        },
    )

    # Profile who wants sports + greek life — should favor SEC/Big 10 publics.
    run(
        "AL / Business / ACT 27 / wants Sporty + Greek",
        StudentProfile(
            gpa=3.6, act=27, intended_major="Business",
            budget=35000, state="AL",
            weather_pref=None, vibe_prefs=["Sporty", "Greek life"],
        ),
        weights={
            "academic_fit": 3, "affordability": 7,
            "location_fit": 4, "weather_fit": 1, "vibe_fit": 10,
        },
    )
