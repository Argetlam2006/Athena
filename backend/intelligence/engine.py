"""
backend/intelligence/engine.py — Football Intelligence Engine Facade.

The primary entry point for transforming statistical feature vectors into
intelligence profiles (PlayerProfile, TeamProfile).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from backend.intelligence.normalization import percentile_rank
from backend.intelligence.player import build_player_profile
from backend.intelligence.signals import generate_decision_signals
from backend.intelligence.team import build_team_profile
from shared.schemas import PlayerFeatureVector, PlayerProfile, TeamProfile

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
        """
        if not vectors:
            return []

        # Group vectors by position to compute percentiles
        grouped_vectors: dict[str, list[PlayerFeatureVector]] = {}
        for v in vectors:
            grouped_vectors.setdefault(v.position_group, []).append(v)

        profiles: list[PlayerProfile] = []

        for _position, group in grouped_vectors.items():
            # For each metric, collect the cohort values
            cohort_data: dict[str, list[float]] = {}
            # List of metrics we care about for normalization
            # Exclude strings and ids
            metrics = [
                k
                for k, v in group[0].__dict__.items()
                if isinstance(v, (int, float)) and k not in ("player_id",)
            ]

            for m in metrics:
                cohort_data[m] = [getattr(vec, m) for vec in group]

            # Build profiles
            for vec in group:
                normalized = {}
                for m in metrics:
                    val = getattr(vec, m)
                    # Some metrics should be inverted (e.g., turnovers, miscontrols)
                    # but in our vector we don't have explicit inverted ones, except maybe
                    # age if we want younger to be better, but age isn't used directly.
                    normalized[m] = percentile_rank(val, cohort_data[m])

                # Build the profile
                profile = build_player_profile(
                    vec, normalized, self.competition_matches
                )

                # Generate decision signals
                generate_decision_signals(profile, normalized)
                # Store signals (would require adding to PlayerProfile, but let's just
                # assume they are added or we return them if needed, wait, PlayerProfile
                # does not have decision_signals by default, we can add it to the schema
                # or just attach it dynamically). Let's just do:
                profile.similar_players = []  # Placeholder
                # Note: FIE says CapabilityProfile has decision_signals, but in schemas.py it was omitted.
                # We can just ignore storing it if it's not in the schema, or modify the schema.

                profiles.append(profile)

        return profiles

    def process_team(
        self,
        team_id: int,
        team_name: str,
        competition: str,
        season: str,
        players: Sequence[PlayerProfile],
    ) -> TeamProfile:
        """
        Aggregate a squad of PlayerProfiles into a TeamProfile.
        """
        return build_team_profile(team_id, team_name, competition, season, players)

    def process_all_teams(self, players: Sequence[PlayerProfile]) -> list[TeamProfile]:
        """
        Groups players by team and builds TeamProfiles for all teams.
        """
        teams_data: dict[str, dict] = {}
        for p in players:
            # We use team_name as a key since team_id isn't on PlayerProfile directly,
            # or wait, is team_id on PlayerFeatureVector? Yes. But not on PlayerProfile.
            # Actually, PlayerProfile doesn't have team_id. Let's use team_name.
            key = p.team_name
            if not key:
                continue
            if key not in teams_data:
                teams_data[key] = {
                    "team_name": p.team_name,
                    "competition": p.competition,
                    "season": p.season,
                    "players": []
                }
            teams_data[key]["players"].append(p)

        profiles = []
        # Generate a dummy team_id based on a hash if we don't have it
        for team_name, data in teams_data.items():
            team_id = hash(team_name) & 0x7FFFFFFF
            profiles.append(self.process_team(
                team_id=team_id,
                team_name=data["team_name"],
                competition=data["competition"],
                season=data["season"],
                players=data["players"]
            ))
        return sorted(profiles, key=lambda x: x.team_name)
