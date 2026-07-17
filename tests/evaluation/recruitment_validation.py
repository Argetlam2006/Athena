from backend.recommendation.engine import DecisionIntelligenceEngine
from frontend.data.players import get_player_index
from shared.schemas import ProfileType, RecruitmentCriteria
from tests.evaluation.player_capability_validation import (
    get_full_profile,
    get_player_by_name,
)


def validate_recruitment():
    print("\n--- Validating Recruitment Recommendations ---")

    engine = DecisionIntelligenceEngine()

    # Load pool
    print("Loading Player Pool for Recruitment...")
    player_idx = get_player_index()
    career_idx = player_idx[player_idx["profile_type"] == ProfileType.CAREER.value]

    # Just take top 500 for speed in testing
    pool = []
    for pid in career_idx["player_id"].head(500):
        p = get_full_profile(int(pid))
        if p:
            pool.append(p)

    print(f"Pool loaded with {len(pool)} players.")

    # 1. Replace Busquets / Defensive Anchor
    busquets = get_player_by_name("sergio busquets")
    if not busquets:
        print("Warning: Sergio Busquets not found, skipping anchor recruitment test.")
    else:
        print(f"\nTesting Replacement for {busquets['player_name']}")
        criteria = RecruitmentCriteria(
            position="Midfielder",
            required_capabilities={"ball_security": 70.0, "press_resistance": 65.0},
        )

        candidates = engine.rank_candidates(pool, criteria)
        print(f"Found {len(candidates)} candidates.")

        # We expect players with high ball_security to be at the top
        if candidates:
            top_candidate = candidates[0]
            print(
                f"Top Candidate: {top_candidate.player.player_name} (Score: {top_candidate.fit_score:.1f})"
            )

            p_cap = top_candidate.player.capability_profile
            if p_cap.ball_security.score >= 70.0:
                print(
                    f"[PASS] Top candidate meets ball_security criteria (Score: {p_cap.ball_security.score:.1f})"
                )
            else:
                print(
                    f"[FAIL] Top candidate fails ball_security criteria (Score: {p_cap.ball_security.score:.1f})"
                )
        else:
            print("[FAIL] No candidates found.")

    # 2. Forward with Attacking Threat
    print("\nTesting Elite Forward Recruitment")
    criteria = RecruitmentCriteria(
        position="Forward", required_capabilities={"attacking_threat": 80.0}
    )

    candidates = engine.rank_candidates(pool, criteria)
    print(f"Found {len(candidates)} candidates.")

    if candidates:
        top_candidate = candidates[0]
        print(
            f"Top Candidate: {top_candidate.player.player_name} (Score: {top_candidate.fit_score:.1f})"
        )

        p_cap = top_candidate.player.capability_profile
        if p_cap.attacking_threat.score >= 80.0:
            print(
                f"[PASS] Top candidate meets attacking_threat criteria (Score: {p_cap.attacking_threat.score:.1f})"
            )
        else:
            print(
                f"[FAIL] Top candidate fails attacking_threat criteria (Score: {p_cap.attacking_threat.score:.1f})"
            )
    else:
        print("[FAIL] No candidates found.")


if __name__ == "__main__":
    validate_recruitment()
