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

-- ─── CTE 4b: defensive statistics per player per match ─────────────────────────
defensive_stats AS (
    SELECT
        match_id,
        player_id,
        COUNT(*) FILTER (WHERE type_name = 'Pressure')                       AS pressures,
        COUNT(*) FILTER (WHERE type_name = 'Ball Recovery')                  AS ball_recoveries,
        COUNT(*) FILTER (WHERE type_name = 'Clearance')                      AS clearances,
        COUNT(*) FILTER (WHERE type_name = 'Duel' AND duel_type = 'Tackle')  AS tackles,
        COUNT(*) FILTER (WHERE type_name = 'Interception')                   AS interceptions,
        COUNT(*) FILTER (WHERE type_name = 'Duel' AND duel_type = 'Tackle' AND duel_outcome IN ('Won', 'Success In Play', 'Success Out')) AS tackles_won,
        COUNT(*) FILTER (WHERE type_name = 'Dribbled Past')                  AS dribbled_past,
        COUNT(*) FILTER (WHERE type_name = 'Error')                          AS errors_leading_to_shot,
        COUNT(*) FILTER (WHERE aerial_won = true)                            AS aerials_won,
        COUNT(*) FILTER (WHERE aerial_won = true OR (type_name = 'Duel' AND duel_type = 'Aerial Lost')) AS aerials_total
    FROM   events
    WHERE  type_name IN ('Pressure', 'Ball Recovery', 'Clearance', 'Duel', 'Interception', 'Dribbled Past', 'Error', 'Pass', 'Shot', 'Miscontrol')
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

-- ─── CTE 6: event-derived minutes logic ──────────────────────────────────────────
match_durations AS (
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
),

-- ─── CTE 7: player appearances — join lineups with match context ──────────────
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
        m.season_name,
        CASE 
            WHEN l.starting_position IS NOT NULL THEN COALESCE(so.sub_off_minute, md.max_minute)
            ELSE CASE WHEN sp.first_event_minute IS NOT NULL THEN md.max_minute - sp.first_event_minute ELSE 0 END
        END AS minutes_played
    FROM   lineups l
    JOIN   matches m ON l.match_id = m.match_id
    LEFT JOIN match_durations md ON l.match_id = md.match_id
    LEFT JOIN substitution_off so ON l.match_id = so.match_id AND l.player_id = so.player_id
    LEFT JOIN substitution_on_proxy sp ON l.match_id = sp.match_id AND l.player_id = sp.player_id
    WHERE  l.starting_position IS NOT NULL
       OR  sp.first_event_minute IS NOT NULL
),

-- ─── CTE 8: primary position — the most common starting position for each
--           player in each competition-season (uses DuckDB's QUALIFY clause)
position_counts AS (
    SELECT
        player_id,
        competition_id,
        season_id,
        starting_position     AS position_name,
        COUNT(*)              AS pos_count,
        SUM(COUNT(*)) OVER (PARTITION BY player_id, competition_id, season_id) AS total_starts,
        ROW_NUMBER() OVER (
            PARTITION BY player_id, competition_id, season_id
            ORDER     BY COUNT(*) DESC
        ) AS pos_rank,
        COUNT(*) OVER (PARTITION BY player_id, competition_id, season_id) AS positions_played_count
    FROM   player_appearances
    WHERE  starting_position IS NOT NULL
    GROUP  BY player_id, competition_id, season_id, starting_position
),
primary_positions AS (
    SELECT
        p1.player_id,
        p1.competition_id,
        p1.season_id,
        p1.position_name,
        p2.position_name AS secondary_position_name,
        ROUND(CAST(p1.pos_count AS FLOAT) / CAST(p1.total_starts AS FLOAT), 2) AS position_confidence,
        p1.positions_played_count
    FROM position_counts p1
    LEFT JOIN position_counts p2
        ON p1.player_id = p2.player_id
        AND p1.competition_id = p2.competition_id
        AND p1.season_id = p2.season_id
        AND p2.pos_rank = 2
    WHERE p1.pos_rank = 1
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
        pp.secondary_position_name,
        COALESCE(pp.position_confidence, 1.0)                                AS position_confidence,
        COALESCE(pp.positions_played_count, 1)                               AS positions_played_count,

        -- Appearance volume
        COUNT(DISTINCT pa.match_id)                                          AS matches_played,
        
        -- Deterministically reconstructed minutes
        SUM(pa.minutes_played)                                               AS minutes_played,

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

        -- ── Defensive aggregations ───────────────────────────────────────────
        COALESCE(SUM(def.pressures),             0)                          AS pressures,
        COALESCE(SUM(def.ball_recoveries),       0)                          AS ball_recoveries,
        COALESCE(SUM(def.clearances),            0)                          AS clearances,
        COALESCE(SUM(def.tackles),               0)                          AS tackles,
        COALESCE(SUM(def.tackles_won),           0)                          AS tackles_won,
        COALESCE(SUM(def.interceptions),         0)                          AS interceptions,
        COALESCE(SUM(def.dribbled_past),         0)                          AS dribbled_past,
        COALESCE(SUM(def.errors_leading_to_shot),0)                          AS errors_leading_to_shot,
        COALESCE(SUM(def.aerials_won),           0)                          AS aerials_won,
        COALESCE(SUM(def.aerials_total),         0)                          AS aerials_total,

        -- Possession-adjusted defensive aggregations
        COALESCE(SUM(def.pressures * (2.0 / (1.0 + EXP(-0.1 * (
            CASE WHEN pa.team_name = vms.home_team_name THEN vms.home_possession_pct ELSE vms.away_possession_pct END - 50.0
        ))))), 0)                                                            AS padj_pressures,
        COALESCE(SUM(def.ball_recoveries * (2.0 / (1.0 + EXP(-0.1 * (
            CASE WHEN pa.team_name = vms.home_team_name THEN vms.home_possession_pct ELSE vms.away_possession_pct END - 50.0
        ))))), 0)                                                            AS padj_recoveries,
        COALESCE(SUM(def.clearances * (2.0 / (1.0 + EXP(-0.1 * (
            CASE WHEN pa.team_name = vms.home_team_name THEN vms.home_possession_pct ELSE vms.away_possession_pct END - 50.0
        ))))), 0)                                                            AS padj_clearances,
        COALESCE(SUM(def.tackles * (2.0 / (1.0 + EXP(-0.1 * (
            CASE WHEN pa.team_name = vms.home_team_name THEN vms.home_possession_pct ELSE vms.away_possession_pct END - 50.0
        ))))), 0)                                                            AS padj_tackles,
        COALESCE(SUM(def.interceptions * (2.0 / (1.0 + EXP(-0.1 * (
            CASE WHEN pa.team_name = vms.home_team_name THEN vms.home_possession_pct ELSE vms.away_possession_pct END - 50.0
        ))))), 0)                                                            AS padj_interceptions,

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
    LEFT JOIN  defensive_stats    def ON pa.match_id        = def.match_id
                                     AND pa.player_id       = def.player_id
    LEFT JOIN  pressure_stats     prs ON pa.match_id        = prs.match_id
                                     AND pa.player_id       = prs.player_id
    LEFT JOIN  vw_match_summary   vms ON pa.match_id        = vms.match_id
    GROUP BY
        pa.player_id, pa.player_name, pa.player_nickname,
        pa.team_id,   pa.team_name,
        pa.competition_id, pa.competition_name,
        pa.season_id, pa.season_name,
        pa.height_cm, pa.weight_kg, pa.country_name, pa.birth_date,
        pp.position_name, pp.secondary_position_name, pp.position_confidence, pp.positions_played_count
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
    secondary_position_name,
    position_confidence,
    country_name,
    height_cm,
    weight_kg,
    birth_date,
    positions_played_count,

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

    -- ── Defensive metrics ───────────────────────────────────────────────────
    pressures,
    ball_recoveries,
    clearances,
    tackles,
    tackles_won,
    interceptions,
    dribbled_past,
    errors_leading_to_shot,
    aerials_won,
    aerials_total,
    padj_pressures,
    padj_recoveries,
    padj_clearances,
    padj_tackles,
    padj_interceptions,

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
    ROUND(total_carry_distance_m * 90.0 / NULLIF(minutes_played, 0), 1)      AS carry_distance_p90,
    ROUND(progressive_passes  * 90.0 / NULLIF(minutes_played, 0), 2)         AS progressive_passes_p90,
    ROUND(progressive_carries * 90.0 / NULLIF(minutes_played, 0), 2)         AS progressive_carries_p90,
    ROUND(switches * 90.0 / NULLIF(minutes_played, 0), 3)                    AS switches_p90,
    ROUND(crosses * 90.0 / NULLIF(minutes_played, 0), 3)                     AS crosses_p90,
    ROUND(through_balls * 90.0 / NULLIF(minutes_played, 0), 3)               AS through_balls_p90,
    ROUND(shot_assists * 90.0 / NULLIF(minutes_played, 0), 3)                AS shot_assists_p90,
    ROUND(goal_assists * 90.0 / NULLIF(minutes_played, 0), 3)                AS goal_assists_p90,
    ROUND(padj_pressures * 90.0 / NULLIF(minutes_played, 0), 2)              AS pressures_p90,
    ROUND(padj_recoveries * 90.0 / NULLIF(minutes_played, 0), 2)             AS recoveries_p90,
    ROUND(padj_clearances * 90.0 / NULLIF(minutes_played, 0), 2)             AS clearances_p90,
    ROUND(padj_tackles * 90.0 / NULLIF(minutes_played, 0), 2)                AS tackles_p90,
    ROUND(padj_interceptions * 90.0 / NULLIF(minutes_played, 0), 2)          AS interceptions_p90,
    ROUND(tackles_won * 90.0 / NULLIF(minutes_played, 0), 2)                 AS tackles_won_p90,
    ROUND(dribbled_past * 90.0 / NULLIF(minutes_played, 0), 2)               AS dribbled_past_p90,
    ROUND(errors_leading_to_shot * 90.0 / NULLIF(minutes_played, 0), 3)      AS errors_leading_to_shot_p90,
    ROUND(aerials_won * 90.0 / NULLIF(minutes_played, 0), 2)                 AS aerials_won_p90,
    ROUND(aerials_total * 90.0 / NULLIF(minutes_played, 0), 2)               AS aerials_total_p90,
    ROUND(events_under_pressure * 90.0 / NULLIF(minutes_played, 0), 2)       AS events_under_pressure_p90

FROM   aggregated
ORDER  BY xg_total DESC, goals DESC, total_passes DESC
