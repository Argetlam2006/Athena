"""
backend/retrieval/coverage.py — CoverageValidator for EvidenceBundles.

Enforces the architectural invariant: the LLM must never receive a prompt
when coverage gaps would force it to fabricate evidence.

The single source of truth for required claim types is the Strategy,
propagated through RetrievalPlan.expected_claim_types into the
EvidenceBundle's coverage metadata.  The CoverageValidator checks
against this plan-derived data — it does not maintain its own
requirements.
"""

from __future__ import annotations

import logging

from shared.schemas.retrieval import ClaimType, EvidenceBundle

logger = logging.getLogger(__name__)


# Claim types the LLM can reason about even when absent (e.g. enhancements
# that supplement reasoning but aren't critical).
OPTIONAL_CLAIM_TYPES: frozenset[str] = frozenset({
    ClaimType.ROLE_FIT.value,
    ClaimType.SHARED_STRENGTH.value,
    ClaimType.KEY_DIFFERENCE.value,
    ClaimType.TEAM_BOTTLENECK.value,
})


class CoverageValidationError(Exception):
    """Raised when an EvidenceBundle does not satisfy coverage requirements."""

    def __init__(
        self,
        message: str,
        missing: list[str],
    ):
        self.missing = missing
        super().__init__(message)


class CoverageValidator:
    """Validates that an EvidenceBundle has sufficient coverage for prompt building.

    The prompt builder MUST call validate() before building a prompt.
    If validation fails, the prompt builder MUST NOT proceed.

    This validator does NOT define its own required-claim-type rules.
    Requirements are declared by the Strategy, embedded in the
    RetrievalPlan, and tracked as coverage metadata by the executor.
    The validator simply rejects bundles where required claims are
    missing.
    """

    def validate(self, bundle: EvidenceBundle) -> None:
        """Validate bundle coverage.

        Raises CoverageValidationError if required claim types are missing.
        Returns silently if coverage is sufficient.

        The LLM should only receive bundles that pass this check.
        """
        if not bundle.coverage:
            logger.warning("Bundle has no coverage metadata — skipping validation")
            return

        # Missing claim types that are not in the optional set
        required_missing = [
            ct for ct in bundle.coverage.missing
            if ct not in OPTIONAL_CLAIM_TYPES
        ]

        if required_missing:
            raise CoverageValidationError(
                message=(
                    f"EvidenceBundle missing required claim types: {required_missing}. "
                    f"The LLM cannot answer this question without fabricated evidence."
                ),
                missing=required_missing,
            )

        # Log non-critical gaps for audit
        if bundle.coverage.missing:
            logger.info(
                "Coverage gap (non-critical): missing=%s",
                bundle.coverage.missing,
            )

    def validate_or_warn(self, bundle: EvidenceBundle) -> bool:
        """Validate and return True if valid, False otherwise (no exception).

        Catches only CoverageValidationError.  Other errors propagate
        so that programmer mistakes and infrastructure failures are
        surfaced rather than silently swallowed.
        """
        try:
            self.validate(bundle)
            return True
        except CoverageValidationError:
            logger.warning("Coverage validation failed")
            return False
