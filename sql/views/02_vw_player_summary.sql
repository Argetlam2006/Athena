/*
 * sql/views/02_vw_player_summary.sql
 *
 * Player performance aggregation across all matches per competition-season.
 * This is Athena's primary analytical view — the foundation for percentiles,
 * recruitment, and the player workspace.
 *
 * Techniques demonstrated:
 *   - Six-CTE pipeline with clear separation of concerns
 *   - FILTER clause for conditional aggregation (cleaner than CASE WHEN SUM)
 *   - NULLIF / COALESCE for null-safe arithmetic
 *   - Euclidean distance for carry_distance_m using SQRT + POWER
 *   - Per-90 metric normalisation (multiply by 90 / minutes_played)
 *   - ROUND for clean output at every computed column
 *   - QUALIFY for mode-of-position (most frequent starting position)
 *   - LEFT JOINs on all event sub-aggregations (players without events → 0)
 *
 * Approximation note:
 *   minutes_played = matches_played × 90
 *   This is an intentional simplification for Phase 2.2.
 *   Precise substitution timing requires tracking sub events, which
 *   is deferred to Phase 3 (Analytics Engine).
 */

CREATE OR REPLACE VIEW vw_player_summary AS

WITH

-- ─── CTE 1: pass statistics per player per match ─────────────────────────────
pass_stats AS (
    SELECT
        match_id,
        player_id,
        COUNT(*)                                                              AS total_passes,
        COUNT(*) FILTER (WHERE pass_outcome IS NULL)                         AS accurate_passes,
        COALESCE(SUM(pass_length),  0.0)                                     AS total_pass_distance_m,
        COALESCE(AVG(pass_length),  0.0)                                     AS avg_pass_length_m,
        COUNT(*) FILTER (WHERE pass_cross        = true)                     AS crosses,
        COUNT(*) FILTER (WHERE pass_switch       = true)                     AS switches,
        COUNT(*) FILTER (WHERE pass_through_ball = true)                     AS through_balls,
        COUNT(*) FILTER (WHERE pass_shot_assist  = true)                     AS shot_assists,
        COUNT(*) FILTER (WHERE pass_goal_assist  = true)                     AS goal_assists,
        -- Progressive passes: forward passes of ≥ 10m in the attacking half
        COUNT(*) FILTER (
            WHERE pass_end_x > 60
              AND pass_end_x > location_x
              AND pass_length >= 10
        )                                                                     AS progressive_passes
    FROM   events
    WHERE  type_name = 'Pass'
      AND  player_id IS NOT NULL
    GROUP  BY match_id, player_id
),

-- ─── CTE 2: shot statistics per player per match ─────────────────────────────
shot_stats AS (
    SELECT
        match_id,
        player_id,
        COUNT(*)                                                              AS total_shots,
        COUNT(*) FILTER (WHERE shot_outcome = 'Goal')                        AS goals,
        COUNT(*) FILTER (WHERE shot_outcome IN (
                                   'Goal', 'Saved', 'Saved To Post'
                               ))                                            AS shots_on_target,
        COALESCE(SUM(shot_statsbomb_xg), 0.0)                               AS xg_total,
        -- Non-penalty xG: exclude direct free-kick and penalty shots
        COALESCE(SUM(shot_statsbomb_xg) FILTER (
            WHERE shot_type NOT IN ('Free Kick', 'Penalty')
        ), 0.0)                                                              AS npxg_total
    FROM   events
    WHERE  type_name = 'Shot'
      AND  player_id IS NOT NULL
    GROUP  BY match_id, player_id
),

-- ─── CTE 3: carry statistics per player per match ─────────────────────────────
carry_stats AS (
    SELECT
        match_id,
        player_id,
        COUNT(*)                                                              AS total_carries,
        -- Euclidean distance of each carry in metres
        COALESCE(SUM(
            SQRT(
                POWER(carry_end_x - location_x, 2) +
                POWER(carry_end_y - location_y, 2)
            )
        ), 0.0)                                                              AS total_carry_distance_m,
        -- Progressive carries: carried the ball ≥ 10m towards the goal
        COUNT(*) FILTER (
            WHERE carry_end_x > location_x
              AND (carry_end_x - location_x) >= 10
        )                                                                    AS progressive_carries
    FROM   events
    WHERE  type_name = 'Carry'
      AND  player_id IS NOT NULL
    GROUP  BY match_id, player_id
),

-- ─── CTE 4: dribble statistics per player per match ───────────────────────────
dribble_stats AS (
    SELECT
        match_id,
        player_id,
        COUNT(*)                                                              AS total_dribbles,
        COUNT(*) FILTER (WHERE dribble_outcome = 'Complete')                 AS dribbles_completed
    FROM   events
    WHERE  type_name = 'Dribble'
      AND  player_id IS NOT NULL
    GROUP  BY match_id, player_id
),

-- ─── CTE 5: pressure & volume stats per player per match ─────────────────────
pressure_stats AS (
    SELECT
        match_id,
        player_id,
        COUNT(*)                                                              AS total_events,
        COUNT(*) FILTER (WHERE under_pressure = true)                        AS events_under_pressure
    FROM   events
    WHERE  player_id IS NOT NULL
    GROUP  BY match_id, player_id
),

-- ─── CTE 6: player appearances — join lineups with match context ──────────────
player_appearances AS (
    SELECT
        l.player_id,
        l.player_name,
        l.player_nickname,
        l.team_id,
        l.team_name,
        l.match_id,
        l.starting_position,
        l.height_cm,
        l.weight_kg,
        l.country_name,
        l.birth_date,
        m.competition_id,
        m.competition_name,
        m.season_id,
        m.season_name
    FROM   lineups l
    JOIN   matches m ON l.match_id = m.match_id
),

-- ─── CTE 7: primary position — the most common starting position for each
--           player in each competition-season (uses DuckDB's QUALIFY clause)
primary_positions AS (
    SELECT
        player_id,
        competition_id,
        season_id,
        starting_position     AS position_name,
        COUNT(*)              AS pos_count
    FROM   player_appearances
    WHERE  starting_position IS NOT NULL
    GROUP  BY player_id, competition_id, season_id, starting_position
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY player_id, competition_id, season_id
        ORDER     BY COUNT(*) DESC
    ) = 1
),

-- ─── Final aggregation ────────────────────────────────────────────────────────
aggregated AS (
    SELECT
        pa.player_id,
        pa.player_name,
        pa.player_nickname,
        pa.team_id,
        pa.team_name,
        pa.competition_id,
        pa.competition_name,
        pa.season_id,
        pa.season_name,
        pa.height_cm,
        pa.weight_kg,
        pa.country_name,
        pa.birth_date,
        pp.position_name,

        -- Appearance volume
        COUNT(DISTINCT pa.match_id)                                          AS matches_played,
        -- Approximation: assume 90 minutes per appearance
        COUNT(DISTINCT pa.match_id) * 90                                     AS minutes_played,

        -- ── Pass aggregations ────────────────────────────────────────────────
        COALESCE(SUM(ps.total_passes),           0)                          AS total_passes,
        COALESCE(SUM(ps.accurate_passes),        0)                          AS accurate_passes,
        COALESCE(SUM(ps.total_pass_distance_m),  0.0)                        AS total_pass_distance_m,
        ROUND(COALESCE(AVG(ps.avg_pass_length_m), 0.0), 2)                  AS avg_pass_length_m,
        COALESCE(SUM(ps.crosses),                0)                          AS crosses,
        COALESCE(SUM(ps.switches),               0)                          AS switches,
        COALESCE(SUM(ps.through_balls),          0)                          AS through_balls,
        COALESCE(SUM(ps.shot_assists),           0)                          AS shot_assists,
        COALESCE(SUM(ps.goal_assists),           0)                          AS goal_assists,
        COALESCE(SUM(ps.progressive_passes),     0)                          AS progressive_passes,

        -- ── Shot aggregations ────────────────────────────────────────────────
        COALESCE(SUM(ss.total_shots),            0)                          AS total_shots,
        COALESCE(SUM(ss.goals),                  0)                          AS goals,
        COALESCE(SUM(ss.shots_on_target),        0)                          AS shots_on_target,
        ROUND(COALESCE(SUM(ss.xg_total),         0.0), 3)                   AS xg_total,
        ROUND(COALESCE(SUM(ss.npxg_total),       0.0), 3)                   AS npxg_total,

        -- ── Carry aggregations ───────────────────────────────────────────────
        COALESCE(SUM(cs.total_carries),          0)                          AS total_carries,
        ROUND(COALESCE(SUM(cs.total_carry_distance_m), 0.0), 1)             AS total_carry_distance_m,
        COALESCE(SUM(cs.progressive_carries),    0)                          AS progressive_carries,

        -- ── Dribble aggregations ─────────────────────────────────────────────
        COALESCE(SUM(ds.total_dribbles),         0)                          AS total_dribbles,
        COALESCE(SUM(ds.dribbles_completed),     0)                          AS dribbles_completed,

        -- ── Pressure / volume ────────────────────────────────────────────────
        COALESCE(SUM(prs.total_events),          0)                          AS total_events,
        COALESCE(SUM(prs.events_under_pressure), 0)                          AS events_under_pressure

    FROM       player_appearances pa
    LEFT JOIN  primary_positions  pp  ON pa.player_id       = pp.player_id
                                     AND pa.competition_id  = pp.competition_id
                                     AND pa.season_id       = pp.season_id
    LEFT JOIN  pass_stats         ps  ON pa.match_id        = ps.match_id
                                     AND pa.player_id       = ps.player_id
    LEFT JOIN  shot_stats         ss  ON pa.match_id        = ss.match_id
                                     AND pa.player_id       = ss.player_id
    LEFT JOIN  carry_stats        cs  ON pa.match_id        = cs.match_id
                                     AND pa.player_id       = cs.player_id
    LEFT JOIN  dribble_stats      ds  ON pa.match_id        = ds.match_id
                                     AND pa.player_id       = ds.player_id
    LEFT JOIN  pressure_stats     prs ON pa.match_id        = prs.match_id
                                     AND pa.player_id       = prs.player_id
    GROUP BY
        pa.player_id, pa.player_name, pa.player_nickname,
        pa.team_id,   pa.team_name,
        pa.competition_id, pa.competition_name,
        pa.season_id, pa.season_name,
        pa.height_cm, pa.weight_kg, pa.country_name, pa.birth_date,
        pp.position_name
)

SELECT
    player_id,
    player_name,
    player_nickname,
    team_id,
    team_name,
    competition_id,
    competition_name,
    season_id,
    season_name,
    position_name,
    country_name,
    height_cm,
    weight_kg,
    birth_date,

    matches_played,
    minutes_played,
    total_events,

    -- ── Pass metrics ────────────────────────────────────────────────────────
    total_passes,
    accurate_passes,
    ROUND(
        accurate_passes * 100.0 / NULLIF(total_passes, 0),
        1
    )                                                                         AS pass_accuracy_pct,
    avg_pass_length_m,
    total_pass_distance_m,
    progressive_passes,
    crosses,
    switches,
    through_balls,
    shot_assists,
    goal_assists,

    -- ── Shot metrics ────────────────────────────────────────────────────────
    total_shots,
    shots_on_target,
    ROUND(
        shots_on_target * 100.0 / NULLIF(total_shots, 0),
        1
    )                                                                         AS shot_accuracy_pct,
    goals,
    xg_total,
    npxg_total,
    ROUND(goals - xg_total, 3)                                                AS goals_minus_xg,
    ROUND(xg_total / NULLIF(total_shots, 0), 3)                              AS xg_per_shot,

    -- ── Carry & dribble metrics ─────────────────────────────────────────────
    total_carries,
    total_carry_distance_m,
    progressive_carries,
    total_dribbles,
    dribbles_completed,
    ROUND(
        dribbles_completed * 100.0 / NULLIF(total_dribbles, 0),
        1
    )                                                                         AS dribble_success_pct,

    -- ── Pressure ────────────────────────────────────────────────────────────
    events_under_pressure,
    ROUND(
        events_under_pressure * 100.0 / NULLIF(total_events, 0),
        1
    )                                                                         AS pressure_pct,

    -- ── Per-90 metrics (the standard unit for fair comparison) ───────────────
    ROUND(goals      * 90.0 / NULLIF(minutes_played, 0), 3)                  AS goals_p90,
    ROUND(xg_total   * 90.0 / NULLIF(minutes_played, 0), 3)                  AS xg_p90,
    ROUND(npxg_total * 90.0 / NULLIF(minutes_played, 0), 3)                  AS npxg_p90,
    ROUND(total_shots  * 90.0 / NULLIF(minutes_played, 0), 2)                AS shots_p90,
    ROUND(total_passes * 90.0 / NULLIF(minutes_played, 0), 2)                AS passes_p90,
    ROUND(total_carries * 90.0 / NULLIF(minutes_played, 0), 2)               AS carries_p90,
    ROUND(progressive_passes  * 90.0 / NULLIF(minutes_played, 0), 2)         AS progressive_passes_p90,
    ROUND(progressive_carries * 90.0 / NULLIF(minutes_played, 0), 2)         AS progressive_carries_p90,
    ROUND(goal_assists * 90.0 / NULLIF(minutes_played, 0), 3)                AS goal_assists_p90

FROM   aggregated
ORDER  BY xg_total DESC, goals DESC, total_passes DESC
