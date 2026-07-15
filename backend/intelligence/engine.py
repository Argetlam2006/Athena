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
        Uses O(N log N) vectorized pandas ranking for deterministic output.
        """
        if not vectors:
            return []

        import pandas as pd

        # Convert vectors to DataFrame for vectorized processing
        df = pd.DataFrame([vars(v) for v in vectors])
        
        # Identify numeric metrics to normalize
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if 'player_id' in numeric_cols:
            numeric_cols.remove('player_id')

        # Vectorized percentile rank computation grouped by position_group
        # (rank - 0.5) / N * 100 matches the explicit tie-splitting logic exactly.
        ranks_df = df.groupby('position_group')[numeric_cols].transform(
            lambda x: ((x.rank(method='average') - 0.5) / len(x) * 100.0).clip(0.0, 100.0)
        ).fillna(0.0)

        profiles: list[PlayerProfile] = []

        # Reconstruct profiles
        for i, vec in enumerate(vectors):
            # Extract normalized values for this player
            normalized = ranks_df.iloc[i].to_dict()

            # Build the profile
            profile = build_player_profile(
                vec, normalized, self.competition_matches
            )

            # Generate decision signals
            generate_decision_signals(profile, normalized)
            profile.similar_players = []  # Placeholder

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
