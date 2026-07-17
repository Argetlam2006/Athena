"""
scripts/generate_validation_snapshot.py

Generates a permanent benchmark snapshot of the intelligence model.
Includes: top players per capability, archetype distribution, unknown %, 
and capability percentiles for regression tracking.
"""

import json
from pathlib import Path
from backend.intelligence.store import IntelligenceStore
from shared.schemas import ProfileType

SNAPSHOT_PATH = Path("data/warehouse/benchmark_snapshot.json")

def main():
    store = IntelligenceStore()
    if not store.is_valid():
        print("Intelligence store not valid. Run pipeline first.")
        return

    players = store.get_all_players(ProfileType.COMPETITION)
    if not players:
        print("No players found in store.")
        return

    snapshot = {
        "total_players": len(players),
        "top_players": {},
        "archetype_distribution": {},
        "unknown_percentage": 0.0,
    }

    # Archetype Distribution
    arch_counts = {}
    for p in players:
        arch = p.display_archetype
        arch_counts[arch] = arch_counts.get(arch, 0) + 1

    snapshot["archetype_distribution"] = arch_counts
    if "Unknown" in arch_counts:
        snapshot["unknown_percentage"] = round(arch_counts["Unknown"] / len(players) * 100.0, 2)

    # Top Players per Capability
    caps = [
        "ball_progression", "chance_creation", "ball_security",
        "press_resistance", "defensive_activity", "attacking_threat"
    ]
    
    for cap in caps:
        # Sort players by capability score descending
        sorted_players = sorted(
            [p for p in players if getattr(p.capability_profile, cap)],
            key=lambda p: getattr(p.capability_profile, cap).score,
            reverse=True
        )
        
        snapshot["top_players"][cap] = [
            {"player_name": p.player_name, "position": p.position_group, "score": getattr(p.capability_profile, cap).score}
            for p in sorted_players[:5]
        ]

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

    print(f"Snapshot written to {SNAPSHOT_PATH}")
    print(f"Unknown %: {snapshot['unknown_percentage']}%")

if __name__ == "__main__":
    main()
