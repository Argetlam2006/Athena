"""
backend/explanation/context.py — Explicit Context Definitions for the Explanation Layer.

These dataclasses represent the validated evidence payloads that will be sent to the AI.
They are internal view models for the explanation subsystem and should never be used
as cross-domain contracts.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidencePacket:
    """
    A structured, validated package of analytical evidence.
    Organizes capability scores, supporting metrics, and decision signals
    so the Prompt Builder doesn't have to reconstruct relationships.
    """

    source: str  # e.g., "capability:ball_progression", "signal:elite_goal_scorer"
    title: str
    confidence: float
    supporting_metrics: list[dict[str, Any]] = field(default_factory=list)
    supporting_signals: list[str] = field(default_factory=list)
    optional_caveats: list[str] = field(default_factory=list)


@dataclass
class PlayerExplanationContext:
    """Context block for analyzing a specific player."""

    player_id: int
    player_name: str
    team_name: str
    position_group: str
    birth_date: str | None
    minutes_played: float

    archetype: str | None
    overall_confidence: float

    # Fully validated, structured evidence blocks
    evidence_packets: list[EvidencePacket] = field(default_factory=list)


@dataclass
class TeamExplanationContext:
    """
    Structured context for explaining a team profile.
    """

    team_id: int
    team_name: str
    competition: str
    season: str
    squad_size: int
    average_age: float

    style_label: str

    # Phase 15 Collective Intelligence Fields
    collective_identity: dict[str, Any] = field(default_factory=dict)
    concentration_risks: list[dict[str, Any]] = field(default_factory=list)
    system_bottlenecks: list[dict[str, Any]] = field(default_factory=list)
    key_fragilities: list[dict[str, Any]] = field(default_factory=list)

    evidence_packets: list[EvidencePacket] = field(default_factory=list)


@dataclass
class RecruitmentExplanationContext:
    """
    Structured context for explaining a recruitment recommendation.
    """

    position_target: str
    tactical_style_target: str | None
    required_capabilities: dict[str, float]

    # Ranked candidate contexts
    candidates: list[dict[str, Any]] = field(
        default_factory=list
    )  # Serialized candidate data + fit scores


@dataclass
class ComparisonExplanationContext:
    """
    Structured context for explaining a player comparison.
    """

    players: list[PlayerExplanationContext] = field(default_factory=list)
    shared_strengths: list[str] = field(default_factory=list)
    key_differences: list[str] = field(default_factory=list)
