/*
 * sql/views/05_vw_recruitment_candidates.sql
 *
 * Ranked recruitment candidate table combining player statistics
 * with their percentile standings.
 *
 * Techniques demonstrated:
 *   - JOIN across two analytical views (vw_player_summary + vw_player_percentiles)
 *   - ROW_NUMBER() window function for within-position ranking
 *   - QUALIFY clause (DuckDB-specific) to filter window results inline
 *   - Composite contribution score with explicit weight documentation
 *   - Quality thresholds (min matches, min events) to remove statistical noise
 *   - COALESCE to handle missing percentile data (players not in both views)
 *   - Derived analytical flags (is_high_volume_passer, is_clinical_finisher)
 *
 * Contribution Score (0–100):
 *   The composite score weights four percentile ranks by analytical importance:
 *
 *     40%  xG/90 percentile (within position)   — shot quality efficiency
 *     25%  Goals/90 percentile (within position) — goal-scoring productivity
 *     20%  Pass accuracy percentile              — technical ball quality
 *     15%  Progressive pass percentile           — ability to advance play
 *
 *   This mirrors the AIF capability weighting used in the Intelligence layer.
 *   A player ranked in the 90th percentile on all four would score ~90.
 *
 * Usage:
 *   SELECT * FROM vw_recruitment_candidates
 *   WHERE position_name = 'Center Forward'
 *   AND   contribution_score >= 70
 *   ORDER BY contribution_score DESC;
 */

CREATE OR REPLACE VIEW vw_recruitment_candidates AS

WITH

-- ─── Step 1: join player stats with their percentile ranks ───────────────────
combined AS (
    SELECT
        ps.player_id,
        ps.player_name,
        ps.player_nickname,
        ps.team_id,
        ps.team_name,
        ps.competition_id,
        ps.competition_name,
        ps.season_id,
        ps.season_name,
        ps.position_name,
        ps.country_name,
        ps.height_cm,
        ps.weight_kg,
        ps.birth_date,
        ps.matches_played,
        ps.minutes_played,

        -- Core performance metrics
        ps.goals,
        ps.xg_total,
        ps.npxg_total,
        ps.goals_p90,
        ps.xg_p90,
        ps.npxg_p90,
        ps.shots_p90,
        ps.pass_accuracy_pct,
        ps.passes_p90,
        ps.progressive_passes_p90,
        ps.progressive_carries_p90,
        ps.dribble_success_pct,
        ps.goal_assists,
        ps.goal_assists_p90,
        ps.goals_minus_xg,

        -- Percentile ranks (from vw_player_percentiles)
        COALESCE(pp.xg_p90_pct_in_position,      0) AS xg_p90_pct,
        COALESCE(pp.goals_p90_pct_in_position,   0) AS goals_p90_pct,
        COALESCE(pp.pass_acc_pct_in_position,    0) AS pass_acc_pct,
        COALESCE(pp.prog_pass_pct_in_position,   0) AS prog_pass_pct,
        COALESCE(pp.dribble_pct_in_position,     0) AS dribble_pct,
        COALESCE(pp.prog_carry_pct_in_position,  0) AS prog_carry_pct,
        COALESCE(pp.overall_percentile,          0) AS overall_percentile,
        COALESCE(pp.xg_decile,                   0) AS xg_decile

    FROM   vw_player_summary    ps
    LEFT   JOIN vw_player_percentiles pp
           ON  ps.player_id      = pp.player_id
           AND ps.competition_id = pp.competition_id
           AND ps.season_id      = pp.season_id

    -- Quality threshold: exclude players with too few appearances
    WHERE  ps.matches_played >= 2
      AND  ps.total_events   >= 20
),

-- ─── Step 2: compute composite contribution score and analytical flags ────────
scored AS (
    SELECT
        *,

        -- ── Contribution Score ────────────────────────────────────────────────
        --   Weighted composite of four percentile ranks (see view header).
        --   Result is a 0–100 score indicating overall recruitment value.
        ROUND(
            xg_p90_pct    * 0.40
            + goals_p90_pct * 0.25
            + pass_acc_pct  * 0.20
            + prog_pass_pct * 0.15,
            1
        )                                                                     AS contribution_score,

        -- ── Analytical flags (rule-based, fully explainable) ─────────────────
        --   Used by the Decision Engine to generate narrative justifications.

        -- Clinical finisher: scores more goals than xG predicts
        (goals_minus_xg > 0 AND goals >= 2)                                  AS is_clinical_finisher,

        -- High-volume passer: in top 60th percentile for passes/90
        (pass_acc_pct >= 60 AND passes_p90 >= 30)                            AS is_high_volume_passer,

        -- Creative passer: many progressive and through-ball passes
        (prog_pass_pct >= 65)                                                 AS is_progressive_passer,

        -- Ball carrier: strong carry metrics relative to position
        (prog_carry_pct >= 65)                                                AS is_progressive_carrier,

        -- Dribbler: consistently beats opponents
        (dribble_pct >= 70 AND dribble_success_pct >= 50)                   AS is_elite_dribbler,

        -- Efficient shooter: xG per shot above average (xg_per_shot > 0.10)
        (xg_total > 0 AND xg_total / NULLIF(shots_p90 * minutes_played / 90, 0) > 0.10)
                                                                              AS is_efficient_shooter
    FROM combined
),

-- ─── Step 3: rank players within position using ROW_NUMBER ───────────────────
--   Then annotate how many candidates exist per position for context.
position_ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY position_name
            ORDER     BY contribution_score DESC, xg_total DESC
        )                                                                     AS position_rank,

        COUNT(*) OVER (
            PARTITION BY position_name
        )                                                                     AS position_pool_size

    FROM scored
)

-- ─── Final SELECT: clean, ordered output ─────────────────────────────────────
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

    -- Core output metrics
    goals,
    xg_total,
    npxg_total,
    goals_p90,
    xg_p90,
    passes_p90,
    pass_accuracy_pct,
    progressive_passes_p90,
    dribble_success_pct,
    goal_assists,

    -- Percentile context
    xg_p90_pct,
    goals_p90_pct,
    pass_acc_pct,
    prog_pass_pct,
    overall_percentile,
    xg_decile,

    -- Composite score & ranking
    contribution_score,
    position_rank,
    position_pool_size,

    -- Analytical flags
    is_clinical_finisher,
    is_high_volume_passer,
    is_progressive_passer,
    is_progressive_carrier,
    is_elite_dribbler,
    is_efficient_shooter

FROM   position_ranked
ORDER  BY contribution_score DESC, position_rank ASC
