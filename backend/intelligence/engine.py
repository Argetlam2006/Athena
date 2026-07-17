"""
backend/intelligence/engine.py - Football Intelligence Engine Facade.

The primary entry point for transforming statistical feature vectors into
intelligence profiles (PlayerProfile, TeamProfile).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from backend.collective.engine import build_collective_profile
from backend.intelligence.archetypes import assign_archetypes
from backend.intelligence.player import build_player_profile
from backend.intelligence.signals import generate_decision_signals
from shared.schemas import CollectiveProfile, PlayerFeatureVector, PlayerProfile

logger = logging.getLogger(__name__)


class FootballIntelligenceEngine:
    """
    Facade for the intelligence transformation layer.
    """

    def __init__(self, competition_matches: int = 38):
        self.competition_matches = competition_matches

    def process_cohort(
        self, vectors: Sequence[PlayerFeatureVector]
    ) -> list[PlayerProfile]:
        """
        Process a cohort of players (e.g. all players in a competition/season).
        Dynamically computes percentiles within position groups and generates profiles.
        Uses O(N log N) vectorized pandas ranking for deterministic output.
        """
        if not vectors:
            return []

        import pandas as pd

        # Convert vectors to DataFrame for vectorized processing
        df = pd.DataFrame([vars(v) for v in vectors])

        # Identify numeric metrics to normalize
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        for excluded in [
            "player_id",
            "minutes_played",
            "matches_played",
            "positions_played_count",
        ]:
            if excluded in numeric_cols:
                numeric_cols.remove(excluded)

        # Apply Bayesian Sample Size Normalisation (Shrinkage)
        from shared.constants import MIN_SAMPLE_MINUTES, SHRINKAGE_TARGET_MINUTES

        if "minutes_played" in df.columns:
            weight = (
                (df["minutes_played"] - MIN_SAMPLE_MINUTES)
                / (SHRINKAGE_TARGET_MINUTES - MIN_SAMPLE_MINUTES)
            ).clip(0.0, 1.0)
            for col in numeric_cols:
                cohort_means = df.groupby(["profile_type", "position_group"])[
                    col
                ].transform("mean")
                df[col] = (df[col] * weight) + (cohort_means * (1.0 - weight))

        # Vectorized percentile rank computation grouped by profile_type and position_group
        # (rank - 0.5) / N * 100 matches the explicit tie-splitting logic exactly.
        ranks_df = (
            df.groupby(["profile_type", "position_group"])[numeric_cols]
            .transform(
                lambda x: ((x.rank(method="average") - 0.5) / len(x) * 100.0).clip(
                    0.0, 100.0
                )
            )
            .fillna(0.0)
        )

        profiles: list[PlayerProfile] = []

        # Reconstruct profiles
        for i, vec in enumerate(vectors):
            # Extract normalized values for this player
            normalized = ranks_df.iloc[i].to_dict()

            # Build the profile
            profile = build_player_profile(vec, normalized, self.competition_matches)

            # Generate decision signals
            generate_decision_signals(profile, normalized)
            profile.similar_players = []  # Placeholder

            profiles.append(profile)

        # Derives playing style from positional cohort (Layer 2)
        assign_archetypes(profiles)

        import math
        from collections import defaultdict

        from backend.intelligence.player import compute_overall_rating
        from backend.intelligence.roles import get_role_family
        from shared.schemas import RatingPresentation

        # Group by role family
        cohorts = defaultdict(list)
        for p in profiles:
            arch = p.display_archetype
            role_family = get_role_family(arch)
            p.role_family = role_family  # We can dynamically attach this for processing, or it can just be inferred

            if p.capability_profile:
                cap_scores = {
                    "ball_progression": p.capability_profile.ball_progression,
                    "chance_creation": p.capability_profile.chance_creation,
                    "ball_security": p.capability_profile.ball_security,
                    "press_resistance": p.capability_profile.press_resistance,
                    "defensive_activity": p.capability_profile.defensive_activity,
                    "attacking_threat": p.capability_profile.attacking_threat,
                }
                # Compute role-aware overall rating
                overall = compute_overall_rating(cap_scores, role_family)
                p.capability_profile.overall_rating = overall
                cohorts[role_family].append(p)

        # 4. Compute Rating Presentation dynamically per cohort
        for _role_family, cohort_players in cohorts.items():
            raw_ratings = [
                p.capability_profile.overall_rating
                for p in cohort_players
                if p.capability_profile
                and p.capability_profile.overall_rating is not None
            ]
            if raw_ratings:
                mean_rating = sum(raw_ratings) / len(raw_ratings)
                variance = sum((r - mean_rating) ** 2 for r in raw_ratings) / len(
                    raw_ratings
                )
                std_rating = math.sqrt(variance) if variance > 0 else 1.0

                for p in cohort_players:
                    if (
                        p.capability_profile
                        and p.capability_profile.overall_rating is not None
                    ):
                        raw = p.capability_profile.overall_rating
                        z_score = (raw - mean_rating) / std_rating

                        # Percentile from standard normal
                        percentile = (
                            (1.0 + math.erf(z_score / math.sqrt(2.0))) / 2.0 * 100.0
                        )

                        # Map to 0-100 scale using calibration curve
                        import numpy as np

                        percentiles = [
                            0.0,
                            50.0,
                            75.0,
                            90.0,
                            95.0,
                            98.0,
                            99.0,
                            99.5,
                            99.9,
                            100.0,
                        ]
                        ratings = [
                            40.0,
                            70.0,
                            78.0,
                            84.0,
                            88.0,
                            92.0,
                            94.0,
                            96.0,
                            99.0,
                            99.9,
                        ]

                        display = np.interp(percentile, percentiles, ratings)
                        display = max(0.0, min(99.9, display))

                        p.rating_presentation = RatingPresentation(
                            raw_rating=raw,
                            display_rating=round(float(display), 1),
                            rating_percentile=round(percentile, 1),
                            z_score=round(z_score, 2),
                        )

        return profiles

    def process_team(
        self,
        team_id: int,
        team_name: str,
        competition: str,
        season: str,
        players: Sequence[PlayerProfile],
        global_pool: Sequence[PlayerProfile],
    ) -> CollectiveProfile:
        """
        Aggregate a squad of PlayerProfiles into a CollectiveProfile.
        """
        return build_collective_profile(
            team_id, team_name, competition, season, list(players), list(global_pool)
        )

    def process_all_teams(
        self, players: Sequence[PlayerProfile]
    ) -> list[CollectiveProfile]:
        """
        Groups players by team and builds CollectiveProfiles for all teams.
        """
        teams_data: dict[str, dict] = {}
        for p in players:
            key = p.team_name
            if not key:
                continue
            if key not in teams_data:
                teams_data[key] = {
                    "team_name": p.team_name,
                    "competition": p.competition,
                    "season": p.season,
                    "players": [],
                }
            teams_data[key]["players"].append(p)

        profiles = []
        for team_name, data in teams_data.items():
            team_id = hash(team_name) & 0x7FFFFFFF
            profiles.append(
                self.process_team(
                    team_id=team_id,
                    team_name=data["team_name"],
                    competition=data["competition"],
                    season=data["season"],
                    players=data["players"],
                    global_pool=players,
                )
            )
        return sorted(profiles, key=lambda x: x.team_name)
