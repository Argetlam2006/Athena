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
    CollectiveIdentity,
    CollectiveProfile,
    PlayerProfile,
    SupportingMetric,
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
            "ball_progression", 85.0, 1.0, [SupportingMetric("progressive_passes_p90", 5.0, 95.0, 0.5, "exp")]
        ),
        chance_creation=CapabilityScore(
            "chance_creation", 98.0, 1.0, [SupportingMetric("shot_assists_p90", 2.0, 98.0, 0.5, "exp")]
        ),
        ball_security=CapabilityScore(
            "ball_security", 80.0, 1.0, [SupportingMetric("pass_accuracy_pct", 85.0, 80.0, 0.5, "exp")]
        ),
        press_resistance=CapabilityScore("press_resistance", 90.0, 1.0, []),
        defensive_activity=CapabilityScore("defensive_activity", 80.0, 0.9, [
            SupportingMetric("pressures_p90", 25.0, 99.0, 0.25, "exp"),
            SupportingMetric("defensive_philosophy", 1.0, 100.0, 0.0, "Defensive Activity evaluated using Active philosophy.")
        ]),
        attacking_threat=CapabilityScore("attacking_threat", 60.0, 0.8, []),
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
    )


def test_valid_player_context_builds(valid_player_profile):
    engine = ExplanationContextEngine()
    ctx = engine.get_player_context(valid_player_profile)

    assert ctx.player_name == "Test Player"
    assert len(ctx.evidence_packets) == 6  # 6 capabilities

    # Check that a packet contains supporting metrics
    bp_packet = next(
        p for p in ctx.evidence_packets if p.source == "capability:ball_progression"
    )
    assert bp_packet.title == "Ball Progression Capability"
    assert any(m["metric_name"] == "score" and m["raw_value"] == 85.0 for m in bp_packet.supporting_metrics)
    assert any(m["metric_name"] == "progressive_passes_p90" and m["raw_value"] == 5.0 for m in bp_packet.supporting_metrics)
    
    # Check that defensive philosophy is present
    da_packet = next(
        p for p in ctx.evidence_packets if p.source == "capability:defensive_activity"
    )
    assert any(m["metric_name"] == "defensive_philosophy" and m["explanation"] == "Defensive Activity evaluated using Active philosophy." for m in da_packet.supporting_metrics)


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
    tp = CollectiveProfile(
        team_id=101,
        team_name="Test Team",
        competition="Ligue 1",
        season="2023",
        identity=CollectiveIdentity(primary_identity="Direct"),
        avg_capabilities={"ball_progression": 80.0},
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
    # Trigger a failure by missing team_name
    tp = CollectiveProfile(
        team_id=101,
        team_name="",
        competition="Ligue 1",
        season="2023",
        avg_capabilities={},
    )
    engine = ExplanationContextEngine()
    with pytest.raises(ContextValidationError, match="Team context missing team name"):
        engine.get_team_context(tp)
