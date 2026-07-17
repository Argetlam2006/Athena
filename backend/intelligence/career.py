"""
backend/intelligence/career.py - Deterministic Career Aggregation.

Aggregates single-season PlayerFeatureVectors into a CareerFeatureVector
by accurately reverse-engineering raw counts from per-90 metrics and percentages,
aggregating them, and recalculating the final metrics.
"""

from shared.schemas import PlayerFeatureVector, ProfileType


class CareerBuilder:
    """Builds Career Feature Vectors from Season Feature Vectors."""

    @staticmethod
    def build_career_vector(seasons: list[PlayerFeatureVector]) -> PlayerFeatureVector:
        if not seasons:
            raise ValueError("Cannot build career from empty seasons list.")

        # Ensure we are aggregating Season Profiles (ProfileType.SEASON)
        if any(s.profile_type != ProfileType.SEASON for s in seasons):
            raise ValueError(
                "CareerBuilder must aggregate ProfileType.SEASON profiles only."
            )

        # Determine core identity
        player_id = seasons[0].player_id
        player_name = seasons[0].player_name

        # Most frequent position
        positions = [s.position_group for s in seasons if s.position_group != "Unknown"]
        if positions:
            position_group = max(set(positions), key=positions.count)
        else:
            position_group = "Unknown"

        secondary_positions = [
            s.secondary_position_group
            for s in seasons
            if getattr(s, "secondary_position_group", None)
        ]
        secondary_position_group = (
            max(set(secondary_positions), key=secondary_positions.count)
            if secondary_positions
            else None
        )

        confidences = [getattr(s, "position_confidence", 1.0) for s in seasons]
        position_confidence = (
            sum(confidences) / len(confidences) if confidences else 1.0
        )

        # Accumulators for raw counts
        total_minutes = 0.0
        total_matches = 0
        total_positions_played = 0

        # Ball Progression
        total_progressive_passes = 0.0
        total_progressive_carries = 0.0
        total_carry_distance = 0.0
        total_switches = 0.0

        # Chance Creation
        total_shot_assists = 0.0
        total_goal_assists = 0.0
        total_through_balls = 0.0
        total_crosses = 0.0

        # Ball Security
        total_passes = 0.0
        total_accurate_passes = 0.0
        total_dribbles = 0.0
        total_successful_dribbles = 0.0
        total_pass_length = 0.0  # weighted by total passes

        # Press Resistance
        total_events_under_pressure = 0.0
        total_events = 0.0  # for pressure_pct

        # Defensive Activity
        total_pressures = 0.0
        total_recoveries = 0.0
        total_clearances = 0.0
        total_tackles = 0.0
        total_interceptions = 0.0
        total_tackles_won = 0.0
        total_dribbled_past = 0.0
        total_errors_leading_to_shot = 0.0
        total_aerials_won = 0.0
        total_aerials_total = 0.0

        # Attacking Threat
        total_npxg = 0.0
        total_goals = 0.0
        total_xg = 0.0
        total_shots = 0.0
        total_shots_on_target = 0.0

        for s in seasons:
            mins = s.minutes_played or 0.0
            total_minutes += mins
            total_matches += s.matches_played or 0
            total_positions_played = max(
                total_positions_played, s.positions_played_count
            )

            rm = s.raw_metrics or {}

            # Helper for un-normalizing p90 if raw counts missing
            def unp90(val: float, raw_key: str, rm=rm, mins=mins) -> float:
                return rm.get(raw_key, (val / 90.0) * mins)

            # Ball Progression
            total_progressive_passes += unp90(
                s.progressive_passes_p90, "progressive_passes"
            )
            total_progressive_carries += unp90(
                s.progressive_carries_p90, "progressive_carries"
            )
            total_carry_distance += unp90(s.carry_distance_p90, "carry_distance_m")
            total_switches += unp90(s.switches_p90, "switches")

            # Chance Creation
            total_shot_assists += unp90(s.shot_assists_p90, "shot_assists")
            total_goal_assists += unp90(s.goal_assists_p90, "goal_assists")
            total_through_balls += unp90(s.through_balls_p90, "through_balls")
            total_crosses += unp90(s.crosses_p90, "crosses")

            # Ball Security
            season_passes = unp90(s.passes_p90, "total_passes")
            total_passes += season_passes

            acc_passes = rm.get(
                "accurate_passes", (s.pass_accuracy_pct / 100.0) * season_passes
            )
            total_accurate_passes += acc_passes

            pass_len = rm.get(
                "total_pass_distance_m", s.avg_pass_length_m * season_passes
            )
            total_pass_length += pass_len

            # Dribbles proxy
            proxy_dribbles = rm.get(
                "total_dribbles",
                unp90(s.progressive_carries_p90, "progressive_carries") + 1.0,
            )
            total_dribbles += proxy_dribbles
            total_successful_dribbles += rm.get(
                "successful_dribbles", (s.dribble_success_pct / 100.0) * proxy_dribbles
            )

            # Press Resistance
            season_events_under_pressure = unp90(
                s.events_under_pressure_p90, "events_under_pressure"
            )
            total_events_under_pressure += season_events_under_pressure
            if "total_events" in rm:
                total_events += rm["total_events"]
            elif s.pressure_pct > 0:
                total_events += season_events_under_pressure / (s.pressure_pct / 100.0)

            # Defensive Activity
            total_pressures += unp90(s.pressures_p90, "padj_pressures")
            total_recoveries += unp90(s.recoveries_p90, "padj_recoveries")
            total_clearances += unp90(s.clearances_p90, "padj_clearances")
            total_tackles += unp90(getattr(s, "tackles_p90", 0.0), "padj_tackles")
            total_interceptions += unp90(
                getattr(s, "interceptions_p90", 0.0), "padj_interceptions"
            )
            total_tackles_won += unp90(
                getattr(s, "tackles_won_p90", 0.0), "tackles_won"
            )
            total_dribbled_past += unp90(
                getattr(s, "dribbled_past_p90", 0.0), "dribbled_past"
            )
            total_errors_leading_to_shot += unp90(
                getattr(s, "errors_leading_to_shot_p90", 0.0), "errors_leading_to_shot"
            )
            total_aerials_won += unp90(
                getattr(s, "aerials_won_p90", 0.0), "aerials_won"
            )
            total_aerials_total += unp90(
                getattr(s, "aerials_total_p90", 0.0), "aerials_total"
            )

            # Attacking Threat
            total_npxg += unp90(s.npxg_p90, "npxg")
            total_goals += unp90(s.goals_p90, "goals")

            xg_total_season = rm.get(
                "xg", unp90(s.goals_p90, "goals") - s.goals_minus_xg
            )
            total_xg += xg_total_season

            season_shots = rm.get(
                "shots", xg_total_season / s.xg_per_shot if s.xg_per_shot > 0 else 0.0
            )
            total_shots += season_shots
            total_shots_on_target += rm.get(
                "shots_on_target", (s.shot_accuracy_pct / 100.0) * season_shots
            )

        # Re-normalize for Career
        def p90(val: float) -> float:
            return round((val * 90.0) / total_minutes, 3) if total_minutes > 0 else 0.0

        def pct(part: float, whole: float) -> float:
            return round((part / whole) * 100.0, 1) if whole > 0 else 0.0

        return PlayerFeatureVector(
            player_id=player_id,
            player_name=player_name,
            position_group=position_group,
            secondary_position_group=secondary_position_group,
            position_confidence=position_confidence,
            team_name="Multiple",
            competition="All Competitions",
            season="Career",
            profile_type=ProfileType.CAREER,
            birth_date=seasons[0].birth_date,
            matches_played=total_matches,
            minutes_played=total_minutes,
            # Ball Progression
            progressive_passes_p90=p90(total_progressive_passes),
            progressive_carries_p90=p90(total_progressive_carries),
            carry_distance_p90=p90(total_carry_distance),
            switches_p90=p90(total_switches),
            # Chance Creation
            shot_assists_p90=p90(total_shot_assists),
            goal_assists_p90=p90(total_goal_assists),
            through_balls_p90=p90(total_through_balls),
            crosses_p90=p90(total_crosses),
            # Ball Security
            pass_accuracy_pct=pct(total_accurate_passes, total_passes),
            dribble_success_pct=pct(total_successful_dribbles, total_dribbles),
            passes_p90=p90(total_passes),
            avg_pass_length_m=round(total_pass_length / total_passes, 1)
            if total_passes > 0
            else 0.0,
            # Press Resistance
            pressure_pct=pct(total_events_under_pressure, total_events),
            events_under_pressure_p90=p90(total_events_under_pressure),
            # Defensive Activity
            pressures_p90=p90(total_pressures),
            recoveries_p90=p90(total_recoveries),
            clearances_p90=p90(total_clearances),
            tackles_p90=p90(total_tackles),
            interceptions_p90=p90(total_interceptions),
            tackles_won_p90=p90(total_tackles_won),
            dribbled_past_p90=p90(total_dribbled_past),
            errors_leading_to_shot_p90=p90(total_errors_leading_to_shot),
            aerials_won_p90=p90(total_aerials_won),
            aerials_total_p90=p90(total_aerials_total),
            # Attacking Threat
            npxg_p90=p90(total_npxg),
            goals_p90=p90(total_goals),
            xg_per_shot=round(total_xg / total_shots, 3) if total_shots > 0 else 0.0,
            shot_accuracy_pct=pct(total_shots_on_target, total_shots),
            goals_minus_xg=round(total_goals - total_xg, 3),
            positions_played_count=total_positions_played,
            raw_metrics={
                "goals": int(round(total_goals)),
                "goal_assists": int(round(total_goal_assists)),
                "shot_assists": int(round(total_shot_assists)),
                "total_shots": int(round(total_shots)),
                "shots_on_target": int(round(total_shots_on_target)),
                "total_passes": int(round(total_passes)),
                "accurate_passes": int(round(total_accurate_passes)),
                "progressive_passes": int(round(total_progressive_passes)),
                "progressive_carries": int(round(total_progressive_carries)),
                "total_dribbles": int(round(total_dribbles)),
                "dribbles_completed": int(round(total_successful_dribbles)),
                "pressures": int(round(total_pressures)),
                "ball_recoveries": int(round(total_recoveries)),
                "clearances": int(round(total_clearances)),
                "tackles": int(round(total_tackles)),
                "interceptions": int(round(total_interceptions)),
                "aerials_won": int(round(total_aerials_won)),
                "aerials_total": int(round(total_aerials_total)),
                "xg_total": round(total_xg, 3),
                "npxg_total": round(total_npxg, 3),
            },
        )
