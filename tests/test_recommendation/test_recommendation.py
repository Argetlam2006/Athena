"""
tests/test_recommendation/test_recommendation.py — Unit and Regression Tests for Decision Intelligence.
"""

from __future__ import annotations

import pytest
from shared.schemas import PlayerProfile, CapabilityProfile, CapabilityScore, RecruitmentCriteria, TeamProfile
from backend.recommendation.comparison import compare_players
from backend.recommendation.recruitment import rank_candidates, recommend_replacement
from backend.recommendation.engine import DecisionIntelligenceEngine

@pytest.fixture
def mock_profiles():
    cap1 = CapabilityProfile(
        player_id=1, player_name="Player A", season="2023", competition="PL", position_group="Forward", minutes_played=2000,
        ball_progression=CapabilityScore("ball_progression", 85.0, 1.0),
        chance_creation=CapabilityScore("chance_creation", 90.0, 1.0),
        ball_security=CapabilityScore("ball_security", 75.0, 1.0),
        press_resistance=CapabilityScore("press_resistance", 80.0, 1.0),
        defensive_activity=CapabilityScore("defensive_activity", 40.0, 1.0),
        attacking_threat=CapabilityScore("attacking_threat", 95.0, 1.0),
        physical_availability=CapabilityScore("physical_availability", 90.0, 1.0),
        tactical_versatility=CapabilityScore("tactical_versatility", 60.0, 1.0)
    )
    p1 = PlayerProfile(
        player_id=1, player_name="Player A", position_group="Forward", team_name="Team X", competition="PL", season="2023",
        age_years=25, minutes_played=2000, capability_profile=cap1, decision_signals=["elite_goal_scorer", "strong_chance_creator"]
    )
    
    cap2 = CapabilityProfile(
        player_id=2, player_name="Player B", season="2023", competition="PL", position_group="Forward", minutes_played=2100,
        ball_progression=CapabilityScore("ball_progression", 82.0, 1.0),
        chance_creation=CapabilityScore("chance_creation", 85.0, 1.0),
        ball_security=CapabilityScore("ball_security", 70.0, 1.0),
        press_resistance=CapabilityScore("press_resistance", 75.0, 1.0),
        defensive_activity=CapabilityScore("defensive_activity", 45.0, 1.0),
        attacking_threat=CapabilityScore("attacking_threat", 92.0, 1.0),
        physical_availability=CapabilityScore("physical_availability", 88.0, 1.0),
        tactical_versatility=CapabilityScore("tactical_versatility", 65.0, 1.0)
    )
    p2 = PlayerProfile(
        player_id=2, player_name="Player B", position_group="Forward", team_name="Team Y", competition="PL", season="2023",
        age_years=24, minutes_played=2100, capability_profile=cap2, decision_signals=["elite_goal_scorer"]
    )
    
    cap3 = CapabilityProfile(
        player_id=3, player_name="Player C", season="2023", competition="PL", position_group="Defender", minutes_played=2200,
        ball_progression=CapabilityScore("ball_progression", 60.0, 1.0),
        chance_creation=CapabilityScore("chance_creation", 40.0, 1.0),
        ball_security=CapabilityScore("ball_security", 85.0, 1.0),
        press_resistance=CapabilityScore("press_resistance", 70.0, 1.0),
        defensive_activity=CapabilityScore("defensive_activity", 95.0, 1.0),
        attacking_threat=CapabilityScore("attacking_threat", 20.0, 1.0),
        physical_availability=CapabilityScore("physical_availability", 95.0, 1.0),
        tactical_versatility=CapabilityScore("tactical_versatility", 50.0, 1.0)
    )
    p3 = PlayerProfile(
        player_id=3, player_name="Player C", position_group="Defender", team_name="Team Z", competition="PL", season="2023",
        age_years=28, minutes_played=2200, capability_profile=cap3, decision_signals=["defensive_specialist"]
    )

    return [p1, p2, p3]


def test_comparison_result(mock_profiles):
    """Test deterministic comparison logic."""
    p1, p2 = mock_profiles[0], mock_profiles[1]
    result = compare_players([p1, p2])
    
    assert len(result.players) == 2
    assert "Strong Ball Progression" in result.shared_strengths
    assert "Strong Chance Creation" in result.shared_strengths
    # They are very close, so max_score - min_score > 15 won't trigger for any cap
    assert len(result.key_differences) == 0
    assert result.capability_comparison["ball_progression"]["Player A"] == 85.0
    assert result.capability_comparison["ball_progression"]["Player B"] == 82.0


def test_recruitment_ranking(mock_profiles):
    """Test candidate ranking correctness based on criteria."""
    criteria = RecruitmentCriteria(
        position="Forward",
        required_capabilities={"attacking_threat": 1.0},
        tactical_style="Direct and Progressive"
    )
    
    candidates = rank_candidates(mock_profiles, criteria)
    
    # Should only return Forwards
    assert len(candidates) == 2
    
    # Player A should be ranked higher than B because A has higher attacking_threat (95 vs 92)
    # and higher progression/creation (for Direct and Progressive style)
    assert candidates[0].player.player_name == "Player A"
    assert candidates[1].player.player_name == "Player B"
    assert candidates[0].rank == 1
    assert candidates[1].rank == 2
    
    # Evidence must be present
    assert "Elite Attacking Threat (95.0)" in candidates[0].strengths
    assert "Strong fit for Direct and Progressive" in candidates[0].strengths


def test_replacement_logic(mock_profiles):
    """Test the recommend_replacement logic."""
    # We want to replace Player A
    target = mock_profiles[0]
    # In a real scenario, Player A would be excluded, but let's test it does exclude
    recs = recommend_replacement(target, mock_profiles)
    
    # Should only return Player B (same position)
    assert len(recs) == 1
    assert recs[0].player.player_name == "Player B"
    assert "similarity_to_target" in recs[0].explanation_context
    assert recs[0].explanation_context["similarity_to_target"] > 90.0  # They are very close


def test_engine_facade(mock_profiles):
    """Test the facade methods."""
    engine = DecisionIntelligenceEngine()
    
    # compare
    comp = engine.compare_players([mock_profiles[0], mock_profiles[2]])
    assert "Defensive Activity: Player C (95.0) outperforms Player A (40.0)" in comp.key_differences
    
    # evaluate fit
    team = TeamProfile(team_id=1, team_name="Mock Team", competition="PL", season="2023", squad_size=20, style_label="High Press")
    fit = engine.evaluate_team_fit(mock_profiles[2], team)
    
    assert fit["player_name"] == "Player C"
    assert fit["target_style"] == "High Press"
    assert fit["fit_score"] > 80.0  # Defender has 95 defensive activity and 95 availability
    assert "Excellent fit" in fit["explanation"]


def test_golden_regression_ranking(mock_profiles):
    """Regression test ensuring fixed cohorts produce deterministic identical scores."""
    criteria = RecruitmentCriteria(
        position="Forward",
        required_capabilities={"chance_creation": 0.6, "attacking_threat": 0.4}
    )
    
    candidates = rank_candidates(mock_profiles, criteria)
    
    # Player A: base = (90*0.6 + 95*0.4) = 54 + 38 = 92
    # Player B: base = (85*0.6 + 92*0.4) = 51 + 36.8 = 87.8
    # No tactical style specified, so fit_score = base_score
    
    assert candidates[0].fit_score == pytest.approx(92.0)
    assert candidates[1].fit_score == pytest.approx(87.8)
