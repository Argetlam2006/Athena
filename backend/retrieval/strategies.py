"""
backend/retrieval/strategies.py — Retrieval Strategy registry and base interface.

Strategies map a StructuredIntent to a RetrievalPlan.
The dispatch table is a registry — adding a new strategy means registering
a class; no dispatcher code changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod

from shared.schemas.retrieval import (
    ClaimType,
    EdgeType,
    EntityRef,
    IntentType,
    NodeType,
    RetrievalPlan,
    RetrievalStep,
    RetrievalStepType,
    StructuredIntent,
)

logger = logging.getLogger(__name__)


# ─── Strategy base ────────────────────────────────────────────────────────────


class RetrievalStrategy(ABC):
    """Base class for all retrieval strategies.

    Each strategy maps a StructuredIntent → RetrievalPlan.
    The plan describes *what* to retrieve; the executor decides *how*.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical strategy name (used in plan_id, logs, dispatch)."""

    @abstractmethod
    def supports(self, intent: StructuredIntent) -> float:
        """Return a match score 0.0–1.0 for how well this strategy handles intent.

        1.0 = perfect match (this is the primary strategy for this intent type)
        0.0 = cannot handle at all
        Intermediate values support future routing optimisations.
        """

    @abstractmethod
    def plan(self, intent: StructuredIntent) -> RetrievalPlan:
        """Produce a deterministic, serialisable RetrievalPlan from an intent."""

    def _make_plan_id(self, intent: StructuredIntent) -> str:
        raw = f"{self.name}|{intent.primary_type.value}|{json.dumps(intent.entities, sort_keys=True)}"
        return f"plan_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


# ─── Strategy registry ────────────────────────────────────────────────────────

_strategy_registry: dict[str, RetrievalStrategy] = {}


def register_strategy(strategy_cls: type[RetrievalStrategy]) -> type[RetrievalStrategy]:
    """Decorator/function to register a strategy class.

    Instantiates the strategy once and caches the singleton.
    Strategies are stateless plan factories -- they carry no per-call
    state, so a single instance is correct and efficient.
    """
    instance = strategy_cls()
    _strategy_registry[instance.name] = instance
    return strategy_cls


def get_strategy(name: str) -> RetrievalStrategy:
    """Return the cached strategy instance by name."""
    instance = _strategy_registry.get(name)
    if not instance:
        available = list(_strategy_registry.keys())
        raise KeyError(f"Unknown strategy '{name}'. Available: {available}")
    return instance


def dispatch_strategy(intent: StructuredIntent) -> RetrievalStrategy:
    """Select the best strategy for a given intent.

    Iterates registered strategies and picks the one with the highest
    support score.  Strategies are singletons -- no instantiation per call.
    """
    best_score = 0.0
    best_instance: RetrievalStrategy | None = None

    for instance in _strategy_registry.values():
        score = instance.supports(intent)
        if score > best_score:
            best_score = score
            best_instance = instance

    if best_instance is None:
        raise RuntimeError("No strategy registered and no fallback available.")

    logger.info(
        "Dispatch: intent=%s -> strategy=%s (score=%.2f)",
        intent.primary_type.value, best_instance.name, best_score,
    )
    return best_instance


def list_strategies() -> list[str]:
    """Return all registered strategy names."""
    return list(_strategy_registry.keys())


# ═════════════════════════════════════════════════════════════════════════════
# Player Analysis — single-player capability + archetype claims.
# ═════════════════════════════════════════════════════════════════════════════


@register_strategy
class PlayerAnalysisStrategy(RetrievalStrategy):
    """Strategy for single-player intelligence analysis.

    Produces capability claims (6) + archetype claim (1) for the
    focus player.  This covers player analysis, scouting, and
    capability-deep-dive questions.
    """

    @property
    def name(self) -> str:
        return "player_analysis"

    def supports(self, intent: StructuredIntent) -> float:
        if intent.primary_type == IntentType.PLAYER_ANALYSIS:
            return 1.0
        # Keyword-based fallback for raw-text queries
        text = intent.raw_text.lower()
        if any(kw in text for kw in ("profile", "strengths", "weaknesses",
                                      "archetype", "capabilities", "scouting",
                                      "analyse", "analyze", "evaluate")):
            return 0.6
        return 0.0

    def plan(self, intent: StructuredIntent) -> RetrievalPlan:
        focus_id = intent.entities.get("focus_player")
        if not focus_id:
            return RetrievalPlan(
                plan_id=self._make_plan_id(intent),
                strategy_name=self.name,
                intent=intent,
                steps=[],
                expected_claim_types=[],
                store_fingerprint="",
                entity_count=0,
                traversal_count=0,
            )
        focus_ref = EntityRef(node_type=NodeType.PLAYER, entity_id=str(focus_id))

        steps = [
            RetrievalStep(step_type=RetrievalStepType.GET_ENTITY, entity_ref=focus_ref),
            RetrievalStep(step_type=RetrievalStepType.TRAVERSE_EDGES,
                          entity_ref=focus_ref, edge_type=EdgeType.HAS_CAPABILITY),
            RetrievalStep(step_type=RetrievalStepType.PROJECT_CLAIMS,
                          entity_ref=focus_ref,
                          claim_types=[ClaimType.CAPABILITY.value, ClaimType.ARCHE_TYPE.value]),
        ]

        return RetrievalPlan(
            plan_id=self._make_plan_id(intent),
            strategy_name=self.name,
            intent=intent,
            steps=steps,
            expected_claim_types=[ClaimType.CAPABILITY.value, ClaimType.ARCHE_TYPE.value],
            store_fingerprint=intent.filters.get("store_fingerprint", ""),
            entity_count=1,
            traversal_count=1,
        )


# ═════════════════════════════════════════════════════════════════════════════
# Team Analysis — team-level capability + fragility claims.
# ═════════════════════════════════════════════════════════════════════════════


@register_strategy
class TeamAnalysisStrategy(RetrievalStrategy):
    """Strategy for team-level intelligence analysis.

    Produces team capability claims (6), team fragility claims (top 5),
    team identity claim (1), team bottleneck claims, and team
    concentration claims (6, one per capability) — giving the LLM
    structured evidence for tactical reasoning.
    """

    @property
    def name(self) -> str:
        return "team_analysis"

    def supports(self, intent: StructuredIntent) -> float:
        if intent.primary_type == IntentType.TEAM_ANALYSIS:
            return 1.0
        text = intent.raw_text.lower()
        if any(kw in text for kw in ("team", "squad", "tactical", "formation")):
            return 0.4
        return 0.0

    def _build_team_steps(self, team_eid: str) -> list[RetrievalStep]:
        """Build the standard sequence of steps for a single team."""
        ref = EntityRef(node_type=NodeType.TEAM, entity_id=team_eid)
        return [
            RetrievalStep(step_type=RetrievalStepType.GET_ENTITY, entity_ref=ref),
            RetrievalStep(step_type=RetrievalStepType.TRAVERSE_EDGES,
                          entity_ref=ref, edge_type=EdgeType.HAS_SQUAD_CAPABILITY),
            RetrievalStep(step_type=RetrievalStepType.PROJECT_CLAIMS,
                          entity_ref=ref,
                          claim_types=[
                              ClaimType.TEAM_CAPABILITY.value,
                              ClaimType.TEAM_FRAGILITY.value,
                              ClaimType.TEAM_IDENTITY.value,
                              ClaimType.TEAM_BOTTLENECK.value,
                              ClaimType.TEAM_CONCENTRATION.value,
                          ]),
        ]

    def plan(self, intent: StructuredIntent) -> RetrievalPlan:
        team_eid = intent.entities.get("team")
        compare_eid = intent.entities.get("team_compare")

        entity_count = 0
        steps: list[RetrievalStep] = []

        if team_eid:
            entity_count += 1
            steps.extend(self._build_team_steps(team_eid))
        if compare_eid:
            entity_count += 1
            steps.extend(self._build_team_steps(compare_eid))

        return RetrievalPlan(
            plan_id=self._make_plan_id(intent),
            strategy_name=self.name,
            intent=intent,
            steps=steps,
            expected_claim_types=[
                ClaimType.TEAM_CAPABILITY.value,
                ClaimType.TEAM_FRAGILITY.value,
                ClaimType.TEAM_IDENTITY.value,
                ClaimType.TEAM_BOTTLENECK.value,
                ClaimType.TEAM_CONCENTRATION.value,
            ],
            store_fingerprint=intent.filters.get("store_fingerprint", ""),
            entity_count=entity_count,
            traversal_count=sum(1 for s in steps if s.step_type == RetrievalStepType.TRAVERSE_EDGES),
        )


# ═════════════════════════════════════════════════════════════════════════════
# Fallback strategy — handles intents no specialised strategy matches.
# ═════════════════════════════════════════════════════════════════════════════


@register_strategy
class GeneralStrategy(RetrievalStrategy):
    """Fallback strategy for general football knowledge queries.

    Produces an empty plan with expected_claim_types=[] — the executor
    returns an empty bundle and coverage always passes for general
    questions.  This lets the bridge fall through to the existing
    PromptBuilder without retrieval.
    """

    @property
    def name(self) -> str:
        return "general"

    def supports(self, intent: StructuredIntent) -> float:
        return 0.5

    def plan(self, intent: StructuredIntent) -> RetrievalPlan:
        return RetrievalPlan(
            plan_id=self._make_plan_id(intent),
            strategy_name=self.name,
            intent=intent,
            steps=[],
            expected_claim_types=[],
            store_fingerprint="",
            entity_count=0,
            traversal_count=0,
        )


# ═════════════════════════════════════════════════════════════════════════════
# Concrete strategy implementations
# ═════════════════════════════════════════════════════════════════════════════


@register_strategy
class ComparisonStrategy(RetrievalStrategy):
    """Strategy for comparing two or more players across all capabilities."""

    @property
    def name(self) -> str:
        return "comparison"

    def supports(self, intent: StructuredIntent) -> float:
        return 1.0 if intent.primary_type == IntentType.COMPARE_PLAYERS else 0.0

    def plan(self, intent: StructuredIntent) -> RetrievalPlan:
        player_ids = [
            intent.entities.get("focus_player"),
            intent.entities.get("compare_player"),
        ]
        player_ids = [pid for pid in player_ids if pid is not None]
        player_ids = list(dict.fromkeys(player_ids))  # deduplicate

        steps: list[RetrievalStep] = []
        expected_claim_types: list[str] = []

        for pid in player_ids:
            ref = EntityRef(node_type=NodeType.PLAYER, entity_id=str(pid))
            steps.append(RetrievalStep(
                step_type=RetrievalStepType.GET_ENTITY,
                entity_ref=ref,
            ))
            steps.append(RetrievalStep(
                step_type=RetrievalStepType.TRAVERSE_EDGES,
                entity_ref=ref,
                edge_type=EdgeType.HAS_CAPABILITY,
            ))
            steps.append(RetrievalStep(
                step_type=RetrievalStepType.PROJECT_CLAIMS,
                entity_ref=ref,
                claim_types=[ClaimType.CAPABILITY.value],
            ))
            expected_claim_types.append(ClaimType.CAPABILITY.value)
            steps.append(RetrievalStep(
                step_type=RetrievalStepType.PROJECT_CLAIMS,
                entity_ref=ref,
                claim_types=[ClaimType.ARCHE_TYPE.value],
            ))
            expected_claim_types.append(ClaimType.ARCHE_TYPE.value)

        return RetrievalPlan(
            plan_id=self._make_plan_id(intent),
            strategy_name=self.name,
            intent=intent,
            steps=steps,
            expected_claim_types=list(set(expected_claim_types)) or [
                ClaimType.CAPABILITY.value, ClaimType.ARCHE_TYPE.value,
            ],
            store_fingerprint=intent.filters.get("store_fingerprint", ""),
            entity_count=len(player_ids),
            traversal_count=len([s for s in steps if s.step_type == RetrievalStepType.TRAVERSE_EDGES]),
        )


@register_strategy
class ReplacementStrategy(RetrievalStrategy):
    """Strategy for finding and evaluating replacements for a player."""

    @property
    def name(self) -> str:
        return "replacement"

    def supports(self, intent: StructuredIntent) -> float:
        score = 0.0
        if intent.primary_type == IntentType.RECRUITMENT:
            score = 0.8
        if "replacement" in intent.raw_text.lower():
            score = max(score, 0.9)
        return score

    def plan(self, intent: StructuredIntent) -> RetrievalPlan:
        focus_id = intent.entities.get("focus_player")
        if not focus_id:
            raise ValueError("Replacement strategy requires 'focus_player' in intent.entities")

        focus_ref = EntityRef(node_type=NodeType.PLAYER, entity_id=str(focus_id))

        steps = [
            RetrievalStep(
                step_type=RetrievalStepType.GET_ENTITY,
                entity_ref=focus_ref,
            ),
            RetrievalStep(
                step_type=RetrievalStepType.TRAVERSE_EDGES,
                entity_ref=focus_ref,
                edge_type=EdgeType.HAS_CAPABILITY,
            ),
            RetrievalStep(
                step_type=RetrievalStepType.PROJECT_CLAIMS,
                entity_ref=focus_ref,
                claim_types=[ClaimType.CAPABILITY.value, ClaimType.ARCHE_TYPE.value],
            ),
            RetrievalStep(
                step_type=RetrievalStepType.TRAVERSE_EDGES,
                entity_ref=focus_ref,
                edge_type=EdgeType.REPLACEMENT_FOR,
                metadata={"max_results": 5},
            ),
            RetrievalStep(
                step_type=RetrievalStepType.PROJECT_CLAIMS,
                entity_ref=focus_ref,
                claim_types=[ClaimType.ROLE_FIT.value],
            ),
        ]

        return RetrievalPlan(
            plan_id=self._make_plan_id(intent),
            strategy_name=self.name,
            intent=intent,
            steps=steps,
            expected_claim_types=[
                ClaimType.CAPABILITY.value,
                ClaimType.ARCHE_TYPE.value,
                ClaimType.ROLE_FIT.value,
            ],
            store_fingerprint=intent.filters.get("store_fingerprint", ""),
            entity_count=1,
            traversal_count=3,
        )
