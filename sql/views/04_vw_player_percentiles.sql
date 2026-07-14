/*
 * sql/views/04_vw_player_percentiles.sql
 *
 * Player percentile rankings for key performance metrics.
 * Reads directly from vw_player_summary (a downstream view).
 *
 * Techniques demonstrated:
 *   - PERCENT_RANK()  window function: true percentile rank (0.0 – 1.0)
 *   - NTILE(10)       window function: decile buckets (1 = bottom, 10 = top)
 *   - PARTITION BY    for position-relative ranking (apples to apples)
 *   - Multiple window frames in a single SELECT
 *   - Composite "overall_percentile" using weighted average of metric ranks
 *   - ROUND for presentation-ready percentile values (0 – 100 scale)
 *   - Filtering via QUALIFY equivalent — min matches in WHERE clause
 *
 * How to read:
 *   xg_p90_pct_in_position = 0.90 means the player is in the top 10%
 *   for xG/90 among players in the same position.
 *
 *   overall_percentile is a weighted composite across four key metrics
 *   and represents the player's all-round analytical standing.
 */

CREATE OR REPLACE VIEW vw_player_percentiles AS

WITH

-- ─── Only include players with meaningful sample sizes ───────────────────────
qualified AS (
    SELECT *
    FROM   vw_player_summary
    WHERE  matches_played  >= 1
      AND  total_events    >= 10   -- At least 10 events = appeared in the game
),

-- ─── Per-position percentile ranks ───────────────────────────────────────────
--   Ranking within position group ensures attackers are compared to attackers,
--   midfielders to midfielders, etc.
ranked AS (
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
        matches_played,
        minutes_played,

        -- Key metrics (shown on radar charts and in recruitment view)
        goals_p90,
        xg_p90,
        npxg_p90,
        shots_p90,
        passes_p90,
        pass_accuracy_pct,
        progressive_passes_p90,
        progressive_carries_p90,
        dribble_success_pct,
        goal_assists_p90,
        pressure_pct,

        -- Raw totals for reference
        goals,
        xg_total,
        total_passes,
        total_shots,
        total_carries,
        total_dribbles,

        -- ── Percentile ranks within position ─────────────────────────────────
        --   PERCENT_RANK returns 0.0 for the bottom player, 1.0 for the top.
        --   Multiplied by 100 and rounded for 0–100 scale.
        ROUND(PERCENT_RANK() OVER (
            PARTITION BY position_name
            ORDER     BY xg_p90 ASC NULLS FIRST
        ) * 100, 1)                                                           AS xg_p90_pct_in_position,

        ROUND(PERCENT_RANK() OVER (
            PARTITION BY position_name
            ORDER     BY goals_p90 ASC NULLS FIRST
        ) * 100, 1)                                                           AS goals_p90_pct_in_position,

        ROUND(PERCENT_RANK() OVER (
            PARTITION BY position_name
            ORDER     BY pass_accuracy_pct ASC NULLS FIRST
        ) * 100, 1)                                                           AS pass_acc_pct_in_position,

        ROUND(PERCENT_RANK() OVER (
            PARTITION BY position_name
            ORDER     BY dribble_success_pct ASC NULLS FIRST
        ) * 100, 1)                                                           AS dribble_pct_in_position,

        ROUND(PERCENT_RANK() OVER (
            PARTITION BY position_name
            ORDER     BY progressive_passes_p90 ASC NULLS FIRST
        ) * 100, 1)                                                           AS prog_pass_pct_in_position,

        ROUND(PERCENT_RANK() OVER (
            PARTITION BY position_name
            ORDER     BY progressive_carries_p90 ASC NULLS FIRST
        ) * 100, 1)                                                           AS prog_carry_pct_in_position,

        -- ── Overall percentile ranks (all positions combined) ─────────────────
        ROUND(PERCENT_RANK() OVER (
            ORDER BY xg_total ASC NULLS FIRST
        ) * 100, 1)                                                           AS xg_total_pct_overall,

        ROUND(PERCENT_RANK() OVER (
            ORDER BY goals ASC NULLS FIRST
        ) * 100, 1)                                                           AS goals_pct_overall,

        -- ── Decile buckets (1 = bottom 10%, 10 = top 10%) ────────────────────
        NTILE(10) OVER (
            ORDER BY xg_total ASC NULLS FIRST
        )                                                                     AS xg_decile,

        NTILE(10) OVER (
            PARTITION BY position_name
            ORDER     BY xg_p90 ASC NULLS FIRST
        )                                                                     AS xg_p90_decile_in_position

    FROM qualified
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
    matches_played,
    minutes_played,

    -- Metric values
    goals,
    goals_p90,
    xg_p90,
    npxg_p90,
    shots_p90,
    passes_p90,
    pass_accuracy_pct,
    progressive_passes_p90,
    progressive_carries_p90,
    dribble_success_pct,
    goal_assists_p90,
    pressure_pct,

    -- Percentile ranks within position
    xg_p90_pct_in_position,
    goals_p90_pct_in_position,
    pass_acc_pct_in_position,
    dribble_pct_in_position,
    prog_pass_pct_in_position,
    prog_carry_pct_in_position,

    -- Overall percentile ranks
    xg_total_pct_overall,
    goals_pct_overall,

    -- Decile buckets
    xg_decile,
    xg_p90_decile_in_position,

    -- ── Composite overall percentile ──────────────────────────────────────────
    --   Weighted average of four key metric percentile ranks (within position).
    --   Weights reflect the analytical importance of each metric.
    --
    --   xG/90 contribution (35%) — primary attacking efficiency
    --   Goals/90              (25%) — direct goal output
    --   Pass accuracy         (20%) — technical quality on the ball
    --   Dribble success rate  (20%) — 1v1 effectiveness
    ROUND(
        xg_p90_pct_in_position     * 0.35
        + goals_p90_pct_in_position * 0.25
        + pass_acc_pct_in_position  * 0.20
        + dribble_pct_in_position   * 0.20,
        1
    )                                                                         AS overall_percentile

FROM   ranked
ORDER  BY overall_percentile DESC NULLS LAST
