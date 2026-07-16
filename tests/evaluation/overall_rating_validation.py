import pandas as pd
from typing import List
from shared.schemas import ProfileType

def get_player_by_name(name: str) -> dict:
    from backend.intelligence.store import PLAYER_INDEX_PATH
    df = pd.read_parquet(PLAYER_INDEX_PATH)
    matches = df[(df['normalized_name'].str.contains(name.lower())) & (df['profile_type'] == ProfileType.CAREER.value)]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()

def get_full_profile(player_id: int):
    from frontend.data.players import get_player_profile
    return get_player_profile(player_id)

def validate_overall_rating(expected_order: List[str]):
    print(f"\n--- Validating Overall Rating Tiers ---")
    
    profiles = []
    for name in expected_order:
        p_idx = get_player_by_name(name)
        if not p_idx:
            print(f"Warning: Player '{name}' not found.")
            continue
            
        full_prof = get_full_profile(int(p_idx['player_id']))
        if full_prof and full_prof.capability_profile:
            r = getattr(full_prof.capability_profile, 'overall_rating', 0.0)
            profiles.append((name, r))
        else:
            print(f"Warning: Profile missing capabilities for '{name}'.")
            
    # Sort actual
    actual_order = sorted(profiles, key=lambda x: x[1], reverse=True)
    
    print("\nExpected Order:")
    for i, name in enumerate(expected_order):
        print(f"{i+1}. {name}")
        
    print("\nActual Order (Athena):")
    for i, (name, score) in enumerate(actual_order):
        print(f"{i+1}. {name} ({score:.1f})")
        
    issues = []
    for exp_rank, name in enumerate(expected_order):
        act_rank = next((i for i, x in enumerate(actual_order) if x[0] == name), -1)
        if act_rank != -1:
            diff = act_rank - exp_rank
            if abs(diff) > len(expected_order) / 2:
                issues.append(f"Severe inversion for {name}: Expected #{exp_rank+1}, Actual #{act_rank+1}")
                
    if issues:
        print("\n[WARNING] Found significant overall rating inversions:")
        for issue in issues:
            print("  - " + issue)
    else:
        print("\n[PASS] No severe inversions found in overall rating tiers.")

if __name__ == "__main__":
    validate_overall_rating([
        "lionel andrés messi",
        "thierry henry",
        "andrés iniesta",
        "xavi hernández",
        "sergio busquets",
        "mesut",
        "patrick vieira"
    ])
