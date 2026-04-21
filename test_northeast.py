"""Verify the Northeast pipeline completes in <30s and returns >=50 schools."""

import time
from collections import Counter

from agents.agent1_matcher import StudentProfile, find_matching_schools

NE_STATES = ["CT", "MA", "ME", "NH", "NJ", "NY", "PA", "RI", "VT"]
matcher_state = ",".join(NE_STATES)

profile = StudentProfile(gpa=3.7, sat=1300, state=matcher_state, budget=80000)

t0 = time.time()
schools = find_matching_schools(profile)
elapsed = time.time() - t0

print(f"\nAgent 1 returned {len(schools)} schools in {elapsed:.1f}s")
by = Counter((s.get("state") or "?").upper() for s in schools)
print("\nDistribution by state:")
for st, n in sorted(by.items()):
    print(f"  {st}: {n}")

# Spec checks
print("\nSpec checks:")
ok_count  = len(schools) >= 50
ok_time   = elapsed < 30.0
non_ne    = sorted({s.get("state") for s in schools if (s.get("state") or "").upper() not in NE_STATES})
ok_no_leak = not non_ne
print(f"  [{'PASS' if ok_count   else 'FAIL'}] >=50 schools ({len(schools)})")
print(f"  [{'PASS' if ok_time    else 'FAIL'}] finished in <30s ({elapsed:.1f}s)")
print(f"  [{'PASS' if ok_no_leak else 'FAIL'}] no non-NE states leaked ({non_ne})")
