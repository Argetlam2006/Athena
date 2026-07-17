"""
backend/intelligence/counterfactual.py — Counterfactual Analysis Engine

Simulates team capability shifts by adding or removing players.
The backbone of Recruitment, Squad Planning, and Dependency Analysis.
"""


from backend.intelligence.team import aggregate_capabilities
from shared.schemas import CollectiveProfile, CounterfactualResult, PlayerProfile


class CounterfactualEngine:

    @staticmethod
    def simulate_removal(
        team: CollectiveProfile, squad: list[PlayerProfile], player_to_remove: PlayerProfile
    ) -> list[CounterfactualResult]:
        """
        Simulate the impact of removing a player from the squad.
        Returns a list of CounterfactualResult objects detailing the capability deltas.
        """
        original_agg = aggregate_capabilities(squad)

        # Create a new squad excluding the player
        # We match by player_id
        new_squad = [p for p in squad if p.player_id != player_to_remove.player_id]

        if not new_squad:
            return [] # Can't simulate an empty squad

        new_agg = aggregate_capabilities(new_squad)

        results = []
        for cap, original_val in original_agg.items():
            if original_val > 0:
                new_val = new_agg.get(cap, 0.0)
                results.append(
                    CounterfactualResult(
                        capability_name=cap,
                        original_score=original_val,
                        new_score=new_val
                    )
                )

        return sorted(results, key=lambda x: x.delta) # Most negative delta first (biggest loss)

    @staticmethod
    def simulate_addition(
        team: CollectiveProfile, squad: list[PlayerProfile], player_to_add: PlayerProfile
    ) -> list[CounterfactualResult]:
        """
        Simulate the impact of adding a player to the squad.
        Returns a list of CounterfactualResult objects detailing the capability deltas.
        """
        original_agg = aggregate_capabilities(squad)

        # Create a new squad including the player
        new_squad = list(squad)
        # Avoid duplicate additions if they are already in the squad
        if not any(p.player_id == player_to_add.player_id for p in squad):
            new_squad.append(player_to_add)

        new_agg = aggregate_capabilities(new_squad)

        results = []
        for cap, new_val in new_agg.items():
            original_val = original_agg.get(cap, 0.0)
            if original_val > 0 or new_val > 0:
                results.append(
                    CounterfactualResult(
                        capability_name=cap,
                        original_score=original_val,
                        new_score=new_val
                    )
                )

        return sorted(results, key=lambda x: x.delta, reverse=True) # Most positive delta first (biggest gain)

