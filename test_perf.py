"""Stage-by-stage wall-clock timing for the national no-preference pipeline.

Runs the same path render_running uses, with the diversification + selective
enrichment, and prints per-stage seconds. Run twice to compare cold vs warm
(IPEDS + climate caches).
"""

import time
from collections import Counter

from agents.agent1_matcher import StudentProfile, find_matching_schools_national
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards
from agents.ipeds import enrich_schools_with_ipeds
from agents.vibe import enrich_schools_with_vibes
from agents.weather import enrich_schools_with_climate


def _diversify_by_state(scored, top_per_state=3, target_count=100):
    if not scored: return []
    by_state = {}
    for fs in scored:
        state = ((fs.school.get("state") if fs.school else "") or "?").upper()
        by_state.setdefault(state, []).append(fs)
    for st in by_state:
        by_state[st].sort(key=lambda fs: fs.overall, reverse=True)
    tier1, tier1_ids = [], set()
    for st, lst in by_state.items():
        for fs in lst[:top_per_state]:
            tier1.append(fs); tier1_ids.add(fs.school_id)
    if len(tier1) >= target_count:
        tier1.sort(key=lambda fs: fs.overall, reverse=True)
        return tier1[:target_count]
    rest = sorted([fs for fs in scored if fs.school_id not in tier1_ids],
                   key=lambda fs: fs.overall, reverse=True)
    final = (tier1 + rest[:target_count - len(tier1)])
    final.sort(key=lambda fs: fs.overall, reverse=True)
    return final


profile = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major=None, budget=None,
    state=None, home_state="CA",
    tuition_preference=None, student_status="domestic",
)
weights = {"academic_fit": 3, "affordability": 3, "location_fit": 3,
           "weather_fit": 3, "vibe_fit": 3}

print("\n=== Stage-by-stage wall-clock ===")
overall_t0 = time.time()

t0 = time.time()
schools = find_matching_schools_national(profile)
t_agent1 = time.time() - t0
print(f"  Agent 1 fan-out (50 states + elite): {t_agent1:6.2f}s   [{len(schools)} schools]")

t0 = time.time()
enrich_schools_with_vibes(schools)
t_vibes = time.time() - t0
print(f"  Vibe enrichment:                     {t_vibes:6.2f}s")

t0 = time.time()
pre_scored = score_schools(profile, schools, weights=weights)
pre_scored.sort(key=lambda x: x.overall, reverse=True)
diversified = _diversify_by_state(pre_scored)
top_ids = {fs.school_id for fs in diversified}
schools_top = [s for s in schools if s.get("id") in top_ids]
t_prescore = time.time() - t0
print(f"  Pre-score + diversify (885 -> 100):  {t_prescore:6.2f}s")

t0 = time.time()
enrich_schools_with_climate(schools_top)
t_climate = time.time() - t0
print(f"  Climate enrichment (top 100):        {t_climate:6.2f}s")

t0 = time.time()
top_50_ids = {fs.school_id for fs in diversified[:50]}
schools_top_50 = [s for s in schools_top if s.get("id") in top_50_ids]
enrich_schools_with_ipeds(schools_top_50)
t_ipeds = time.time() - t0
print(f"  IPEDS enrichment (top 50):           {t_ipeds:6.2f}s")

t0 = time.time()
scored = score_schools(profile, schools_top, weights=weights)
scored.sort(key=lambda x: x.overall, reverse=True)
t_score = time.time() - t0
print(f"  Agent 2 scoring (top 100):           {t_score:6.2f}s")

t0 = time.time()
cards = build_profile_cards(scored, profile, weights, top_n=100)
cards.sort(key=lambda c: c.overall_fit, reverse=True)
t_cards = time.time() - t0
print(f"  Agent 3 card building:               {t_cards:6.2f}s")

total = time.time() - overall_t0
print(f"\n  TOTAL wall-clock:                    {total:6.2f}s")
print(f"  Top result: {cards[0].name} ({cards[0].overall_fit:.1f}, {cards[0].classification})")
