"""
backend/reasoning/projector.py — Claim projection engine.

Projects entities and edges from the Entity Graph into Claims —
atomic, deterministic assertions with provenance and qualifiers.

Claims are the ONLY artifact the LLM reasons over.
"""

from __future__ import annotations

import hashlib
import json
import logging

from backend.intelligence.store import IntelligenceStore
from backend.knowledge.query import GraphQuery
from backend.reasoning.qualifiers import derive_qualifiers_from_profile
from shared.config.capabilities import CAPABILITY_DISPLAY_NAMES, CORE_CAPABILITIES
from shared.schemas.retrieval import (
    Claim,
    ClaimProvenance,
    ClaimQualifier,
    EdgeType,
    EntityRef,
    QualifierKind,
    Severity,
)

logger = logging.getLogger(__name__)


# ─── Claim ID generation ──────────────────────────────────────────────────────


def make_claim_id(
    entity_ref: EntityRef,
    predicate_key: str,
    store_fingerprint: str,
) -> str:
    """Deterministic claim ID from (about_entity, predicate_key, fingerprint).

    Same inputs → same claim_id across processes.
    """
    raw = f"{entity_ref}|{predicate_key}|{store_fingerprint}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Provenance builder ──────────────────────────────────────────────────────


def build_provenance(
    engine: str,
    store_fingerprint: str,
    rule_refs: list[str] | None = None,
) -> ClaimProvenance:
    """Build a ClaimProvenance for the current store state."""
    from shared.constants import MODEL_VERSION, SCHEMA_VERSION, WEIGHTING_VERSION

    return ClaimProvenance(
        engine=engine,
        version_lineage=".".join([MODEL_VERSION, SCHEMA_VERSION, WEIGHTING_VERSION]),
        store_fingerprint=store_fingerprint,
        rule_refs=rule_refs or [],
    )


# ─── Projector ────────────────────────────────────────────────────────────────


class ClaimProjector:
    """Projects claims from the Entity Graph and Intelligence Store.

    Usage:
        projector = ClaimProjector()
        claim = projector.capability_claim(player_id=42, capability="ball_progression")
    """

    def __init__(self):
        self.store = IntelligenceStore()
        self.graph = GraphQuery()
        self._fingerprint: str = ""
        self._load_fingerprint()

    def _load_fingerprint(self) -> None:
        """Load store fingerprint for provenance."""
        from pathlib import Path

        fp_path = Path("data/warehouse/intelligence_fingerprint.json")
        if fp_path.exists():
            try:
                with open(fp_path) as f:
                    data = json.load(f)
                self._fingerprint = data.get("model_version", "unknown")
            except Exception:
                self._fingerprint = "unknown"

    # ── Capability claims ─────────────────────────────────────────────────

    def capability_claims(
        self,
        entity_ref: EntityRef,
        player_id: int,
    ) -> list[Claim]:
        """Project capability claims for a player from the graph.

        Reads the player's HAS_CAPABILITY edges and enriches each
        with the full CapabilityScore data from the store.

        Returns one Claim per capability.
        """
        edges = self.graph.get_edges(
            source_ref=entity_ref,
            edge_type=EdgeType.HAS_CAPABILITY,
        )
        if not edges:
            return []

        # Load player profile for qualifier data
        profile = self.store.get_player(player_id)
        if not profile:
            return []

        claims: list[Claim] = []
        for edge in edges:
            # entity_id has the form "capability:ball_progression" — extract the key
            cap_name = edge.target.entity_id.split(":", 1)[-1] if ":" in edge.target.entity_id else edge.target.entity_id

            if cap_name not in CORE_CAPABILITIES:
                continue

            cap_obj = getattr(profile.capability_profile, cap_name, None)
            if cap_obj is None:
                continue

            display = CAPABILITY_DISPLAY_NAMES.get(cap_name, cap_name.replace("_", " ").title())

            # Derive qualifiers from profile data
            qualifiers = derive_qualifiers_from_profile(profile, cap_name)

            # Build statement from the capability score
            score = cap_obj.score if cap_obj.score else 0.0
            if score >= 85:
                level = "Elite"
            elif score >= 75:
                level = "Strong"
            elif score >= 60:
                level = "Above Average"
            elif score >= 40:
                level = "Average"
            else:
                level = "Below Average"

            claim = Claim(
                claim_id=make_claim_id(entity_ref, f"capability:{cap_name}", self._fingerprint),
                about_entity=entity_ref,
                claim_type="capability",
                predicate_key=f"capability:{cap_name}",
                statement=f"{level} {display} ({score:.1f}/100)",
                strength=score,
                confidence="high" if cap_obj.confidence >= 0.8 else (
                    "medium" if cap_obj.confidence >= 0.5 else "low"
                ),
                confidence_basis=f"Sample: {profile.minutes_played or 0:.0f} min, "
                                f"{getattr(profile, 'matches_played', 0)} matches",
                supports=[
                    {
                        "metric_name": sm.metric_name,
                        "raw_value": sm.raw_value,
                        "percentile": sm.percentile,
                        "contribution_weight": sm.contribution_weight,
                        "explanation": sm.explanation,
                    }
                    for sm in cap_obj.evidence
                ],
                qualifiers=qualifiers,
                provenance=build_provenance(
                    engine="FIE",
                    store_fingerprint=self._fingerprint,
                    rule_refs=[f"FOOTBALL_INTELLIGENCE_ENGINE.md §{cap_name}"],
                ),
            )
            claims.append(claim)

        return claims

    # ── Archetype claims ──────────────────────────────────────────────────

    def archetype_claim(
        self,
        entity_ref: EntityRef,
        player_id: int,
    ) -> Claim | None:
        """Project the archetype classification claim for a player."""
        profile = self.store.get_player(player_id)
        if not profile or not profile.archetype_profile:
            return None

        arch = profile.archetype_profile
        if arch.primary_archetype == "Unknown" and arch.confidence == 0.0:
            return None

        qualifiers = derive_qualifiers_from_profile(profile)

        return Claim(
            claim_id=make_claim_id(entity_ref, "archetype", self._fingerprint),
            about_entity=entity_ref,
            claim_type="archetype",
            predicate_key="archetype",
            statement=f"Classified as {arch.primary_archetype} "
                      f"(confidence: {arch.confidence:.1f}%)",
            strength=arch.confidence,
            confidence="high" if arch.confidence >= 80 else (
                "medium" if arch.confidence >= 50 else "low"
            ),
            confidence_basis=f"Similarity: {arch.confidence:.1f}% to ideal vector",
            supports=[
                {
                    "metric_name": cap,
                    "raw_value": 0.0,
                    "percentile": 0.0,
                    "contribution_weight": 0.0,
                    "explanation": "Contributing capability",
                }
                for cap in arch.contributing_capabilities
            ],
            qualifiers=qualifiers,
            provenance=build_provenance(
                engine="FIE",
                store_fingerprint=self._fingerprint,
                rule_refs=["backend.intelligence.archetypes.assign_archetypes"],
            ),
        )

    # ── Role-fit claims ──────────────────────────────────────────────────

    def role_fit_claims(
        self,
        entity_ref: EntityRef,
        player_id: int,
    ) -> list[Claim]:
        """Project role-fit claims for a player.

        Uses the existing evaluate_tactical_fit engine to produce a
        SystemCompatibilityContext, then projects that into a claim.
        """
        from backend.recommendation.matching import evaluate_tactical_fit

        profile = self.store.get_player(player_id)
        if not profile or not profile.capability_profile:
            return []

        # Evaluate against common tactical systems
        systems = [
            "Possession-Dominant", "High Press", "Counter-Attacking",
            "Direct and Progressive", "Defensive and Resilient",
        ]
        claims: list[Claim] = []

        for system in systems:
            fit = evaluate_tactical_fit(profile, system)
            if fit is None or fit.overall_compatibility == 0.0:
                continue

            qualifiers = derive_qualifiers_from_profile(profile)
            claim = Claim(
                claim_id=make_claim_id(entity_ref, f"role_fit:{system}", self._fingerprint),
                about_entity=entity_ref,
                claim_type="role_fit",
                predicate_key=f"role_fit:{system}",
                statement=f"{system} fit: {fit.overall_compatibility:.1f}/100",
                strength=fit.overall_compatibility,
                confidence="high" if fit.overall_compatibility >= 80 else (
                    "medium" if fit.overall_compatibility >= 50 else "low"
                ),
                confidence_basis=(
                    f"Alignment={fit.capability_alignment:.1f}, "
                    f"Identity={fit.tactical_identity_preservation:.1f}, "
                    f"Relief={fit.dependency_relief:.1f}"
                ),
                supports=[
                    {"metric_name": "Capability Alignment",
                     "raw_value": fit.capability_alignment, "percentile": 0.0,
                     "contribution_weight": 0.4, "explanation": "Core capability match"},
                    {"metric_name": "Identity Preservation",
                     "raw_value": fit.tactical_identity_preservation, "percentile": 0.0,
                     "contribution_weight": 0.2, "explanation": "Tactical fit stability"},
                    {"metric_name": "Dependency Relief",
                     "raw_value": fit.dependency_relief, "percentile": 0.0,
                     "contribution_weight": 0.2, "explanation": "Addresses team gaps"},
                    {"metric_name": "Availability",
                     "raw_value": fit.availability_impact, "percentile": 0.0,
                     "contribution_weight": 0.1, "explanation": "Match availability risk"},
                ],
                qualifiers=qualifiers,
                provenance=build_provenance(
                    engine="DecisionEngine",
                    store_fingerprint=self._fingerprint,
                    rule_refs=["backend.recommendation.matching.evaluate_tactical_fit"],
                ),
            )
            claims.append(claim)

        return claims

    # ── Team capability claims ───────────────────────────────────────────

    def team_capability_claims(
        self,
        entity_ref: EntityRef,
    ) -> list[Claim]:
        """Project team-level capability claims from HAS_SQUAD_CAPABILITY edges."""
        edges = self.graph.get_edges(
            source_ref=entity_ref,
            edge_type=EdgeType.HAS_SQUAD_CAPABILITY,
        )
        if not edges:
            return []

        claims: list[Claim] = []
        for edge in edges:
            cap_name = edge.target.entity_id.split(":", 1)[-1]
            score = (edge.weight or 0) * 100

            qualifiers: list = []
            if score < 40:
                qualifiers.append(ClaimQualifier(
                    kind=QualifierKind.DATA_COVERAGE,
                    severity=Severity.CAUTIONARY,
                    statement=f"Weak team capability ({score:.0f}/100)",
                ))

            claims.append(Claim(
                claim_id=make_claim_id(entity_ref, f"team_capability:{cap_name}", self._fingerprint),
                about_entity=entity_ref,
                claim_type="team_capability",
                predicate_key=f"team_capability:{cap_name}",
                statement=f"Team {cap_name}: {score:.1f}/100",
                strength=score,
                confidence="high",
                confidence_basis="Squad-average capability score",
                supports=[
                    {"metric_name": "Squad Avg", "raw_value": score, "percentile": score,
                     "contribution_weight": 1.0, "explanation": "Appearances-weighted squad average"},
                ],
                qualifiers=qualifiers,
                provenance=build_provenance(
                    engine="CollectiveEngine",
                    store_fingerprint=self._fingerprint,
                    rule_refs=["backend.collective.engine"],
                ),
            ))
        return claims

    # ── Team fragility claims ────────────────────────────────────────────

    def team_fragility_claims(
        self,
        entity_ref: EntityRef,
    ) -> list[Claim]:
        """Project team fragility claims from FRAGILE_ON edges."""
        edges = self.graph.get_edges(
            source_ref=entity_ref,
            edge_type=EdgeType.FRAGILE_ON,
        )
        if not edges:
            return []

        edges.sort(key=lambda e: e.metadata.get("structural_deficit", 0), reverse=True)
        claims: list[Claim] = []
        for edge in edges[:5]:
            meta = edge.metadata
            deficit = meta.get("structural_deficit", 0)

            claims.append(Claim(
                claim_id=make_claim_id(entity_ref, f"fragility:{edge.target.entity_id}", self._fingerprint),
                about_entity=entity_ref,
                about_relation=edge.target,
                claim_type="team_fragility",
                predicate_key=f"fragility:{edge.target.entity_id}",
                statement=f"Fragile on player {edge.target.entity_id} (deficit={deficit:.1f})",
                strength=100 - deficit,
                confidence="medium",
                confidence_basis=f"Structural deficit={deficit:.1f}",
                supports=[
                    {"metric_name": "Structural Deficit", "raw_value": deficit,
                     "percentile": 0.0, "contribution_weight": 0.6,
                     "explanation": "Capability loss without this player"},
                    {"metric_name": "Replaceability", "raw_value": meta.get("replaceability_index", 0),
                     "percentile": 0.0, "contribution_weight": 0.4,
                     "explanation": "Ease of finding a replacement"},
                ],
                provenance=build_provenance(
                    engine="CollectiveEngine",
                    store_fingerprint=self._fingerprint,
                    rule_refs=["backend.collective.fragility.analyze_system_fragility"],
                ),
            ))
        return claims

    # ── Project all claims for an entity ──────────────────────────────────

    def project_for_player(self, entity_ref: EntityRef, player_id: int) -> list[Claim]:
        """Project ALL claims for a player entity.

        Returns capability + archetype + signal claims.
        """
        claims: list[Claim] = []

        # Capability claims (up to 6)
        try:
            cap_claims = self.capability_claims(entity_ref, player_id)
            claims.extend(cap_claims)
        except Exception as e:
            logger.warning(f"Capability projection failed for player {player_id}: {e}")

        # Archetype claim (1)
        try:
            arch = self.archetype_claim(entity_ref, player_id)
            if arch:
                claims.append(arch)
        except Exception as e:
            logger.warning(f"Archetype projection failed for player {player_id}: {e}")

        return claims
