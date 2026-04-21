"""Verify the new Reach/Match/Safety rules against the two test profiles."""

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import _classify

# Targets we want to see classified.
TARGETS = {
    # Profile A: GPA 3.5, SAT 1240
    "A": {
        "profile": StudentProfile(gpa=3.5, sat=1240, intended_major=None, budget=None, state=None),
        "expectations": {
            "University of California-Los Angeles": "Reach",
            "California State University-Long Beach": ["Safety", "Match"],
        },
    },
    # Profile B: GPA 3.9, SAT 1550
    "B": {
        "profile": StudentProfile(gpa=3.9, sat=1550, intended_major=None, budget=None, state=None),
        "expectations": {
            "University of California-Los Angeles": ["Match", "Reach"],
            "Harvard University": "Reach",
            "University of Massachusetts-Amherst": "Safety",
        },
    },
}

# Get data for the target schools. UCLA is in CA, Harvard + UMass in MA.
# Fetch a broad pool for each state and pick out the targets.
def fetch_state(state_code: str) -> dict[str, dict]:
    p = StudentProfile(state=state_code)
    schools = find_matching_schools(p, min_results=150, max_fetched=300)
    return {(s.get("name") or ""): s for s in schools}


print("Fetching schools from Scorecard (CA + MA)...")
ca = fetch_state("CA")
ma = fetch_state("MA")
pool = {**ca, **ma}

# Show the data we're classifying against for transparency
print("\nTarget school stats:")
for school_name in {n for group in TARGETS.values() for n in group["expectations"]}:
    s = pool.get(school_name)
    if not s:
        print(f"  [NOT FOUND] {school_name}")
        continue
    admit = s.get("admission_rate")
    sat25 = s.get("sat_25")
    sat75 = s.get("sat_75")
    print(f"  {school_name[:40]:40}  admit={admit}  sat25={sat25}  sat75={sat75}")

# Run the test
print()
for label, cfg in TARGETS.items():
    p = cfg["profile"]
    print(f"=== Profile {label}: GPA {p.gpa}, SAT {p.sat} ===")
    for school_name, expected in cfg["expectations"].items():
        s = pool.get(school_name)
        if not s:
            print(f"  [NOT FOUND] {school_name}")
            continue
        result = _classify(p, s)
        expected_list = expected if isinstance(expected, list) else [expected]
        ok = result in expected_list
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {school_name[:40]:40}  classified: {result:6}  expected: {expected}")
