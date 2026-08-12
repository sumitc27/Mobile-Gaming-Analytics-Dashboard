"""
analysis.py
===========
Core analytics engine for mobile gaming metrics.
Computes: Cohort Retention, DAU/MAU, ARPU, LTV, Churn

Run this AFTER data_generation.py has created the CSV files.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving plots
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
REPORTS_DIR = BASE / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

sns.set_theme(style="darkgrid", palette="husl")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["font.family"] = "DejaVu Sans"


# ─── Load Data ────────────────────────────────────────────────────────────────
def load_data():
    users = pd.read_csv(DATA_DIR / "users.csv", parse_dates=["install_date"])
    activity = pd.read_csv(DATA_DIR / "daily_activity.csv", parse_dates=["activity_date"])
    df = activity.merge(users[["user_id", "game", "country", "channel", "device",
                                "is_paying", "install_date"]], on="user_id")
    return users, activity, df


# ─── 1. Cohort Retention Analysis ─────────────────────────────────────────────
def cohort_retention_analysis(users, activity):
    """
    Compute monthly cohort retention rates.
    Returns a pivot table: cohort_month x day_since_install
    """
    users["cohort_month"] = users["install_date"].dt.to_period("M")
    merged = activity.merge(users[["user_id", "cohort_month"]], on="user_id")

    # Count unique active users per cohort per day
    cohort_data = (
        merged.groupby(["cohort_month", "day_since_install"])["user_id"]
        .nunique()
        .reset_index()
        .rename(columns={"user_id": "active_users"})
    )

    # Cohort sizes (Day 0 = install day)
    cohort_sizes = cohort_data[cohort_data["day_since_install"] == 0][
        ["cohort_month", "active_users"]
    ].rename(columns={"active_users": "cohort_size"})

    cohort_data = cohort_data.merge(cohort_sizes, on="cohort_month")
    cohort_data["retention_rate"] = cohort_data["active_users"] / cohort_data["cohort_size"]

    # Pivot for heatmap
    pivot = cohort_data.pivot_table(
        index="cohort_month", columns="day_since_install", values="retention_rate"
    )
    return pivot, cohort_data


def plot_retention_heatmap(pivot):
    fig, ax = plt.subplots(figsize=(14, 6))
    # Only show days 0, 1, 3, 7, 14, 30, 60
    key_days = [d for d in [0, 1, 3, 7, 14, 30, 60] if d in pivot.columns]
    subset = pivot[key_days].dropna(how="all")

    sns.heatmap(
        subset,
        annot=True,
        fmt=".0%",
        cmap="YlOrRd_r",
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": "Retention Rate"},
    )
    ax.set_title("📊 Monthly Cohort Retention Heatmap", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Day Since Install", fontsize=12)
    ax.set_ylabel("Install Cohort (Month)", fontsize=12)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "retention_heatmap.png", bbox_inches="tight")
    plt.close()
    print("  ✅ Saved: retention_heatmap.png")


# ─── 2. DAU / MAU Trend ───────────────────────────────────────────────────────
def compute_dau_mau(activity):
    """Compute daily DAU and rolling 30-day MAU."""
    dau = (
        activity.groupby("activity_date")["user_id"]
        .nunique()
        .reset_index()
        .rename(columns={"user_id": "DAU"})
    )
    dau = dau.sort_values("activity_date")
    dau["MAU"] = dau["DAU"].rolling(30).sum()  # Simplified rolling 30-day active
    dau["Stickiness"] = dau["DAU"] / dau["MAU"]
    return dau


def plot_dau_mau(dau):
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # DAU/MAU plot
    ax1 = axes[0]
    ax1.fill_between(dau["activity_date"], dau["DAU"], alpha=0.3, color="#4361ee")
    ax1.plot(dau["activity_date"], dau["DAU"], color="#4361ee", linewidth=2, label="DAU")
    ax1.plot(dau["activity_date"], dau["MAU"], color="#f72585", linewidth=2,
             linestyle="--", label="MAU (30-day rolling)")
    ax1.set_title("📈 Daily Active Users (DAU) & Monthly Active Users (MAU)", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Users", fontsize=11)
    ax1.legend(fontsize=11)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    # Stickiness plot
    ax2 = axes[1]
    ax2.fill_between(dau["activity_date"], dau["Stickiness"], alpha=0.3, color="#7209b7")
    ax2.plot(dau["activity_date"], dau["Stickiness"], color="#7209b7", linewidth=2)
    ax2.axhline(y=0.20, color="red", linestyle="--", alpha=0.6, label="Industry Benchmark (20%)")
    ax2.set_title("🎯 Stickiness (DAU/MAU) — Measure of Habit Formation", fontsize=14, fontweight="bold")
    ax2.set_ylabel("Stickiness Ratio", fontsize=11)
    ax2.set_xlabel("Date", fontsize=11)
    ax2.legend(fontsize=11)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))

    plt.tight_layout(pad=3.0)
    plt.savefig(REPORTS_DIR / "dau_mau_trend.png", bbox_inches="tight")
    plt.close()
    print("  ✅ Saved: dau_mau_trend.png")


# ─── 3. ARPU & Revenue Analysis ───────────────────────────────────────────────
def compute_arpu(activity, users):
    """Compute ARPU by date and game."""
    daily_revenue = (
        activity.groupby("activity_date")
        .agg(revenue=("revenue", "sum"), active_users=("user_id", "nunique"))
        .reset_index()
    )
    daily_revenue["ARPU"] = daily_revenue["revenue"] / daily_revenue["active_users"]

    # Revenue by game
    df = activity.merge(users[["user_id", "game"]], on="user_id")
    revenue_by_game = df.groupby("game")["revenue"].sum().reset_index()

    return daily_revenue, revenue_by_game


def plot_revenue_analysis(daily_revenue, revenue_by_game):
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # ARPU over time
    ax1 = axes[0]
    ax1.plot(daily_revenue["activity_date"], daily_revenue["ARPU"].rolling(7).mean(),
             color="#3a86ff", linewidth=2.5)
    ax1.fill_between(daily_revenue["activity_date"],
                     daily_revenue["ARPU"].rolling(7).mean(), alpha=0.15, color="#3a86ff")
    ax1.set_title("💰 ARPU Over Time (7-Day Rolling Avg)", fontsize=14, fontweight="bold")
    ax1.set_ylabel("ARPU (USD)", fontsize=11)
    ax1.set_xlabel("Date", fontsize=11)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"${y:.3f}"))

    # Revenue by game
    ax2 = axes[1]
    colors = ["#4cc9f0", "#4361ee", "#7209b7", "#f72585"]
    bars = ax2.bar(revenue_by_game["game"], revenue_by_game["revenue"], color=colors, edgecolor="white")
    ax2.set_title("🎮 Total Revenue by Game", fontsize=14, fontweight="bold")
    ax2.set_ylabel("Total Revenue (USD)", fontsize=11)
    ax2.set_xlabel("Game", fontsize=11)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"${y:,.0f}"))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=20, ha="right")

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2., height * 1.01,
                 f"${height:,.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.tight_layout(pad=3.0)
    plt.savefig(REPORTS_DIR / "revenue_analysis.png", bbox_inches="tight")
    plt.close()
    print("  ✅ Saved: revenue_analysis.png")


# ─── 4. Acquisition Channel Analysis ─────────────────────────────────────────
def plot_channel_analysis(df):
    channel_stats = df.groupby("channel").agg(
        users=("user_id", "nunique"),
        revenue=("revenue", "sum"),
        sessions=("sessions", "sum"),
    ).reset_index()
    channel_stats["ARPU"] = channel_stats["revenue"] / channel_stats["users"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    colors = sns.color_palette("husl", len(channel_stats))

    # Users by channel
    axes[0].pie(channel_stats["users"], labels=channel_stats["channel"],
                autopct="%1.1f%%", startangle=90, colors=colors,
                wedgeprops=dict(edgecolor="white", linewidth=2))
    axes[0].set_title("👥 Users by Acquisition Channel", fontsize=13, fontweight="bold")

    # Revenue by channel
    axes[1].barh(channel_stats["channel"], channel_stats["revenue"], color=colors)
    axes[1].set_title("💵 Revenue by Channel", fontsize=13, fontweight="bold")
    axes[1].xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    axes[1].set_xlabel("Total Revenue (USD)")

    # ARPU by channel
    axes[2].bar(channel_stats["channel"], channel_stats["ARPU"], color=colors)
    axes[2].set_title("⭐ ARPU by Channel", fontsize=13, fontweight="bold")
    axes[2].yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"${y:.3f}"))
    axes[2].set_ylabel("ARPU (USD)")
    plt.setp(axes[2].xaxis.get_majorticklabels(), rotation=30, ha="right")

    plt.tight_layout(pad=2.0)
    plt.savefig(REPORTS_DIR / "channel_analysis.png", bbox_inches="tight")
    plt.close()
    print("  ✅ Saved: channel_analysis.png")


# ─── 5. Summary Statistics ───────────────────────────────────────────────────
def compute_summary(users, activity, cohort_data):
    total_users = len(users)
    total_revenue = activity["revenue"].sum()
    total_dau = activity.groupby("activity_date")["user_id"].nunique().mean()

    # D1, D7, D30 retention (average across all cohorts)
    def avg_retention(day):
        subset = cohort_data[cohort_data["day_since_install"] == day]
        return subset["retention_rate"].mean() if not subset.empty else None

    summary = {
        "Total Users": f"{total_users:,}",
        "Total Revenue (USD)": f"${total_revenue:,.2f}",
        "Avg DAU": f"{total_dau:,.0f}",
        "Paying User Rate": f"{users['is_paying'].mean()*100:.1f}%",
        "D1 Retention": f"{avg_retention(1)*100:.1f}%" if avg_retention(1) else "N/A",
        "D7 Retention": f"{avg_retention(7)*100:.1f}%" if avg_retention(7) else "N/A",
        "D30 Retention": f"{avg_retention(30)*100:.1f}%" if avg_retention(30) else "N/A",
        "Avg ARPU (daily)": f"${total_revenue / activity['user_id'].nunique():.4f}",
    }
    return summary


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[ANALYTICS] Running Mobile Gaming Analytics...")
    print("  -> Loading data...")
    users, activity, df = load_data()

    print("  -> Computing cohort retention...")
    pivot, cohort_data = cohort_retention_analysis(users, activity)
    plot_retention_heatmap(pivot)

    print("  -> Computing DAU/MAU...")
    dau = compute_dau_mau(activity)
    plot_dau_mau(dau)

    print("  -> Computing ARPU & Revenue...")
    daily_revenue, revenue_by_game = compute_arpu(activity, users)
    plot_revenue_analysis(daily_revenue, revenue_by_game)

    print("  -> Analyzing acquisition channels...")
    plot_channel_analysis(df)

    print("  -> Computing summary stats...")
    summary = compute_summary(users, activity, cohort_data)

    print("\n" + "=" * 50)
    print("[METRICS] KEY BUSINESS METRICS SUMMARY")
    print("=" * 50)
    for k, v in summary.items():
        print(f"  {k:<25} {v}")
    print("=" * 50)
    print(f"\n[OK] All plots saved to: {REPORTS_DIR}")
    print("[NEXT] Run dashboard.py next for interactive visualizations!")
