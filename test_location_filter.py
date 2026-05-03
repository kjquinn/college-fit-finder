"""Confirm By State and By Region filters narrow the Scorecard pool correctly.

Test 1: filter_state="AZ" — every returned school must be in Arizona.
Test 2: state="<Northeast comma-list>" — every returned school must be in
        one of the Northeast states.
"""

from collections import Counter

from agents.agent1_matcher import StudentProfile, find_matching_schools


# Region -> state set (mirror of REGION_TO_STATES["Northeast"] in app.py).
NORTHEAST = {"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"}


# ── Test 1: By State / Arizona ─────────────────────────────────────────-
print("\n=== Test 1: filter_state='AZ' ===")
profile_az = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major=None, budget=None,
    state=None,                # would normally hold the matcher state
    home_state="CA",
    filter_state="AZ",         # this should override and force AZ
    tuition_preference=None, student_status="domestic",
)
schools_az = find_matching_schools(profile_az, min_results=50, max_fetched=150)
states_az = Counter((s.get("state") or "?").upper() for s in schools_az)
print(f"  pool size: {len(schools_az)}")
print(f"  state distribution: {dict(states_az)}")
non_az = [s for s in schools_az if (s.get("state") or "").upper() != "AZ"]
assert not non_az, f"Expected only AZ schools, got {len(non_az)} non-AZ"
print(f"  [OK] all {len(schools_az)} schools are in Arizona")


# ── Test 2: By Region / Northeast ──────────────────────────────────────-
print("\n=== Test 2: state='<Northeast comma-list>' (no filter_state) ===")
ne_csv = ",".join(sorted(NORTHEAST))
profile_ne = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major=None, budget=None,
    state=ne_csv,              # region-derived list
    home_state="CA",
    filter_state=None,         # not in By State mode
    tuition_preference=None, student_status="domestic",
)
schools_ne = find_matching_schools(profile_ne, min_results=100, max_fetched=200)
states_ne = Counter((s.get("state") or "?").upper() for s in schools_ne)
print(f"  pool size: {len(schools_ne)}")
print(f"  state distribution: {dict(states_ne)}")
out_of_region = [
    s for s in schools_ne if (s.get("state") or "").upper() not in NORTHEAST
]
assert not out_of_region, (
    f"Expected only Northeast schools, got {len(out_of_region)} from other states"
)
print(f"  [OK] all {len(schools_ne)} schools are in the Northeast region")


# ── Test 3: filter_state takes precedence over `state` ─────────────────-
# Defensive — if someone constructs a profile with both fields set,
# _build_params should prefer filter_state. Confirm with NY (Northeast)
# vs filter_state="AZ" (out of region) — result must be only AZ schools.
print("\n=== Test 3: filter_state='AZ' overrides state='NY' ===")
profile_both = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major=None, budget=None,
    state="NY", filter_state="AZ",
    home_state="CA",
    tuition_preference=None, student_status="domestic",
)
schools_both = find_matching_schools(profile_both, min_results=20, max_fetched=80)
states_both = Counter((s.get("state") or "?").upper() for s in schools_both)
print(f"  state distribution: {dict(states_both)}")
non_az = [s for s in schools_both if (s.get("state") or "").upper() != "AZ"]
assert not non_az, f"filter_state should override state; got {len(non_az)} non-AZ"
print(f"  [OK] filter_state overrode the region; all {len(schools_both)} are AZ")
