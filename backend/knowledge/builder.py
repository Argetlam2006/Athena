"""
backend/knowledge/builder.py — Entity Graph builder.

Reads from the Intelligence Store and produces typed entity + edge tables
in DuckDB.  Every edge is declared in the registry (backend/knowledge/registry.py)
and projected from store data with no new football analysis.

Properties proved by the builder:
  • Determinism — same store → identical graph
  • Idempotency — rebuild produces same output as initial build
  • Reproducibility — graph can be regenerated from store alone
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

from backend.intelligence.store import (
    STORE_DIR as INTELLIGENCE_STORE_DIR,
)
from backend.intelligence.store import (
    IntelligenceStore,
)
from backend.knowledge.registry import EDGE_REGISTRY
from shared.schemas import ProfileType
from shared.schemas.retrieval import EdgeType, NodeType

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

GRAPH_DIR = Path("data/knowledge")
NODES_PATH = GRAPH_DIR / "nodes.parquet"
EDGES_PATH = GRAPH_DIR / "edges.parquet"
BUILD_REPORT_PATH = GRAPH_DIR / "build_report.json"
EDGE_TYPES_TABLE = "edge_registry"

# ─── Registry check ──────────────────────────────────────────────────────────


def register_edge_types(con: duckdb.DuckDBPyConnection) -> None:
    """Persist the edge registry into the graph database for CI verification."""
    rows = [
        {"edge_type": et.value, "origin": src.origin.value, "engine": src.engine}
        for et, src in EDGE_REGISTRY.items()
    ]
    # Register via DuckDB Python API (ruff: _reg_df used by DuckDB local scope)
    _reg_df = pd.DataFrame(rows)  # noqa: F841 — used by DuckDB SQL local-scope access
    con.execute(f"CREATE OR REPLACE TABLE {EDGE_TYPES_TABLE} AS SELECT * FROM _reg_df")


def verify_edge_registry(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Check that every EdgeType in the schema is registered in EDGE_REGISTRY.

    Returns a list of missing edge types (empty = complete).
    """
    registered = {et.value for et in EDGE_REGISTRY}
    declared = {et.value for et in EdgeType}
    missing = declared - registered
    return sorted(missing)


# ─── Build report ────────────────────────────────────────────────────────────


@dataclass
class GraphBuildReport:
    """Observability report emitted by every graph build."""

    successful: bool
    entity_count: int
    edge_count_by_type: dict[str, int]
    generation_time_ms: float
    fingerprint: str
    registry_ok: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        total_edges = sum(self.edge_count_by_type.values())
        return (
            f"GraphBuildReport("
            f"ok={self.successful}, "
            f"entities={self.entity_count}, "
            f"edges={total_edges}, "
            f"types={len(self.edge_count_by_type)}, "
            f"time={self.generation_time_ms:.0f}ms"
            f")"
        )


# ─── Builder ─────────────────────────────────────────────────────────────────


class GraphBuilder:
    """Constructs the Entity Graph from the Intelligence Store.

    Usage:
        builder = GraphBuilder()
        report = builder.build()
    """

    def __init__(self, graph_dir: Path = GRAPH_DIR):
        self.graph_dir = graph_dir
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.store = IntelligenceStore()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _player_node_type(self, profile) -> NodeType:
        """Determine the correct NodeType for a PlayerProfile's profile_type."""
        from shared.schemas import ProfileType

        mapping = {
            ProfileType.CAREER: NodeType.PLAYER,
            ProfileType.SEASON: NodeType.PLAYER,
            ProfileType.COMPETITION: NodeType.PLAYER,
        }
        pt = getattr(profile, "profile_type", ProfileType.CAREER)
        return mapping.get(pt, NodeType.PLAYER)

    def _player_entity_id(self, profile) -> str:
        """Unique entity key for a player profile."""
        return str(profile.player_id)

    def _team_entity_id(self, team_name: str, competition: str, season: str) -> str:
        """Unique entity key for a team."""
        # A team+competition+season is the natural key
        return f"{team_name}__{competition}__{season}".replace(" ", "_").lower()

    # ── Build phases ──────────────────────────────────────────────────────

    def _build_player_nodes(self, all_players: list) -> tuple[pd.DataFrame, dict]:
        """Build the player nodes table.

        Returns (nodes_df, player_entity_map) where entity_map is
        {player_id: EntityRef as str} for edge building.
        """
        rows = []
        entity_map = {}

        for p in all_players:
            eid = self._player_entity_id(p)
            rows.append({
                "node_type": NodeType.PLAYER.value,
                "entity_id": eid,
                "display_name": p.player_name,
                "position_group": p.position_group,
                "team_name": p.team_name,
                "competition": p.competition,
                "season": p.season,
                "profile_type": getattr(p, "profile_type", ""),
                "birth_date": str(p.birth_date) if p.birth_date else None,
                "archetype": p.display_archetype,
                "minutes_played": float(p.minutes_played) if p.minutes_played else 0.0,
            })
            entity_map[p.player_id] = str(eid)

        return pd.DataFrame(rows), entity_map

    def _build_team_nodes(self, collectives: list) -> tuple[pd.DataFrame, dict]:
        """Build team nodes.

        Returns (nodes_df, team_entity_map) where entity_map is
        {team_name + competition + season: EntityRef as str}.
        """
        rows = []
        entity_map = {}

        for c in collectives:
            eid = self._team_entity_id(c.team_name, c.competition, c.season)
            rows.append({
                "node_type": NodeType.TEAM.value,
                "entity_id": eid,
                "display_name": c.team_name,
                "competition": c.competition,
                "season": c.season,
                "identity": c.identity.primary_identity if c.identity else "",
            })
            key = (c.team_name, c.competition, c.season)
            entity_map[key] = str(eid)

        return pd.DataFrame(rows), entity_map

    def _build_has_capability_edges(self, players: list) -> list[dict]:
        """Build HAS_CAPABILITY edges from CapabilityProfile data.

        Edge source: CapabilityProfile per player, per capability.
        Registry attribution: FIE (CapabilityProfile).
        """
        from shared.config.capabilities import CORE_CAPABILITIES

        rows = []
        for p in players:
            if not p.capability_profile:
                continue
            source_id = self._player_entity_id(p)
            for cap_name in CORE_CAPABILITIES:
                cap = getattr(p.capability_profile, cap_name)
                if cap is None:
                    continue
                target_id = f"{NodeType.CAPABILITY.value}:{cap_name}"
                rows.append({
                    "source_type": NodeType.PLAYER.value,
                    "source_id": source_id,
                    "target_type": NodeType.CAPABILITY.value,
                    "target_id": target_id,
                    "edge_type": EdgeType.HAS_CAPABILITY.value,
                    "weight": cap.score / 100.0 if cap.score else 0.0,
                    "metadata": json.dumps({
                        "score": cap.score,
                        "confidence": cap.confidence,
                        "evidence_count": len(cap.evidence),
                    }),
                })
        return rows

    def _build_member_of_edges(self, players: list, player_map: dict) -> list[dict]:
        """Build MEMBER_OF edges from PlayerProfile team assignments.

        Only competition-profile players have concrete team assignments
        (career profiles report "Multiple").  We build edges from
        competition profiles.

        Edge source: player profile fields (team_name, competition, season).
        Registry attribution: FIE (IntelligenceStore).
        """
        rows = []
        for p in players:
            if not p.team_name or p.team_name == "Multiple":
                continue
            pid = str(p.player_id)
            source_id = pid
            target_id = self._team_entity_id(p.team_name, p.competition, p.season)
            rows.append({
                "source_type": NodeType.PLAYER.value,
                "source_id": source_id,
                "target_type": NodeType.TEAM.value,
                "target_id": target_id,
                "edge_type": EdgeType.MEMBER_OF.value,
                "weight": 1.0,
                "metadata": json.dumps({
                    "minutes_played": float(p.minutes_played) if p.minutes_played else 0.0,
                    "matches_played": getattr(p, "matches_played", None),
                }),
            })
        return rows

    def _build_classified_as_edges(self, players: list) -> list[dict]:
        """Build CLASSIFIED_AS edges from PlayerProfile.archetype_profile.

        Edge source: ArchetypeProfile (primary_archetype, confidence).
        Registry attribution: FIE (assign_archetypes).
        """
        rows = []
        for p in players:
            if not p.archetype_profile:
                continue
            arch = p.archetype_profile
            if arch.primary_archetype == "Unknown" or arch.primary_archetype == "Goalkeeper":
                # Goalkeeper is a position-default label, not a football judgment
                if arch.primary_archetype == "Unknown" and arch.confidence == 0.0:
                    continue
            source_id = self._player_entity_id(p)
            target_id = f"{NodeType.ARCHE_TYPE.value}:{arch.primary_archetype.replace(' ', '_').lower()}"
            rows.append({
                "source_type": NodeType.PLAYER.value,
                "source_id": source_id,
                "target_type": NodeType.ARCHE_TYPE.value,
                "target_id": target_id,
                "edge_type": EdgeType.CLASSIFIED_AS.value,
                "weight": arch.confidence / 100.0 if arch.confidence else 0.0,
                "metadata": json.dumps({
                    "confidence": arch.confidence,
                    "alternatives": arch.alternatives,
                    "contributing_capabilities": arch.contributing_capabilities,
                }),
            })
        return rows

    def _build_triggers_edges(self, players: list) -> list[dict]:
        """Build TRIGGERS edges from PlayerProfile.decision_signals.

        Edge source: score list of signal names.
        Registry attribution: DecisionEngine (generate_decision_signals).

        Signals are populated on competition (per-season) profiles, not
        career profiles, so we use competition players for this.
        """
        rows = []
        seen: set[tuple[str, str]] = set()
        for p in players:
            if not p.decision_signals:
                continue
            pid = str(p.player_id)
            source_id = pid
            for signal in p.decision_signals:
                key = (source_id, signal)
                if key in seen:
                    continue  # avoid duplicates
                seen.add(key)
                target_id = f"{NodeType.SIGNAL.value}:{signal}"
                rows.append({
                    "source_type": NodeType.PLAYER.value,
                    "source_id": source_id,
                    "target_type": NodeType.SIGNAL.value,
                    "target_id": target_id,
                    "edge_type": EdgeType.TRIGGERS.value,
                    "weight": 1.0,
                    "metadata": "{}",
                })
        return rows

    def _build_team_capability_edges(self, collectives: list, team_map: dict) -> list[dict]:
        """Build HAS_SQUAD_CAPABILITY edges from CollectiveProfile.avg_capabilities.

        Edge source: squad-average scores per capability.
        Registry attribution: CollectiveEngine.
        """
        rows = []
        for c in collectives:
            key = (c.team_name, c.competition, c.season)
            source_id = team_map.get(key)
            if not source_id:
                continue
            for cap_name, score in c.avg_capabilities.items():
                if score is None:
                    continue
                target_id = f"{NodeType.CAPABILITY.value}:{cap_name}"
                rows.append({
                    "source_type": NodeType.TEAM.value,
                    "source_id": source_id,
                    "target_type": NodeType.CAPABILITY.value,
                    "target_id": target_id,
                    "edge_type": EdgeType.HAS_SQUAD_CAPABILITY.value,
                    "weight": score / 100.0 if score else 0.0,
                    "metadata": json.dumps({"score": score}),
                })
        return rows

    def _build_fragile_on_edges(self, collectives: list, team_map: dict) -> list[dict]:
        """Build FRAGILE_ON edges from CollectiveProfile.fragility_map.

        Edge source: SystemFragility data (structural_deficit, replaceability_index).
        Registry attribution: CollectiveEngine (analyze_system_fragility).
        """
        rows = []
        for c in collectives:
            key = (c.team_name, c.competition, c.season)
            source_id = team_map.get(key)
            if not source_id:
                continue
            for f in c.fragility_map:
                target_id = f"player:{f.player_id}"
                rows.append({
                    "source_type": NodeType.TEAM.value,
                    "source_id": source_id,
                    "target_type": NodeType.PLAYER.value,
                    "target_id": target_id,
                    "edge_type": EdgeType.FRAGILE_ON.value,
                    "weight": min(1.0, f.structural_deficit / 100.0),
                    "metadata": json.dumps({
                        "structural_deficit": f.structural_deficit,
                        "replaceability_index": f.replaceability_index,
                        "capability_loss": f.capability_loss,
                    }),
                })
        return rows

    def _write_parquet(self, con: duckdb.DuckDBPyConnection, df: pd.DataFrame,
                       path: Path, table_name: str) -> None:
        """Write a DataFrame to parquet and register it in DuckDB."""
        df.to_parquet(path, engine="pyarrow", index=False)
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")

    # ── Main build ────────────────────────────────────────────────────────

    def build(self) -> GraphBuildReport:
        """Execute a full graph build from the Intelligence Store.

        Returns a GraphBuildReport with build metadata and warnings.
        """
        start = time.perf_counter()
        warnings: list[str] = []

        # 1. Load the Intelligence Store
        #    Career profiles are the primary entities (richest view: archetypes).
        #    Competition profiles provide context-specific edges (member_of, triggers).
        career_players = self.store.get_all_players(profile_type=ProfileType.CAREER)
        comp_players = self.store.get_all_players(profile_type=ProfileType.COMPETITION)
        collectives = self.store.get_all_collectives()

        if not career_players:
            return GraphBuildReport(
                successful=False, entity_count=0, edge_count_by_type={},
                generation_time_ms=0.0, fingerprint="",
                registry_ok=False, warnings=["No players in store"],
            )

        # 2. Load store fingerprint
        fingerprint = ""
        fp_path = INTELLIGENCE_STORE_DIR / "intelligence_fingerprint.json"
        if fp_path.exists():
            try:
                with open(fp_path) as f:
                    fingerprint = json.loads(json.dumps(json.load(f)))
                fingerprint = fingerprint.get("model_version", "")
            except Exception:
                fingerprint = "unknown"

        # 3. Build nodes
        #    We build player nodes from career profiles only (single entity per
        #    player).  Competition profiles provide edges that refer to the same
        #    player IDs — they map to the same entity.
        player_nodes, player_map = self._build_player_nodes(career_players)
        team_nodes, team_map = self._build_team_nodes(collectives)

        # Merge nodes into single DataFrame
        all_node_dfs = [df for df in [player_nodes, team_nodes] if not df.empty]
        if not all_node_dfs:
            return GraphBuildReport(
                successful=False, entity_count=0, edge_count_by_type={},
                generation_time_ms=0.0, fingerprint=fingerprint,
                registry_ok=False, warnings=["No nodes to build"],
            )
        nodes_df = pd.concat(all_node_dfs, ignore_index=True)

        # 4. Build edges
        #    Career players → entity-level edges (has_capability, classified_as)
        #    Competition players → context-level edges (member_of, triggers)
        #    Collectives → team-level edges (has_squad_capability, fragile_on,
        #                   has_bottleneck, has_concentration)
        edge_builders = [
            self._build_has_capability_edges(career_players),
            self._build_member_of_edges(comp_players, player_map),
            self._build_classified_as_edges(career_players),
            self._build_triggers_edges(comp_players),
            self._build_team_capability_edges(collectives, team_map),
            self._build_fragile_on_edges(collectives, team_map),
        ]
        all_edges = []
        for edges in edge_builders:
            all_edges.extend(edges)

        edges_df = pd.DataFrame(all_edges) if all_edges else pd.DataFrame()

        # 5. Edge count per type
        edge_count_by_type: dict[str, int] = {}
        if not edges_df.empty:
            edge_count_by_type = edges_df.groupby("edge_type").size().to_dict()

        # 6. Verify registry — every EdgeType in the schema must have a
        #    registration entry, even if we don't build it in this milestone.
        con = duckdb.connect(":memory:")
        try:
            register_edge_types(con)
            missing = verify_edge_registry(con)
            registry_ok = len(missing) == 0
            if not registry_ok:
                warnings.append(
                    f"Edge types not yet registered in EDGE_REGISTRY (planned for later milestones): {missing}"
                )
            built_types = set(edge_count_by_type.keys())
            all_registered_types = {et.value for et in EDGE_REGISTRY}
            unbuilt = all_registered_types - built_types
            if unbuilt:
                warnings.append(
                    f"Registered edge types not built in this build (expected for M1 — many are derived or strategy-level): {sorted(unbuilt)}"
                )
        finally:
            con.close()

        # 7. Write to parquet
        self._write_parquet(
            duckdb.connect(":memory:"), nodes_df, NODES_PATH, "nodes"
        )
        self._write_parquet(
            duckdb.connect(":memory:"), edges_df, EDGES_PATH, "edges"
        )

        elapsed = (time.perf_counter() - start) * 1000

        report = GraphBuildReport(
            successful=True,
            entity_count=len(nodes_df),
            edge_count_by_type=edge_count_by_type,
            generation_time_ms=elapsed,
            fingerprint=fingerprint,
            registry_ok=registry_ok,
            warnings=warnings,
        )

        # Persist build report
        with open(BUILD_REPORT_PATH, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info(str(report))
        return report
