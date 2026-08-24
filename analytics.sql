-- Fintech Automated KYC & Fraud Risk Detection Engine
-- PostgreSQL analytics demonstrating CTEs, window functions, percentiles,
-- cohorts and statistical merchant segmentation.

-- 1) FRAUD TREND ANALYSIS
-- Hourly suspicious-upload rate by merchant segment and city. LAG measures
-- change versus the prior hour; DENSE_RANK surfaces the sharpest spikes.
WITH hourly AS (
    SELECT
        date_trunc('hour', v."timestamp") AS hour_bucket,
        m.merchant_segment,
        COALESCE(m.city, 'UNKNOWN') AS city,
        COUNT(*) AS total_uploads,
        COUNT(*) FILTER (WHERE v.flagged_status = 'Suspicious') AS suspicious_uploads,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE v.flagged_status = 'Suspicious')
            / NULLIF(COUNT(*), 0), 2
        ) AS suspicious_rate_pct
    FROM verifications v
    JOIN merchants m ON m.merchant_id = v.merchant_id
    GROUP BY 1, 2, 3
), deltas AS (
    SELECT
        *,
        LAG(suspicious_rate_pct) OVER (
            PARTITION BY merchant_segment, city
            ORDER BY hour_bucket
        ) AS previous_hour_rate_pct
    FROM hourly
), ranked AS (
    SELECT
        *,
        suspicious_rate_pct - COALESCE(previous_hour_rate_pct, suspicious_rate_pct) AS rate_delta_pct,
        DENSE_RANK() OVER (
            PARTITION BY hour_bucket
            ORDER BY suspicious_rate_pct - COALESCE(previous_hour_rate_pct, suspicious_rate_pct) DESC
        ) AS spike_rank
    FROM deltas
)
SELECT *
FROM ranked
ORDER BY hour_bucket DESC, spike_rank;

-- 2) DAILY MERCHANT SPIKES
-- DENSE_RANK identifies merchants contributing the most suspicious uploads each day.
WITH merchant_daily AS (
    SELECT
        date_trunc('day', "timestamp")::date AS verification_day,
        merchant_id,
        COUNT(*) AS total_verifications,
        COUNT(*) FILTER (WHERE flagged_status = 'Suspicious') AS suspicious_count
    FROM verifications
    GROUP BY 1, 2
)
SELECT
    *,
    ROUND(100.0 * suspicious_count / NULLIF(total_verifications, 0), 2) AS suspicious_rate_pct,
    DENSE_RANK() OVER (
        PARTITION BY verification_day
        ORDER BY suspicious_count DESC
    ) AS merchant_fraud_rank
FROM merchant_daily
ORDER BY verification_day DESC, merchant_fraud_rank;

-- 3) OPERATIONAL LATENCY
-- Median and p95 are more useful than the mean when inference latency is skewed.
SELECT
    document_type,
    COUNT(*) AS verification_count,
    ROUND(AVG(processing_time_ms), 2) AS avg_processing_time_ms,
    ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY processing_time_ms)::numeric, 2) AS median_processing_time_ms,
    ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY processing_time_ms)::numeric, 2) AS p95_processing_time_ms
FROM verifications
GROUP BY document_type
ORDER BY p95_processing_time_ms DESC;

-- 4) MERCHANT ONBOARDING COHORT PASS RATES
-- Pass = auto-approved low-risk verification. Repeat activity is also surfaced.
WITH cohort_activity AS (
    SELECT
        date_trunc('month', m.onboarding_cohort)::date AS onboarding_month,
        m.merchant_id,
        COUNT(v.verification_id) AS attempts,
        COUNT(v.verification_id) FILTER (WHERE v.intervention = 'AUTO_APPROVE') AS approvals,
        MIN(v."timestamp") AS first_verification_at,
        MAX(v."timestamp") AS last_verification_at
    FROM merchants m
    LEFT JOIN verifications v ON v.merchant_id = m.merchant_id
    GROUP BY 1, 2
)
SELECT
    onboarding_month,
    COUNT(*) AS merchants_in_cohort,
    SUM(attempts) AS total_attempts,
    SUM(approvals) AS total_approvals,
    ROUND(100.0 * SUM(approvals) / NULLIF(SUM(attempts), 0), 2) AS approval_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE attempts > 1) / NULLIF(COUNT(*), 0), 2) AS repeat_verification_rate_pct
FROM cohort_activity
GROUP BY onboarding_month
ORDER BY onboarding_month;

-- 5) STATISTICAL MERCHANT SEGMENTATION
-- Compare each merchant's tamper rate with the population mean/stddev.
-- z >= 2 is an analytics signal for investigation, not a production fraud verdict.
WITH merchant_rates AS (
    SELECT
        merchant_id,
        COUNT(*) AS total_verifications,
        AVG((flagged_status = 'Suspicious')::int)::numeric AS suspicious_rate
    FROM verifications
    GROUP BY merchant_id
    HAVING COUNT(*) >= 5
), population AS (
    SELECT
        AVG(suspicious_rate) AS mean_rate,
        STDDEV_SAMP(suspicious_rate) AS std_rate
    FROM merchant_rates
), scored AS (
    SELECT
        mr.*,
        CASE
            WHEN p.std_rate IS NULL OR p.std_rate = 0 THEN 0
            ELSE (mr.suspicious_rate - p.mean_rate) / p.std_rate
        END AS z_score
    FROM merchant_rates mr
    CROSS JOIN population p
)
SELECT
    merchant_id,
    total_verifications,
    ROUND(100 * suspicious_rate, 2) AS suspicious_rate_pct,
    ROUND(z_score, 2) AS z_score,
    CASE
        WHEN z_score >= 2 THEN 'HIGH_RISK_MERCHANT_REVIEW'
        WHEN z_score >= 1 THEN 'ENHANCED_MONITORING'
        ELSE 'STANDARD_MONITORING'
    END AS recommended_intervention
FROM scored
ORDER BY z_score DESC;

-- 6) BUSINESS INTERVENTION MIX
-- Measures operational load and auto-approval opportunity.
SELECT
    date_trunc('day', "timestamp")::date AS verification_day,
    COUNT(*) AS total_verifications,
    COUNT(*) FILTER (WHERE intervention = 'AUTO_APPROVE') AS auto_approved,
    COUNT(*) FILTER (WHERE intervention = 'MANUAL_REVIEW') AS manual_review,
    COUNT(*) FILTER (WHERE intervention = 'BLOCK_AND_ESCALATE') AS blocked_and_escalated,
    ROUND(100.0 * COUNT(*) FILTER (WHERE intervention = 'AUTO_APPROVE') / NULLIF(COUNT(*), 0), 2) AS auto_approval_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE intervention = 'MANUAL_REVIEW') / NULLIF(COUNT(*), 0), 2) AS manual_review_rate_pct
FROM verifications
GROUP BY 1
ORDER BY verification_day DESC;
