
  
  create view "soundflow"."dev_intermediate"."int_enriched_events__dbt_tmp" as (
    /*
  Enriched stream events — joins events with track, artist, and user dims.
  This is the main fact table used downstream by all mart models.
*/

WITH events AS (
    SELECT * FROM "soundflow"."dev_staging"."stg_stream_events"
),

tracks AS (
    SELECT * FROM "soundflow"."dev_staging"."stg_tracks"
),

artists AS (
    SELECT * FROM "soundflow"."dev_staging"."stg_artists"
),

users AS (
    SELECT * FROM "soundflow"."dev_staging"."stg_users"
),

enriched AS (
    SELECT
        -- Event
        e.event_id,
        e.started_at,
        e.event_date,
        e.ms_played,
        e.track_duration_ms,
        e.pct_played,
        e.is_completed,
        e.is_skipped,
        e.device_type,
        e.platform,
        e.is_shuffle,
        e.is_offline,

        -- Track
        t.track_id,
        t.track_title,
        t.genre,
        t.release_year,
        t.is_explicit,
        t.tempo_bpm,
        t.energy_score,
        t.duration_ms         AS track_duration_ms_catalog,

        -- Artist
        a.artist_id,
        a.artist_name,
        a.country             AS artist_country,

        -- User
        u.user_id,
        u.username,
        u.country             AS user_country,
        u.subscription_type,
        u.age_group,
        u.joined_date

    FROM events AS e
    LEFT JOIN tracks AS t  ON e.track_id = t.track_id
    LEFT JOIN artists AS a ON t.artist_id = a.artist_id
    LEFT JOIN users AS u   ON e.user_id = u.user_id
)

SELECT * FROM enriched
  );
