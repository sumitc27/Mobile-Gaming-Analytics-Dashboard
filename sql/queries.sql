-- ============================================================
-- queries.sql
-- Business Intelligence SQL Queries for Mobile Gaming Analytics
-- Compatible with SQLite
-- ============================================================

-- ─── SETUP: Create tables from CSV (run in Python) ────────────────────────
-- See load_to_sqlite.py for how to load CSV data into SQLite

-- ============================================================
-- SECTION 1: USER ACQUISITION
-- ============================================================

-- Q1: Daily install counts
SELECT
    DATE(install_date) AS install_date,
    COUNT(DISTINCT user_id) AS new_installs,
    SUM(COUNT(DISTINCT user_id)) OVER (ORDER BY DATE(install_date)) AS cumulative_installs
FROM users
GROUP BY DATE(install_date)
ORDER BY install_date;

-- Q2: Installs by acquisition channel
SELECT
    channel,
    COUNT(DISTINCT user_id) AS installs,
    ROUND(COUNT(DISTINCT user_id) * 100.0 / SUM(COUNT(DISTINCT user_id)) OVER (), 1) AS share_pct
FROM users
GROUP BY channel
ORDER BY installs DESC;

-- Q3: Installs by country and game
SELECT
    country,
    game,
    COUNT(DISTINCT user_id) AS installs
FROM users
GROUP BY country, game
ORDER BY country, installs DESC;

-- ============================================================
-- SECTION 2: RETENTION ANALYSIS
-- ============================================================

-- Q4: D1, D7, D30 Retention Rates (Cohort-based)
WITH install_cohort AS (
    SELECT user_id, DATE(install_date) AS cohort_date
    FROM users
),
daily_active AS (
    SELECT user_id, activity_date, day_since_install
    FROM daily_activity
),
cohort_sizes AS (
    SELECT cohort_date, COUNT(DISTINCT user_id) AS cohort_size
    FROM install_cohort
    GROUP BY cohort_date
),
retained AS (
    SELECT
        ic.cohort_date,
        da.day_since_install,
        COUNT(DISTINCT da.user_id) AS retained_users
    FROM install_cohort ic
    JOIN daily_active da ON ic.user_id = da.user_id
    WHERE da.day_since_install IN (0, 1, 7, 14, 30)
    GROUP BY ic.cohort_date, da.day_since_install
)
SELECT
    r.cohort_date,
    cs.cohort_size,
    MAX(CASE WHEN r.day_since_install = 1  THEN ROUND(r.retained_users * 100.0 / cs.cohort_size, 1) END) AS D1_retention_pct,
    MAX(CASE WHEN r.day_since_install = 7  THEN ROUND(r.retained_users * 100.0 / cs.cohort_size, 1) END) AS D7_retention_pct,
    MAX(CASE WHEN r.day_since_install = 14 THEN ROUND(r.retained_users * 100.0 / cs.cohort_size, 1) END) AS D14_retention_pct,
    MAX(CASE WHEN r.day_since_install = 30 THEN ROUND(r.retained_users * 100.0 / cs.cohort_size, 1) END) AS D30_retention_pct
FROM retained r
JOIN cohort_sizes cs ON r.cohort_date = cs.cohort_date
GROUP BY r.cohort_date, cs.cohort_size
ORDER BY r.cohort_date;

-- ============================================================
-- SECTION 3: ENGAGEMENT METRICS
-- ============================================================

-- Q5: Daily Active Users (DAU)
SELECT
    activity_date,
    COUNT(DISTINCT user_id) AS DAU,
    AVG(sessions) AS avg_sessions_per_user,
    AVG(session_length_min) AS avg_session_length_min
FROM daily_activity
GROUP BY activity_date
ORDER BY activity_date;

-- Q6: Average Sessions Per User Per Day (by game)
SELECT
    u.game,
    AVG(da.sessions) AS avg_sessions_per_user,
    AVG(da.session_length_min) AS avg_session_length_min,
    COUNT(DISTINCT da.user_id) AS unique_users
FROM daily_activity da
JOIN users u ON da.user_id = u.user_id
GROUP BY u.game
ORDER BY avg_sessions_per_user DESC;

-- Q7: User Lifecycle Stages
WITH user_last_seen AS (
    SELECT
        user_id,
        MAX(activity_date) AS last_active,
        MIN(activity_date) AS first_active,
        COUNT(DISTINCT activity_date) AS active_days
    FROM daily_activity
    GROUP BY user_id
)
SELECT
    CASE
        WHEN julianday('2025-04-01') - julianday(last_active) <= 1  THEN '🟢 Active Today'
        WHEN julianday('2025-04-01') - julianday(last_active) <= 7  THEN '🟡 Active This Week'
        WHEN julianday('2025-04-01') - julianday(last_active) <= 30 THEN '🟠 At Risk (7-30d)'
        ELSE '🔴 Churned (>30d)'
    END AS lifecycle_stage,
    COUNT(DISTINCT user_id) AS user_count,
    ROUND(COUNT(DISTINCT user_id) * 100.0 / SUM(COUNT(DISTINCT user_id)) OVER (), 1) AS pct
FROM user_last_seen
GROUP BY lifecycle_stage
ORDER BY user_count DESC;

-- ============================================================
-- SECTION 4: MONETIZATION METRICS
-- ============================================================

-- Q8: Daily Revenue and ARPU
SELECT
    da.activity_date,
    SUM(da.revenue) AS daily_revenue,
    COUNT(DISTINCT da.user_id) AS active_users,
    COUNT(DISTINCT CASE WHEN da.revenue > 0 THEN da.user_id END) AS paying_users,
    ROUND(SUM(da.revenue) / COUNT(DISTINCT da.user_id), 4) AS ARPU,
    ROUND(SUM(da.revenue) / NULLIF(COUNT(DISTINCT CASE WHEN da.revenue > 0 THEN da.user_id END), 0), 2) AS ARPPU
FROM daily_activity da
GROUP BY da.activity_date
ORDER BY da.activity_date;

-- Q9: Revenue by Acquisition Channel (ROAS proxy)
SELECT
    u.channel,
    COUNT(DISTINCT da.user_id) AS total_users,
    SUM(da.revenue) AS total_revenue,
    ROUND(SUM(da.revenue) / COUNT(DISTINCT da.user_id), 4) AS ARPU,
    COUNT(DISTINCT CASE WHEN da.revenue > 0 THEN da.user_id END) AS paying_users,
    ROUND(COUNT(DISTINCT CASE WHEN da.revenue > 0 THEN da.user_id END) * 100.0 /
          COUNT(DISTINCT da.user_id), 1) AS conversion_rate_pct
FROM daily_activity da
JOIN users u ON da.user_id = u.user_id
GROUP BY u.channel
ORDER BY ARPU DESC;

-- Q10: Top Revenue-Generating Games
SELECT
    u.game,
    SUM(da.revenue) AS total_revenue,
    COUNT(DISTINCT da.user_id) AS unique_users,
    ROUND(SUM(da.revenue) / COUNT(DISTINCT da.user_id), 4) AS ARPU,
    COUNT(DISTINCT CASE WHEN da.revenue > 0 THEN da.user_id END) AS paying_users
FROM daily_activity da
JOIN users u ON da.user_id = u.user_id
GROUP BY u.game
ORDER BY total_revenue DESC;

-- ============================================================
-- SECTION 5: ADVANCED — LTV ESTIMATION
-- ============================================================

-- Q11: Simplified LTV by Channel (Revenue / Cohort)
WITH user_revenue AS (
    SELECT
        da.user_id,
        SUM(da.revenue) AS lifetime_revenue,
        COUNT(DISTINCT da.activity_date) AS active_days
    FROM daily_activity da
    GROUP BY da.user_id
)
SELECT
    u.channel,
    COUNT(u.user_id) AS cohort_size,
    ROUND(AVG(ur.lifetime_revenue), 4) AS avg_LTV,
    ROUND(AVG(ur.active_days), 1) AS avg_lifetime_days,
    ROUND(SUM(ur.lifetime_revenue), 2) AS total_revenue
FROM users u
LEFT JOIN user_revenue ur ON u.user_id = ur.user_id
GROUP BY u.channel
ORDER BY avg_LTV DESC;

-- Q12: Power Users (top 10% by revenue)
WITH user_revenue AS (
    SELECT
        user_id,
        SUM(revenue) AS total_revenue
    FROM daily_activity
    GROUP BY user_id
),
percentiles AS (
    SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY total_revenue) AS p90
    FROM user_revenue
)
SELECT
    ur.user_id,
    u.country,
    u.game,
    u.channel,
    ROUND(ur.total_revenue, 2) AS lifetime_revenue
FROM user_revenue ur
JOIN users u ON ur.user_id = u.user_id
CROSS JOIN percentiles p
WHERE ur.total_revenue >= p.p90
ORDER BY ur.total_revenue DESC
LIMIT 50;
