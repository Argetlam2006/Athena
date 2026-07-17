from shared.schemas import CapabilityConcentration, PlayerProfile


def compute_capability_concentration(players: list[PlayerProfile]) -> list[CapabilityConcentration]:
    """
    Calculate Herfindahl-Hirschman Index (HHI) for capability concentration.
    HHI > 2500 generally indicates a highly concentrated/centralized system.
    """
    caps = ["ball_progression", "chance_creation", "ball_security",
            "press_resistance", "defensive_activity", "attacking_threat"]

    results = []

    for c in caps:
        total = 0.0
        contributions = []

        for p in players:
            if p.capability_profile:
                val = getattr(p.capability_profile, c, None)
                score = val.score if val else 0.0
                if score > 0:
                    contributions.append((p.player_name, score))
                    total += score

        if total == 0:
            results.append(CapabilityConcentration(c, 0.0, False, []))
            continue

        # Calculate market shares (percentages)
        shares = [(name, (score / total) * 100) for name, score in contributions]

        # HHI is sum of squares of market shares
        hhi = sum(share ** 2 for _, share in shares)

        # Sort by contribution
        shares.sort(key=lambda x: x[1], reverse=True)
        top_3 = shares[:3]

        # Vulnerability threshold: HHI > 2500 means over-centralized
        is_centralized = hhi > 2500

        results.append(CapabilityConcentration(
            capability_name=c,
            hhi_score=round(hhi, 1),
            is_over_centralized=is_centralized,
            top_contributors=[(name, round(share, 1)) for name, share in top_3]
        ))

    return results
