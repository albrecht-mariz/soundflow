-- Skip rate must be between 0 and 100.
-- Returns failing rows — zero rows = test passes.

SELECT *
FROM {{ ref('daily_listening_stats') }}
WHERE
    skip_rate_pct < 0
    OR skip_rate_pct > 100
