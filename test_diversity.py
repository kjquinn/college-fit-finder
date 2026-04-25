"""Verify geographic diversity in the national no-filter top-100."""

from collections import Counter

from agents.agent1_matcher import StudentProfile, find_matching_schools_national
from agents.agent2_scorer import score_schools

# Inline import of the diversity helper since it lives in app.py.
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "_app", pathlib.Path(__file__).parent / "app.py"
)
# We can't actually run app.py (it calls st.set_page_config etc.), so
# replicate the diversifier inline for the test.

def _diversify_by_state(scored, top_per_state=3, target_count=100):
    if not scored: return []
    by_state = {}
    for fs in scored:
        state = ((fs.school.get("state") if fs.school else "") or "?").upper()
        by_state.setdefault(state, []).append(fs)
    for state in by_state:
        by_state[state].sort(key=lambda fs: fs.overall, reverse=True)
    tier1, tier1_ids = [], set()
    for state, lst in by_state.items():
        for fs in lst[:top_per_state]:
            tier1.append(fs); tier1_ids.add(fs.school_id)
    if len(tier1) >= target_count:
        tier1.sort(key=lambda fs: fs.overall, reverse=True)
        return tier1[:target_count]
    remaining = [fs for fs in scored if fs.school_id not in tier1_ids]
    remaining.sort(key=lambda fs: fs.overall, reverse=True)
    needed = target_count - len(tier1)
    final = tier1 + remaining[:needed]
    final.sort(key=lambda fs: fs.overall, reverse=True)
    return final


# Profile A — no preferences
profile = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major=None, budget=None,
    state=None, home_state="CA",
    tuition_preference=None, student_status="domestic",
)

schools = find_matching_schools_national(profile)
print(f"\nPool: {len(schools)} schools")

weights = {"academic_fit": 3, "affordability": 3, "location_fit": 3,
           "weather_fit": 3, "vibe_fit": 3}
scored = score_schools(profile, schools, weights=weights)

# Before diversity — naive top-100 by fit
naive_top = scored[:100]
naive_states = Counter(((fs.school.get("state") if fs.school else "") or "?").upper()
                        for fs in naive_top)
print(f"\nNaive top-100 (no diversity):")
print(f"  Distinct states: {len(naive_states)}")
print(f"  State counts: {dict(naive_states.most_common(10))}")

# After diversity
diverse = _diversify_by_state(scored, top_per_state=3, target_count=100)
diverse_states = Counter(((fs.school.get("state") if fs.school else "") or "?").upper()
                          for fs in diverse)
print(f"\nGeographically diversified top-100:")
print(f"  Distinct states: {len(diverse_states)}")
print(f"  Schools per state (full breakdown):")
for state, n in sorted(diverse_states.items(), key=lambda kv: -kv[1]):
    print(f"    {state}: {n}")

# Confirm sort order of diverse
fits = [fs.overall for fs in diverse]
print(f"\n  Sorted by fit desc: {fits == sorted(fits, reverse=True)}")
print(f"  Top 5 fits: {[round(f, 1) for f in fits[:5]]}")
print(f"  Bottom 5 fits: {[round(f, 1) for f in fits[-5:]]}")

print(f"\n  Spec check (≥20 distinct states): "
      f"{'PASS' if len(diverse_states) >= 20 else 'FAIL'}")
