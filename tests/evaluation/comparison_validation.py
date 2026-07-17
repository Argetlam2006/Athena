from backend.recommendation.engine import DecisionIntelligenceEngine
from tests.evaluation.player_capability_validation import (
    get_full_profile,
    get_player_by_name,
)


def validate_comparison():
    print("\n--- Validating Player Comparison ---")

    engine = DecisionIntelligenceEngine()

    messi_idx = get_player_by_name("lionel andrés messi")
    henry_idx = get_player_by_name("thierry henry")

    if not messi_idx or not henry_idx:
        print("Warning: Required players not found for comparison test.")
        return

    messi = get_full_profile(int(messi_idx["player_id"]))
    henry = get_full_profile(int(henry_idx["player_id"]))

    result = engine.compare_players([messi, henry])

    print(f"Comparing {messi.player_name} vs {henry.player_name}")
    print(f"Shared Strengths: {result.shared_strengths}")
    print(f"Key Differences: {result.key_differences}")

    if result.capability_comparison:
        print("[PASS] Capability comparison generated.")
    else:
        print("[FAIL] Capability comparison missing.")

    if len(result.shared_strengths) > 0 and len(result.key_differences) > 0:
        print("[PASS] Deterministic insights generated for comparison.")
    else:
        print("[FAIL] Missing deterministic insights.")


if __name__ == "__main__":
    validate_comparison()
