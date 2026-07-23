"""
backend/retrieval/shadow.py — Shadow deployment harness for retrieval v1.

For every Ask Athena request during shadow deployment:

  1. Run retrieval in parallel with the existing pipeline.
  2. Log all retrieval metrics.
  3. Discard retrieval output (return existing response to user).

Shadow mode is enabled by setting ATHENA_DEPLOYMENT_MODE=shadow
in addition to ATHENA_USE_RETRIEVAL=false (the default).

Once shadow data shows stable metrics, switch to ATHENA_USE_RETRIEVAL=true
for controlled enablement.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.explanation.intent import ConversationIntent, IntentClassifier
from backend.retrieval.bridge import CoverageValidationError, RetrievalPromptBridge
from backend.retrieval.strategies import dispatch_strategy
from shared.config.settings import settings
from shared.schemas.retrieval import IntentType, StructuredIntent

logger = logging.getLogger(__name__)

# Shadow log path
SHADOW_LOG_DIR = Path("data/shadow")
SHADOW_LOG_PATH = SHADOW_LOG_DIR / "shadow_log.jsonl"

# Intent mapping (same as retrieval_service.py)
_INTENT_MAP: dict[ConversationIntent, IntentType] = {
    ConversationIntent.PLAYER_ANALYSIS: IntentType.PLAYER_ANALYSIS,
    ConversationIntent.TEAM_ANALYSIS: IntentType.TEAM_ANALYSIS,
    ConversationIntent.COMPARE_PLAYERS: IntentType.COMPARE_PLAYERS,
    ConversationIntent.RECRUITMENT: IntentType.RECRUITMENT,
    ConversationIntent.COUNTERFACTUAL: IntentType.COUNTERFACTUAL,
    ConversationIntent.GENERAL: IntentType.GENERAL,
    ConversationIntent.UNKNOWN: IntentType.GENERAL,
}


@dataclass
class ShadowRecord:
    """A single shadow deployment record — one request's retrieval metrics."""

    # Request identity
    timestamp: str = ""
    query_preview: str = ""  # first 80 chars

    # Intent
    classified_intent: str = ""
    resolved_intent: str = ""  # after mapping
    strategy: str = ""
    plan_id: str = ""
    entity_count: int = 0

    # Execution
    retrieval_time_ms: float = 0.0
    claim_count: int = 0
    prompt_size_bytes: int = 0

    # Coverage
    coverage_satisfied: list[str] = field(default_factory=list)
    coverage_missing: list[str] = field(default_factory=list)
    coverage_complete: bool = False

    # Outcome
    retrieval_used: bool = False
    error: str | None = None
    error_type: str | None = None


def _adapt_intent(
    query: str,
    active_workspace_id: str,
    selected_player_id: int | None,
    selected_team_id: int | None,
) -> tuple[StructuredIntent, ConversationIntent]:
    """Adapt UI state to StructuredIntent (same logic as retrieval_service)."""
    classification = IntentClassifier.classify(
        query, active_workspace_id,
        [selected_player_id] if selected_player_id else None,
    )
    intent_type = _INTENT_MAP.get(classification.intent, IntentType.GENERAL)
    entities: dict[str, str] = {}
    if selected_player_id is not None:
        entities["focus_player"] = str(selected_player_id)
    if selected_team_id is not None:
        entities["team"] = str(selected_team_id)

    intent = StructuredIntent(
        primary_type=intent_type,
        entities=entities,
        raw_text=query,
    )
    return intent, classification.intent


def run_shadow(
    query: str,
    active_workspace_id: str,
    selected_player_id: int | None,
    selected_team_id: int | None,
) -> None:
    """Run retrieval in the background and log metrics.

    This function swallows all exceptions — shadow execution must never
    affect the user-facing response.
    """
    if settings.ATHENA_ENV.lower() not in ("production", "staging", "shadow"):
        return  # Only log in deployment environments

    SHADOW_LOG_DIR.mkdir(parents=True, exist_ok=True)

    bridge = RetrievalPromptBridge()
    start = time.perf_counter()
    record = ShadowRecord(
        timestamp=datetime.now().isoformat(),
        query_preview=query[:80],
    )

    try:
        intent, classified_intent = _adapt_intent(
            query, active_workspace_id, selected_player_id, selected_team_id,
        )
        record.classified_intent = classified_intent.value
        record.resolved_intent = intent.primary_type.value

        # Dispatch strategy (for logging even if coverage fails)
        strategy = dispatch_strategy(intent)
        plan = strategy.plan(intent)
        record.strategy = strategy.name
        record.plan_id = plan.plan_id
        record.entity_count = plan.entity_count

        # Build prompt (raises CoverageValidationError if insufficient)
        try:
            pkg = bridge.build_prompt(query, intent)
            meta = pkg.metadata
            record.retrieval_used = meta.get("retrieval_used", False)
            record.claim_count = meta.get("retrieval_claim_count", 0)
            record.prompt_size_bytes = meta.get("context_size_bytes", 0)
            record.coverage_satisfied = meta.get("retrieval_coverage_satisfied", [])
            record.coverage_missing = meta.get("retrieval_coverage_missing", [])
            record.coverage_complete = meta.get("retrieval_coverage_complete", False)

            if record.retrieval_used:
                logger.info(
                    "SHADOW retrieval=used intent=%s strategy=%s claims=%d size=%dB time=%.1fms",
                    record.resolved_intent, record.strategy,
                    record.claim_count, record.prompt_size_bytes,
                    record.retrieval_time_ms,
                )
            else:
                logger.info(
                    "SHADOW retrieval=fallback intent=%s strategy=%s",
                    record.resolved_intent, record.strategy,
                )

        except CoverageValidationError as e:
            record.error = str(e)[:200]
            record.error_type = "CoverageValidationError"
            record.retrieval_used = False
            logger.info(
                "SHADOW retrieval=blocked intent=%s reason=coverage_gap missing=%s",
                record.resolved_intent, str(e.missing),
            )

    except Exception as e:
        record.error = str(e)[:200]
        record.error_type = type(e).__name__
        record.retrieval_used = False
        logger.warning(
            "SHADOW retrieval=error type=%s query=%.60s",
            record.error_type, query,
        )

    finally:
        record.retrieval_time_ms = (time.perf_counter() - start) * 1000

        # Append to shadow log
        with open(SHADOW_LOG_PATH, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")


def summarize_shadow_log(log_path: Path = SHADOW_LOG_PATH) -> dict[str, Any]:
    """Read the shadow log and produce a summary of all records."""
    if not log_path.exists():
        return {"error": "No shadow log found", "total_requests": 0}

    records: list[ShadowRecord] = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data = json.loads(line)
                    records.append(ShadowRecord(**data))
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue

    if not records:
        return {"error": "No valid records in shadow log", "total_requests": 0}

    total = len(records)
    retrieval_used = sum(1 for r in records if r.retrieval_used)
    retrieval_fallback = sum(1 for r in records if not r.retrieval_used and not r.error)
    retrieval_blocked = sum(1 for r in records if r.error_type == "CoverageValidationError")
    retrieval_errors = sum(1 for r in records if r.error and r.error_type != "CoverageValidationError")
    times = [r.retrieval_time_ms for r in records if r.retrieval_used]
    claims = [r.claim_count for r in records if r.retrieval_used]
    sizes = [r.prompt_size_bytes for r in records if r.retrieval_used]

    return {
        "total_requests": total,
        "retrieval_used": retrieval_used,
        "retrieval_fallback": retrieval_fallback,
        "retrieval_blocked": retrieval_blocked,
        "retrieval_errors": retrieval_errors,
        "retrieval_used_pct": round(retrieval_used / total * 100, 1) if total else 0,
        "avg_time_ms": round(sum(times) / len(times), 1) if times else 0,
        "max_time_ms": round(max(times), 1) if times else 0,
        "p50_time_ms": round(sorted(times)[len(times) // 2], 1) if times else 0,
        "avg_claims": round(sum(claims) / len(claims), 1) if claims else 0,
        "avg_prompt_size_bytes": round(sum(sizes) / len(sizes), 1) if sizes else 0,
        "strategies_used": list({r.strategy for r in records if r.retrieval_used}),
        "intents_seen": list({r.resolved_intent for r in records}),
        "coverage_gaps": list({
            str(r.coverage_missing) for r in records if r.coverage_missing
        }),
    }
