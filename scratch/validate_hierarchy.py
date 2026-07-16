import os
from collections import defaultdict

from backend.warehouse.connection import connect
from backend.intelligence.store import IntelligenceStore, PLAYER_INDEX_PATH
import pandas as pd
from shared.schemas import ProfileType

def validate_hierarchy():
    print("Loading Intelligence Store Index...")
    store = IntelligenceStore()
    if not store.is_valid():
        print("Intelligence Store is not valid according to fingerprint.")
    
    # Load player index
    df = pd.read_parquet(PLAYER_INDEX_PATH)
    
    # Check types
    career_profiles = df[df['profile_type'] == ProfileType.CAREER.value]
    season_profiles = df[df['profile_type'] == ProfileType.SEASON.value]
    competition_profiles = df[df['profile_type'] == ProfileType.COMPETITION.value]
    
    print(f"Loaded {len(career_profiles)} Career, {len(season_profiles)} Season, {len(competition_profiles)} Competition profiles.")

    # 1. 1:1 Mapping between unique player IDs and Career profiles
    unique_players = df['player_id'].nunique()
    if unique_players != len(career_profiles):
        print(f"FAIL: Unique players ({unique_players}) != Career profiles ({len(career_profiles)})")
    else:
        print(f"PASS: 1:1 Mapping for unique players to Career profiles")
        
    # 2. No orphaned profiles
    career_pids = set(career_profiles['player_id'])
    season_pids = set(season_profiles['player_id'])
    comp_pids = set(competition_profiles['player_id'])
    
    orphans = season_pids - career_pids
    if orphans:
        print(f"FAIL: Found {len(orphans)} season profiles without a career profile.")
    else:
        print(f"PASS: No orphaned season profiles")
        
    orphans2 = comp_pids - season_pids
    if orphans2:
        print(f"FAIL: Found {len(orphans2)} competition profiles without a season profile.")
    else:
        print(f"PASS: No orphaned competition profiles")
        
    print("Hierarchy validation complete.")

if __name__ == "__main__":
    validate_hierarchy()
