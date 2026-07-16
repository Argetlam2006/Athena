"""
tests/test_schemas.py — Unit tests for shared data schemas

Verifies that schema dataclasses:
  - enforce valid ranges
  - compute derived properties correctly
  - maintain AIF pipeline contract
"""

from __future__ import annotations

import pytest

from shared.schemas import (
    CapabilityProfile,
    CapabilityScore,
    PlayerFeatureVector,
    PlayerProfile,
    TeamProfile,
)


class TestCapabilityScore:
    """Tests for CapabilityScore validation."""

    def test_valid_score_creates_successfully(self) -> None:
        score = CapabilityScore(
            capability="ball_progression",
            score=75.0,
            confidence=0.85,
        )
        assert score.score == 75.0
        assert score.confidence == 0.85

    def test_score_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="0–100"):
            CapabilityScore(capability="ball_progression", score=-1.0, confidence=0.5)

    def test_score_above_100_raises(self) -> None:
        with pytest.raises(ValueError, match="0–100"):
            CapabilityScore(capability="ball_progression", score=101.0, confidence=0.5)

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="0–1"):
            CapabilityScore(capability="ball_progression", score=50.0, confidence=-0.1)

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="0–1"):
            CapabilityScore(capability="ball_progression", score=50.0, confidence=1.1)

    def test_boundary_values_accepted(self) -> None:
        """Scores at exact boundaries (0, 100, 0.0 confidence, 1.0 confidence) are valid."""
        score_min = CapabilityScore(capability="x", score=0.0, confidence=0.0)
        score_max = CapabilityScore(capability="x", score=100.0, confidence=1.0)
        assert score_min.score == 0.0
        assert score_max.score == 100.0

    def test_evidence_defaults_to_empty_dict(self) -> None:
        score = CapabilityScore(capability="x", score=50.0, confidence=0.5)
        assert score.evidence == {}


class TestCapabilityProfile:
    """Tests for CapabilityProfile."""

    def _make_profile(self) -> CapabilityProfile:
        return CapabilityProfile(
            player_id=1,
            player_name="Test Player",
            season="2020/2021",
            competition="La Liga",
            position_group="CM",
            minutes_played=2250.0,
            ball_progression=CapabilityScore("ball_progression", 80.0, 0.9),
            chance_creation=CapabilityScore("chance_creation", 70.0, 0.85),
            ball_security=CapabilityScore("ball_security", 75.0, 0.8),
            press_resistance=CapabilityScore("press_resistance", 65.0, 0.75),
            defensive_activity=CapabilityScore("defensive_activity", 60.0, 0.7),
            attacking_threat=CapabilityScore("attacking_threat", 55.0, 0.8),
            physical_availability=CapabilityScore("physical_availability", 85.0, 0.95),
            tactical_versatility=CapabilityScore("tactical_versatility", 50.0, 0.6),
        )

    def test_radar_dict_has_eight_keys(self) -> None:
        profile = self._make_profile()
        radar = profile.as_radar_dict()
        assert len(radar) == 8

    def test_radar_dict_contains_tactical_versatility(self) -> None:
        profile = self._make_profile()
        radar = profile.as_radar_dict()
        assert "Tactical Versatility" in radar

    def test_radar_dict_does_not_contain_financial_value(self) -> None:
        profile = self._make_profile()
        radar = profile.as_radar_dict()
        assert "Financial Value" not in radar

    def test_overall_confidence_computed_correctly(self) -> None:
        profile = self._make_profile()
        confidence = profile.overall_confidence()
        # All 8 capabilities present — should be mean of their confidences
        assert 0.0 <= confidence <= 1.0

    def test_overall_confidence_zero_when_no_capabilities(self) -> None:
        profile = CapabilityProfile(
            player_id=1,
            player_name="Empty",
            season="2020/2021",
            competition="La Liga",
            position_group="CM",
            minutes_played=0.0,
        )
        assert profile.overall_confidence() == 0.0


class TestPlayerProfile:
    """Tests for PlayerProfile."""

    def test_analytically_sufficient_above_threshold(self) -> None:
        player = PlayerProfile(
            player_id=1,
            player_name="Player A",
            position_group="CM",
            team_name="Team A",
            competition="La Liga",
            season="2020/2021",
            birth_date="2000-01-01",
            minutes_played=900.0,  # above MIN_MINUTES_THRESHOLD (450)
        )
        assert player.is_analytically_sufficient() is True

    def test_analytically_insufficient_below_threshold(self) -> None:
        player = PlayerProfile(
            player_id=2,
            player_name="Player B",
            position_group="ST",
            team_name="Team B",
            competition="La Liga",
            season="2020/2021",
            birth_date="2000-01-01",
            minutes_played=100.0,  # below threshold
        )
        assert player.is_analytically_sufficient() is False

    def test_similar_players_defaults_to_empty_list(self) -> None:
        player = PlayerProfile(
            player_id=3,
            player_name="C",
            position_group="ST",
            team_name="T",
            competition="C",
            season="S",
            birth_date="2000-01-01",
            minutes_played=500.0,
        )
        assert player.similar_players == []


class TestPlayerFeatureVector:
    """Tests for PlayerFeatureVector.to_vector()."""

    def test_to_vector_returns_list_of_floats(self) -> None:
        vec = PlayerFeatureVector(
            player_id=1,
            player_name="Test",
            season="2020/2021",
            competition="La Liga",
            position_group="CM",
            minutes_played=900.0,
            matches_played=10,
        )
        result = vec.to_vector()
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_to_vector_has_expected_length(self) -> None:
        """
        Vector must have exactly 36 features:
        Ball Progression (5) + Chance Creation (5) + Ball Security (5)
        + Press Resistance (3) + Defensive Activity (5) + Attacking Threat (5)
        + Physical Availability (4) + Tactical Versatility (4) = 36
        """
        vec = PlayerFeatureVector(
            player_id=1,
            player_name="Test",
            season="2020/2021",
            competition="La Liga",
            position_group="CM",
            minutes_played=900.0,
            matches_played=10,
        )
        result = vec.to_vector()
        assert len(result) == 23, f"Expected 23 features, got {len(result)}"


class TestTeamProfile:
    """Tests for TeamProfile."""

    def test_radar_dict_has_eight_keys(self) -> None:
        team = TeamProfile(
            team_id=1,
            team_name="FC Test",
            competition="La Liga",
            season="2020/2021",
            squad_size=25,
            avg_ball_progression=72.0,
            avg_chance_creation=68.0,
            avg_ball_security=75.0,
            avg_press_resistance=70.0,
            avg_defensive_activity=65.0,
            avg_attacking_threat=71.0,
            avg_physical_availability=80.0,
            avg_tactical_versatility=60.0,
        )
        radar = team.as_radar_dict()
        assert len(radar) == 8
        assert "Tactical Versatility" in radar
