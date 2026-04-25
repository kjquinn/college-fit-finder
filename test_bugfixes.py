"""End-to-end verification for the three profiles after the bug-fix sweep."""

from collections import Counter

from agents.agent1_matcher import StudentProfile, find_matching_schools


def run(label: str, matcher_profile: StudentProfile) -> None:
    print(f"\n{'='*72}\n{label}\n{'='*72}")
    schools = find_matching_schools(matcher_profile)
    by_state = Counter((s.get("state") or "?").upper() for s in schools)
    print(f"Total schools: {len(schools)}")
    print(f"Distinct states: {len(by_state)}")
    print("Top 10 states by count:")
    for state, n in sorted(by_state.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {state}: {n}")


# Profile A — minimal inputs. Mirrors render_running's matcher_profile path:
#   regions=["No preference"]    → allowed_states=None
#   max_distance=0               → matcher_state=None  (no state filter)
#   major=Undecided              → intended_major=None
#   budget=0                     → budget=None
#   tuition_pref=no_preference   → tuition_preference=None
profile_a = StudentProfile(
    gpa=3.0,
    sat=None, act=None,
    intended_major=None,
    budget=None,
    state=None,                       # ← no state filter at API level
    home_state="CA",
    tuition_preference=None,
    student_status="domestic",
)
run("Profile A — GPA 3.0, no scores, Undecided, CA home, no preferences",
    profile_a)


# Profile B — region Northeast, $60k budget, CS major
NE_STATES = ["ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"]
profile_b = StudentProfile(
    gpa=3.8, sat=1400, act=None,
    intended_major="Computer Science",
    budget=60000,
    state=",".join(NE_STATES),         # ← region-derived multi-state filter
    home_state="TX",
    tuition_preference=None,
    student_status="domestic",
)
run("Profile B — GPA 3.8, SAT 1400, CS, TX home, Northeast region, $60k",
    profile_b)


# Profile C — in-state only AZ, $30k budget, Business
profile_c = StudentProfile(
    gpa=3.5, sat=1200, act=None,
    intended_major="Business",
    budget=30000,
    state=None,                        # ← no API-level state filter
    home_state="AZ",                   # ← but state-scope filter restricts to AZ
    tuition_preference="in_state",     # ← because of this preference
    student_status="domestic",
)
run("Profile C — GPA 3.5, SAT 1200, Business, AZ home, in-state only, $30k",
    profile_c)
