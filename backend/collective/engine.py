from backend.collective.bottlenecks import identify_bottlenecks
from backend.collective.fragility import analyze_system_fragility
from backend.collective.identity import generate_collective_identity
from backend.collective.structure import compute_capability_concentration
from shared.schemas import CollectiveProfile, PlayerProfile


def build_collective_profile(
    team_id: int,
    team_name: str,
    competition: str,
    season: str,
    players: list[PlayerProfile],
    global_pool: list[PlayerProfile],
) -> CollectiveProfile:
    """
    Orchestrates the Collective Intelligence Engine pipeline.
    Transforms standard team averages into a deterministic CollectiveSystem model.
    """

    squad_size = len(players)
    valid_ages = [p.age_years for p in players if p.age_years]
    avg_age = round(sum(valid_ages) / len(valid_ages), 1) if valid_ages else None

    # 1. Dynamic Identity
    identity = generate_collective_identity(players, global_pool)

    # 2. Structural Concentration (HHI)
    concentration = compute_capability_concentration(players)

    # Compute average capabilities
    snake_caps = {
        "ball_progression": 0.0,
        "chance_creation": 0.0,
        "ball_security": 0.0,
        "press_resistance": 0.0,
        "defensive_activity": 0.0,
        "attacking_threat": 0.0,
    }
    valid_counts = dict.fromkeys(snake_caps.keys(), 0)

    for p in players:
        if p.capability_profile:
            caps = p.capability_profile
            for cap_name in snake_caps.keys():
                cap_obj = getattr(caps, cap_name)
                if cap_obj:
                    snake_caps[cap_name] += cap_obj.score
                    valid_counts[cap_name] += 1

    for k in snake_caps.keys():
        if valid_counts[k] > 0:
            snake_caps[k] = round(snake_caps[k] / valid_counts[k], 1)

    # 3. Bottleneck Analysis
    bottlenecks = identify_bottlenecks(snake_caps)

    # 4. System Fragility & Replaceability
    fragility_map = analyze_system_fragility(players, global_pool)

    return CollectiveProfile(
        team_id=team_id,
        team_name=team_name,
        competition=competition,
        season=season,
        squad_size=squad_size,
        avg_age=avg_age,
        identity=identity,
        concentration=concentration,
        fragility_map=fragility_map,
        bottlenecks=bottlenecks,
        avg_capabilities=snake_caps,
    )


def compute_team_grade(team_profile: CollectiveProfile) -> str:
    """
    Deterministically computes a team's capability grade based on its average capabilities.
    """
    if not team_profile or not team_profile.avg_capabilities:
        return "N/A"

    caps = [v for v in team_profile.avg_capabilities.values() if v > 0.0]
    if not caps:
        return "N/A"

    avg = sum(caps) / len(caps)

    if avg >= 85:
        return "A+"
    elif avg >= 80:
        return "A"
    elif avg >= 75:
        return "A-"
    elif avg >= 70:
        return "B+"
    elif avg >= 65:
        return "B"
    elif avg >= 60:
        return "B-"
    elif avg >= 55:
        return "C+"
    elif avg >= 50:
        return "C"
    elif avg >= 45:
        return "C-"
    return "D"
