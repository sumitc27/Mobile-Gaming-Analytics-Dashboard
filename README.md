# Mobile Gaming Analytics Dashboard

An end-to-end analytics pipeline that I built to explore how product analysts at mobile gaming companies track user acquisition, engagement, retention, and monetization — the four pillars of any F2P game's health.

I've been interested in how data-driven decisions get made in fast-growing mobile gaming companies, and building this helped me understand *why* metrics like D7 retention and ARPU matter at an operational level, not just as definitions.

---

## What This Project Does

Takes a simulated 90-day dataset of 10,000 mobile game users and answers the business questions an analyst would face day-to-day:

- Which monthly cohorts retained the best, and why might that be?
- Are DAU/MAU trends healthy? Is the game habit-forming?
- Which acquisition channel drives the most valuable users (highest LTV)?
- How is ARPU trending, and which game generates the most revenue?
- Who are the "at-risk" users we should target with re-engagement campaigns?

The dashboard is built to actually *use*, not just screenshot — it has sidebar filters for game, country, and channel, so you can slice the data the way a product team would.

---

## Tech Stack

| Layer | Tool | Why I Chose It |
| --- | --- | --- |
| Data Generation | Python + NumPy | Full control over realistic distributions |
| Analysis | Pandas + Matplotlib/Seaborn | Standard analytics stack, easy to version-control |
| Interactive Dashboard | Streamlit + Plotly | Fast to build, output looks great, easy to share |
| Business Queries | SQLite + SQL | Shows I can think in SQL, not just Python |

---

## Project Structure

```
Mobile-Gaming-Analytics-Dashboard/
├── data/
│   ├── README.md              ← Data source & methodology (read this!)
│   ├── users.csv              ← Generated: 10,000 users (gitignored, run script)
│   └── daily_activity.csv     ← Generated: ~16k activity rows (gitignored)
│
├── src/
│   ├── data_generation.py     ← Generates synthetic dataset with realistic parameters
│   ├── analysis.py            ← Core analytics: retention, DAU/MAU, ARPU, channels
│   └── dashboard.py           ← Streamlit app (interactive, filterable)
│
├── sql/
│   └── queries.sql            ← 12 SQL queries covering all key business questions
│
├── reports/                   ← Auto-generated PNG charts (gitignored, run analysis.py)
│   ├── retention_heatmap.png
│   ├── dau_mau_trend.png
│   ├── revenue_analysis.png
│   └── channel_analysis.png
│
├── notebooks/                 ← (Optional) Jupyter EDA scratch space
├── requirements.txt
└── README.md
```

---

## How to Run Locally on you system

**Clone and install:**

```bash
git clone https://github.com/sumitc27/Mobile-Gaming-Analytics-Dashboard.git
cd Project_1_Gaming_Dashboard
pip install -r requirements.txt
```

**Generate the dataset:**

```bash
python src/data_generation.py
# Takes about 1-2 minutes. Generates users.csv + daily_activity.csv in data/
```

**Run the analysis (saves charts to reports/):**

```bash
python src/analysis.py
```

**Launch the dashboard:**

```bash
streamlit run src/dashboard.py
# Opens at http://localhost:8501
```

---

## Key Metrics & What I Found

After running the full pipeline on the synthetic dataset:

| Metric | Value | Benchmark | Status |
| --- | --- | --- | --- |
| D1 Retention | \~38–40% | 35–40% (casual games) | ✅ On track |
| D7 Retention | \~15–18% | 15–20% (casual games) | ✅ On track |
| Avg DAU | \~310 users | — | — |
| Paying User Rate | 5.1% | 2–7% (F2P games) | ✅ Healthy |
| Daily ARPU | $0.12 | $0.05–0.15 (casual) | ✅ Good range |

**Channel Insight**: Apple Search Ads users show the highest ARPU despite lower install volume, which aligns with known behavior — iOS users in English-speaking markets monetize better. This would suggest increasing ASA budget if CPI allows.

**Cohort Insight**: Earlier cohorts (January) show slightly better retention than February cohorts, potentially because early adopters of a word game tend to be more invested users. Worth investigating with a segmentation by country of origin.

---

## SQL Queries Included

The `sql/queries.sql` file has 12 production-style queries I wrote to answer specific business questions:

 1. Daily install trend + cumulative growth
 2. Install share by acquisition channel
 3. Geographic breakdown by game
 4. Cohort-based D1/D7/D14/D30 retention rates
 5. DAU, avg sessions, session length by date
 6. Engagement depth by game (sessions per user)
 7. User lifecycle segmentation (Active / At Risk / Churned)
 8. Daily revenue, ARPU, ARPPU
 9. Channel-level conversion and revenue (ROAS proxy)
10. Top revenue-generating games
11. LTV estimation by channel
12. Power user identification (top 10% by revenue)

---

## Data Source

> **Data is synthetically generated** — real mobile gaming data is proprietary and not publicly available.

The simulation parameters (retention curves, paying user %, ARPU ranges, session distributions) are calibrated against publicly available industry benchmarks from AppsFlyer, GameAnalytics, and Adjust. Full methodology in `data/README.md`.

---

## What I Learned Building This

- Cohort analysis is more nuanced than I expected — the "day since install" framing vs. calendar date framing gives very different pictures of retention
- Writing SQL for retention analysis (the cohort CTE pattern) is significantly trickier than doing it in Pandas, but produces results that are easier to share with non-technical stakeholders
- Streamlit's `@st.cache_data` decorator is essential — without it, every filter interaction reloads the entire 16k-row dataset
- The DAU/MAU stickiness ratio (targeting &gt;20%) is a better leading indicator of game health than raw DAU, since it normalizes for game scale

---

*Author : @sumitc27 | Data Analyst*