"""
backend/explanation/validator.py — Context Validation for the Explanation Layer.

Ensures that incomplete or semantically invalid evidence never reaches the LLM.
"""

from backend.explanation.context import (
    ComparisonExplanationContext,
    EvidencePacket,
    PlayerExplanationContext,
    RecruitmentExplanationContext,
    TeamExplanationContext,
)


class ContextValidationError(Exception):
    """Raised when an explanation context fails semantic validation."""

    pass


def validate_evidence_packet(packet: EvidencePacket) -> None:
    """
    Validates a single EvidencePacket for semantic completeness.
    """
    if not packet.title:
        raise ContextValidationError("Evidence packet missing title.")

    if packet.confidence is None or not (0.0 <= packet.confidence <= 1.0):
        raise ContextValidationError(
            f"Invalid confidence value {packet.confidence} in packet {packet.title}."
        )

    if not packet.supporting_metrics and packet.supporting_metrics != []:
        raise ContextValidationError(
            f"Missing supporting metrics in packet {packet.title}."
        )

    # If it's a capability packet, the score should ideally exist in supporting metrics.
    if packet.source.startswith("capability:"):
        has_score = False
        if isinstance(packet.supporting_metrics, dict):
            has_score = "score" in packet.supporting_metrics
        elif isinstance(packet.supporting_metrics, list):
            has_score = any(
                isinstance(m, dict) and m.get("metric_name") == "score"
                for m in packet.supporting_metrics
            )
            if not has_score:
                has_score = any(
                    isinstance(m, dict) and "score" in m
                    for m in packet.supporting_metrics
                )

        if not has_score:
            raise ContextValidationError(
                f"Capability packet {packet.title} missing 'score' metric."
            )


def validate_player_context(ctx: PlayerExplanationContext) -> None:
    """
    Validates a PlayerExplanationContext.
    """
    if not ctx.player_name:
        raise ContextValidationError("Player context missing player name.")

    if not ctx.evidence_packets:
        raise ContextValidationError(
            f"Player context for {ctx.player_name} contains no evidence packets."
        )

    if ctx.overall_confidence is None or not (0.0 <= ctx.overall_confidence <= 1.0):
        raise ContextValidationError(
            f"Invalid overall confidence in player context for {ctx.player_name}."
        )

    # Validate each packet
    for packet in ctx.evidence_packets:
        validate_evidence_packet(packet)


def validate_team_context(ctx: TeamExplanationContext) -> None:
    """
    Validates a TeamExplanationContext.
    """
    if not ctx.team_name:
        raise ContextValidationError("Team context missing team name.")

    if ctx.squad_size <= 0:
        raise ContextValidationError(
            f"Team context for {ctx.team_name} has invalid squad size."
        )

    if not ctx.style_label:
        raise ContextValidationError(
            f"Team context for {ctx.team_name} missing tactical style label."
        )

    for packet in ctx.evidence_packets:
        validate_evidence_packet(packet)


def validate_recruitment_context(ctx: RecruitmentExplanationContext) -> None:
    """
    Validates a RecruitmentExplanationContext.
    """
    if not ctx.position_target:
        raise ContextValidationError("Recruitment context missing position target.")

    if not ctx.candidates:
        raise ContextValidationError(
            "Recruitment context has no candidates to explain."
        )

    for idx, candidate in enumerate(ctx.candidates):
        if "fit_score" not in candidate:
            raise ContextValidationError(f"Candidate at index {idx} missing fit_score.")
        if "player_name" not in candidate:
            raise ContextValidationError(
                f"Candidate at index {idx} missing player_name."
            )


def validate_comparison_context(ctx: ComparisonExplanationContext) -> None:
    """
    Validates a ComparisonExplanationContext.
    """
    if len(ctx.players) < 2:
        raise ContextValidationError("Comparison context must have at least 2 players.")

    for player_ctx in ctx.players:
        validate_player_context(player_ctx)
