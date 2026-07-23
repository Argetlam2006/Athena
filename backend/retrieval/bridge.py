"""
backend/retrieval/bridge.py — Bridge between retrieval layer and existing explanation pipeline.

Provides a single function that takes a user query, resolves intent, executes
retrieval, validates coverage, and passes the EvidenceBundle into the existing
PromptBuilder — without changing any existing code.
"""

from __future__ import annotations

import logging

from backend.explanation.prompt_builder import PromptBuilder
from backend.retrieval.coverage import CoverageValidationError, CoverageValidator
from backend.retrieval.execution import RetrievalExecutor
from backend.retrieval.strategies import dispatch_strategy
from shared.schemas.retrieval import (
    StructuredIntent,
)

logger = logging.getLogger(__name__)

# ─── Tracing fields injected into PromptPackage.metadata ──────────────────────

TRACE_META_KEYS = frozenset({
    "retrieval_strategy",
    "retrieval_plan_id",
    "retrieval_entity_count",
    "retrieval_traversal_count",
    "retrieval_execution_time_ms",
    "retrieval_claim_count",
    "retrieval_coverage_satisfied",
    "retrieval_coverage_missing",
    "retrieval_coverage_complete",
})


class RetrievalPromptBridge:
    """Bridge that composes retrieval + coverage + prompt building.

    Usage:
        bridge = RetrievalPromptBridge()
        prompt_pkg = bridge.build_prompt(
            user_query="How does Messi compare to Ronaldo?",
            intent=StructuredIntent(...)
        )
        # prompt_pkg goes directly to Provider.generate()
    """

    def __init__(self):
        self.executor = RetrievalExecutor()
        self.validator = CoverageValidator()
        self.prompt_builder = PromptBuilder()

    def build_prompt(
        self,
        user_query: str,
        intent: StructuredIntent,
    ) -> object:
        """Full pipeline: strategy -> plan -> execution -> coverage -> prompt.

        Args:
            user_query: The original user question.
            intent: The resolved, structured intent.

        Returns:
            A PromptPackage ready for Provider.generate().

        Raises:
            CoverageValidationError: if critical evidence is missing.
        """
        # 1. Select strategy and build plan
        strategy = dispatch_strategy(intent)
        plan = strategy.plan(intent)
        logger.debug(
            "Plan: strategy=%s, plan_id=%s, steps=%d",
            plan.strategy_name, plan.plan_id, len(plan.steps),
        )

        # 2. Execute plan against the Entity Graph
        bundle = self.executor.execute(plan, intent)
        logger.debug(
            "Execution: claims=%d, coverage=%s",
            len(bundle.claims),
            {
                "satisfied": bundle.coverage.satisfied,
                "missing": bundle.coverage.missing,
            },
        )

        # 3. Validate coverage (raises if critical evidence missing)
        self.validator.validate(bundle)
        logger.info(
            "Coverage OK: intent=%s, claims=%d, types=%s",
            intent.primary_type.value,
            len(bundle.claims),
            bundle.coverage.satisfied,
        )

        # 4. Build prompt using existing PromptBuilder
        prompt_pkg = self.prompt_builder.build(
            user_query=user_query,
            context=bundle,
            context_type=f"retrieval_{intent.primary_type.value}",
        )

        # 5. Augment metadata with retrieval trace (no new fields on PromptPackage)
        retrieval_used = (
            plan.entity_count > 0 or plan.traversal_count > 0
            or len(bundle.claims) > 0
        )
        prompt_pkg.metadata.update({
            "retrieval_used": retrieval_used,
            "retrieval_strategy": plan.strategy_name if retrieval_used else "",
            "retrieval_plan_id": plan.plan_id if retrieval_used else "",
            "retrieval_entity_count": plan.entity_count if retrieval_used else 0,
            "retrieval_traversal_count": plan.traversal_count if retrieval_used else 0,
            "retrieval_execution_time_ms": bundle.execution_time_ms if retrieval_used else 0.0,
            "retrieval_claim_count": len(bundle.claims) if retrieval_used else 0,
            "retrieval_coverage_satisfied": bundle.coverage.satisfied if retrieval_used else [],
            "retrieval_coverage_missing": bundle.coverage.missing if retrieval_used else [],
            "retrieval_coverage_complete": bundle.coverage.is_complete if retrieval_used else False,
        })

        return prompt_pkg

    def build_prompt_or_none(
        self,
        user_query: str,
        intent: StructuredIntent,
    ) -> object | None:
        """Like build_prompt, but returns None on coverage failure instead of raising.

        Only catches CoverageValidationError.  Other exceptions
        (programmer errors, infrastructure failures) propagate so they
        are visible to monitoring and debugging.
        """
        try:
            return self.build_prompt(user_query, intent)
        except CoverageValidationError:
            logger.warning("Coverage insufficient, skipping prompt generation")
            return None
