-- ============================================================
-- Phase 1: Data Quality Audit Script
-- Run with: docker exec idea_mining_db psql -U admin -d app_ideas -f /tmp/audit.sql
-- ============================================================

\echo '=========================================='
\echo '  IDEA MINING PLATFORM — DATA AUDIT'
\echo '=========================================='
\echo ''

-- 0. Pipeline Row Counts
\echo '--- 0. PIPELINE STATUS ---'
SELECT 'raw.subreddit_data' as layer, count(*) as rows FROM raw.subreddit_data
UNION ALL
SELECT 'staging.cleaned_reddit', count(*) FROM staging.cleaned_reddit
UNION ALL
SELECT 'staging.llm_outputs', count(*) FROM staging.llm_outputs;

\echo ''

-- 1. Valid vs Invalid split
\echo '--- 1. VALID vs INVALID IDEAS ---'
SELECT is_valid_idea, COUNT(*) as count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as percentage
FROM staging.llm_outputs
GROUP BY 1 ORDER BY 1 DESC;

\echo ''

-- 2. Confidence score distribution
\echo '--- 2. CONFIDENCE SCORE DISTRIBUTION ---'
SELECT confidence_score, COUNT(*) as count
FROM staging.llm_outputs
GROUP BY 1 ORDER BY 1;

\echo ''

-- 3. Pain intensity (valid ideas only)
\echo '--- 3. PAIN INTENSITY (valid ideas only) ---'
SELECT pain_intensity, COUNT(*) as count
FROM staging.llm_outputs
WHERE is_valid_idea = true
GROUP BY 1 ORDER BY 1;

\echo ''

-- 4. Product category breakdown
\echo '--- 4. PRODUCT CATEGORY ---'
SELECT COALESCE(product_category, '(NULL)') as product_category, COUNT(*) as count
FROM staging.llm_outputs
WHERE is_valid_idea = true
GROUP BY 1 ORDER BY 2 DESC;

\echo ''

-- 5. Urgency breakdown
\echo '--- 5. URGENCY ---'
SELECT COALESCE(urgency, '(NULL)') as urgency, COUNT(*) as count
FROM staging.llm_outputs
WHERE is_valid_idea = true
GROUP BY 1 ORDER BY 2 DESC;

\echo ''

-- 6. Monetization model
\echo '--- 6. MONETIZATION MODEL ---'
SELECT COALESCE(monetization_model, '(NULL)') as monetization_model, COUNT(*) as count
FROM staging.llm_outputs
WHERE is_valid_idea = true
GROUP BY 1 ORDER BY 2 DESC;

\echo ''

-- 7. Market size signal
\echo '--- 7. MARKET SIZE SIGNAL ---'
SELECT COALESCE(market_size_signal, '(NULL)') as market_size_signal, COUNT(*) as count
FROM staging.llm_outputs
WHERE is_valid_idea = true
GROUP BY 1 ORDER BY 2 DESC;

\echo ''

-- 8. Willingness to pay
\echo '--- 8. WILLINGNESS TO PAY (valid ideas) ---'
SELECT willingness_to_pay, COUNT(*) as count
FROM staging.llm_outputs
WHERE is_valid_idea = true
GROUP BY 1 ORDER BY 1 DESC;

\echo ''

-- 9. NULL field audit (critical)
\echo '--- 9. NULL FIELD AUDIT (valid ideas only) ---'
SELECT
  COUNT(*) as total_valid_ideas,
  COUNT(*) FILTER (WHERE problem_statement IS NULL) as missing_problem,
  COUNT(*) FILTER (WHERE suggested_solution IS NULL) as missing_solution,
  COUNT(*) FILTER (WHERE target_audience IS NULL) as missing_audience,
  COUNT(*) FILTER (WHERE product_category IS NULL) as missing_category,
  COUNT(*) FILTER (WHERE urgency IS NULL) as missing_urgency,
  COUNT(*) FILTER (WHERE monetization_model IS NULL) as missing_monetization,
  COUNT(*) FILTER (WHERE market_size_signal IS NULL) as missing_market
FROM staging.llm_outputs
WHERE is_valid_idea = true;

\echo ''

-- 10. Subreddit performance
\echo '--- 10. SUBREDDIT PERFORMANCE ---'
SELECT r.subreddit,
       COUNT(DISTINCT r.post_id) as total_posts,
       COUNT(DISTINCT l.post_id) as analyzed,
       COUNT(DISTINCT l.post_id) FILTER (WHERE l.is_valid_idea = true) as valid_ideas,
       ROUND(100.0 * COUNT(DISTINCT l.post_id) FILTER (WHERE l.is_valid_idea = true)
             / NULLIF(COUNT(DISTINCT l.post_id), 0), 1) as valid_pct
FROM raw.subreddit_data r
LEFT JOIN staging.llm_outputs l ON r.post_id = l.post_id
GROUP BY r.subreddit
ORDER BY valid_ideas DESC;

\echo ''

-- 11. Spot-check: Top 10 valid ideas (highest confidence)
\echo '--- 11. SPOT-CHECK: TOP 10 VALID IDEAS ---'
SELECT l.post_id,
       LEFT(r.title, 80) as title,
       l.confidence_score as conf,
       l.pain_intensity as pain,
       l.urgency,
       l.product_category as category,
       LEFT(l.problem_statement, 100) as problem
FROM staging.llm_outputs l
JOIN raw.subreddit_data r ON l.post_id = r.post_id
WHERE l.is_valid_idea = true
ORDER BY l.confidence_score DESC, l.pain_intensity DESC
LIMIT 10;

\echo ''

-- 12. Spot-check: 10 rejected posts (is_valid_idea = false)
\echo '--- 12. SPOT-CHECK: 10 REJECTED POSTS ---'
SELECT l.post_id,
       LEFT(r.title, 80) as title,
       l.confidence_score as conf
FROM staging.llm_outputs l
JOIN raw.subreddit_data r ON l.post_id = r.post_id
WHERE l.is_valid_idea = false
ORDER BY l.confidence_score DESC
LIMIT 10;

\echo ''

-- 13. Spot-check: Borderline cases (valid but low confidence)
\echo '--- 13. SPOT-CHECK: BORDERLINE CASES (valid, confidence <= 4) ---'
SELECT l.post_id,
       LEFT(r.title, 80) as title,
       l.confidence_score as conf,
       l.pain_intensity as pain,
       LEFT(l.problem_statement, 100) as problem
FROM staging.llm_outputs l
JOIN raw.subreddit_data r ON l.post_id = r.post_id
WHERE l.is_valid_idea = true AND l.confidence_score <= 4
LIMIT 10;

\echo ''
\echo '=========================================='
\echo '  AUDIT COMPLETE'
\echo '=========================================='
