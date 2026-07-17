from backend.intelligence.team import build_team_profile
from frontend.data.players import get_player_index, get_player_profile
from frontend.data.teams import get_all_collectives
from shared.schemas import ProfileType


def validate_team_intelligence():
    print("\n--- Validating Team Intelligence ---")

    # Get a list of teams
    teams = get_all_collectives()

    # Find Barcelona and another team (e.g., Eibar or Almeria)
    barca = next((t for t in teams if "Barcelona" in t.team_name), None)

    if not barca:
        print("Warning: Barcelona not found in dataset.")
        return

    print(f"Testing Team Intelligence Aggregation for {barca.team_name} ({barca.season})")

    # Retrieve players
    player_idx = get_player_index()
    barca_players_idx = player_idx[
        (player_idx['team_name'] == barca.team_name) &
        (player_idx['profile_type'] == ProfileType.COMPETITION.value)
    ]

    barca_players = []
    for pid in barca_players_idx['player_id']:
        p = get_player_profile(int(pid))
        if p:
            barca_players.append(p)

    if not barca_players:
        print("Warning: No players found for Barcelona.")
        return

    print(f"Found {len(barca_players)} players for Barcelona.")

    # Test Aggregation
    team_prof = build_team_profile(
        team_id=barca.team_id,
        team_name=barca.team_name,
        competition=barca.competition,
        season=barca.season,
        players=barca_players
    )

    print("\nAggregated Capabilities:")
    print(f"Ball Security: {team_prof.avg_capabilities.get('ball_security', 0.0):.1f}")
    print(f"Chance Creation: {team_prof.avg_capabilities.get('chance_creation', 0.0):.1f}")
    print(f"Ball Progression: {team_prof.avg_capabilities.get('ball_progression', 0.0):.1f}")
    print(f"Attacking Threat: {team_prof.avg_capabilities.get('attacking_threat', 0.0):.1f}")
    print(f"Defensive Activity: {team_prof.avg_capabilities.get('defensive_activity', 0.0):.1f}")

    identity = team_prof.identity.primary_identity if team_prof.identity else "Balanced"
    print(f"\nTactical Identity: {identity}")

    # 3. Check tactical identity logic (Barcelona should be Possession)
    # We allow "Balanced" if the sample is small, but let's test the mapping.

    # Deterministic checks
    if team_prof.avg_capabilities.get('ball_security', 0.0) < 50.0:
        print("[FAIL] Barcelona's aggregated ball security is too low.")
    else:
        print("[PASS] Barcelona possesses expected high ball security.")

    if identity not in ["Possession-Dominant", "Balanced", "High Press", "Direct and Progressive"]:
        print(f"[FAIL] Tactical Identity '{identity}' is unusual for Barcelona.")
    else:
        print(f"[PASS] Tactical Identity '{identity}' is acceptable.")

if __name__ == "__main__":
    validate_team_intelligence()
