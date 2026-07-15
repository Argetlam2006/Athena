"""
backend/explanation/builder.py — Context Construction for the Explanation Layer.

Transforms domain profiles (PlayerProfile, TeamProfile, etc.) into 
strongly typed, validated ExplanationContexts.
"""

from typing import Any
from shared.schemas import (
    PlayerProfile, 
    TeamProfile, 
    RecruitmentCandidate, 
    RecruitmentCriteria, 
    ComparisonResult
)
from backend.explanation.context import (
    EvidencePacket,
    PlayerExplanationContext,
    TeamExplanationContext,
    RecruitmentExplanationContext,
    ComparisonExplanationContext
)

def _build_capability_packet(cap_name: str, cap_obj: Any, signals: list[str]) -> EvidencePacket:
    """Builds an EvidencePacket for a specific capability."""
    metrics = {"score": getattr(cap_obj, "score", 0.0)}
    if hasattr(cap_obj, "evidence") and isinstance(cap_obj.evidence, dict):
        for k, v in cap_obj.evidence.items():
            metrics[k] = v
            
    title = cap_name.replace("_", " ").title()
    
    return EvidencePacket(
        source=f"capability:{cap_name}",
        title=f"{title} Capability",
        confidence=getattr(cap_obj, "confidence", 1.0),
        supporting_metrics=metrics,
        supporting_signals=signals,
        optional_caveats=[]
    )

def build_player_context(profile: PlayerProfile) -> PlayerExplanationContext:
    """Builds an explanation context from a PlayerProfile."""
    packets = []
    
    if profile.capability_profile:
        cap_prof = profile.capability_profile
        # Map capabilities to packets
        cap_names = [
            "ball_progression", "chance_creation", "ball_security", 
            "press_resistance", "defensive_activity", "attacking_threat", 
            "physical_availability", "tactical_versatility"
        ]
        
        for cap_name in cap_names:
            cap_obj = getattr(cap_prof, cap_name)
            if cap_obj:
                # Find signals related to this capability (mock mapping for now)
                # In a real app, signals would have a capability affinity.
                related_signals = [sig for sig in profile.decision_signals if sig.lower() in cap_name.lower()]
                if not related_signals and cap_obj.score > 80:
                    # just providing some evidence relation
                    related_signals = [sig for sig in profile.decision_signals]
                    
                packets.append(_build_capability_packet(cap_name, cap_obj, related_signals))
                
    overall_conf = profile.capability_profile.overall_confidence() if profile.capability_profile else 1.0
    
    return PlayerExplanationContext(
        player_id=profile.player_id,
        player_name=profile.player_name,
        team_name=profile.team_name,
        position_group=profile.position_group,
        age_years=profile.age_years,
        minutes_played=profile.minutes_played,
        archetype=profile.archetype or "Unknown",
        overall_confidence=overall_conf,
        evidence_packets=packets
    )

def build_team_context(profile: TeamProfile) -> TeamExplanationContext:
    """Builds an explanation context from a TeamProfile."""
    packets = []
    
    # We create evidence packets for the aggregated capabilities
    cap_names = [
        "ball_progression", "chance_creation", "ball_security", 
        "press_resistance", "defensive_activity", "attacking_threat", 
        "physical_availability", "tactical_versatility"
    ]
    
    for cap_name in cap_names:
        score = getattr(profile, f"avg_{cap_name}", None)
        if score is not None:
            packets.append(
                EvidencePacket(
                    source=f"capability:{cap_name}",
                    title=f"{cap_name.replace('_', ' ').title()} Capability (Squad Avg)",
                    confidence=1.0,
                    supporting_metrics={"score": score},
                    supporting_signals=[]
                )
            )
            
    return TeamExplanationContext(
        team_id=profile.team_id,
        team_name=profile.team_name,
        competition=profile.competition,
        season=profile.season,
        squad_size=profile.squad_size,
        average_age=profile.avg_age,
        style_label=profile.style_label or "Balanced",
        evidence_packets=packets
    )

def build_recruitment_context(criteria: RecruitmentCriteria, candidates: list[RecruitmentCandidate]) -> RecruitmentExplanationContext:
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
            "evidence_context": c.explanation_context
        }
        serialized_candidates.append(serialized)
        
    return RecruitmentExplanationContext(
        position_target=criteria.position or "Any",
        tactical_style_target=criteria.tactical_style,
        required_capabilities=criteria.required_capabilities,
        candidates=serialized_candidates
    )

def build_comparison_context(result: ComparisonResult) -> ComparisonExplanationContext:
    """Builds an explanation context for a player comparison."""
    player_contexts = [build_player_context(p) for p in result.players]
    
    return ComparisonExplanationContext(
        players=player_contexts,
        shared_strengths=result.shared_strengths,
        key_differences=result.key_differences
    )
