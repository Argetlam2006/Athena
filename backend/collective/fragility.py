import numpy as np

from shared.schemas import PlayerProfile, SystemFragility


def get_base_averages(players: list[PlayerProfile]) -> dict[str, float]:
    caps = [
        "ball_progression",
        "chance_creation",
        "ball_security",
        "press_resistance",
        "defensive_activity",
        "attacking_threat",
    ]
    res = {}
    for c in caps:
        vals = [
            getattr(p.capability_profile, c).score
            for p in players
            if p.capability_profile and getattr(p.capability_profile, c)
        ]
        res[c] = float(np.mean(vals)) if vals else 0.0
    return res


def analyze_system_fragility(
    players: list[PlayerProfile], global_pool: list[PlayerProfile]
) -> list[SystemFragility]:
    """
    Deterministically remove every player individually to measure capability collapse.
    Calculates a Replaceability Index by finding the best available replacement
    for their position and measuring the structural deficit.
    """
    if len(players) < 2 or not global_pool:
        return []

    base_avg = get_base_averages(players)
    fragility_map = []

    # Pre-group global pool
    pool_by_pos = {}
    for p in global_pool:
        pos = p.position_group
        if pos not in pool_by_pos:
            pool_by_pos[pos] = []
        pool_by_pos[pos].append(p)

    for player in players:
        # 1. Measure Capability Loss
        squad_without_player = [p for p in players if p.player_id != player.player_id]
        new_avg = get_base_averages(squad_without_player)

        loss = {}
        total_loss = 0.0
        for k, v in base_avg.items():
            delta = v - new_avg[k]
            if delta > 0:
                loss[k] = round(delta, 1)
                total_loss += delta

        # 2. Restoration by Best Replacement
        candidates = pool_by_pos.get(player.position_group, [])

        best_restored_total = -999.0

        # O(1) calculations for candidate averages
        n_players = len(squad_without_player) + 1
        sum_without = {k: new_avg[k] * len(squad_without_player) for k in loss.keys()}

        for cand in candidates:
            if cand.player_id == player.player_id:
                continue

            restored = 0.0
            if cand.capability_profile:
                cp = cand.capability_profile
                for k in loss.keys():
                    # Handle Optional[CapabilityScore] safely
                    cap_score_obj = getattr(cp, k, None)
                    cand_val = cap_score_obj.score if cap_score_obj else 0.0

                    cand_avg_k = (sum_without[k] + cand_val) / n_players
                    cand_delta = cand_avg_k - new_avg[k]
                    restored += cand_delta

            if restored > best_restored_total:
                best_restored_total = restored

        if best_restored_total < 0:
            best_restored_total = 0.0

        structural_deficit = total_loss - best_restored_total
        if structural_deficit <= 0:
            structural_deficit = 0.1  # Floor to avoid div by zero

        replaceability_index = 100.0 / structural_deficit

        fragility_map.append(
            SystemFragility(
                player_name=player.player_name,
                player_id=player.player_id,
                capability_loss=loss,
                replaceability_index=round(replaceability_index, 2),
                structural_deficit=round(structural_deficit, 1),
            )
        )

    # Sort by structural deficit descending (most irreplaceable first)
    fragility_map.sort(key=lambda x: x.structural_deficit, reverse=True)
    return fragility_map
