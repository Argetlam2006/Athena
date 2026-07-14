/*
 * sql/views/01_vw_match_summary.sql
 *
 * Match-level analytical overview.
 * One row per match enriched with derived event statistics.
 *
 * Techniques demonstrated:
 *   - Conditional aggregation with FILTER clause
 *   - CASE expressions for result classification
 *   - NULLIF to avoid division-by-zero
 *   - Multi-CTE pipeline
 *   - LEFT JOIN on aggregated subqueries
 */

CREATE OR REPLACE VIEW vw_match_summary AS

WITH

-- ─── Step 1: aggregate event stats per match per team ───────────────────────
match_events AS (
    SELECT
        match_id,
        team_id,
        team_name,

        -- Volume
        COUNT(*)                                                              AS total_events,

        -- Passing
        COUNT(*)   FILTER (WHERE type_name = 'Pass')                         AS total_passes,
        COUNT(*)   FILTER (WHERE type_name = 'Pass'
                               AND pass_outcome IS NULL)                     AS accurate_passes,

        -- Shooting
        COUNT(*)   FILTER (WHERE type_name = 'Shot')                         AS shots,
        COUNT(*)   FILTER (WHERE type_name = 'Shot'
                               AND shot_outcome IN ('Goal',
                                                    'Saved',
                                                    'Saved To Post'))        AS shots_on_target,
        COUNT(*)   FILTER (WHERE type_name = 'Shot'
                               AND shot_outcome = 'Goal')                    AS goals_from_events,
        COALESCE(
            SUM(shot_statsbomb_xg)
            FILTER (WHERE type_name = 'Shot'),
            0.0
        )                                                                     AS xg,

        -- Ball progression
        COUNT(*)   FILTER (WHERE type_name = 'Carry')                        AS carries,
        COUNT(*)   FILTER (WHERE type_name = 'Dribble'
                               AND dribble_outcome = 'Complete')             AS successful_dribbles,

        -- Pressure
        COUNT(*)   FILTER (WHERE under_pressure = true)                      AS events_under_pressure

    FROM   events
    WHERE  team_id IS NOT NULL
    GROUP  BY match_id, team_id, team_name
),

-- ─── Step 2: pivot to home / away columns using the matches join ─────────────
home_stats AS (
    SELECT
        me.match_id,
        me.total_passes                                                       AS home_passes,
        me.accurate_passes                                                    AS home_accurate_passes,
        ROUND(
            me.accurate_passes * 100.0 / NULLIF(me.total_passes, 0), 1
        )                                                                     AS home_pass_accuracy_pct,
        me.shots                                                              AS home_shots,
        me.shots_on_target                                                    AS home_shots_on_target,
        ROUND(me.xg, 3)                                                       AS home_xg,
        me.carries                                                            AS home_carries,
        me.successful_dribbles                                                AS home_dribbles,
        me.total_events                                                       AS home_events,
        me.events_under_pressure                                              AS home_events_under_pressure
    FROM   match_events me
    JOIN   matches      m  ON me.match_id = m.match_id
                          AND me.team_id  = m.home_team_id
),

away_stats AS (
    SELECT
        me.match_id,
        me.total_passes                                                       AS away_passes,
        me.accurate_passes                                                    AS away_accurate_passes,
        ROUND(
            me.accurate_passes * 100.0 / NULLIF(me.total_passes, 0), 1
        )                                                                     AS away_pass_accuracy_pct,
        me.shots                                                              AS away_shots,
        me.shots_on_target                                                    AS away_shots_on_target,
        ROUND(me.xg, 3)                                                       AS away_xg,
        me.carries                                                            AS away_carries,
        me.successful_dribbles                                                AS away_dribbles,
        me.total_events                                                       AS away_events,
        me.events_under_pressure                                              AS away_events_under_pressure
    FROM   match_events me
    JOIN   matches      m  ON me.match_id = m.match_id
                          AND me.team_id  = m.away_team_id
)

-- ─── Final: combine match metadata with aggregated event stats ───────────────
SELECT
    m.match_id,
    m.match_date,
    m.competition_name,
    m.season_name,
    m.match_week,
    m.home_team_name,
    m.away_team_name,
    m.home_score,
    m.away_score,
    m.stadium_name,
    m.referee_name,

    -- ── Result & character ──────────────────────────────────────────────────
    CASE
        WHEN m.home_score  > m.away_score THEN 'Home Win'
        WHEN m.home_score  < m.away_score THEN 'Away Win'
        ELSE 'Draw'
    END                                                                       AS result,

    (m.home_score + m.away_score)                                             AS total_goals,
    ABS(m.home_score - m.away_score)                                          AS goal_difference,

    CASE
        WHEN (m.home_score + m.away_score) >= 4 THEN 'High Scoring'
        WHEN (m.home_score + m.away_score) = 0  THEN 'Goalless'
        ELSE 'Normal'
    END                                                                       AS match_classification,

    -- ── Home event stats ────────────────────────────────────────────────────
    hs.home_passes,
    hs.home_accurate_passes,
    hs.home_pass_accuracy_pct,
    hs.home_shots,
    hs.home_shots_on_target,
    hs.home_xg,
    hs.home_carries,
    hs.home_dribbles,
    hs.home_events,

    -- ── Away event stats ────────────────────────────────────────────────────
    aws.away_passes,
    aws.away_accurate_passes,
    aws.away_pass_accuracy_pct,
    aws.away_shots,
    aws.away_shots_on_target,
    aws.away_xg,
    aws.away_carries,
    aws.away_dribbles,
    aws.away_events,

    -- ── Derived match analytics ─────────────────────────────────────────────
    ROUND(
        COALESCE(hs.home_xg,   0)
      - COALESCE(aws.away_xg,  0),
        3
    )                                                                         AS xg_differential,

    -- Shot share: home team's portion of all shots (0–100%)
    ROUND(
        COALESCE(hs.home_shots, 0) * 100.0
        / NULLIF(
            COALESCE(hs.home_shots, 0) + COALESCE(aws.away_shots, 0),
            0
          ),
        1
    )                                                                         AS home_shot_share_pct,

    -- Pass volume balance
    COALESCE(hs.home_passes, 0) + COALESCE(aws.away_passes, 0)               AS total_passes

FROM   matches m
LEFT   JOIN home_stats hs  ON m.match_id = hs.match_id
LEFT   JOIN away_stats aws ON m.match_id = aws.match_id
ORDER  BY m.match_date DESC, m.match_id
