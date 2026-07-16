"""
tests/test_explanation/test_context_engine.py — Tests for the Context Engine.
"""

import json
from dataclasses import asdict

import pytest

from backend.explanation.engine import ExplanationContextEngine
from backend.explanation.validator import ContextValidationError
from shared.schemas import (
    CapabilityProfile,
    CapabilityScore,
    PlayerProfile,
    TeamProfile,
)


@pytest.fixture
def valid_player_profile() -> PlayerProfile:
    cap = CapabilityProfile(
        player_id=1,
        player_name="Test Player",
        season="2023",
        competition="Ligue 1",
        position_group="Forward",
        minutes_played=2000,
        ball_progression=CapabilityScore(
            "ball_progression", 85.0, 1.0, {"progressive_passes_p90": 5.0}
        ),
        chance_creation=CapabilityScore(
            "chance_creation", 98.0, 1.0, {"shot_assists_p90": 2.0}
        ),
        ball_security=CapabilityScore(
            "ball_security", 80.0, 1.0, {"pass_accuracy_pct": 85.0}
        ),
        press_resistance=CapabilityScore("press_resistance", 90.0, 1.0, {}),
        defensive_activity=CapabilityScore("defensive_activity", 25.0, 1.0, {}),
        attacking_threat=CapabilityScore("attacking_threat", 95.0, 1.0, {}),
        physical_availability=CapabilityScore("physical_availability", 85.0, 1.0, {}),
        tactical_versatility=CapabilityScore("tactical_versatility", 70.0, 1.0, {}),
    )
    return PlayerProfile(
        player_id=1,
        player_name="Test Player",
        position_group="Forward",
        team_name="PSG",
        competition="Ligue 1",
        season="2023",
        birth_date="2000-01-01",
        minutes_played=2000,
        capability_profile=cap,
        decision_signals=["elite_goal_scorer"],
        archetype="Complete Forward",
    )


def test_valid_player_context_builds(valid_player_profile):
    engine = ExplanationContextEngine()
    ctx = engine.get_player_context(valid_player_profile)

    assert ctx.player_name == "Test Player"
    assert len(ctx.evidence_packets) == 8  # 8 capabilities

    # Check that a packet contains supporting metrics
    bp_packet = next(
        p for p in ctx.evidence_packets if p.source == "capability:ball_progression"
    )
    assert bp_packet.title == "Ball Progression Capability"
    assert bp_packet.supporting_metrics["score"] == 85.0
    assert bp_packet.supporting_metrics["progressive_passes_p90"] == 5.0


def test_missing_evidence_fails_validation(valid_player_profile):
    # Mess up the player profile to cause a validation error
    valid_player_profile.capability_profile.ball_progression.score = 85.0
    # Let's mock a validation failure: no packets
    valid_player_profile.capability_profile = None

    engine = ExplanationContextEngine()
    with pytest.raises(ContextValidationError, match="contains no evidence packets"):
        engine.get_player_context(valid_player_profile)


def test_invalid_confidence_fails_validation(valid_player_profile):
    # Set invalid confidence
    valid_player_profile.capability_profile.ball_progression.confidence = 1.5

    engine = ExplanationContextEngine()
    with pytest.raises(ContextValidationError, match="Invalid .*confidence"):
        engine.get_player_context(valid_player_profile)


def test_team_context_serialization():
    tp = TeamProfile(
        team_id=101,
        team_name="Test Team",
        competition="Ligue 1",
        season="2023",
        squad_size=25,
        avg_ball_progression=80.0,
        style_label="Direct",
    )

    engine = ExplanationContextEngine()
    ctx = engine.get_team_context(tp)

    assert ctx.team_name == "Test Team"
    # Serialize to JSON-compatible dict
    serialized = asdict(ctx)

    # Verify JSON serialization works seamlessly (no custom objects breaking it)
    json_str = json.dumps(serialized)
    assert "Test Team" in json_str
    assert "Direct" in json_str


def test_team_validation_failure():
    tp = TeamProfile(
        team_id=101,
        team_name="Test Team",
        competition="Ligue 1",
        season="2023",
        squad_size=0,  # Invalid
        style_label="Direct",
    )
    engine = ExplanationContextEngine()
    with pytest.raises(ContextValidationError, match="invalid squad size"):
        engine.get_team_context(tp)
