"""
International student pipeline verification.

Profile: home CA, student_status=international, tuition_preference shouldn't
matter, budget=$80k.

Assertions:
  1. Agent 1 returns schools from multiple states (no in-state scope)
  2. Every school's "relevant tuition" is its out-of-state rate
  3. At least one school has international_pct > 0.10
  4. Every card with international_pct > 10% carries "international friendly"
"""

from agents.agent1_matcher import StudentProfile, _relevant_tuition, find_matching_schools
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards
from agents.vibe import enrich_schools_with_vibes

profile = StudentProfile(
    gpa=3.8, sat=1400,
    budget=80_000,
    state=None,               # no state filter on query → mix of states
    home_state="CA",
    tuition_preference=None,  # international students don't set this
    student_status="international",
)

schools = find_matching_schools(profile)
print(f"Agent 1 returned {len(schools)} schools")

# 1 — mix of states
states = sorted({(s.get("state") or "?").upper() for s in schools})
print(f"States in pool: {states[:10]}{'...' if len(states)>10 else ''} (total {len(states)})")
mix_ok = len(states) > 1

# 2 — tuition picked is the OOS rate for every school
def _is_oos(s):
    picked = _relevant_tuition(s, profile)
    oos = s.get("out_of_state_tuition")
    in_st = s.get("in_state_tuition")
    # If both exist and they differ, we want the OOS one.
    if oos is not None:
        return picked == oos
    # Fallback when OOS is unpublished — _relevant_tuition returns in_state as a fallback.
    return picked == in_st

tuition_ok = all(_is_oos(s) for s in schools)

# 3 — some schools have >10% international
intl_schools = [s for s in schools if (s.get("international_pct") or 0) > 0.10]
intl_any = len(intl_schools) > 0

# 4 — cards with high intl % carry the tag
schools = enrich_schools_with_vibes(schools)
scored = score_schools(profile, schools, weights={"academic_fit": 3, "affordability": 3,
                                                  "location_fit": 3, "weather_fit": 3, "vibe_fit": 3})
cards = build_profile_cards(scored, profile, {"academic_fit": 3, "affordability": 3,
                                               "location_fit": 3, "weather_fit": 3, "vibe_fit": 3}, top_n=100)
high_intl_cards = [c for c in cards if (c.international_pct or 0) > 0.10]
tagged_correctly = all("international friendly" in c.vibe_tags for c in high_intl_cards)

print(f"\nHigh-international cards: {len(high_intl_cards)} (of {len(cards)})")
print("Sample (>10% international with the auto-tag):")
for c in sorted(high_intl_cards, key=lambda c: -(c.international_pct or 0))[:5]:
    pct = c.international_pct * 100
    tags = [t for t in c.vibe_tags if t == "international friendly"]
    print(f"  {c.name[:40]:40}  intl={pct:5.1f}%  tag_present={bool(tags)}")

print("\nSpec checks:")
print(f"  [{'PASS' if mix_ok           else 'FAIL'}] schools span multiple states (no in-state restriction)")
print(f"  [{'PASS' if tuition_ok       else 'FAIL'}] every relevant-tuition = school's OOS rate")
print(f"  [{'PASS' if intl_any         else 'FAIL'}] at least one school >10% international")
print(f"  [{'PASS' if tagged_correctly else 'FAIL'}] all >10% cards carry 'international friendly' tag")
