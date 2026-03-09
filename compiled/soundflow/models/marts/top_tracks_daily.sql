/*
  Top tracks per day — ranked by stream count.
  Includes track and artist metadata for easy reporting.
*/

WITH events AS (
    SELECT * FROM "soundflow"."intermediate"."int_enriched_events"
),

track_day AS (
    SELECT
        event_date,
        track_id,
        track_title,
        artist_id,
        artist_name,
        genre,
        release_year,

        COUNT(*)                                    AS stream_count,
        COUNT(DISTINCT user_id)                     AS unique_listeners,
        SUM(ms_played) / 1000.0 / 3600.0           AS listening_hours,
        AVG(pct_played)                             AS avg_pct_played,
        SUM(CAST(is_completed AS INT))              AS completions,
        SUM(CAST(is_skipped AS INT))                AS skips,
        ROUND(
            SUM(CAST(is_completed AS INT)) * 100.0 / COUNT(*), 2
        )                                           AS completion_rate_pct

    FROM events
    GROUP BY
        event_date, track_id, track_title,
        artist_id, artist_name, genre, release_year
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY event_date
            ORDER BY stream_count DESC
        ) AS daily_rank
    FROM track_day
)

SELECT * FROM ranked
WHERE daily_rank <= 100
ORDER BY event_date DESC, daily_rank ASC