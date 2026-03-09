
    
    

with child as (
    select artist_id as from_field
    from "soundflow"."staging"."stg_tracks"
    where artist_id is not null
),

parent as (
    select artist_id as to_field
    from "soundflow"."staging"."stg_artists"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


