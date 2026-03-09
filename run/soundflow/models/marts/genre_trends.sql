
  
    
    

    create  table
      "soundflow"."marts"."genre_trends__dbt_tmp"
  
    as (
      /*
  Daily genre popularity trends.
  One row per genre per day.
*/

WITH events AS (
    SELECT * FROM "soundflow"."intermediate"."int_enriched_events"
),

genre_day AS (
    SELECT
        event_date,
        genre,

        COUNT(*)                                    AS stream_count,
        COUNT(DISTINCT user_id)                     AS unique_listeners,
        COUNT(DISTINCT track_id)                    AS unique_tracks,
        COUNT(DISTINCT artist_id)                   AS unique_artists,
        SUM(ms_played) / 1000.0 / 3600.0           AS listening_hours,
        AVG(pct_played)                             AS avg_pct_played,
        ROUND(
            SUM(CAST(is_completed AS INT)) * 100.0 / COUNT(*), 2
        )                                           AS completion_rate_pct

    FROM events
    WHERE genre IS NOT NULL
    GROUP BY event_date, genre
),

with_rank AS (
    SELECT
        *,
        ROUND(
            stream_count * 100.0 / SUM(stream_count) OVER (PARTITION BY event_date), 2
        )   AS pct_of_daily_streams,
        RANK() OVER (
            PARTITION BY event_date
            ORDER BY stream_count DESC
        )   AS daily_rank
    FROM genre_day
)

SELECT * FROM with_rank
ORDER BY event_date DESC, daily_rank ASC
    );
  
  