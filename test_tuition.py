"""
Verify: CA home + in-state only + budget=20k
  - UC schools appear with in-state tuition around $13-15k
  - Non-CA schools are excluded entirely (in-state scope restriction)
"""

from collections import Counter

from agents.agent1_matcher import StudentProfile, find_matching_schools

profile = StudentProfile(
    gpa=3.8, sat=1400,
    budget=20_000,
    state="CA",                 # Scorecard query scoped to CA so we get UC
    home_state="CA",
    tuition_preference="in_state",
)

schools = find_matching_schools(profile)
print(f"Agent 1 returned {len(schools)} schools")

by_state = Counter((s.get("state") or "?").upper() for s in schools)
print("\nStates in result:")
for st, n in sorted(by_state.items()):
    print(f"  {st}: {n}")

# Spot-check: UC campuses should be present with real in-state tuition.
uc_campuses = [s for s in schools if "University of California" in (s.get("name") or "")]
print(f"\nUC campuses found: {len(uc_campuses)}")
for s in sorted(uc_campuses, key=lambda x: x.get("name") or "")[:6]:
    ins = s.get("in_state_tuition")
    oos = s.get("out_of_state_tuition")
    print(f"  {s['name'][:42]:42}  in-state={('$'+format(ins,',')) if ins else '—':>10}  "
          f"out-of-state={('$'+format(oos,',')) if oos else '—':>10}")

print("\nSpec checks:")
ok_states = all(st == "CA" or st == "?" for st in by_state)
ok_has_uc = len(uc_campuses) > 0
ok_in_state_range = all(
    s.get("in_state_tuition") is None or 8_000 <= s.get("in_state_tuition") <= 20_000
    for s in uc_campuses
)
print(f"  [{'PASS' if ok_states        else 'FAIL'}] all returned schools are in CA")
print(f"  [{'PASS' if ok_has_uc        else 'FAIL'}] at least one UC campus returned")
print(f"  [{'PASS' if ok_in_state_range else 'FAIL'}] UC in-state tuition in plausible band ($8k-$20k)")
