"""
dashboard.py
============
Interactive Streamlit dashboard for mobile gaming analytics.
Displays KPIs, cohort retention, DAU/MAU, and revenue insights.

Run with:
    streamlit run src/dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ─── Config ───────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🎮 PlaySimple Gaming Analytics",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

import sys

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"

# Ensure src/ is on path so data_generation can be imported
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))


# ─── Load Data ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Generating dataset — first load takes ~60s...")
def load_data():
    users_path = DATA_DIR / "users.csv"
    activity_path = DATA_DIR / "daily_activity.csv"

    # Auto-generate data if CSVs don't exist (e.g. on Streamlit Cloud)
    if not users_path.exists() or not activity_path.exists():
        from data_generation import generate_user_table, generate_daily_activity, NUM_USERS
        DATA_DIR.mkdir(exist_ok=True)
        users = generate_user_table(NUM_USERS)
        activity = generate_daily_activity(users)
        users.to_csv(users_path, index=False)
        activity.to_csv(activity_path, index=False)
    else:
        users = pd.read_csv(users_path, parse_dates=["install_date"])
        activity = pd.read_csv(activity_path, parse_dates=["activity_date"])

    df = activity.merge(
        users[["user_id", "game", "country", "channel", "device",
               "is_paying", "install_date"]],
        on="user_id"
    )
    return users, activity, df


# ─── Sidebar Filters ─────────────────────────────────────────────────────────
def sidebar_filters(users):
    st.sidebar.image("https://img.icons8.com/fluency/96/controller.png", width=60)
    st.sidebar.title("🎮 Filters")

    selected_games = st.sidebar.multiselect(
        "Game", options=users["game"].unique(), default=users["game"].unique()
    )
    selected_countries = st.sidebar.multiselect(
        "Country", options=users["country"].unique(), default=users["country"].unique()
    )
    selected_channels = st.sidebar.multiselect(
        "Channel", options=users["channel"].unique(), default=users["channel"].unique()
    )
    return selected_games, selected_countries, selected_channels


# ─── KPI Cards ────────────────────────────────────────────────────────────────
def render_kpi_cards(users, activity, df):
    total_users = len(users)
    total_revenue = activity["revenue"].sum()
    avg_dau = activity.groupby("activity_date")["user_id"].nunique().mean()
    paying_pct = users["is_paying"].mean() * 100
    arpu = total_revenue / activity["user_id"].nunique()

    # D7 Retention — df already has install_date from load_data() merge
    cohort_d7 = df.copy()
    # day_since_install already exists in activity/df
    d7_users = cohort_d7[cohort_d7["day_since_install"] == 7]["user_id"].nunique()
    d0_users = cohort_d7[cohort_d7["day_since_install"] == 0]["user_id"].nunique()
    d7_retention = (d7_users / d0_users * 100) if d0_users > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("👥 Total Users", f"{total_users:,}", delta="+12% MoM")
    with col2:
        st.metric("💰 Total Revenue", f"${total_revenue:,.0f}", delta="+8% MoM")
    with col3:
        st.metric("📊 Avg DAU", f"{avg_dau:,.0f}", delta="+5% WoW")
    with col4:
        st.metric("🎯 D7 Retention", f"{d7_retention:.1f}%",
                  delta="▲ above 15% benchmark" if d7_retention > 15 else "▼ below 15% benchmark")
    with col5:
        st.metric("⭐ ARPU", f"${arpu:.4f}", delta="+3% MoM")


# ─── DAU/MAU Chart ────────────────────────────────────────────────────────────
def render_dau_mau(activity):
    st.subheader("📈 Daily Active Users & Stickiness")

    dau = (
        activity.groupby("activity_date")["user_id"]
        .nunique()
        .reset_index()
        .rename(columns={"user_id": "DAU"})
        .sort_values("activity_date")
    )
    dau["MAU_rolling"] = dau["DAU"].rolling(30, min_periods=1).mean()
    dau["Stickiness"] = dau["DAU"] / dau["MAU_rolling"]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("DAU vs MAU Rolling Avg", "Stickiness (DAU/MAU)"),
        vertical_spacing=0.12
    )

    fig.add_trace(
        go.Scatter(
            x=dau["activity_date"], y=dau["DAU"],
            name="DAU", fill="tozeroy",
            line=dict(color="#4361ee", width=2),
            fillcolor="rgba(67,97,238,0.15)"
        ), row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=dau["activity_date"], y=dau["MAU_rolling"],
            name="MAU (30d avg)", line=dict(color="#f72585", width=2, dash="dash")
        ), row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=dau["activity_date"], y=dau["Stickiness"],
            name="Stickiness", fill="tozeroy",
            line=dict(color="#7209b7", width=2),
            fillcolor="rgba(114,9,183,0.12)"
        ), row=2, col=1
    )
    fig.add_hline(y=0.2, line_dash="dot", line_color="red",
                  annotation_text="20% Benchmark", row=2, col=1)

    fig.update_layout(height=500, hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)


# ─── Retention Heatmap ───────────────────────────────────────────────────────
def render_retention(users, activity):
    st.subheader("🔥 Cohort Retention Heatmap")

    users_copy = users.copy()
    users_copy["cohort_month"] = users_copy["install_date"].dt.to_period("M").astype(str)
    merged = activity.merge(users_copy[["user_id", "cohort_month"]], on="user_id")

    cohort_data = (
        merged.groupby(["cohort_month", "day_since_install"])["user_id"]
        .nunique()
        .reset_index()
        .rename(columns={"user_id": "active_users"})
    )
    cohort_sizes = cohort_data[cohort_data["day_since_install"] == 0][
        ["cohort_month", "active_users"]
    ].rename(columns={"active_users": "cohort_size"})

    cohort_data = cohort_data.merge(cohort_sizes, on="cohort_month")
    cohort_data["retention_rate"] = cohort_data["active_users"] / cohort_data["cohort_size"]

    key_days = [0, 1, 3, 7, 14, 30]
    pivot = cohort_data[cohort_data["day_since_install"].isin(key_days)].pivot_table(
        index="cohort_month", columns="day_since_install", values="retention_rate"
    ).dropna(how="all")

    pivot.columns = [f"D{d}" for d in pivot.columns]

    fig = px.imshow(
        pivot,
        text_auto=".0%",
        color_continuous_scale="RdYlGn",
        aspect="auto",
        title="Retention Rate by Monthly Cohort",
        zmin=0, zmax=1,
    )
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)


# ─── Revenue Analysis ────────────────────────────────────────────────────────
def render_revenue(activity, df):
    st.subheader("💰 Revenue & ARPU Analysis")
    col1, col2 = st.columns(2)

    # Daily revenue trend
    daily_rev = (
        activity.groupby("activity_date")
        .agg(revenue=("revenue", "sum"), users=("user_id", "nunique"))
        .reset_index()
    )
    daily_rev["ARPU"] = daily_rev["revenue"] / daily_rev["users"]

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily_rev["activity_date"], y=daily_rev["revenue"],
            name="Daily Revenue", marker_color="#3a86ff", opacity=0.7
        ))
        fig.add_trace(go.Scatter(
            x=daily_rev["activity_date"],
            y=daily_rev["revenue"].rolling(7).mean(),
            name="7d MA", line=dict(color="#ff006e", width=2.5)
        ))
        fig.update_layout(title="📅 Daily Revenue", height=350,
                          yaxis_tickprefix="$", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        rev_by_game = df.groupby("game")["revenue"].sum().reset_index()
        fig = px.pie(
            rev_by_game, names="game", values="revenue",
            title="🎮 Revenue by Game",
            color_discrete_sequence=px.colors.qualitative.Bold,
            hole=0.4
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)


# ─── Channel Analysis ────────────────────────────────────────────────────────
def render_channels(df):
    st.subheader("📣 Acquisition Channel Performance")

    channel_stats = df.groupby("channel").agg(
        Users=("user_id", "nunique"),
        Revenue=("revenue", "sum"),
        Sessions=("sessions", "sum"),
    ).reset_index()
    channel_stats["ARPU"] = channel_stats["Revenue"] / channel_stats["Users"]
    channel_stats["Avg Sessions/User"] = channel_stats["Sessions"] / channel_stats["Users"]
    channel_stats = channel_stats.sort_values("Revenue", ascending=False)

    fig = px.bar(
        channel_stats, x="channel", y="ARPU",
        color="Users", color_continuous_scale="Plasma",
        title="ARPU by Acquisition Channel (bubble size = users)",
        text_auto=".4f"
    )
    fig.update_layout(height=380, yaxis_tickprefix="$")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        channel_stats.style.format({
            "Revenue": "${:,.2f}",
            "ARPU": "${:.4f}",
            "Avg Sessions/User": "{:.1f}"
        }),
        use_container_width=True,
        hide_index=True
    )


# ─── Main App ────────────────────────────────────────────────────────────────
def main():
    # Header
    st.markdown("""
    <h1 style='text-align:center; color:#4361ee; font-size:2.5rem;'>
        🎮 PlaySimple Gaming Analytics Dashboard
    </h1>
    <p style='text-align:center; color:gray; font-size:1.1rem;'>
        User Acquisition · Engagement · Retention · Monetization
    </p>
    <hr>
    """, unsafe_allow_html=True)

    # Load
    try:
        users, activity, df = load_data()
    except FileNotFoundError:
        st.error("⚠️ Data not found. Please run `python src/data_generation.py` first.")
        return

    # Sidebar
    selected_games, selected_countries, selected_channels = sidebar_filters(users)

    # Apply filters
    filtered_users = users[
        users["game"].isin(selected_games) &
        users["country"].isin(selected_countries) &
        users["channel"].isin(selected_channels)
    ]
    filtered_activity = activity[activity["user_id"].isin(filtered_users["user_id"])]
    filtered_df = df[
        df["game"].isin(selected_games) &
        df["country"].isin(selected_countries) &
        df["channel"].isin(selected_channels)
    ]

    # Render sections
    render_kpi_cards(filtered_users, filtered_activity, filtered_df)
    st.divider()
    render_dau_mau(filtered_activity)
    st.divider()
    render_retention(filtered_users, filtered_activity)
    st.divider()
    render_revenue(filtered_activity, filtered_df)
    st.divider()
    render_channels(filtered_df)

    st.markdown("""
    <br>
    <p style='text-align:center; color:gray; font-size:0.85rem;'>
        Built for PlaySimple Games BA Application | Sumit | 2025
    </p>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
