
  
  create view "soundflow"."dev_staging"."stg_stream_events__dbt_tmp" as (
    WITH source AS (
    SELECT * FROM "soundflow"."raw"."stream_events"
),

renamed AS (
    SELECT
        event_id,
        user_id,
        track_id,
        CAST(started_at AS TIMESTAMP)                                   AS started_at,
        CAST(started_at AS DATE)                                        AS event_date,
        CAST(ms_played AS INTEGER)                                      AS ms_played,
        CAST(track_duration_ms AS INTEGER)                              AS track_duration_ms,
        ROUND(
            CAST(ms_played AS DOUBLE) / CAST(track_duration_ms AS DOUBLE) * 100, 1
        )                                                               AS pct_played,
        CAST(completed AS BOOLEAN)                                      AS is_completed,
        CAST(skipped AS BOOLEAN)                                        AS is_skipped,
        device_type,
        platform,
        CAST(shuffle_mode AS BOOLEAN)                                   AS is_shuffle,
        CAST(offline_mode AS BOOLEAN)                                   AS is_offline
    FROM source
)

SELECT * FROM renamed
  );
