"""Verify the GPA-scale normalization and downstream fit-score impact.

The user asked specifically for a 4.5/4.5 comparison. The two formulas
spec'd (divide-by-1.25 above 4.0 / multiply-by-0.8) are reciprocals,
so 4.5 normalizes to 3.6 on BOTH scales — the curves only diverge for
GPAs at or below 4.0. We run the user's case AND a 4.0/4.0 case so the
asymmetric behavior is visible.
"""

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import normalize_gpa, score_schools
from agents.vibe import enrich_schools_with_vibes


# ── Unit checks on normalize_gpa ────────────────────────────────────────
print("normalize_gpa unit checks:")
cases = [
    (4.5, 4.0),  # weighted on 4.0 scale → 4.5 / 1.25 = 3.6
    (4.5, 5.0),  # 4.5 on 5.0 scale       → 4.5 * 0.8  = 3.6
    (5.0, 4.0),  # weighted max on 4.0    → 5.0 / 1.25 = 4.0
    (5.0, 5.0),  # max on 5.0             → 5.0 * 0.8  = 4.0
    (4.0, 4.0),  # at 4.0 cap on 4.0      → passthrough = 4.0
    (4.0, 5.0),  # 4.0 on 5.0 scale       → 4.0 * 0.8  = 3.2
    (3.5, 4.0),  # under 4.0 on 4.0       → passthrough = 3.5
    (3.5, 5.0),  # 3.5 on 5.0 scale       → 3.5 * 0.8  = 2.8
    (None, 4.0),
]
for gpa, scale in cases:
    print(f"  normalize_gpa({gpa!r:>5}, {scale}) = {normalize_gpa(gpa, scale)}")

# ── User-requested case: 4.5 on each scale ──────────────────────────────
print("\nUser-requested case: GPA 4.5 on both scales")
n_4 = normalize_gpa(4.5, 4.0)
n_5 = normalize_gpa(4.5, 5.0)
print(f"  4.5 on 4.0 scale -> normalized {n_4}")
print(f"  4.5 on 5.0 scale -> normalized {n_5}")
print(
    f"  difference: {abs(n_4 - n_5):.4f}  "
    f"(per spec, both formulas are reciprocals so 4.5 lands at 3.6 either way)"
)

# ── Asymmetric case: 4.0 on each scale ─────────────────────────────────-
print("\nAsymmetric case: GPA 4.0 on both scales")
n_4_at = normalize_gpa(4.0, 4.0)
n_5_at = normalize_gpa(4.0, 5.0)
print(f"  4.0 on 4.0 scale -> normalized {n_4_at}")
print(f"  4.0 on 5.0 scale -> normalized {n_5_at}")
assert n_4_at != n_5_at, "Expected divergence at GPA 4.0 across scales"
print(f"  difference: {abs(n_4_at - n_5_at):.4f}  (clearly different)")

# ── End-to-end: do the same raw 4.0 GPA produce different fit scores? ──
print("\nEnd-to-end fit-score check on 'University of Arizona' (104179):")
base_kwargs = dict(
    sat=1300, act=None,
    intended_major=None, budget=None,
    state="AZ", home_state="AZ",
    tuition_preference=None, student_status="domestic",
)
profile_4 = StudentProfile(gpa=4.0, gpa_scale=4.0, **base_kwargs)
profile_5 = StudentProfile(gpa=4.0, gpa_scale=5.0, **base_kwargs)
weights = {"academic_fit": 5, "affordability": 1, "location_fit": 1,
           "weather_fit": 1, "vibe_fit": 1}

schools = find_matching_schools(profile_4)
enrich_schools_with_vibes(schools)
ua = next((s for s in schools if s.get("id") == 104179), None)
if ua is None:
    print("  University of Arizona not in pool — using first school as fallback.")
    ua = schools[0]

fs_4 = score_schools(profile_4, [ua], weights=weights)[0]
fs_5 = score_schools(profile_5, [ua], weights=weights)[0]
print(f"  school: {ua['name']}  (admit {ua.get('admission_rate')})")
print(f"  GPA 4.0 / 4.0 scale: academic_fit={fs_4.categories['academic_fit']}  "
      f"overall={fs_4.overall}  class={fs_4.classification}")
print(f"  GPA 4.0 / 5.0 scale: academic_fit={fs_5.categories['academic_fit']}  "
      f"overall={fs_5.overall}  class={fs_5.classification}")

assert fs_4.categories["academic_fit"] != fs_5.categories["academic_fit"], (
    "academic_fit should differ when raw GPA 4.0 is interpreted on different scales"
)
assert fs_4.overall != fs_5.overall, "overall fit should differ across scales"
print("\n[OK] normalize_gpa drives different academic fit scores across scales.")

# ── Also re-run the user's exact requested case at the score level ─────-
print("\nUser-requested 4.5 / 4.5 case at the score level (same school):")
profile_45_4 = StudentProfile(gpa=4.5, gpa_scale=4.0, **base_kwargs)
profile_45_5 = StudentProfile(gpa=4.5, gpa_scale=5.0, **base_kwargs)
fs_45_4 = score_schools(profile_45_4, [ua], weights=weights)[0]
fs_45_5 = score_schools(profile_45_5, [ua], weights=weights)[0]
print(f"  GPA 4.5 / 4.0 scale: academic_fit={fs_45_4.categories['academic_fit']}  "
      f"overall={fs_45_4.overall}")
print(f"  GPA 4.5 / 5.0 scale: academic_fit={fs_45_5.categories['academic_fit']}  "
      f"overall={fs_45_5.overall}")
print(
    "  (These are equal by design — the spec'd formulas are reciprocals "
    "above 4.0; a follow-up could ask for an asymmetric formula if the "
    "intent was for 4.5/4.5 to differ.)"
)
