"""
backend/retrieval/context.py — Deterministic conversation context for Ask Athena.

Tracks resolved entities across conversation turns so follow-up questions
like "Who is better under pressure?" reuse the previous comparison context.

No LLM, no embedding similarity — only deterministic entity tracking.

When a new query has no explicit entities (no player/team names resolved
from the text), the context resolver checks the conversation history for
a matching entity reference:

- Pronoun resolution: "him", "her", "they", "their" -> last mentioned entities
- Implicit reference: "who is better" -> last comparison pair
- "compare him with X" -> last focus + new resolve
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationContext:
    """Deterministic entity context across conversation turns.

    Updated after every successful retrieval response.
    Used by the next turn's entity resolution when the raw query
    doesn't contain resolvable entity names.
    """

    # Last resolved entities (most recent first)
    last_player_ids: list[int] = field(default_factory=list)
    last_team_entity_ids: list[str] = field(default_factory=list)

    # Current comparison pair (if the last query was a comparison)
    comparison_pair: tuple[int, int] | None = None

    # Current analysis target (last single-entity query)
    current_player_id: int | None = None
    current_team_id: str | None = None

    # The raw text of the last user query (for context matching)
    last_query: str = ""

    # Intent of the last query
    last_intent: str = ""


# ─── Singleton context ───────────────────────────────────────────────────────

_context: ConversationContext | None = None


def get_context() -> ConversationContext:
    """Get the singleton conversation context."""
    global _context
    if _context is None:
        _context = ConversationContext()
    return _context


def update_context(
    intent: str,
    entities: dict[str, str],
    query: str,
) -> None:
    """Update conversation context after a resolved intent."""
    ctx = get_context()
    ctx.last_query = query
    ctx.last_intent = intent

    # Track player IDs
    for key in ("focus_player", "compare_player"):
        val = entities.get(key)
        if val:
            try:
                pid = int(val)
                if pid not in ctx.last_player_ids:
                    ctx.last_player_ids.insert(0, pid)
                if key == "focus_player":
                    ctx.current_player_id = pid
            except (ValueError, TypeError):
                pass

    # Track team entity IDs
    for key in ("team", "team_focus", "team_compare"):
        val = entities.get(key)
        if val:
            if val not in ctx.last_team_entity_ids:
                ctx.last_team_entity_ids.insert(0, val)
            if key in ("team", "team_focus"):
                ctx.current_team_id = val

    # Track comparison pairs
    fp = entities.get("focus_player")
    cp = entities.get("compare_player")
    if fp and cp:
        try:
            ctx.comparison_pair = (int(fp), int(cp))
        except (ValueError, TypeError):
            pass


def resolve_from_context(query: str, primary_type: str) -> dict[str, str]:
    """Resolve entities for a query using conversation context when the
    query text doesn't contain resolvable entity names.

    Rules:
    - "compare him/her/them with X" -> reuse comparison pair with new entity
    - "who is better" / "how about under pressure" -> reuse comparison pair
    - "analyze him/her/them" -> reuse last focus
    - "who progresses better" -> reuse comparison pair
    - generic follow-up -> reuse comparison pair or current target
    """
    ctx = get_context()
    entities: dict[str, str] = {}

    q_lower = query.lower().strip()

    # Detect follow-up patterns
    has_entities = bool(resolve_names_from_text(query))

    if not has_entities:
        # Follow-up about comparison
        if ctx.comparison_pair and ctx.last_intent in ("compare_players",):
            # "who is better", "how about under pressure", "compare them"
            if any(kw in q_lower for kw in ("better", "worse", "pressure", "progress",
                                            "defend", "attack", "pass", "shoot",
                                            "under pressure", "how about", "what about",
                                            "compare them", "between them")):
                entities["focus_player"] = str(ctx.comparison_pair[0])
                entities["compare_player"] = str(ctx.comparison_pair[1])
                return entities

            # "compare him with X" or "compare her with X"
            for kw in ("compare him with", "compare her with", "compare them with",
                       "compare him to", "compare her to", "compare them to"):
                if kw in q_lower:
                    new_target = q_lower.split(kw)[-1].strip()
                    if new_target:
                        from backend.retrieval.resolver import get_entity_index
                        index = get_entity_index()
                        resolved = index.resolve_both(new_target)
                        if resolved["players"]:
                            entities["focus_player"] = str(ctx.comparison_pair[0])
                            entities["compare_player"] = str(resolved["players"][0]["id"])
                            return entities

        # Follow-up about single player
        if ctx.current_player_id:
            # "analyze him", "his strengths", "under pressure"
            if any(kw in q_lower for kw in ("his", "her", "their", "him", "strengths",
                                            "weaknesses", "archetype", "capabilities",
                                            "under pressure", "ball progression",
                                            "defensive", "passing", "pressing")):
                entities["focus_player"] = str(ctx.current_player_id)
                return entities

    return entities


def resolve_names_from_text(query: str) -> bool:
    """Check if a query contains recognisable entity names
    (quick check without doing full resolution)."""
    from backend.retrieval.resolver import get_entity_index
    index = get_entity_index()
    result = index.resolve_both(query)
    return bool(result["players"]) or bool(result["teams"])
