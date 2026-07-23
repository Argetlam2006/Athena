"""
backend/knowledge/query.py — Entity Graph query interface.

Provides typed access to the Entity Graph for retrieval execution.
All queries return typed domain objects (EntityRef, Edge) rather than
raw dicts, so downstream consumers are isolated from storage format.

This module contains NO football analysis — only graph traversal logic.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb

from backend.knowledge.builder import EDGES_PATH, NODES_PATH
from shared.schemas.retrieval import Edge, EdgeType, EntityRef, NodeType

logger = logging.getLogger(__name__)


class GraphQuery:
    """Query interface for the Entity Graph.

    Usage:
        gq = GraphQuery()
        edges = gq.get_edges(EntityRef(NodeType.PLAYER, "42"), EdgeType.HAS_CAPABILITY)
        nodes = gq.get_entity(EntityRef(NodeType.TEAM, "some_team"))
    """

    def __init__(self, edges_path: Path = EDGES_PATH, nodes_path: Path = NODES_PATH):
        self.edges_path = edges_path
        self.nodes_path = nodes_path

        if not edges_path.exists() or not nodes_path.exists():
            logger.warning("Graph tables not found — call GraphBuilder.build() first.")

    def _connect(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(":memory:")
        if self.edges_path.exists():
            con.execute(
                f"CREATE OR REPLACE VIEW edges AS SELECT * FROM read_parquet('{self.edges_path}')"
            )
        if self.nodes_path.exists():
            con.execute(
                f"CREATE OR REPLACE VIEW nodes AS SELECT * FROM read_parquet('{self.nodes_path}')"
            )
        return con

    @staticmethod
    def _row_to_edge(row: dict) -> Edge:
        """Convert a raw parquet row dict into a typed Edge object."""
        return Edge(
            source=EntityRef(
                node_type=NodeType(row["source_type"]),
                entity_id=row["source_id"],
            ),
            target=EntityRef(
                node_type=NodeType(row["target_type"]),
                entity_id=row["target_id"],
            ),
            edge_type=EdgeType(row["edge_type"]),
            weight=row.get("weight"),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else row.get("metadata") or {},
        )

    def get_entity(self, ref: EntityRef) -> dict | None:
        """Fetch a single entity node by reference.

        Returns node fields as a dict.  Nodes are lightweight metadata
        projections (display name, position, archetype) that vary by node
        type — a single typed schema would be too lossy or too generic.
        """
        con = self._connect()
        try:
            result = con.execute(
                "SELECT * FROM nodes WHERE node_type = ? AND entity_id = ?",
                [ref.node_type.value, ref.entity_id],
            ).fetchdf()
            if result.empty:
                return None
            return result.iloc[0].to_dict()
        finally:
            con.close()

    def get_edges(
        self,
        source_ref: EntityRef | None = None,
        edge_type: EdgeType | None = None,
        target_type: NodeType | None = None,
    ) -> list[Edge]:
        """Fetch edges with optional filters on source, type, and target type.

        Always returns typed Edge objects.  Downstream consumers never
        touch raw parquet columns.

        Returns empty list if the graph has not been built yet.
        """
        con = self._connect()
        try:
            # Check if the edge view exists
            try:
                con.execute("SELECT 1 FROM edges LIMIT 1").fetchone()
            except Exception:
                return []

            conditions = ["1=1"]
            params: list = []

            if source_ref:
                conditions.append("source_type = ? AND source_id = ?")
                params.extend([source_ref.node_type.value, source_ref.entity_id])

            if edge_type:
                conditions.append("edge_type = ?")
                params.append(edge_type.value)

            if target_type:
                conditions.append("target_type = ?")
                params.append(target_type.value)

            sql = f"SELECT * FROM edges WHERE {' AND '.join(conditions)}"
            df = con.execute(sql, params).fetchdf()
            if df.empty:
                return []
            return [self._row_to_edge(row) for row in df.to_dict(orient="records")]
        finally:
            con.close()

    def traverse(
        self,
        start: EntityRef,
        edge_type: EdgeType | None = None,
        target_type: NodeType | None = None,
        max_hops: int = 1,
    ) -> list[list[Edge]]:
        """Walk the graph from a start entity, collecting typed edge paths.

        Each returned list is one path (sequence of Edge objects) from
        start to the reachable entity at the final hop.

        NOTE: max_hops > 1 requires DuckDB recursive CTEs. This
        implementation handles the common case of 1-hop traversal
        efficiently; multi-hop uses iterative expansion without
        cycle detection — use only on acyclic graphs.
        """
        if max_hops < 1:
            return []

        edges = self.get_edges(
            source_ref=start,
            edge_type=edge_type,
            target_type=target_type,
        )
        paths: list[list[Edge]] = [[e] for e in edges]

        # Multi-hop: iterative expansion (no cycle detection)
        for _ in range(2, max_hops + 1):
            new_paths: list[list[Edge]] = []
            for path in paths:
                last_edge = path[-1]
                current_ref = last_edge.target
                next_edges = self.get_edges(
                    source_ref=current_ref,
                    edge_type=edge_type,
                    target_type=target_type,
                )
                for ne in next_edges:
                    new_paths.append(path + [ne])
            paths = new_paths if new_paths else paths

        return paths

    def get_nodes_by_type(self, node_type: NodeType | str) -> list[dict]:
        """Return all nodes of a given type.
        Returns raw dicts (node field structure varies by type).
        Returns empty list if the graph has not been built yet.
        """
        type_value = node_type.value if isinstance(node_type, NodeType) else node_type
        con = self._connect()
        try:
            try:
                con.execute("SELECT 1 FROM nodes LIMIT 1").fetchone()
            except Exception:
                return []
            df = con.execute(
                "SELECT * FROM nodes WHERE node_type = ?",
                [type_value],
            ).fetchdf()
            return df.to_dict(orient="records") if not df.empty else []
        finally:
            con.close()

    def get_graph_summary(self) -> dict:
        """Return a summary of graph contents (node/edge counts by type)."""
        con = self._connect()
        try:
            node_counts = con.execute(
                "SELECT node_type, COUNT(*) as cnt FROM nodes GROUP BY node_type"
            ).fetchdf()
            edge_counts = con.execute(
                "SELECT edge_type, COUNT(*) as cnt FROM edges GROUP BY edge_type"
            ).fetchdf()

            return {
                "nodes": dict(zip(node_counts.node_type, node_counts.cnt, strict=False))
                if not node_counts.empty
                else {},
                "edges": dict(zip(edge_counts.edge_type, edge_counts.cnt, strict=False))
                if not edge_counts.empty
                else {},
            }
        finally:
            con.close()
