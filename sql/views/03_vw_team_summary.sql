/*
 * sql/views/03_vw_team_summary.sql
 *
 * Team-level analytical overview per competition-season.
 * One row per team per competition-season.
 *
 * Techniques demonstrated:
 *   - Multiple CTEs combining home and away perspectives
 *   - CASE expressions for W/D/L classification
 *   - Conditional aggregation across different team roles (home vs away)
 *   - xG differential as a measure of attacking quality vs concession quality
 *   - Points tally using standard 3-1-0 system
 *   - UNION ALL to combine home and away match records per team
 */

CREATE OR REPLACE VIEW vw_team_summary AS

WITH

-- ─── Step 1: event-level aggregations per team per match ─────────────────────
team_match_events AS (
    SELECT
        match_id,
        team_id,
        team_name,

        -- Attacking output
        COUNT(*) FILTER (WHERE type_name = 'Shot')                          AS shots_for,
        COUNT(*) FILTER (WHERE type_name = 'Shot'
                             AND shot_outcome = 'Goal')                     AS goals_from_events,
        COALESCE(
            SUM(shot_statsbomb_xg) FILTER (WHERE type_name = 'Shot'),
            0.0
        )                                                                    AS xg_for,

        -- Passing quality
        COUNT(*) FILTER (WHERE type_name = 'Pass')                          AS total_passes,
        COUNT(*) FILTER (WHERE type_name = 'Pass'
                             AND pass_outcome IS NULL)                      AS accurate_passes,

        -- Ball progression
        COUNT(*) FILTER (WHERE type_name = 'Carry')                         AS carries,
        COUNT(*) FILTER (WHERE type_name = 'Dribble'
                             AND dribble_outcome = 'Complete')              AS successful_dribbles,

        -- Pressure applied (defending team pressures = opponent ball events under pressure)
        COUNT(*) FILTER (WHERE under_pressure = true)                       AS events_under_pressure

    FROM   events
    WHERE  team_id IS NOT NULL
    GROUP  BY match_id, team_id, team_name
),

-- ─── Step 2: derive xG conceded — what the opposing team created against us ──
team_xg_against AS (
    SELECT
        tme.match_id,
        -- The opposition team
        CASE
            WHEN tme.team_id = m.home_team_id THEN m.away_team_id
            ELSE m.home_team_id
        END                                                                  AS team_id,
        tme.xg_for                                                           AS xg_against,
        tme.shots_for                                                        AS shots_against
    FROM   team_match_events tme
    JOIN   matches m ON tme.match_id = m.match_id
),

-- ─── Step 3: flatten each team's home and away appearances into one table ────
team_results AS (
    -- Home appearances
    SELECT
        m.home_team_id                                                       AS team_id,
        m.home_team_name                                                     AS team_name,
        m.competition_id,
        m.competition_name,
        m.season_id,
        m.season_name,
        m.match_id,
        m.home_score                                                         AS goals_scored,
        m.away_score                                                         AS goals_conceded,
        CASE
            WHEN m.home_score > m.away_score THEN 'Win'
            WHEN m.home_score = m.away_score THEN 'Draw'
            ELSE 'Loss'
        END                                                                  AS result
    FROM matches m

    UNION ALL

    -- Away appearances
    SELECT
        m.away_team_id,
        m.away_team_name,
        m.competition_id,
        m.competition_name,
        m.season_id,
        m.season_name,
        m.match_id,
        m.away_score,
        m.home_score,
        CASE
            WHEN m.away_score > m.home_score THEN 'Win'
            WHEN m.away_score = m.home_score THEN 'Draw'
            ELSE 'Loss'
        END
    FROM matches m
)

-- ─── Final: aggregate team stats per competition-season ───────────────────────
SELECT
    tr.team_id,
    tr.team_name,
    tr.competition_id,
    tr.competition_name,
    tr.season_id,
    tr.season_name,

    -- ── Season record ────────────────────────────────────────────────────────
    COUNT(DISTINCT tr.match_id)                                               AS matches_played,
    COUNT(*) FILTER (WHERE tr.result = 'Win')                                 AS wins,
    COUNT(*) FILTER (WHERE tr.result = 'Draw')                                AS draws,
    COUNT(*) FILTER (WHERE tr.result = 'Loss')                                AS losses,

    -- Points: 3 per win, 1 per draw
    COUNT(*) FILTER (WHERE tr.result = 'Win')  * 3
    + COUNT(*) FILTER (WHERE tr.result = 'Draw')                              AS points,

    -- Goals
    SUM(tr.goals_scored)                                                      AS goals_scored,
    SUM(tr.goals_conceded)                                                    AS goals_conceded,
    SUM(tr.goals_scored) - SUM(tr.goals_conceded)                             AS goal_difference,

    -- ── xG metrics (expected goals) ──────────────────────────────────────────
    ROUND(SUM(tme.xg_for),   3)                                               AS xg_for,
    ROUND(SUM(txa.xg_against), 3)                                             AS xg_against,
    ROUND(SUM(tme.xg_for) - SUM(txa.xg_against), 3)                         AS xg_difference,

    -- ── Shooting ─────────────────────────────────────────────────────────────
    SUM(tme.shots_for)                                                        AS total_shots,
    SUM(txa.shots_against)                                                    AS shots_conceded,

    -- ── Passing quality ──────────────────────────────────────────────────────
    SUM(tme.total_passes)                                                     AS total_passes,
    SUM(tme.accurate_passes)                                                  AS accurate_passes,
    ROUND(
        SUM(tme.accurate_passes) * 100.0 / NULLIF(SUM(tme.total_passes), 0),
        1
    )                                                                         AS pass_accuracy_pct,

    -- ── Ball progression ─────────────────────────────────────────────────────
    SUM(tme.carries)                                                          AS total_carries,
    SUM(tme.successful_dribbles)                                              AS successful_dribbles,

    -- ── Per-match averages ───────────────────────────────────────────────────
    ROUND(SUM(tr.goals_scored)  / NULLIF(COUNT(DISTINCT tr.match_id), 0), 2) AS avg_goals_scored,
    ROUND(SUM(tme.xg_for)       / NULLIF(COUNT(DISTINCT tr.match_id), 0), 3) AS avg_xg_per_match,
    ROUND(SUM(tme.total_passes) / NULLIF(COUNT(DISTINCT tr.match_id), 0), 1) AS avg_passes_per_match

FROM       team_results      tr
LEFT JOIN  team_match_events tme ON tr.match_id = tme.match_id
                                AND tr.team_id  = tme.team_id
LEFT JOIN  team_xg_against   txa ON tr.match_id = txa.match_id
                                AND tr.team_id  = txa.team_id
GROUP BY
    tr.team_id, tr.team_name,
    tr.competition_id, tr.competition_name,
    tr.season_id, tr.season_name
ORDER BY points DESC, goal_difference DESC
