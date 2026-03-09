-- Daily rank must be between 1 and 100 (top_tracks_daily is filtered to top 100).
-- Returns failing rows — zero rows = test passes.

SELECT *
FROM {{ ref('top_tracks_daily') }}
WHERE
    daily_rank < 1
    OR daily_rank > 100
