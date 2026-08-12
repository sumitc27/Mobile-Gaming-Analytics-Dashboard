# Data Source & Methodology

## Why Synthetic Data?

Real mobile gaming data — session logs, revenue events, user IDs — is **proprietary and confidential**. No public dataset exists that captures all the metrics I wanted to explore (DAU/MAU, cohort retention, ARPU, LTV, acquisition channel breakdown) together in one clean form for casual word games specifically.

Rather than working with a stripped-down Kaggle dataset that doesn't reflect the actual analytics pipeline at a gaming company, I decided to **generate realistic synthetic data** from scratch. This approach gave me full control over the schema, let me encode realistic gaming behavior (retention decay, paying user distributions, channel-level ARPU differences), and forced me to understand *why* the data looks the way it does — which I think is more valuable than just running queries on someone else's export.

---

## Benchmark Sources

The synthetic data parameters are not made up — they are calibrated against **publicly available mobile gaming industry benchmarks**:

| Metric | Value Used | Industry Benchmark Source |
|---|---|---|
| **D1 Retention** | ~38–42% | AppsFlyer Mobile Benchmarks 2023: Casual games D1 avg = 35–40% |
| **D7 Retention** | ~15–20% | GameAnalytics Mobile Gaming Report 2023: Casual D7 avg = 15–20% |
| **D30 Retention** | ~6–10% | Adjust Mobile App Trends 2023: Casual games D30 avg = 5–8% |
| **Paying User Rate** | ~5% | Industry standard for F2P casual games: 2–7% |
| **ARPU (daily)** | ~$0.03–0.05 | AppsFlyer Performance Index: Casual games ARPU |
| **DAU/MAU (Stickiness)** | ~15–25% | GameAnalytics benchmark: word games avg 18–22% |
| **Session Count/Day** | ~3 sessions | Internal benchmarks published by Sensor Tower / data.ai |

**References:**
- [AppsFlyer Mobile App Benchmarks](https://www.appsflyer.com/resources/reports/mobile-app-engagement-benchmarks/)
- [GameAnalytics Global Mobile Gaming Report 2023](https://gameanalytics.com/blog/mobile-gaming-benchmarks/)
- [Adjust Mobile App Trends 2024](https://www.adjust.com/resources/ebooks/mobile-app-trends-2024/)
- [Sensor Tower State of Mobile Gaming 2023](https://sensortower.com/blog/state-of-mobile-gaming-2023)

---

## Data Generation Logic

The synthetic dataset simulates **10,000 users** across a **90-day window** for a portfolio of 4 casual word games (modeled after games like Daily Themed Crossword, WordTrip, WordJam, TileMatch).

### User Table (`users.csv`)
Each user has:
- `user_id` — unique identifier (e.g., `U000001`)
- `install_date` — randomly distributed across first 45 days of the simulation window
- `game` — assigned by weighted probability (mimics portfolio distribution)
- `country` — weighted: India 35%, USA 30%, UK 15%, CA 10%, AU 10%
- `channel` — weighted: Organic 30%, Facebook 25%, Google UAC 20%, Apple SA 15%, Referral 10%
- `device` — Android 60%, iOS 40% (reflects global market share data)
- `user_quality` — a latent `Beta(2,3)` quality score that controls retention probability
- `is_paying` — 5% of users are designated as paying users

### Activity Table (`daily_activity.csv`)
Each row = one user's activity on one day. Retention follows a **decaying exponential curve**:

```
retention_prob(day) = 0.40 × exp(−0.05 × day) + 0.03
```

This produces realistic D1 ~40%, D7 ~20%, D30 ~8% numbers. The `user_quality` parameter shifts this curve up/down to create heterogeneity. Sessions follow a Poisson distribution (λ ≈ 3.2). Revenue events are sparse — paying users have a 30% daily chance of a purchase; free users never pay (pure F2P model).

---

## Reproducibility

The random seed is fixed (`SEED = 42`) throughout. Running `python src/data_generation.py` will always produce the **exact same dataset**.

```bash
# Regenerate from scratch
python src/data_generation.py
```

Output files:
- `data/users.csv` — 10,000 rows, 9 columns
- `data/daily_activity.csv` — ~16,000+ rows, 6 columns (varies slightly by seed behavior)
