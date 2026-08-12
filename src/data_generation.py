"""
data_generation.py
==================
Generates synthetic mobile gaming user data to simulate
a PlaySimple-style casual word game analytics dataset.

Metrics generated:
- User installs across 90 days
- Daily sessions per user
- Revenue events (in-app purchases)
- Churn patterns
- Country/channel segmentation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import os

# ─── Configuration ────────────────────────────────────────────────────────────
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

NUM_USERS = 10_000
SIMULATION_DAYS = 90
START_DATE = datetime(2025, 1, 1)

GAMES = ["Daily Themed Crossword", "WordTrip", "WordJam", "TileMatch"]
COUNTRIES = ["India", "USA", "UK", "Canada", "Australia"]
COUNTRY_WEIGHTS = [0.35, 0.30, 0.15, 0.10, 0.10]
CHANNELS = ["Organic", "Facebook Ads", "Google UAC", "Apple Search Ads", "Referral"]
CHANNEL_WEIGHTS = [0.30, 0.25, 0.20, 0.15, 0.10]
DEVICES = ["Android", "iOS"]
DEVICE_WEIGHTS = [0.60, 0.40]


# ─── Retention Model ──────────────────────────────────────────────────────────
def get_retention_probability(day: int, user_quality: float) -> float:
    """
    Simulates realistic retention decay curve.
    D1 ~40%, D7 ~20%, D30 ~8%, D90 ~3%
    user_quality (0-1) adjusts retention up/down.
    """
    base = 0.40 * np.exp(-0.05 * day) + 0.03
    return min(1.0, base * (0.7 + 0.6 * user_quality))


def simulate_user_sessions(day_active: int, base_sessions: float) -> int:
    """Simulate number of sessions for an active user on a given day."""
    sessions = np.random.poisson(base_sessions)
    return max(1, sessions)


# ─── User Table ───────────────────────────────────────────────────────────────
def generate_user_table(num_users: int) -> pd.DataFrame:
    """Generate the base user install table."""
    install_dates = [
        START_DATE + timedelta(days=np.random.randint(0, SIMULATION_DAYS // 2))
        for _ in range(num_users)
    ]
    users = pd.DataFrame({
        "user_id": [f"U{str(i).zfill(6)}" for i in range(num_users)],
        "install_date": install_dates,
        "game": np.random.choice(GAMES, num_users, p=[0.30, 0.30, 0.25, 0.15]),
        "country": np.random.choice(COUNTRIES, num_users, p=COUNTRY_WEIGHTS),
        "channel": np.random.choice(CHANNELS, num_users, p=CHANNEL_WEIGHTS),
        "device": np.random.choice(DEVICES, num_users, p=DEVICE_WEIGHTS),
        "user_quality": np.random.beta(2, 3, num_users),  # 0-1 quality score
        "base_sessions": np.random.lognormal(mean=0.5, sigma=0.5, size=num_users),
        "is_paying": np.random.choice([True, False], num_users, p=[0.05, 0.95]),
    })
    return users


# ─── Daily Activity Table ─────────────────────────────────────────────────────
def generate_daily_activity(users: pd.DataFrame) -> pd.DataFrame:
    """Generate day-by-day activity for each user."""
    rows = []
    end_date = START_DATE + timedelta(days=SIMULATION_DAYS)

    for _, user in users.iterrows():
        install_date = user["install_date"]
        active = True

        for day_num in range(SIMULATION_DAYS):
            activity_date = install_date + timedelta(days=day_num)
            if activity_date >= end_date:
                break

            # Check if user is retained today
            retention_prob = get_retention_probability(day_num, user["user_quality"])
            if day_num > 0:
                active = np.random.random() < retention_prob
            if not active:
                break

            sessions = simulate_user_sessions(day_num, user["base_sessions"])

            # Revenue: paying users have higher chance
            if user["is_paying"]:
                revenue = np.random.choice(
                    [0, 0.99, 1.99, 4.99, 9.99, 19.99],
                    p=[0.70, 0.10, 0.08, 0.06, 0.04, 0.02]
                )
            else:
                revenue = 0.0  # Free users

            rows.append({
                "user_id": user["user_id"],
                "activity_date": activity_date.date(),
                "day_since_install": day_num,
                "sessions": sessions,
                "revenue": round(revenue, 2),
                "session_length_min": round(np.random.lognormal(2.0, 0.5), 1),
            })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("[GAMING] Generating synthetic mobile gaming dataset...")

    print("  -> Generating user table...")
    users = generate_user_table(NUM_USERS)

    print("  -> Simulating daily activity (this may take 1-2 mins)...")
    activity = generate_daily_activity(users)

    # Save
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)

    users_path = os.path.join(out_dir, "users.csv")
    activity_path = os.path.join(out_dir, "daily_activity.csv")

    users.to_csv(users_path, index=False)
    activity.to_csv(activity_path, index=False)

    print(f"  [OK] Users saved to: {users_path}")
    print(f"  [OK] Activity saved to: {activity_path}")
    print(f"\n[SUMMARY] Dataset Summary:")
    print(f"  Total Users: {len(users):,}")
    print(f"  Total Activity Rows: {len(activity):,}")
    print(f"  Paying Users: {users['is_paying'].sum():,} ({users['is_paying'].mean()*100:.1f}%)")
    print(f"  Total Revenue: ${activity['revenue'].sum():,.2f}")
    print(f"  Date Range: {activity['activity_date'].min()} -> {activity['activity_date'].max()}")
