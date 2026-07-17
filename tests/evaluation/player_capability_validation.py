import pandas as pd

from shared.schemas import ProfileType


def get_player_by_name(
    name: str, profile_type: ProfileType = ProfileType.CAREER
) -> dict:
    from backend.intelligence.store import PLAYER_INDEX_PATH

    df = pd.read_parquet(PLAYER_INDEX_PATH)

    # Filter by name and profile type
    matches = df[
        (df["normalized_name"].str.contains(name.lower()))
        & (df["profile_type"] == profile_type.value)
    ]
    if matches.empty:
        return None

    return matches.iloc[0].to_dict()


def get_full_profile(player_id: int):
    from frontend.data.players import get_player_profile

    return get_player_profile(player_id)


def validate_capability_ranking(capability: str, expected_order: list[str]):
    print(f"\n--- Validating Capability: {capability} ---")

    profiles = []
    for name in expected_order:
        p_idx = get_player_by_name(name)
        if not p_idx:
            print(f"Warning: Player '{name}' not found.")
            continue

        full_prof = get_full_profile(int(p_idx["player_id"]))
        if full_prof and full_prof.capability_profile:
            cap_obj = getattr(full_prof.capability_profile, capability)
            score = cap_obj.score if cap_obj else 0.0
            profiles.append((name, score))
        else:
            print(f"Warning: Profile missing capabilities for '{name}'.")

    # Sort actual
    actual_order = sorted(profiles, key=lambda x: x[1], reverse=True)

    print("\nExpected Order:")
    for i, name in enumerate(expected_order):
        print(f"{i + 1}. {name}")

    print("\nActual Order (Athena):")
    for i, (name, score) in enumerate(actual_order):
        print(f"{i + 1}. {name} ({score:.1f})")

    # Check for glaring inversions
    # If the top player in expected is ranked in the bottom half of actual, that's a glaring inversion.
    issues = []
    for exp_rank, name in enumerate(expected_order):
        act_rank = next((i for i, x in enumerate(actual_order) if x[0] == name), -1)
        if act_rank != -1:
            diff = act_rank - exp_rank
            if abs(diff) > len(expected_order) / 2:
                issues.append(
                    f"Severe inversion for {name}: Expected #{exp_rank + 1}, Actual #{act_rank + 1}"
                )

    if issues:
        print("\n[WARNING] Found significant ranking inversions:")
        for issue in issues:
            print("  - " + issue)
    else:
        print("\n[PASS] No severe inversions found in ranking tiers.")


def run_player_capability_validation():
    # 1. Chance Creation (Playmakers)
    validate_capability_ranking(
        "chance_creation",
        ["lionel andrés messi", "mesut", "andrés iniesta", "xavi hernández"],
    )

    # 2. Attacking Threat (Forwards)
    validate_capability_ranking(
        "attacking_threat",
        [
            "lionel andrés messi",
            "thierry henry",
            "alexis alejandro sánchez",
            "luis alberto suárez",
            "neymar",
        ],
    )

    # 3. Defensive Activity (Midfielders/Defenders)
    validate_capability_ranking(
        "defensive_activity", ["patrick vieira", "sergio busquets", "kolo touré"]
    )


if __name__ == "__main__":
    run_player_capability_validation()
