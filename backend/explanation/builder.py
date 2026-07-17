"""
backend/explanation/builder.py - Context Construction for the Explanation Layer.

Transforms domain profiles (PlayerProfile, TeamProfile, etc.) into
strongly typed, validated ExplanationContexts.
"""

from typing import Any

from backend.explanation.context import (
    ComparisonExplanationContext,
    EvidencePacket,
    PlayerExplanationContext,
    RecruitmentExplanationContext,
    TeamExplanationContext,
)
from shared.schemas import (
    CollectiveProfile,
    ComparisonResult,
    PlayerProfile,
    RecruitmentCandidate,
    RecruitmentCriteria,
)


def _build_capability_packet(
    cap_name: str, cap_obj: Any, signals: list[str]
) -> EvidencePacket:
    """Builds an EvidencePacket for a specific capability."""
    metrics = [
        {
            "metric_name": "score",
            "raw_value": getattr(cap_obj, "score", 0.0),
            "percentile": getattr(cap_obj, "score", 0.0),
            "contribution_weight": 1.0,
            "explanation": "Overall Score",
        }
    ]
    if hasattr(cap_obj, "evidence") and isinstance(cap_obj.evidence, list):
        from dataclasses import asdict

        for metric in cap_obj.evidence:
            metrics.append(asdict(metric))

    title = cap_name.replace("_", " ").title()

    return EvidencePacket(
        source=f"capability:{cap_name}",
        title=f"{title} Capability",
        confidence=getattr(cap_obj, "confidence", 1.0),
        supporting_metrics=metrics,
        supporting_signals=signals,
        optional_caveats=[],
    )


def build_player_context(profile: PlayerProfile) -> PlayerExplanationContext:
    """Builds an explanation context from a PlayerProfile."""
    packets = []

    if profile.capability_profile:
        cap_prof = profile.capability_profile
        # Map capabilities to packets
        from shared.config.capabilities import CORE_CAPABILITIES

        cap_names = CORE_CAPABILITIES

        for cap_name in cap_names:
            cap_obj = getattr(cap_prof, cap_name)
            if cap_obj:
                # Find signals related to this capability (mock mapping for now)
                # In a real app, signals would have a capability affinity.
                related_signals = [
                    sig
                    for sig in profile.decision_signals
                    if sig.lower() in cap_name.lower()
                ]
                if not related_signals and cap_obj.score > 80:
                    # just providing some evidence relation
                    related_signals = list(profile.decision_signals)

                packets.append(
                    _build_capability_packet(cap_name, cap_obj, related_signals)
                )

    overall_conf = (
        profile.capability_profile.overall_confidence()
        if profile.capability_profile
        else 1.0
    )

    return PlayerExplanationContext(
        player_id=profile.player_id,
        player_name=profile.player_name,
        team_name=profile.team_name,
        position_group=profile.position_group,
        birth_date=profile.birth_date,
        minutes_played=profile.minutes_played,
        archetype=profile.display_archetype,
        overall_confidence=overall_conf,
        evidence_packets=packets,
    )


def build_team_context(profile: CollectiveProfile) -> TeamExplanationContext:
    """Builds an explanation context from a CollectiveProfile."""
    packets = []

    # We create evidence packets for the aggregated capabilities
    from shared.config.capabilities import CORE_CAPABILITIES

    cap_names = CORE_CAPABILITIES

    for cap_name in cap_names:
        score = profile.avg_capabilities.get(cap_name, None)
        if score is not None:
            packets.append(
                EvidencePacket(
                    source=f"capability:{cap_name}",
                    title=f"{cap_name.replace('_', ' ').title()} Capability (Squad Avg)",
                    confidence=1.0,
                    supporting_metrics=[
                        {
                            "metric_name": "score",
                            "raw_value": score,
                            "percentile": score,
                            "contribution_weight": 1.0,
                            "explanation": "Average squad capability",
                        }
                    ],
                    supporting_signals=[],
                )
            )

    identity_dict = {
        "primary": profile.identity.primary_identity if profile.identity else "Unknown",
        "secondary": profile.identity.secondary_identity if profile.identity else None,
        "emergent_traits": profile.identity.emergent_traits if profile.identity else [],
    }

    concentration = [
        {
            "capability": c.capability_name,
            "hhi": c.hhi_score,
            "is_over_centralized": c.is_over_centralized,
            "top_contributors": c.top_contributors,
        }
        for c in profile.concentration
        if c.is_over_centralized
    ]

    bottlenecks = [
        {
            "upstream": b.upstream_capability,
            "downstream": b.downstream_capability,
            "severity": b.severity,
            "diagnosis": b.diagnosis,
        }
        for b in profile.bottlenecks
    ]

    # Top 3 fragilities
    fragilities = [
        {
            "player_name": f.player_name,
            "replaceability_index": f.replaceability_index,
            "structural_deficit": f.structural_deficit,
        }
        for f in sorted(
            profile.fragility_map, key=lambda x: x.structural_deficit, reverse=True
        )[:3]
    ]

    return TeamExplanationContext(
        team_id=profile.team_id,
        team_name=profile.team_name,
        competition=profile.competition,
        season=profile.season,
        squad_size=20,  # Fixed for now or computed
        average_age=25.0,  # Fixed for now
        style_label=identity_dict["primary"],
        collective_identity=identity_dict,
        concentration_risks=concentration,
        system_bottlenecks=bottlenecks,
        key_fragilities=fragilities,
        evidence_packets=packets,
    )


def build_recruitment_context(
    criteria: RecruitmentCriteria, candidates: list[RecruitmentCandidate]
) -> RecruitmentExplanationContext:
    """Builds an explanation context for recruitment recommendations."""
    serialized_candidates = []

    for c in candidates:
        serialized = {
            "player_name": c.player.player_name,
            "fit_score": c.fit_score,
            "rank": c.rank,
            "strengths": c.strengths,
            "trade_offs": c.trade_offs,
            "decision_signals": c.decision_signals,
            "confidence": c.confidence,
            "evidence_context": c.explanation_context,
        }
        serialized_candidates.append(serialized)

    return RecruitmentExplanationContext(
        position_target=criteria.position or "Any",
        tactical_style_target=criteria.tactical_style,
        required_capabilities=criteria.required_capabilities,
        candidates=serialized_candidates,
    )


def build_comparison_context(result: ComparisonResult) -> ComparisonExplanationContext:
    """Builds an explanation context for a player comparison."""
    player_contexts = [build_player_context(p) for p in result.players]

    return ComparisonExplanationContext(
        players=player_contexts,
        shared_strengths=result.shared_strengths,
        key_differences=result.key_differences,
    )
