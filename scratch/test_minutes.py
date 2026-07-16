import duckdb

con = duckdb.connect('data/warehouse/athena.duckdb')
query = """
WITH match_durations AS (
    SELECT match_id, MAX(minute) AS max_minute
    FROM events
    GROUP BY match_id
),
substitution_off AS (
    SELECT match_id, player_id, MIN(minute) AS sub_off_minute
    FROM events
    WHERE type_name IN ('Substitution', 'Player Off')
    GROUP BY match_id, player_id
),
substitution_on_proxy AS (
    SELECT match_id, player_id, MIN(minute) AS first_event_minute
    FROM events
    GROUP BY match_id, player_id
)
SELECT 
    l.player_name, 
    l.starting_position, 
    so.sub_off_minute, 
    sp.first_event_minute, 
    md.max_minute,
    CASE 
        WHEN l.starting_position IS NOT NULL THEN COALESCE(so.sub_off_minute, md.max_minute)
        ELSE CASE WHEN sp.first_event_minute IS NOT NULL THEN md.max_minute - sp.first_event_minute ELSE 0 END
    END AS minutes
FROM lineups l
JOIN match_durations md ON l.match_id = md.match_id
LEFT JOIN substitution_off so ON l.match_id = so.match_id AND l.player_id = so.player_id
LEFT JOIN substitution_on_proxy sp ON l.match_id = sp.match_id AND l.player_id = sp.player_id
WHERE l.player_name = 'Lionel Andrés Messi Cuccittini'
LIMIT 10;
"""
print(con.execute(query).df())
