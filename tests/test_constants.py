"""
tests/test_constants.py — Verify shared constants are internally consistent

These tests act as a contract guard — if constants.py is modified
incorrectly, these tests catch it before the change breaks downstream modules.
"""

from __future__ import annotations

import pytest

from shared.constants import (
    CAPABILITIES,
    CAPABILITY_DESCRIPTIONS,
    CAPABILITY_DISPLAY_NAMES,
    CAPABILITY_METRIC_MAP,
    CAPABILITY_METRIC_WEIGHTS,
    WORKSPACES,
)


class TestCapabilityConstants:
    """Verify the 8 capabilities are consistently defined across all mappings."""

    EXPECTED_CAPABILITIES = {
        "ball_progression",
        "chance_creation",
        "ball_security",
        "press_resistance",
        "defensive_activity",
        "attacking_threat",
        "physical_availability",
        "tactical_versatility",
    }

    def test_exactly_eight_capabilities(self) -> None:
        assert len(CAPABILITIES) == 8, f"Expected 8 capabilities, got {len(CAPABILITIES)}"

    def test_tactical_versatility_present(self) -> None:
        """Tactical Versatility replaces Financial Value — verify it exists."""
        assert "tactical_versatility" in CAPABILITIES

    def test_financial_value_not_present(self) -> None:
        """Financial Value was replaced — verify it is gone."""
        assert "financial_value" not in CAPABILITIES

    def test_all_capabilities_have_display_names(self) -> None:
        for cap in CAPABILITIES:
            assert cap in CAPABILITY_DISPLAY_NAMES, (
                f"Missing display name for capability: {cap}"
            )

    def test_all_capabilities_have_descriptions(self) -> None:
        for cap in CAPABILITIES:
            assert cap in CAPABILITY_DESCRIPTIONS, (
                f"Missing description for capability: {cap}"
            )

    def test_all_capabilities_have_metric_maps(self) -> None:
        for cap in CAPABILITIES:
            assert cap in CAPABILITY_METRIC_MAP, (
                f"Missing metric map for capability: {cap}"
            )
            assert len(CAPABILITY_METRIC_MAP[cap]) > 0, (
                f"Empty metric list for capability: {cap}"
            )

    def test_all_capabilities_have_weights(self) -> None:
        for cap in CAPABILITIES:
            assert cap in CAPABILITY_METRIC_WEIGHTS, (
                f"Missing weights for capability: {cap}"
            )

    def test_weights_sum_to_one(self) -> None:
        """Each capability's weights must sum to 1.0 (within floating point tolerance)."""
        for cap, weights in CAPABILITY_METRIC_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, (
                f"Weights for {cap} sum to {total:.4f}, expected 1.0"
            )

    def test_weights_match_metric_map(self) -> None:
        """Every metric in the weights map must also be in the metric map."""
        for cap in CAPABILITIES:
            weight_keys = set(CAPABILITY_METRIC_WEIGHTS[cap].keys())
            metric_keys = set(CAPABILITY_METRIC_MAP[cap])
            assert weight_keys == metric_keys, (
                f"Mismatch for {cap}:\n"
                f"  In weights but not metrics: {weight_keys - metric_keys}\n"
                f"  In metrics but not weights: {metric_keys - weight_keys}"
            )

    def test_capability_set_matches_expected(self) -> None:
        """The exact set of capabilities must match the specification."""
        assert set(CAPABILITIES) == self.EXPECTED_CAPABILITIES


class TestWorkspaceConstants:
    """Verify the 5 workspace definitions."""

    EXPECTED_WORKSPACES = {
        "dashboard",
        "player_intelligence",
        "team_intelligence",
        "recruitment",
        "ask_athena",
    }

    def test_exactly_five_workspaces(self) -> None:
        assert len(WORKSPACES) == 5

    def test_all_workspaces_present(self) -> None:
        assert set(WORKSPACES.keys()) == self.EXPECTED_WORKSPACES

    def test_all_workspaces_have_required_fields(self) -> None:
        required_fields = {"display", "icon", "question", "route"}
        for name, config in WORKSPACES.items():
            missing = required_fields - set(config.keys())
            assert not missing, f"Workspace {name!r} missing fields: {missing}"
