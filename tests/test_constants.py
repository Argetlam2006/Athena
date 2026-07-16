"""
tests/test_constants.py — Verify shared constants are internally consistent

These tests act as a contract guard — if config is modified
incorrectly, these tests catch it before the change breaks downstream modules.
"""

from __future__ import annotations

from shared.config.capabilities import (
    CORE_CAPABILITIES,
    CAPABILITY_DESCRIPTIONS,
    CAPABILITY_DISPLAY_NAMES,
    CAPABILITY_METRIC_MAP,
    CAPABILITY_METRIC_WEIGHTS,
)
from shared.config.navigation import WORKSPACES


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
        assert len(CORE_CAPABILITIES) == 8, (
            f"Expected 8 capabilities, got {len(CORE_CAPABILITIES)}"
        )

    def test_tactical_versatility_present(self) -> None:
        """Tactical Versatility replaces Financial Value — verify it exists."""
        assert "tactical_versatility" in CORE_CAPABILITIES

    def test_all_capabilities_have_display_names(self) -> None:
        for cap in CORE_CAPABILITIES:
            assert cap in CAPABILITY_DISPLAY_NAMES, (
                f"Missing display name for capability: {cap}"
            )

    def test_all_capabilities_have_descriptions(self) -> None:
        for cap in CORE_CAPABILITIES:
            assert cap in CAPABILITY_DESCRIPTIONS, (
                f"Missing description for capability: {cap}"
            )

    def test_all_capabilities_have_metric_maps(self) -> None:
        for cap in CORE_CAPABILITIES:
            assert cap in CAPABILITY_METRIC_MAP, (
                f"Missing metric map for capability: {cap}"
            )
            assert len(CAPABILITY_METRIC_MAP[cap]) > 0, (
                f"Empty metric list for capability: {cap}"
            )

    def test_all_capabilities_have_weights(self) -> None:
        for cap in CORE_CAPABILITIES:
            assert cap in CAPABILITY_METRIC_WEIGHTS, (
                f"Missing weights for capability: {cap}"
            )

    def test_weights_sum_to_one(self) -> None:
        """Each capability's weights must sum to 1.0 (within floating point tolerance)."""
        for cap, weights in CAPABILITY_METRIC_WEIGHTS.items():
            # Handle nested dicts (like Chance Creation and Defensive Activity)
            if any(isinstance(v, dict) for v in weights.values()):
                for sub_key, sub_weights in weights.items():
                    total = sum(sub_weights.values())
                    assert abs(total - 1.0) < 0.001, (
                        f"Weights for {cap} ({sub_key}) sum to {total:.4f}, expected 1.0"
                    )
            else:
                total = sum(weights.values())
                assert abs(total - 1.0) < 0.001, (
                    f"Weights for {cap} sum to {total:.4f}, expected 1.0"
                )

    def test_capability_set_matches_expected(self) -> None:
        """The exact set of capabilities must match the specification."""
        assert set(CORE_CAPABILITIES) == self.EXPECTED_CAPABILITIES


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
        workspace_ids = {w.id for w in WORKSPACES}
        assert workspace_ids == self.EXPECTED_WORKSPACES

    def test_all_workspaces_have_required_fields(self) -> None:
        for w in WORKSPACES:
            assert hasattr(w, "id")
            assert hasattr(w, "name")
            assert hasattr(w, "icon")
            assert hasattr(w, "question")
            assert hasattr(w, "status")
            assert hasattr(w, "description")
