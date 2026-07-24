"""
backend/retrieval/resolver.py — Deterministic Named Entity Resolver.

Resolves player names, team names, competition names, known aliases, and
abbreviations from raw query text into typed entity IDs.

No LLM, no embeddings, no semantic search — only deterministic matching.

Resolution order per entity type:
  1. Exact alias lookup
  2. Exact normalized name match
  3. Token-level prefix match (min 4 chars)

The resolver populates StructuredIntent.entities before strategy dispatch.
No retrieval architecture changes.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

# ─── Query normalisation — runs BEFORE intent classification ──────────────────

QUERY_NORMALIZATIONS: list[tuple[re.Pattern, str]] = [
    # Possessive normalization — runs before entity resolution
    (re.compile(r"'s\b"), ""),
    (re.compile(r"s'\b"), "s"),
    # Ampersand normalization
    (re.compile(r"\s*&\s*"), " and "),
    # Position abbreviations
    (re.compile(r"\bDM\b", re.IGNORECASE), "defensive midfielder"),
    (re.compile(r"\bDM\b", re.IGNORECASE), "defensive midfielder"),
    (re.compile(r"\bNo\.?\s*6\b", re.IGNORECASE), "defensive midfielder"),
    (re.compile(r"\bNo\.?\s*8\b", re.IGNORECASE), "box-to-box midfielder"),
    (re.compile(r"\bNo\.?\s*10\b", re.IGNORECASE), "attacking midfielder"),
    (re.compile(r"\bCB\b", re.IGNORECASE), "center back"),
    (re.compile(r"\bRB\b", re.IGNORECASE), "right back"),
    (re.compile(r"\bLB\b", re.IGNORECASE), "left back"),
    (re.compile(r"\bRW\b", re.IGNORECASE), "right winger"),
    (re.compile(r"\bLW\b", re.IGNORECASE), "left winger"),
    (re.compile(r"\bST\b", re.IGNORECASE), "striker"),
    (re.compile(r"\bCF\b", re.IGNORECASE), "center forward"),
    (re.compile(r"\bGK\b", re.IGNORECASE), "goalkeeper"),
    (re.compile(r"\bCM\b", re.IGNORECASE), "central midfielder"),
    (re.compile(r"\bAM\b", re.IGNORECASE), "attacking midfielder"),
    # Comparison keywords
    (re.compile(r"\bvs\b", re.IGNORECASE), "compare"),
    (re.compile(r"\bversus\b", re.IGNORECASE), "compare"),
    # Spelling normalisation
    (re.compile(r"\banalyse\b", re.IGNORECASE), "analyze"),
    (re.compile(r"\bdefence\b", re.IGNORECASE), "defense"),
    (re.compile(r"\boffence\b", re.IGNORECASE), "offense"),
    (re.compile(r"\bfixture\b", re.IGNORECASE), "match"),
]


def normalize_query(query: str) -> str:
    """Normalize football terminology before intent classification."""
    result = query
    for pattern, replacement in QUERY_NORMALIZATIONS:
        result = pattern.sub(replacement, result)
    return result


# ─── Alias tables ─────────────────────────────────────────────────────────────

PLAYER_ALIASES: dict[str, str] = {
    # Manchester City
    "kdb": "Kevin De Bruyne",
    "de bruyne": "Kevin De Bruyne",
    "rodri": "Rodrigo Hernández Cascante",
    "rodrigo hernandez": "Rodrigo Hernández Cascante",
    "haaland": "Erling Haaland",
    # Barcelona / Spain
    "pedri": "Pedro González López",
    "gavi": "Pablo Martín Páez Gavira",
    # Arsenal
    "odegaard": "Martin Ødegaard",
    "odegard": "Martin Ødegaard",
    "saka": "Bukayo Saka",
    "bukayo": "Bukayo Saka",
    # Liverpool
    "salah": "Mohamed Salah",
    "mo salah": "Mohamed Salah",
    "vvd": "Virgil van Dijk",
    "virgil": "Virgil van Dijk",
    "trent": "Trent Alexander-Arnold",
    "alexander-arnold": "Trent Alexander-Arnold",
    # Real Madrid
    "bellingham": "Jude Bellingham",
    "jude": "Jude Bellingham",
    "vinicius": "Vinícius José Paixão de Oliveira Júnior",
    "vini": "Vinícius José Paixão de Oliveira Júnior",
    # Common names
    "vardy": "Jamie Vardy",
    "maguire": "Harry Maguire",
    "grealish": "Jack Grealish",
    "foden": "Phil Foden",
    "phil foden": "Phil Foden",
    "kane": "Harry Kane",
    "harry kane": "Harry Kane",
    "son": "Son Heung-min",
    "heung-min": "Son Heung-min",
    "kimmich": "Joshua Kimmich",
    "musiala": "Jamal Musiala",
    "jamal": "Jamal Musiala",
    "wirtz": "Florian Wirtz",
    "florian": "Florian Wirtz",
    "samba": "Brice Samba",
    "kylian": "Kylian Mbappé Lottin",
    "mbappe": "Kylian Mbappé Lottin",
    "mbappé": "Kylian Mbappé Lottin",
    "neymar": "Neymar da Silva Santos Junior",
    "iniesta": "Andrés Iniesta Luján",
    "xavi": "Xavier Hernández Creus",
    "puyol": "Carles Puyol i Saforcada",
    "busquets": "Sergio Busquets i Burgos",
    "courtois": "Thibaut Courtois",
    "modric": "Luka Modrić",
    "ramos": "Sergio Ramos",
    "alba": "Jordi Alba Ramos",
    "jordi alba": "Jordi Alba Ramos",
    "messi": "Lionel Andrés Messi Cuccittini",
    "lionel messi": "Lionel Andrés Messi Cuccittini",
    "cristiano ronaldo": "Cristiano Ronaldo dos Santos Aveiro",
    "cristiano": "Cristiano Ronaldo dos Santos Aveiro",
    "cr7": "Cristiano Ronaldo dos Santos Aveiro",
}

TEAM_ALIASES: dict[str, str] = {
    "man city": "Manchester City",
    "manchester city": "Manchester City",
    "mancity": "Manchester City",
    "man united": "Manchester United",
    "manchester united": "Manchester United",
    "manutd": "Manchester United",
    "utd": "Manchester United",
    "liverpool": "Liverpool",
    "lfc": "Liverpool",
    "arsenal": "Arsenal",
    "afc": "Arsenal",
    "chelsea": "Chelsea",
    "cfc": "Chelsea",
    "tottenham": "Tottenham Hotspur",
    "spurs": "Tottenham Hotspur",
    "tot": "Tottenham Hotspur",
    "tottenham hotspur": "Tottenham Hotspur",
    "newcastle": "Newcastle United",
    "nufc": "Newcastle United",
    "newcastle united": "Newcastle United",
    "everton": "Everton",
    "efc": "Everton",
    "aston villa": "Aston Villa",
    "avfc": "Aston Villa",
    "west ham": "West Ham United",
    "whu": "West Ham United",
    "west ham united": "West Ham United",
    "leicester": "Leicester City",
    "lcfc": "Leicester City",
    "leicester city": "Leicester City",
    "brighton": "Brighton & Hove Albion",
    "bhafc": "Brighton & Hove Albion",
    "brighton and hove albion": "Brighton & Hove Albion",
    "brighton hove albion": "Brighton & Hove Albion",
    "wolves": "Wolverhampton Wanderers",
    "wwfc": "Wolverhampton Wanderers",
    "barca": "Barcelona",
    "fc barcelona": "Barcelona",
    "barcelona": "Barcelona",
    "real madrid": "Real Madrid",
    "madrid": "Real Madrid",
    "rmcf": "Real Madrid",
    "atletico": "Atlético Madrid",
    "atleti": "Atlético Madrid",
    "atletico madrid": "Atlético Madrid",
    "atlético madrid": "Atlético Madrid",
    "bayern": "Bayern Munich",
    "fc bayern": "Bayern Munich",
    "bayern munich": "Bayern Munich",
    "fc bayern munich": "Bayern Munich",
    "bvb": "Borussia Dortmund",
    "dortmund": "Borussia Dortmund",
    "borussia dortmund": "Borussia Dortmund",
    "psg": "Paris Saint-Germain",
    "paris": "Paris Saint-Germain",
    "paris saint germain": "Paris Saint-Germain",
    "paris saint-germain": "Paris Saint-Germain",
    "juventus": "Juventus",
    "juve": "Juventus",
    "inter": "Inter Milan",
    "inter milan": "Inter Milan",
    "ac milan": "AC Milan",
    "milan": "AC Milan",
    "napoli": "Napoli",
    "ssc napoli": "Napoli",
    "roma": "AS Roma",
    "as roma": "AS Roma",
    "ajax": "Ajax",
    "afc ajax": "Ajax",
    "benfica": "Benfica",
    "sl benfica": "Benfica",
    "porto": "FC Porto",
    "fc porto": "FC Porto",
    "sporting": "Sporting CP",
    "sporting cp": "Sporting CP",
}


# ─── Normalization ────────────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    """Strip accents, lowercase, remove non-alphanumeric except spaces."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─── Entity Index ─────────────────────────────────────────────────────────────


class EntityIndex:
    """In-memory index of known entities for deterministic resolution.

    Built once from the Intelligence Store player index and graph nodes.
    Caches normalized names for fast lookup.
    """

    def __init__(self):
        self._players: dict[str, dict[str, Any]] = {}
        self._teams: dict[str, dict[str, Any]] = {}  # canonical_name -> info
        self._player_aliases: dict[str, str] = {}
        self._team_aliases: dict[str, str] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._build_player_index()
        self._build_team_index()
        self._build_alias_tables()

    def _build_player_index(self) -> None:
        """Load player index from the Intelligence Store."""
        index_path = Path("data/warehouse/player_index.parquet")
        if not index_path.exists():
            return
        df = pd.read_parquet(index_path)
        career = df[df["profile_type"] == "career"].drop_duplicates(subset=["player_id"])

        for _, row in career.iterrows():
            norm = _normalize(row["player_name"])
            self._players[norm] = {
                "id": int(row["player_id"]),
                "name": row["player_name"],
                "norm": norm,
                "position": row.get("position", ""),
                "team": row.get("team_name", ""),
                "type": "player",
            }

    def _build_team_index(self) -> None:
        """Load team entities from the knowledge graph."""
        graph_path = Path("data/knowledge/nodes.parquet")
        if not graph_path.exists():
            return
        df = pd.read_parquet(graph_path)
        teams = df[df["node_type"] == "team"].drop_duplicates(subset=["display_name"])

        for _, row in teams.iterrows():
            display = row["display_name"]
            norm = _normalize(display)
            if norm not in self._teams:
                self._teams[norm] = {
                    "name": display,
                    "norm": norm,
                    "entity_id": row["entity_id"],
                    "type": "team",
                }

    def _build_alias_tables(self) -> None:
        for alias, canonical in PLAYER_ALIASES.items():
            self._player_aliases[_normalize(alias)] = canonical
        for alias, canonical in TEAM_ALIASES.items():
            self._team_aliases[_normalize(alias)] = canonical

    # ── Resolution ────────────────────────────────────────────────────────

    def resolve_player(self, token: str) -> dict[str, Any] | None:
        """Resolve a player query to a player info dict.

        Returns None if not found or if multiple candidates exist (ambiguity).
        """
        self._ensure_loaded()
        norm = _normalize(token)
        if not norm:
            return None

        # 1. Alias lookup
        if norm in self._player_aliases:
            canonical = self._player_aliases[norm]
            canon_norm = _normalize(canonical)
            if canon_norm in self._players:
                return self._players[canon_norm]
            return None

        # 2. Exact normalized name match
        if norm in self._players:
            return self._players[norm]

        # 3. Token-level prefix match
        candidates = self._token_match(norm, self._players)
        # Deduplicate by player_id (same player may appear in multiple index rows)
        unique = {}
        for c in candidates:
            unique[c["id"]] = c
        unique_list = list(unique.values())
        if len(unique_list) == 1:
            return unique_list[0]
        if len(unique_list) > 1:
            return None  # genuinely ambiguous
        return None

    def resolve_team(self, token: str) -> dict[str, Any] | None:
        """Resolve a team alias or name to a team info dict.

        Returns None if not found or if multiple candidates exist (ambiguity).
        """
        self._ensure_loaded()
        norm = _normalize(token)
        if not norm:
            return None

        # 1. Alias lookup
        if norm in self._team_aliases:
            canonical = self._team_aliases[norm]
            canon_norm = _normalize(canonical)
            if canon_norm in self._teams:
                return self._teams[canon_norm]
            # Fallback: construct a synthetic entry when the graph is not yet
            # loaded.  The entity_id follows the graph builder's convention
            # (lowercased name without diacritics) so edge queries will
            # resolve correctly once the graph exists.
            return {
                "entity_id": canonical.lower().replace(" ", "_")
                    .replace("&", "and")
                    .replace("é", "e").replace("ö", "o").replace("ü", "u")
                    .replace("ñ", "n").replace("ó", "o").replace("í", "i")
                    .replace("á", "a").replace("à", "a").replace("è", "e"),
                "name": canonical,
                "norm": canon_norm,
                "type": "team",
            }

        # 2. Exact normalized name match
        if norm in self._teams:
            return self._teams[norm]

        # 3. Token-level prefix match
        candidates = self._token_match(norm, self._teams)
        if len(candidates) == 1:
            return candidates[0]
        return None

    def resolve_players(self, query: str) -> list[dict[str, Any]]:
        """Extract all resolvable player mentions from a query string."""
        self._ensure_loaded()
        results: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        tokens = self._tokenize_query(query)
        for token in tokens:
            player = self.resolve_player(token)
            if player and player["id"] not in seen_ids:
                seen_ids.add(player["id"])
                results.append(player)

        return results

    def resolve_teams(self, query: str) -> list[dict[str, Any]]:
        """Extract all resolvable team mentions from a query string."""
        self._ensure_loaded()
        results: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        tokens = self._tokenize_query(query)
        for token in tokens:
            team = self.resolve_team(token)
            if team and team["name"] not in seen_names:
                seen_names.add(team["name"])
                results.append(team)

        return results

    def resolve_both(self, query: str) -> dict[str, list[dict[str, Any]]]:
        """Resolve both players and teams from a query.

        Teams are checked first per token to avoid name collisions
        (e.g. "Bayern" should be a team, not a player name fragment).
        """
        self._ensure_loaded()
        players: list[dict[str, Any]] = []
        teams: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        seen_teams: set[str] = set()

        tokens = self._tokenize_query(query)
        for token in tokens:
            team = self.resolve_team(token)
            if team and team["name"] not in seen_teams:
                seen_teams.add(team["name"])
                teams.append(team)
            else:
                player = self.resolve_player(token)
                if player and player["id"] not in seen_ids:
                    seen_ids.add(player["id"])
                    players.append(player)

        return {"players": players, "teams": teams}

    def find_ambiguities(self, query: str) -> list[dict[str, Any]]:
        """Return deterministic candidate sets that need user clarification."""
        self._ensure_loaded()
        ambiguities: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()
        full_norm = _normalize(query)

        # Phase 1: full-entity detection.  If the query contains a complete
        # entity name as a substring, that entity is not ambiguous regardless
        # of what individual tokens match.  This prevents "Brighton & Hove
        # Albion" from entering ambiguity via a partial "Albion" token while
        # the full name is clearly present in the query.
        full_entity_norms: set[str] = set()
        for norm in self._teams:
            if norm in full_norm:
                full_entity_norms.add(norm)
        for norm in self._players:
            if norm in full_norm:
                full_entity_norms.add(norm)

        for token in self._tokenize_query(query):
            norm = _normalize(token)
            if not norm or norm in seen_tokens:
                continue
            seen_tokens.add(norm)
            if norm in self._players or norm in self._teams:
                continue
            if norm in self._player_aliases or norm in self._team_aliases:
                continue

            candidates = self._deduplicate_candidates(
                self._token_match(norm, self._players), "id"
            )
            candidates.extend(
                self._deduplicate_candidates(
                    self._token_match(norm, self._teams), "entity_id"
                )
            )

            # Remove candidates already covered by a full-entity name match.
            # The full name was present in the query — individual tokens of
            # that name should not trigger ambiguity.
            candidates = [
                c for c in candidates
                if c.get("norm") not in full_entity_norms
            ]

            if len(candidates) > 1:
                ambiguities.append(
                    {
                        "query": token,
                        "candidates": sorted(
                            candidates,
                            key=lambda candidate: (candidate["name"], candidate["type"]),
                        ),
                    }
                )

        return ambiguities

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _token_match(norm: str, entity_dict: dict) -> list[dict[str, Any]]:
        """Find entities where tokens match by exact match, prefix match (both directions)."""
        tokens = norm.split()
        candidates = []
        for e_norm, e_info in entity_dict.items():
            e_tokens = e_norm.split()
            if any(
                qt == et
                or (
                    len(qt) >= 4
                    and len(et) >= 4
                    and et.startswith(qt)
                )
                for qt in tokens
                for et in e_tokens
            ):
                candidates.append(e_info)
        return candidates

    @staticmethod
    def _deduplicate_candidates(
        candidates: list[dict[str, Any]], key: str
    ) -> list[dict[str, Any]]:
        """Return candidates once, preserving deterministic index order."""
        unique: dict[Any, dict[str, Any]] = {}
        for candidate in candidates:
            unique[candidate[key]] = candidate
        return list(unique.values())

    @staticmethod
    def _tokenize_query(query: str) -> list[str]:
        """Split query into meaningful tokens."""
        q_lower = query.lower().strip().replace("'", "").replace("`", "")
        multi_word_names = [
            "declan rice", "kevin de bruyne", "virgil van dijk", "trent alexander-arnold",
            "phil foden", "bukayo saka", "jude bellingham", "harry kane",
            "jamal musiala", "florian wirtz", "joshua kimmich", "mohamed salah",
            "cristiano ronaldo", "lionel messi", "neymar junior", "kylian mbappe",
            "luka modric", "sergio ramos", "jordi alba", "rodrigo hernandez",
            "erling haaland", "martin odegard", "martin odegaard",
            "bayern munich", "real madrid", "manchester city", "manchester united",
            "man city",
            "borussia dortmund", "bayer leverkusen", "west ham", "aston villa",
            "tottenham hotspur", "newcastle united", "leicester city",
            "brighton and hove albion", "brighton hove albion", "brighton hove",
            "inter milan", "ac milan",
            "paris saint germain", "paris saint-germain",
            "atletico madrid", "atlético madrid",
        ]
        found: list[str] = []
        remaining = q_lower
        for name in sorted(multi_word_names, key=len, reverse=True):
            if name in remaining:
                found.append(name)
                remaining = remaining.replace(name, "", 1).strip()
        single_tokens = [t for t in remaining.split() if len(t) > 1]
        stop_words = {"the", "and", "compare", "analyze", "who", "what", "how", "does",
                      "is", "are", "vs", "versus", "which", "better", "best", "similar",
                      "like", "replace", "replacement", "for", "at", "in", "of", "to",
                      "a", "an", "fit", "fits", "would", "do", "can", "tell", "me",
                      "about", "their", "his", "her", "its", "between", "both", "with",
                      "from", "than", "that", "this", "think", "need", "has", "have",
                      "did", "was", "were", "been", "being", "not", "no", "or", "but",
                      "if", "so", "up", "out", "down", "way", "more", "most", "some",
                      "any", "all", "each", "every", "very", "just", "also", "too",
                      "presses", "pressing", "press", "weaknesses", "strengths",
                      "style", "styles", "system", "systems", "formation", "tactics",
                      "players", "player", "team", "squad", "match", "matches", "game",
                      "games", "season", "seasons", "league", "competition"}
        meaningful = [t for t in single_tokens if t not in stop_words and len(t) > 1]
        return found + meaningful


# ─── Singleton ────────────────────────────────────────────────────────────────

_entity_index: EntityIndex | None = None


def get_entity_index() -> EntityIndex:
    """Get or create the singleton entity index."""
    global _entity_index
    if _entity_index is None:
        _entity_index = EntityIndex()
    return _entity_index
