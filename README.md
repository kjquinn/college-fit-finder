# College Fit Finder

A multi-agent Streamlit app that helps high school students discover colleges
that match their academic profile, budget, location, weather, and campus-vibe
preferences. Pulls real data from the U.S. Department of Education's College
Scorecard and Open-Meteo, blends it with a curated vibe dataset, and produces
ranked, explainable profile cards with Reach/Match/Safety classifications.

## How it works

A three-agent pipeline with two enrichment passes in between.

```
  StudentProfile (GPA, test score, major, budget, state, weather, vibes, weights)
        |
        v
  [Agent 1: Matcher]  ---> Scorecard API (paginated, up to 500 results)
        |                  filters by state + major + budget
        v
  [Vibe Enrichment]   ---> data/school_vibes.json  (unit_id match)
        |
        v
  [Weather Enrichment] --> Open-Meteo Archive API (cached to .cache/weather.json)
        |
        v
  [Agent 2: Fit Scorer] -> scores 5 categories, user-weighted overall,
        |                  classifies Reach / Match / Safety
        v
  [Agent 3: Profiler]  -> top-15 rich cards with descriptions,
        |                  stats grid, strengths & weaknesses
        v
  Streamlit dashboard
```

**Categories Agent 2 scores (0-100 each, then weighted):**
- Academic Fit — SAT/GPA vs. school selectivity
- Affordability — cost of attendance vs. user budget
- Location — same state > same region > elsewhere
- Weather — measured climate vs. user preference
- Vibe — multi-dimensional match using the vibe dataset

## Setup

```bash
git clone https://github.com/kjquinn/college-fit-finder.git
cd college-fit-finder
python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash
# or: .venv\Scripts\activate           # PowerShell
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
COLLEGE_SCORECARD_API_KEY=your_key_here
```

Get a free Scorecard key at https://api.data.gov/signup/.
Open-Meteo requires no key.

## Running

```bash
streamlit run app.py
```

Opens at http://localhost:8501.

## Project structure

```
college-fit-finder/
├── app.py                       Streamlit UI
├── agents/
│   ├── agent1_matcher.py        Scorecard query + pagination
│   ├── agent2_scorer.py         5-category scoring + classification
│   ├── agent3_profiler.py       ProfileCard dataclass + builder
│   ├── vibe.py                  Vibe dataset loader + scoring
│   └── weather.py               Open-Meteo enrichment + disk cache
├── data/
│   └── school_vibes.json        ~400 schools' vibe profiles
├── scripts/
│   └── generate_vibes.py        Regenerates the vibe dataset
├── test_agent1.py .. test_vibes.py   Live smoke tests
└── requirements.txt
```

## Data sources

| Source | What it provides | Why it was chosen |
|--------|------------------|-------------------|
| [College Scorecard](https://collegescorecard.ed.gov/data/documentation/) | School names, IDs, location, admission rate, SAT/ACT percentiles, costs, programs | Authoritative federal dataset, free, well-documented |
| [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api) | ERA5 historical daily weather | Free, no API key, global coverage |
| `data/school_vibes.json` | Party scene, academic intensity, Greek life, politics, athletics, diversity, tags | Built in-repo; 62 schools hand-curated from reputation priors, 338 heuristically scored |

## Known limitations

Things worth knowing, in the spirit of not overselling:

- **GPA ranges are estimated.** Scorecard doesn't publish admitted-student GPA averages. Profile cards show an admission-rate-derived estimate with a visible note explaining the inference.
- **Vibe data is only best-effort.** 338 of the 400 vibe entries come from heuristics (size, ownership, state, admission rate) — those are directionally reasonable but not Princeton-Review accurate. Expand the `CURATED` dict in `scripts/generate_vibes.py` and rerun the generator to improve them.
- **Schools outside the top-400 vibe set** fall back to neutral scores on vibe preferences that need the dataset (Sporty, Greek, Artsy, etc.).
- **Climate is from 2023 alone.** Aggregating multiple years would be more robust but slower. Extreme weather years could skew results.
- **Major matching is substring-based.** "Fine Arts" won't match "Visual and Performing Arts" in Scorecard's CIP titles — phrasing matters.

## Tech stack

- **Python 3.13** + Streamlit
- **`requests`** for API calls (with `ThreadPoolExecutor` for concurrent weather pulls)
- **`python-dotenv`** for local secrets
- Dataclasses everywhere for typed structured data between agents
- On-disk JSON cache for weather, keyed by rounded coordinates

## License

No license declared yet — treat as all-rights-reserved until one is added.
