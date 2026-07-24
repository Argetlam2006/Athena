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
from shared.schemas import CollectiveProfile
from shared.schemas.retrieval import (
    Claim,
    ClaimProvenance,
    ClaimQualifier,
    EdgeType,
    EntityRef,
    NodeType,
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

    def _load_collective_for_ref(self, entity_ref: EntityRef) -> CollectiveProfile | None:
        """Load a CollectiveProfile matching a team EntityRef.

        The graph stores team entity_ids as ``{team_name}__{competition}__{season}``.
        We load all collectives and match by normalised team name.
        """
        if entity_ref.node_type != NodeType.TEAM:
            return None
        entity_key = entity_ref.entity_id.lower()
        collectives = self.store.get_all_collectives()
        for c in collectives:
            key = f"{c.team_name}__{c.competition}__{c.season}".replace(" ", "_").lower()
            if key == entity_key:
                return c
        return None

    def team_capability_claims(
        self,
        entity_ref: EntityRef,
    ) -> list[Claim]:
        """Project team-level capability claims from HAS_SQUAD_CAPABILITY edges.

        Enriches each claim with distributional context (how this capability
        compares to the team's own average across all capabilities) so the
        LLM can reason about relative strengths and weaknesses.
        """
        edges = self.graph.get_edges(
            source_ref=entity_ref,
            edge_type=EdgeType.HAS_SQUAD_CAPABILITY,
        )
        if not edges:
            return []

        # Load the collective profile for distributional context
        collective = self._load_collective_for_ref(entity_ref)
        all_scores = list(collective.avg_capabilities.values()) if collective and collective.avg_capabilities else []
        team_avg = sum(all_scores) / len(all_scores) if all_scores else 50.0

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

            # Add distributional qualifier relative to team's own average
            gap = score - team_avg
            if abs(gap) > 10:
                direction = "strongest" if gap > 0 else "weakest"
                qualifiers.append(ClaimQualifier(
                    kind=QualifierKind.ROLE_DEPENDENCE,
                    severity=Severity.INFORMATIONAL,
                    statement=f"{gap:+.0f} from team average of {team_avg:.0f}/100 ({direction} capability)",
                ))

            claims.append(Claim(
                claim_id=make_claim_id(entity_ref, f"team_capability:{cap_name}", self._fingerprint),
                about_entity=entity_ref,
                claim_type="team_capability",
                predicate_key=f"team_capability:{cap_name}",
                statement=f"Team {cap_name}: {score:.1f}/100",
                strength=score,
                confidence="high",
                confidence_basis=f"Squad-average capability score, team avg={team_avg:.0f}/100",
                supports=[
                    {"metric_name": "Squad Avg", "raw_value": score, "percentile": score,
                     "contribution_weight": 1.0, "explanation": "Squad-average capability score"},
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
        """Project team fragility claims from FRAGILE_ON edges.

        Includes the player name in the statement (fetched from the graph
        node display_name) so the LLM reads "Fragile on Bukayo Saka"
        rather than "Fragile on player:123".
        """
        edges = self.graph.get_edges(
            source_ref=entity_ref,
            edge_type=EdgeType.FRAGILE_ON,
        )
        if not edges:
            return []

        # Pre-load player display names from the graph nodes.
        # FRAGILE_ON edges store targets as "player:{numeric_id}" but the
        # graph nodes use bare numeric entity_ids — strip the prefix when
        # looking up.
        player_names: dict[str, str] = {}
        for edge in edges:
            target = edge.target
            raw_id = target.entity_id
            # Strip "player:" prefix if present to match graph node entity_id
            stripped = raw_id.split(":", 1)[-1] if ":" in raw_id else raw_id
            node_ref = EntityRef(node_type=NodeType.PLAYER, entity_id=stripped)
            node = self.graph.get_entity(node_ref)
            if node:
                player_names[raw_id] = node.get("display_name", stripped)

        edges.sort(key=lambda e: e.metadata.get("structural_deficit", 0), reverse=True)
        claims: list[Claim] = []
        for edge in edges[:5]:
            meta = edge.metadata
            deficit = meta.get("structural_deficit", 0)
            player_name = player_names.get(
                edge.target.entity_id,
                edge.target.entity_id.rsplit(":", 1)[-1],
            )

            claims.append(Claim(
                claim_id=make_claim_id(entity_ref, f"fragility:{edge.target.entity_id}", self._fingerprint),
                about_entity=entity_ref,
                about_relation=edge.target,
                claim_type="team_fragility",
                predicate_key=f"fragility:{edge.target.entity_id}",
                statement=f"Fragile on {player_name} (deficit={deficit:.1f})",
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

    # ── Team identity claims ─────────────────────────────────────────────

    def team_identity_claims(
        self,
        entity_ref: EntityRef,
    ) -> list[Claim]:
        """Project the team's tactical identity as a single claim.

        Reads the CollectiveProfile's CollectiveIdentity (primary style,
        secondary style, emergent traits) and projects it as a structured
        claim the LLM can use for tactical reasoning.
        """
        collective = self._load_collective_for_ref(entity_ref)
        if not collective or not collective.identity:
            return []

        identity = collective.identity
        parts = [f"Primary tactical style: {identity.primary_identity}"]
        if identity.secondary_identity:
            parts.append(f"secondary: {identity.secondary_identity}")
        if identity.emergent_traits:
            parts.append(f"emergent traits: {', '.join(identity.emergent_traits)}")

        # Strength estimate based on identity clarity
        strength = 75.0 if identity.secondary_identity else (
            60.0 if identity.primary_identity != "Balanced" else 40.0
        )

        qualifiers = []
        if identity.primary_identity == "Balanced":
            qualifiers.append(ClaimQualifier(
                kind=QualifierKind.DATA_COVERAGE,
                severity=Severity.INFORMATIONAL,
                statement="Team does not strongly match any single tactical template — may be versatile or transitional",
            ))

        return [Claim(
            claim_id=make_claim_id(entity_ref, "team_identity", self._fingerprint),
            about_entity=entity_ref,
            claim_type="team_identity",
            predicate_key="team_identity",
            statement="; ".join(parts),
            strength=strength,
            confidence="medium",
            confidence_basis=f"Primary={identity.primary_identity}, secondary={identity.secondary_identity or 'none'}",
            supports=[
                {"metric_name": "Primary Identity", "raw_value": float(ord(identity.primary_identity[0])),
                 "percentile": strength, "contribution_weight": 0.6,
                 "explanation": f"Closest tactical template: {identity.primary_identity}"},
                {"metric_name": "Identity Clarity",
                 "raw_value": 1.0 if identity.secondary_identity else 0.5,
                 "percentile": strength, "contribution_weight": 0.4,
                 "explanation": "Whether a secondary identity was detected"},
            ],
            qualifiers=qualifiers,
            related_entity_refs=[
                EntityRef(node_type=NodeType.TACTICAL_SYSTEM, entity_id=f"system:{identity.primary_identity.lower().replace(' ', '_')}"),
            ] if identity.primary_identity != "Balanced" else [],
            provenance=build_provenance(
                engine="CollectiveEngine",
                store_fingerprint=self._fingerprint,
                rule_refs=["backend.collective.identity.generate_collective_identity"],
            ),
        )]

    # ── Team bottleneck claims ───────────────────────────────────────────

    def team_bottleneck_claims(
        self,
        entity_ref: EntityRef,
    ) -> list[Claim]:
        """Project capability-conversion bottlenecks as claims.

        Each bottleneck represents an upstream capability that fails to
        convert into downstream value (e.g. the team progresses well but
        doesn't create threats).
        """
        collective = self._load_collective_for_ref(entity_ref)
        if not collective or not collective.bottlenecks:
            return []

        claims: list[Claim] = []
        for bottleneck in collective.bottlenecks:
            claims.append(Claim(
                claim_id=make_claim_id(
                    entity_ref,
                    f"bottleneck:{bottleneck.upstream_capability}_{bottleneck.downstream_capability}",
                    self._fingerprint,
                ),
                about_entity=entity_ref,
                claim_type="team_bottleneck",
                predicate_key=f"bottleneck:{bottleneck.upstream_capability}_{bottleneck.downstream_capability}",
                statement=bottleneck.diagnosis,
                strength=100.0 - min(bottleneck.severity, 100.0),
                confidence="medium",
                confidence_basis=f"Upstream={bottleneck.upstream_capability}, downstream={bottleneck.downstream_capability}, gap={bottleneck.severity:.0f}pts",
                supports=[
                    {"metric_name": "Upstream Capability", "raw_value": 0.0,
                     "percentile": 0.0, "contribution_weight": 0.5,
                     "explanation": bottleneck.upstream_capability},
                    {"metric_name": "Downstream Capability", "raw_value": 0.0,
                     "percentile": 0.0, "contribution_weight": 0.5,
                     "explanation": bottleneck.downstream_capability},
                ],
                qualifiers=[
                    ClaimQualifier(
                        kind=QualifierKind.DATA_COVERAGE,
                        severity=Severity.INFORMATIONAL,
                        statement=f"Bottleneck severity: {bottleneck.severity:.0f} point gap",
                    ),
                ],
                provenance=build_provenance(
                    engine="CollectiveEngine",
                    store_fingerprint=self._fingerprint,
                    rule_refs=["backend.collective.bottlenecks.identify_bottlenecks"],
                ),
            ))
        return claims

    # ── Team concentration claims ────────────────────────────────────────

    def team_concentration_claims(
        self,
        entity_ref: EntityRef,
    ) -> list[Claim]:
        """Project capability-concentration (HHI) as claims.

        Highlights capabilities that are over-centralised on a small
        number of players — a squad-structure risk the LLM should be
        aware of when evaluating team resilience.
        """
        collective = self._load_collective_for_ref(entity_ref)
        if not collective or not collective.concentration:
            return []

        claims: list[Claim] = []
        for cc in collective.concentration:
            top_names = [name for name, _ in cc.top_contributors]
            top_str = ", ".join(top_names[:3])

            display_name = cc.capability_name.replace("_", " ").title()
            statement = (
                f"{display_name} is {'over-centralised' if cc.is_over_centralized else 'distributed'} "
                f"(HHI={cc.hhi_score:.0f})"
            )
            if top_names:
                statement += f". Top contributors: {top_str}"

            claims.append(Claim(
                claim_id=make_claim_id(entity_ref, f"concentration:{cc.capability_name}", self._fingerprint),
                about_entity=entity_ref,
                claim_type="team_concentration",
                predicate_key=f"concentration:{cc.capability_name}",
                statement=statement,
                strength=max(0.0, 100.0 - cc.hhi_score / 50.0),
                confidence="medium" if cc.is_over_centralized else "high",
                confidence_basis=f"HHI={cc.hhi_score:.0f}, threshold=2500",
                supports=[
                    {"metric_name": "HHI Score", "raw_value": cc.hhi_score,
                     "percentile": 100.0 - min(cc.hhi_score / 50.0, 100.0),
                     "contribution_weight": 1.0,
                     "explanation": f"Herfindahl-Hirschman Index for {display_name} concentration"},
                ],
                qualifiers=[
                    ClaimQualifier(
                        kind=QualifierKind.DATA_COVERAGE,
                        severity=Severity.MATERIAL if cc.is_over_centralized else Severity.INFORMATIONAL,
                        statement=(
                            f"Over-centralised (HHI={cc.hhi_score:.0f} > 2500) — loss of a single "
                            f"top contributor would significantly reduce this capability"
                            if cc.is_over_centralized
                            else f"Reasonably distributed (HHI={cc.hhi_score:.0f} ≤ 2500)"
                        ),
                    ),
                ],
                provenance=build_provenance(
                    engine="CollectiveEngine",
                    store_fingerprint=self._fingerprint,
                    rule_refs=["backend.collective.structure.compute_capability_concentration"],
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
