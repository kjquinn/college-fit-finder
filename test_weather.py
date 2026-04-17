"""Live test: real climate data from Open-Meteo feeding Agents 2 and 3."""

import time

from agents.agent1_matcher import StudentProfile, find_matching_schools
from agents.agent2_scorer import score_schools
from agents.agent3_profiler import build_profile_cards
from agents.weather import enrich_schools_with_climate

profile = StudentProfile(
    gpa=3.8, sat=1400, intended_major="Computer Science",
    budget=85000, state=None,
    weather_pref="Cold", vibe_prefs=["Academic / nerdy"],
)

# Limit pool by only scoring the first 20 so the live API calls stay snappy.
t0 = time.time()
schools = find_matching_schools(profile, min_results=20, max_fetched=100)
t1 = time.time()
print(f"Agent 1: {len(schools)} schools in {t1-t0:.1f}s")

schools_subset = schools[:20]
t2 = time.time()
schools_subset = enrich_schools_with_climate(schools_subset)
t3 = time.time()
print(f"Weather enrichment: {t3-t2:.1f}s for {len(schools_subset)} schools")

enriched = [s for s in schools_subset if s.get("climate_label")]
print(f"Schools with climate data: {len(enriched)}/{len(schools_subset)}")

print("\nSample schools:")
for s in schools_subset[:6]:
    w = s.get("winter_temp_f")
    sm = s.get("summer_temp_f")
    p = s.get("annual_precip_in")
    lab = s.get("climate_label", "?")
    name = (s.get("name") or "")[:45]
    if w is not None:
        print(f"  {name:45}  {s.get('state')}  "
              f"winter={w:.0f}F  summer={sm:.0f}F  "
              f"precip={p:.0f}in  label={lab}")
    else:
        print(f"  {name:45}  {s.get('state')}  NO DATA (lat={s.get('lat')}, lon={s.get('lon')})")

scored = score_schools(profile, schools_subset, weights={
    "academic_fit": 8, "affordability": 5,
    "location_fit": 3, "weather_fit": 8, "vibe_fit": 4,
})
cards = build_profile_cards(scored, profile, {
    "academic_fit": 8, "affordability": 5,
    "location_fit": 3, "weather_fit": 8, "vibe_fit": 4,
}, top_n=5)

print("\nTop 5 cards (weather-weighted):")
for c in cards:
    print(f"\n  [{c.classification}] {c.name}  overall={c.overall_fit:.0f}")
    print(f"    climate={c.climate}  winter={c.winter_temp_f}F  summer={c.summer_temp_f}F  precip={c.annual_precip_in}in ({c.precip_level})")
    print(f"    weather_fit score: {c.category_scores['weather_fit']:.0f}")
    print(f"    summary: {c.climate_summary}")
