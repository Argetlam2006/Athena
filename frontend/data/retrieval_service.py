"""
frontend/data/retrieval_service.py — Retrieval-enabled Ask Athena service.

Provides a retrieval-enhanced alternative to process_athena_turn that
adapts existing UI state into a StructuredIntent and runs the full
retrieval pipeline.  Improved with user-facing failure messages,
ambiguous entity detection, and developer debug mode.

This is an additive code path — the original process_athena_turn
remains untouched as the baseline.
"""

from __future__ import annotations

import logging
import re
import time

from backend.explanation.conversation import ConversationManager
from backend.explanation.intent import ConversationIntent, IntentClassifier
from backend.explanation.providers.factory import get_provider
from backend.retrieval.bridge import CoverageValidationError, RetrievalPromptBridge
from backend.retrieval.context import get_context, resolve_from_context, update_context
from backend.retrieval.debug import (
    DebugTrace,
    format_debug_report,
    is_debug_enabled,
    record_trace,
)
from backend.retrieval.resolver import get_entity_index, normalize_query
from shared.config.settings import settings
from shared.schemas.retrieval import IntentType, StructuredIntent

logger = logging.getLogger(__name__)

# ─── Intent adapter ───────────────────────────────────────────────────────────

_INTENT_MAP: dict[ConversationIntent, IntentType] = {
    ConversationIntent.PLAYER_ANALYSIS: IntentType.PLAYER_ANALYSIS,
    ConversationIntent.TEAM_ANALYSIS: IntentType.TEAM_ANALYSIS,
    ConversationIntent.COMPARE_PLAYERS: IntentType.COMPARE_PLAYERS,
    ConversationIntent.RECRUITMENT: IntentType.RECRUITMENT,
    ConversationIntent.COUNTERFACTUAL: IntentType.COUNTERFACTUAL,
    ConversationIntent.GENERAL: IntentType.GENERAL,
    ConversationIntent.UNKNOWN: IntentType.GENERAL,
}

# ─── Subjective question detection ─────────────────────────────────────

_SUBJECTIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bgreatest\b.*\b(?:footballer|player|ever|of all time)\b", re.IGNORECASE),
    re.compile(r"\bgoat\b", re.IGNORECASE),
    re.compile(r"\bbest\b.*\b(?:footballer|player|ever|of all time)\b", re.IGNORECASE),
    re.compile(r"\bgreatest\b.*\b(?:team|manager|coach|club)\b", re.IGNORECASE),
]

_SUBJECTIVE_RESPONSE: str = (
    "That's a great football debate — but it's a subjective opinion question, "
    "not one Athena can answer with deterministic evidence.\n\n"
    "Athena specializes in **evidence-based football analysis** using the indexed "
    "StatsBomb dataset. I can analyse specific players, teams, tactics, and "
    "recruitment questions with grounded, traceable reasoning drawn from actual "
    "match data.\n\n"
    "For subjective questions like “who is the greatest”, different people "
    "have different criteria — longevity, peak performance, trophies, influence, "
    "era dominance — and there is no single evidence-backed answer.\n\n"
    "**What I can help with instead:**\n"
    "- Analyse a specific player or team\n"
    "- Compare two players’ capability profiles\n"
    "- Evaluate tactical strengths and weaknesses\n"
    "- Recommend recruitment targets based on squad needs\n"
    "- Explain tactical identity and playing style\n\n"
    "Try asking about a player or team you’re interested in!"
)


def _is_subjective_query(query: str) -> bool:
    """Detect subjective football opinion questions that fall outside
    Athena's deterministic evidence scope."""
    for pattern in _SUBJECTIVE_PATTERNS:
        if pattern.search(query):
            return True
    return False


# ─── Helpers ──────────────────────────────────────────────────────────────────

_SUPPORTED_CAPABILITIES = {
    "compare_players": "Compare two players (e.g. \"Compare Messi and Ronaldo\")",
    "player_analysis": "Analyze a single player (e.g. \"Analyze Messi\")",
    "recruitment": "Find replacements or recruitment targets (e.g. \"Who replaces Busquets?\")",
    "team_analysis": "Analyze a team (e.g. \"Analyze Arsenal\")",
}

_INTENT_DESCRIPTIONS = {
    IntentType.COMPARE_PLAYERS.value: "a player comparison",
    IntentType.PLAYER_ANALYSIS.value: "a player analysis",
    IntentType.TEAM_ANALYSIS.value: "a team analysis",
    IntentType.RECRUITMENT.value: "a recruitment or replacement search",
    IntentType.COUNTERFACTUAL.value: "a scenario analysis",
}


def _debug_metadata(trace: DebugTrace) -> dict | None:
    """Attach diagnostics to a response only when developer mode is enabled."""
    if not is_debug_enabled():
        return None
    return {"debug_report": format_debug_report(trace)}


def _build_failure_message(
    intent_type: str,
    resolver_result: dict | None = None,
    reason: str | None = None,
) -> str:
    """Build a user-facing failure message that teaches rather than confuses."""
    understood = _INTENT_DESCRIPTIONS.get(intent_type, "a football analysis")
    lines = [f"I understood this as {understood}, but I can't support it with enough evidence.", ""]

    lines.append("**What I understood:**")
    if resolver_result and (resolver_result["players"] or resolver_result["teams"]):
        for p in resolver_result["players"]:
            lines.append(f"- Player: {p['name']}")
        for t in resolver_result["teams"]:
            lines.append(f"- Team: {t['name']}")
    else:
        lines.append("- I couldn't confidently match a player or team in the available data.")
    lines.append("")

    reason = reason or (
        "the available evidence is incomplete for this request, so I won't fill "
        "the gaps with guesses."
    )
    lines.append(f"**Why I can't answer:** {reason}")
    lines.append("")

    lines.append("**I can help with:**")
    for example in _SUPPORTED_CAPABILITIES.values():
        lines.append(f"- {example}")

    return "\n".join(lines)


def _build_ambiguous_message(ambiguities: list[dict]) -> str:
    """Build a clarification message when entity resolution is ambiguous."""
    lines = ["I found more than one possible match:"]
    for ambiguity in ambiguities:
        lines.append(f"\n**{ambiguity['query']}** could refer to:")
        for candidate in ambiguity["candidates"][:5]:
            details = []
            if candidate.get("position"):
                details.append(candidate["position"])
            if candidate.get("team"):
                details.append(candidate["team"])
            label = f" ({', '.join(details)})" if details else ""
            lines.append(f"- {candidate['name']}{label}")
    lines.append("")
    lines.append("Which one did you mean? Please use their full name or be more specific.")
    return "\n".join(lines)


def _adapt_intent(
    normalized_query: str,
    active_workspace_id: str,
    selected_player_id: int | None,
    selected_team_id: int | None,
) -> tuple[StructuredIntent, dict | None]:
    """Adapt existing UI state + query into a StructuredIntent.

    Args:
        normalized_query: The already-normalized user query.
        active_workspace_id: Current workspace context.
        selected_player_id: Currently selected player (if any).
        selected_team_id: Currently selected team (if any).

    Returns (intent, resolver_result) where resolver_result contains
    raw resolution data for failure message generation.
    """
    classification = IntentClassifier.classify(
        normalized_query, active_workspace_id,
        [selected_player_id] if selected_player_id else None,
    )

    primary_type = _INTENT_MAP.get(
        classification.intent,
        IntentType.GENERAL,
    )

    entities: dict[str, str] = {}
    resolver_result: dict | None = None

    # Always resolve entities from query text first (standalone Ask Athena).
    # UI selection state is a fallback only, never an override for text resolution.
    resolver = get_entity_index()
    resolver_result = resolver.resolve_both(normalized_query)
    players = resolver_result["players"]
    teams = resolver_result["teams"]

    # Intent-specific entity role assignment.
    # primary_type determines the entity role mapping, but resolved entities
    # are used regardless of whether the classifier recognised the intent.
    if primary_type == IntentType.COMPARE_PLAYERS and len(players) >= 2:
        entities["focus_player"] = str(players[0]["id"])
        entities["compare_player"] = str(players[1]["id"])
    elif primary_type == IntentType.COMPARE_PLAYERS and len(players) < 2 and len(teams) >= 2:
        # Team comparison: the classifier saw a "compare" keyword, but text
        # resolution found two teams, not two players.  Route as team analysis
        # using the first team; team_compare is stored for context.
        entities["team"] = teams[0]["entity_id"]
        entities["team_compare"] = teams[1]["entity_id"]
        primary_type = IntentType.TEAM_ANALYSIS
    elif primary_type in (IntentType.PLAYER_ANALYSIS, IntentType.COUNTERFACTUAL) and players:
        entities["focus_player"] = str(players[0]["id"])
        # Scenario query with both player and team resolved (e.g.
        # "How would Manchester City adapt without Rodri?").  Route
        # as team analysis so fragility claims show the player's
        # structural importance.  The player is stored as a context
        # hint so the LLM can reference them.
        if primary_type == IntentType.COUNTERFACTUAL and teams:
            entities["team"] = teams[0]["entity_id"]
            primary_type = IntentType.TEAM_ANALYSIS
    elif primary_type == IntentType.RECRUITMENT:
        if players:
            entities["focus_player"] = str(players[0]["id"])
        elif teams:
            # Team recruitment: user wants to strengthen a squad, not replace
            # a specific player.  Route as team analysis so the LLM receives
            # capability, fragility, and bottleneck evidence for grounded
            # recommendations.
            entities["team"] = teams[0]["entity_id"]
            primary_type = IntentType.TEAM_ANALYSIS
    elif primary_type in (IntentType.TEAM_ANALYSIS, IntentType.SQUAD_DIAGNOSIS) and teams:
        entities["team"] = teams[0]["entity_id"]

    # Catch-all: text resolution found entities but the classifier returned
    # GENERAL or another non-specific type — route by entity type.
    if not entities:
        if players:
            entities["focus_player"] = str(players[0]["id"])
        elif teams:
            entities["team"] = teams[0]["entity_id"]

    # Fall back to UI-selected player/team only when text resolution found nothing
    if not entities:
        if selected_player_id is not None:
            entities["focus_player"] = str(selected_player_id)
        if selected_team_id is not None:
            entities["team"] = str(selected_team_id)

    # Upgrade primary_type when the classifier returned GENERAL but entity
    # resolution found a team or player from free-text.  This ensures the
    # correct strategy (TeamAnalysisStrategy, PlayerAnalysisStrategy) is
    # dispatched rather than falling through to GeneralStrategy which
    # produces an empty plan.
    if primary_type == IntentType.GENERAL:
        if "team" in entities:
            primary_type = IntentType.TEAM_ANALYSIS
        elif "focus_player" in entities:
            primary_type = IntentType.PLAYER_ANALYSIS

    intent = StructuredIntent(
        primary_type=primary_type,
        entities=entities,
        raw_text=normalized_query,
    )
    return intent, resolver_result


# ─── Retrieval service ────────────────────────────────────────────────────────


class RetrievalAthenaService:
    """Retrieval-enhanced Ask Athena service with user-facing failure messages."""

    def __init__(self):
        self.bridge = RetrievalPromptBridge()
        self.manager = ConversationManager()
        self.provider = get_provider(settings.ATHENA_PROVIDER)

    def process_turn(
        self,
        query: str,
        active_workspace_id: str,
        selected_player_id: int | None,
        selected_team_id: int | None,
    ) -> str:
        """Process an Ask Athena turn with retrieval-enhanced evidence."""
        trace = DebugTrace(raw_query=query)
        start_time = time.perf_counter()

        # Detect context shifts (mirrors the legacy process_athena_turn behavior)
        self.manager.detect_and_handle_context_change(
            selected_player_id, selected_team_id, active_workspace_id,
        )

        self.manager.add_user_message(query)

        # Handle subjective opinion questions before any retrieval logic
        if _is_subjective_query(query):
            trace.success = True
            trace.outcome = "subjective"
            trace.execution_time_ms = (time.perf_counter() - start_time) * 1000
            record_trace(trace)
            self.manager.add_assistant_message(_SUBJECTIVE_RESPONSE)
            return _SUBJECTIVE_RESPONSE

        normalized_query = normalize_query(query)
        context = get_context()
        trace.context_last_intent = context.last_intent
        trace.context_comparison_pair = str(context.comparison_pair)
        trace.context_current_player = str(context.current_player_id)
        ambiguities = get_entity_index().find_ambiguities(normalized_query)
        trace.normalized_query = normalized_query
        if ambiguities:
            trace.success = False
            trace.outcome = "clarification"
            trace.execution_time_ms = (time.perf_counter() - start_time) * 1000
            record_trace(trace)
            clarification = _build_ambiguous_message(ambiguities)
            self.manager.add_assistant_message(
                clarification, metadata=_debug_metadata(trace)
            )
            return clarification

        # 1. Intent adaptation with entity resolution
        intent, resolver_result = _adapt_intent(
            normalized_query, active_workspace_id,
            selected_player_id, selected_team_id,
        )
        trace.normalized_query = normalized_query
        trace.intent_type = intent.primary_type.value
        trace.resolved_entities = dict(intent.entities)

        # 2. Conversation context fallback
        if not intent.entities:
            context_entities = resolve_from_context(query, intent.primary_type.value)
            if context_entities:
                ctx = get_context()
                trace.context_last_intent = ctx.last_intent
                trace.context_comparison_pair = str(ctx.comparison_pair)
                trace.context_current_player = str(ctx.current_player_id)
                intent = StructuredIntent(
                    primary_type=intent.primary_type,
                    entities=context_entities,
                    filters=intent.filters,
                    raw_text=intent.raw_text,
                )
                trace.resolved_entities = dict(intent.entities)

        if not intent.entities:
            trace.success = False
            trace.outcome = "graceful_failure"
            trace.execution_time_ms = (time.perf_counter() - start_time) * 1000
            record_trace(trace)
            failure_msg = _build_failure_message(intent.primary_type.value, resolver_result)
            self.manager.add_assistant_message(
                failure_msg, metadata=_debug_metadata(trace)
            )
            return failure_msg

        # 3. Partial resolution: fill comparison from context
        if intent.primary_type == IntentType.COMPARE_PLAYERS and len(intent.entities) < 2:
            ctx_focus = intent.entities.get("focus_player")
            ctx_compare = intent.entities.get("compare_player")
            ctx = get_context()
            if ctx_focus and ctx.comparison_pair:
                intent.entities["compare_player"] = str(
                    ctx.comparison_pair[1] if int(ctx_focus) == ctx.comparison_pair[0]
                    else ctx.comparison_pair[0]
                )
            elif ctx_compare and ctx.comparison_pair:
                intent.entities["focus_player"] = str(
                    ctx.comparison_pair[0] if int(ctx_compare) == ctx.comparison_pair[1]
                    else ctx.comparison_pair[1]
                )

        # 4. Update conversation context
        update_context(intent.primary_type.value, intent.entities, intent.raw_text)

        # 5. Build prompt with retrieval
        try:
            prompt_pkg = self.bridge.build_prompt(intent.raw_text, intent)
        except CoverageValidationError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            trace.success = False
            trace.error = str(e)[:200]
            trace.error_type = "CoverageValidationError"
            trace.outcome = "graceful_failure"
            trace.execution_time_ms = elapsed
            record_trace(trace)

            logger.info("Evidence coverage unavailable for request: %s", e.missing)
            failure_msg = _build_failure_message(
                intent.primary_type.value,
                resolver_result,
            )

            self.manager.add_assistant_message(
                failure_msg, metadata=_debug_metadata(trace)
            )
            return failure_msg

        if not prompt_pkg.metadata.get("retrieval_used", False):
            trace.success = False
            trace.outcome = "graceful_failure"
            trace.execution_time_ms = (time.perf_counter() - start_time) * 1000
            record_trace(trace)
            failure_msg = _build_failure_message(intent.primary_type.value, resolver_result)
            self.manager.add_assistant_message(
                failure_msg, metadata=_debug_metadata(trace)
            )
            return failure_msg

        # 6. Generate LLM response
        try:
            response = self.provider.generate(prompt_pkg)
            elapsed = (time.perf_counter() - start_time) * 1000

            # Build debug trace
            meta = prompt_pkg.metadata
            trace.strategy = meta.get("retrieval_strategy", "")
            trace.plan_id = meta.get("retrieval_plan_id", "")
            trace.plan_step_count = meta.get("retrieval_plan_step_count", 0)
            trace.entity_count = meta.get("retrieval_entity_count", 0)
            trace.traversal_count = meta.get("retrieval_traversal_count", 0)
            trace.claim_count = meta.get("retrieval_claim_count", 0)
            trace.claim_types = meta.get("retrieval_coverage_satisfied", [])
            trace.traversal_summary = meta.get("debug_traversal_summary", [])
            trace.projected_claims = meta.get("debug_projected_claims", [])
            trace.evidence_bundle_stats = meta.get("debug_evidence_bundle", {})
            trace.execution_time_ms = elapsed
            trace.coverage_satisfied = meta.get("retrieval_coverage_satisfied", [])
            trace.coverage_missing = meta.get("retrieval_coverage_missing", [])
            trace.coverage_complete = meta.get("retrieval_coverage_complete", False)
            trace.context_size_bytes = meta.get("context_size_bytes", 0)
            trace.prompt_total_chars = len(
                prompt_pkg.system_prompt
                + prompt_pkg.user_prompt
                + prompt_pkg.serialized_context
            )
            trace.success = True
            trace.outcome = "success"
            record_trace(trace)

            # Build Evidence Inspector metadata
            trace_meta = dict(meta)
            trace_meta["response_model"] = response.model
            trace_meta["response_provider"] = response.provider
            trace_meta.update(_debug_metadata(trace) or {})

            self.manager.add_assistant_message(
                response.generated_text, metadata=trace_meta
            )
            return response.generated_text

        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            trace.success = False
            trace.error = str(e)[:200]
            trace.error_type = type(e).__name__
            trace.outcome = "graceful_failure"
            trace.execution_time_ms = elapsed
            record_trace(trace)

            logger.exception("Ask Athena request failed")
            err_msg = _build_failure_message(
                intent.primary_type.value,
                resolver_result,
                "I couldn't complete the analysis just now. Please try again.",
            )
            self.manager.add_assistant_message(
                err_msg, metadata=_debug_metadata(trace)
            )
            return err_msg

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        self.manager.clear()
        ctx = get_context()
        ctx.last_player_ids.clear()
        ctx.last_team_entity_ids.clear()
        ctx.comparison_pair = None
        ctx.current_player_id = None
        ctx.current_team_id = None
        ctx.last_query = ""
        ctx.last_intent = ""
