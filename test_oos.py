"""Confirm out-of-state preference uses the national fan-out (Bug 2)."""

from collections import Counter

from agents.agent1_matcher import (
    StudentProfile, find_matching_schools, find_matching_schools_national,
)


# Out-of-state preference, no region, no distance — should use national.
profile = StudentProfile(
    gpa=3.5, sat=1300, act=None,
    intended_major=None, budget=None,
    state=None, home_state="CA",
    tuition_preference="out_of_state", student_status="domestic",
)

# Replicate render_running's branch logic
matcher_state = None        # no region, distance=0
is_national_search = (
    matcher_state is None
    and profile.tuition_preference != "in_state"
)
print(f"is_national_search: {is_national_search}")

if is_national_search:
    schools = find_matching_schools_national(profile)
else:
    schools = find_matching_schools(profile)

# State-scope post-filter (Agent 1 already applies _passes_state_scope).
states = Counter((s.get("state") or "?").upper() for s in schools)
print(f"\nTotal: {len(schools)} schools across {len(states)} distinct states")
print(f"Home state CA in pool: {'CA' in states} (expected False — out-of-state pref excludes home)")
print(f"Top 10 states: {dict(states.most_common(10))}")

print(f"\nSAT={profile.sat} (expected 1300) — confirmed in profile dataclass")
