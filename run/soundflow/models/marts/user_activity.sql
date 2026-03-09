
  
    
    

    create  table
      "soundflow"."marts"."user_activity__dbt_tmp"
  
    as (
      /*
  Per-user listening activity summary (all-time).
  One row per user.
*/

WITH events AS (
    SELECT * FROM "soundflow"."intermediate"."int_enriched_events"
),

users AS (
    SELECT * FROM "soundflow"."staging"."stg_users"
),

user_stats AS (
    SELECT
        user_id,
        COUNT(*)                                        AS total_streams,
        COUNT(DISTINCT track_id)                        AS unique_tracks,
        COUNT(DISTINCT artist_id)                       AS unique_artists,
        COUNT(DISTINCT event_date)                      AS active_days,
        SUM(ms_played) / 1000.0 / 3600.0               AS total_listening_hours,
        AVG(pct_played)                                 AS avg_pct_played,
        ROUND(
            SUM(CAST(is_completed AS INT)) * 100.0 / COUNT(*), 2
        )                                               AS completion_rate_pct,
        ROUND(
            SUM(CAST(is_skipped AS INT)) * 100.0 / COUNT(*), 2
        )                                               AS skip_rate_pct,
        MIN(event_date)                                 AS first_stream_date,
        MAX(event_date)                                 AS last_stream_date,
        MODE() WITHIN GROUP (ORDER BY genre)            AS top_genre,
        MODE() WITHIN GROUP (ORDER BY platform)         AS preferred_platform,
        MODE() WITHIN GROUP (ORDER BY device_type)      AS preferred_device,
        SUM(CAST(is_shuffle AS INT))                    AS shuffle_streams,
        SUM(CAST(is_offline AS INT))                    AS offline_streams

    FROM events
    GROUP BY user_id
),

final AS (
    SELECT
        u.user_id,
        u.username,
        u.country,
        u.subscription_type,
        u.age_group,
        u.joined_date,
        COALESCE(s.total_streams, 0)            AS total_streams,
        COALESCE(s.unique_tracks, 0)            AS unique_tracks,
        COALESCE(s.unique_artists, 0)           AS unique_artists,
        COALESCE(s.active_days, 0)              AS active_days,
        COALESCE(s.total_listening_hours, 0)    AS total_listening_hours,
        s.avg_pct_played,
        s.completion_rate_pct,
        s.skip_rate_pct,
        s.first_stream_date,
        s.last_stream_date,
        s.top_genre,
        s.preferred_platform,
        s.preferred_device,
        COALESCE(s.shuffle_streams, 0)          AS shuffle_streams,
        COALESCE(s.offline_streams, 0)          AS offline_streams
    FROM users AS u
    LEFT JOIN user_stats AS s ON u.user_id = s.user_id
)

SELECT * FROM final
    );
  
  