# 🎓 College Fit Finder

A multi-agent AI platform that helps high school students find colleges that genuinely fit them. Enter your academic profile, preferences, and priorities — our intelligent agent pipeline analyzes 800+ schools nationally and delivers a personalized ranked dashboard in under 30 seconds.

---

## 🌐 Live Demo

[Launch College Fit Finder](https://college-fit-finder.streamlit.app)

---

## ✨ Features

- **Personalized fit scores** — 5-category weighted scoring based on your academic profile, budget, location, climate, and campus vibe
- **National school pool** — 800+ schools fetched via 50-state parallel API queries
- **Reach / Match / Safety classification** — based on real admissions data compared to your GPA and SAT/ACT
- **Interactive map** — color-coded pins for all matched schools, clickable for details
- **Full school profiles** — detailed breakdown with strengths, weaknesses, and real data from 3 APIs
- **My List** — save schools and compare them side by side
- **Elite school injection** — Harvard, MIT, Stanford, and 50 other top schools always included
- **GPA scale support** — both 4.0 and 5.0 scales with weighted GPA support

---

## 🤖 Agent Pipeline

| Agent | Role | Output |
|-------|------|--------|
| **Agent 1 — School Matcher** | Queries College Scorecard API across all 50 states in parallel, filters by region/state/budget/major | Pool of 800+ matching schools |
| **Agent 2 — Fit Scorer** | Scores every school across 5 weighted categories, classifies Reach/Match/Safety | Top 100 schools sorted by fit score |
| **Agent 3 — Card Builder** | Builds rich profile cards with personalized strengths, weaknesses, and formatted data | ProfileCard objects ready for display |

**Enrichment Pipelines** (run between Agent 1 and Agent 2):
- **Weather** — real measured climate data via Open-Meteo API
- **Vibe** — campus culture scores from a curated 400-school dataset
- **IPEDS** — student-faculty ratio and financial aid data from Urban Institute API

---

## 🗂️ Project Structure
college-fit-finder/
├── app.py                  # Main Streamlit app and orchestrator
├── agents/
│   ├── agent1_matcher.py   # Agent 1 — School Matcher
│   ├── agent2_scorer.py    # Agent 2 — Fit Scorer
│   ├── agent3_profiler.py  # Agent 3 — Profile Card Builder
│   ├── weather.py          # Weather enrichment pipeline
│   ├── vibe.py             # Campus vibe enrichment pipeline
│   └── ipeds.py            # IPEDS financial/faculty enrichment
├── data/
│   └── school_vibes.json   # Curated 400-school vibe dataset
├── .cache/                 # Auto-generated API response cache
├── requirements.txt        # Python dependencies
└── .env                    # API keys (not committed — see setup)

---

## 🚀 Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/kjquinn/college-fit-finder.git
cd college-fit-finder
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get your College Scorecard API key

Go to [collegescorecard.ed.gov/data](https://collegescorecard.ed.gov/data) and click **Get API Key**. It is free and arrives instantly by email.

The other APIs (Open-Meteo and IPEDS) require no key.

### 4. Create your .env file

Create a file called `.env` in the project root:
COLLEGE_SCORECARD_API_KEY=your_key_here

### 5. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ☁️ Deploying to Streamlit Community Cloud

1. Push your code to GitHub (ensure `.env` is in `.gitignore`)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** and select this repository
4. Set the main file path to `app.py`
5. Under **Advanced settings → Secrets**, add:
```toml
COLLEGE_SCORECARD_API_KEY = "your_key_here"
```
6. Click **Deploy**

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.10+ | Core language |
| Streamlit | Web app framework and UI |
| Folium + streamlit-folium | Interactive map |
| College Scorecard API | Academic and financial school data |
| Open-Meteo API | Real measured climate data |
| IPEDS Urban Institute API | Student-faculty ratio and aid data |
| ThreadPoolExecutor | Parallel API queries for speed |
| Claude Code | AI-assisted development |

---

## 📊 Data Sources

- **[College Scorecard](https://collegescorecard.ed.gov)** — US Department of Education — tuition, acceptance rates, SAT ranges, enrollment, graduation rates
- **[Open-Meteo](https://open-meteo.com)** — Free weather API — real measured temperatures and precipitation by coordinates
- **[IPEDS via Urban Institute](https://educationdata.urban.org)** — Student-faculty ratio, average institutional aid, percentage receiving aid
- **Curated Vibe Dataset** — 400-school dataset with party scene, Greek life, athletics, academic intensity, and diversity scores

---

## 👥 Team

| Name | University | Class |
|------|-----------|-------|
| Jonathan Ledesma | University of Arizona | BNAN 420 — Section 001 |
| Kieran Quinn | University of Arizona | BNAN 420 — Section 001 |
| Tolu Adeoti | University of Arizona | BNAN 420 — Section 001 |

---

## 📄 License

Built for BNAN 420 Unit 3 Project B — University of Arizona, 2026.
