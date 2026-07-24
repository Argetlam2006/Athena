"""
backend/retrieval/execution.py — Retrieval execution engine.

Executes a RetrievalPlan against the Entity Graph and produces
an EvidenceBundle containing Claims and coverage metadata.

This module contains no planning logic and no football analysis.
Its only responsibility is faithful plan execution.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from backend.knowledge.query import GraphQuery
from backend.reasoning.projector import ClaimProjector
from shared.schemas.retrieval import (
    Claim,
    ClaimType,
    Coverage,
    EntityRef,
    EvidenceBundle,
    NodeType,
    RetrievalPlan,
    RetrievalStepType,
    StructuredIntent,
)

logger = logging.getLogger(__name__)

# Type alias for a claim projection function registered in the dispatch table.
ProjectorFn = Callable[[ClaimProjector, EntityRef, int], list[Claim] | Claim | None]


def _project_capability(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project capability claims."""
    return proj.capability_claims(ref, pid)


def _project_archetype(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project archetype claim."""
    arch = proj.archetype_claim(ref, pid)
    return [arch] if arch else []


def _project_role_fit(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project role-fit claims."""
    return proj.role_fit_claims(ref, pid)


def _project_team_capability(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project team capability claims (pid unused — ref determines the team)."""
    return proj.team_capability_claims(ref)


def _project_team_fragility(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project team fragility claims."""
    return proj.team_fragility_claims(ref)


def _project_team_identity(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project team identity claims."""
    return proj.team_identity_claims(ref)


def _project_team_bottleneck(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project team bottleneck claims."""
    return proj.team_bottleneck_claims(ref)


def _project_team_concentration(proj: ClaimProjector, ref: EntityRef, pid: int) -> list[Claim]:
    """Project team concentration claims."""
    return proj.team_concentration_claims(ref)


# ─── Claim type dispatch registry ─────────────────────────────────────────────
#
# This is the single branching point for claim type dispatch.
# Adding a new claim type requires:
#   1. Adding a ClaimType enum member in shared/schemas/retrieval.py
#   2. Adding a projection function here
#   3. Registering it in CLAIM_DISPATCH
#
# No other module needs to change — not even coverage validation.

CLAIM_DISPATCH: dict[ClaimType, ProjectorFn] = {
    ClaimType.CAPABILITY: _project_capability,
    ClaimType.ARCHE_TYPE: _project_archetype,
    ClaimType.ROLE_FIT: _project_role_fit,
    ClaimType.TEAM_CAPABILITY: _project_team_capability,
    ClaimType.TEAM_FRAGILITY: _project_team_fragility,
    ClaimType.TEAM_IDENTITY: _project_team_identity,
    ClaimType.TEAM_BOTTLENECK: _project_team_bottleneck,
    ClaimType.TEAM_CONCENTRATION: _project_team_concentration,
}


class RetrievalExecutor:
    """Executes RetrievalPlans against the Entity Graph.

    The executor is plan-agnostic — it handles any valid plan.
    Strategy logic lives entirely in the plan.
    """

    def __init__(self):
        self.graph = GraphQuery()
        self.projector = ClaimProjector()

    def execute(
        self,
        plan: RetrievalPlan,
        intent: StructuredIntent,
    ) -> EvidenceBundle:
        """Execute a RetrievalPlan and produce an EvidenceBundle.

        Args:
            plan: The plan to execute.
            intent: The original intent (for audit).

        Returns:
            EvidenceBundle with claims, coverage, and execution metadata.
        """
        start = time.perf_counter()
        all_claims: list[Claim] = []
        executed_traversals = 0
        sought_claim_types: set[str] = set(plan.expected_claim_types)

        for step in plan.steps:
            if step.step_type == RetrievalStepType.GET_ENTITY:
                # Validate the entity exists in the graph
                if step.entity_ref:
                    self.graph.get_entity(step.entity_ref)

            elif step.step_type == RetrievalStepType.TRAVERSE_EDGES:
                if step.entity_ref and step.edge_type:
                    self.graph.get_edges(
                        source_ref=step.entity_ref,
                        edge_type=step.edge_type,
                    )
                    executed_traversals += 1

            elif step.step_type == RetrievalStepType.PROJECT_CLAIMS:
                if step.entity_ref and step.claim_types:
                    pid = self._resolve_player_id(step.entity_ref)
                    player_id: int | None = int(pid) if pid is not None else None
                    for ct_name in step.claim_types:
                        try:
                            ct = ClaimType(ct_name)
                        except ValueError:
                            logger.warning(
                                "Unknown claim type '%s' in plan step — skipping",
                                ct_name,
                            )
                            continue
                        projector_fn = CLAIM_DISPATCH.get(ct)
                        if projector_fn is None:
                            logger.warning(
                                "No projector registered for claim type '%s'",
                                ct_name,
                            )
                            continue
                        result = projector_fn(self.projector, step.entity_ref, player_id)
                        if result:
                            if isinstance(result, list):
                                all_claims.extend(result)
                            else:
                                all_claims.append(result)

        elapsed = (time.perf_counter() - start) * 1000

        # Build coverage map
        found_claim_types = list({c.claim_type for c in all_claims})
        missing = list(sought_claim_types - set(found_claim_types))
        satisfied = list(set(found_claim_types) & sought_claim_types)

        coverage = Coverage(
            total_sought=len(sought_claim_types),
            satisfied=satisfied,
            missing=missing,
        )

        return EvidenceBundle(
            intent=intent,
            claims=all_claims,
            plan_id=plan.plan_id,
            store_fingerprint=plan.store_fingerprint,
            coverage=coverage,
            execution_time_ms=elapsed,
            traversal_count=executed_traversals,
        )

    def _resolve_player_id(self, ref: EntityRef) -> int | None:
        """Extract a numeric player_id from an EntityRef."""
        if ref.node_type != NodeType.PLAYER:
            return None
        try:
            return int(ref.entity_id)
        except (ValueError, TypeError):
            return None
