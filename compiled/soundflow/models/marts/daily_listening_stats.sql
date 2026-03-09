/*
  Daily platform-wide listening summary.
  One row per calendar day.
*/

WITH events AS (
    SELECT * FROM "soundflow"."intermediate"."int_enriched_events"
),

daily AS (
    SELECT
        event_date,

        -- Volume
        COUNT(*)                                        AS total_streams,
        COUNT(DISTINCT user_id)                         AS active_users,
        COUNT(DISTINCT track_id)                        AS unique_tracks_played,
        COUNT(DISTINCT artist_id)                       AS unique_artists_played,

        -- Engagement
        SUM(ms_played) / 1000.0 / 3600.0               AS total_listening_hours,
        AVG(pct_played)                                 AS avg_pct_played,
        SUM(CAST(is_completed AS INT))                  AS completed_streams,
        SUM(CAST(is_skipped AS INT))                    AS skipped_streams,
        ROUND(
            SUM(CAST(is_completed AS INT)) * 100.0 / COUNT(*), 2
        )                                               AS completion_rate_pct,
        ROUND(
            SUM(CAST(is_skipped AS INT)) * 100.0 / COUNT(*), 2
        )                                               AS skip_rate_pct,

        -- Platform breakdown
        SUM(CASE WHEN platform = 'ios'        THEN 1 ELSE 0 END) AS streams_ios,
        SUM(CASE WHEN platform = 'android'    THEN 1 ELSE 0 END) AS streams_android,
        SUM(CASE WHEN platform = 'web'        THEN 1 ELSE 0 END) AS streams_web,
        SUM(CASE WHEN platform = 'chromecast' THEN 1 ELSE 0 END) AS streams_chromecast,
        SUM(CASE WHEN platform = 'alexa'      THEN 1 ELSE 0 END) AS streams_alexa,

        -- Subscription breakdown
        SUM(CASE WHEN subscription_type = 'free'    THEN 1 ELSE 0 END) AS streams_free,
        SUM(CASE WHEN subscription_type = 'premium' THEN 1 ELSE 0 END) AS streams_premium,
        SUM(CASE WHEN subscription_type = 'family'  THEN 1 ELSE 0 END) AS streams_family,
        SUM(CASE WHEN subscription_type = 'student' THEN 1 ELSE 0 END) AS streams_student,

        -- Offline / shuffle
        SUM(CAST(is_offline AS INT)) AS offline_streams,
        SUM(CAST(is_shuffle AS INT)) AS shuffle_streams

    FROM events
    GROUP BY event_date
)

SELECT * FROM daily
ORDER BY event_date DESC