"""
backend/knowledge/registry.py — Edge type registry for the retrieval graph.

Every edge type in the Entity Graph must be declared here with its source
function, engine attribution, and invalidation rules.  This registry is the
mechanically-enforceable version of the "no new football analysis" invariant:
if an edge type is not registered, the builder will not produce it.

Edge types are grouped by origin:

  DIRECT  — projected from the store with no new computation.
  DERIVED — computed from store data via deterministic functions the engine
            already defines (e.g. euclidean_distance).  Still "no new analysis"
            because the computation is inherited, not invented.

New edge types must be added here BEFORE the builder can reference them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared.schemas.retrieval import EdgeType


class EdgeOrigin(str, Enum):
    """Whether an edge is a direct store projection or a derived computation."""
    DIRECT = "direct"
    DERIVED = "derived"


@dataclass(frozen=True)
class EdgeSource:
    """Declares the source of truth for an edge type."""

    origin: EdgeOrigin
    """DIRECT = projected from store fields; DERIVED = deterministic computation."""

    engine: str
    """Which engine produces the source data (FIE, DecisionEngine, CollectiveEngine)."""

    source_module: str
    """Python module where the source function lives (for audit / CI checks)."""

    source_function: str
    """Function name that produces or defines this edge's data."""


# ─── Registry ─────────────────────────────────────────────────────────────────

EDGE_REGISTRY: dict[EdgeType, EdgeSource] = {
    # Player → Capability  (direct: CapabilityProfile fields)
    EdgeType.HAS_CAPABILITY: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="shared.schemas",
        source_function="CapabilityProfile",
    ),
    # Player → Team  (direct: PlayerProfile.team_name)
    EdgeType.MEMBER_OF: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="backend.intelligence.store",
        source_function="IntelligenceStore",
    ),
    # Player → Archetype  (direct: PlayerProfile.archetype_profile)
    EdgeType.CLASSIFIED_AS: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="backend.intelligence.archetypes",
        source_function="assign_archetypes",
    ),
    # Player → Signal  (direct: PlayerProfile.decision_signals)
    EdgeType.TRIGGERS: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="DecisionEngine",
        source_module="backend.intelligence.signals",
        source_function="generate_decision_signals",
    ),
    # Team → Player  (direct: CollectiveProfile.fragility_map)
    EdgeType.FRAGILE_ON: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="CollectiveEngine",
        source_module="backend.collective.fragility",
        source_function="analyze_system_fragility",
    ),
    # Team → Capability  (direct: CollectiveProfile.avg_capabilities)
    EdgeType.HAS_SQUAD_CAPABILITY: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="CollectiveEngine",
        source_module="backend.collective.engine",
        source_function="compute_averages",
    ),
    # Team → Bottleneck  (direct: CollectiveProfile.bottlenecks)
    EdgeType.HAS_BOTTLENECK: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="CollectiveEngine",
        source_module="backend.collective.bottlenecks",
        source_function="identify_bottlenecks",
    ),
    # Team → Concentration  (direct: CollectiveProfile.concentration)
    EdgeType.HAS_CONCENTRATION: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="CollectiveEngine",
        source_module="backend.collective.structure",
        source_function="analyze_concentration",
    ),
    # Player → Player (similarity)  (derived: euclidean_distance)
    EdgeType.SIMILAR_TO: EdgeSource(
        origin=EdgeOrigin.DERIVED,
        engine="DecisionEngine",
        source_module="backend.intelligence.normalization",
        source_function="euclidean_distance",
    ),
    # Player → Player (replacement)  (derived: recommend_replacement)
    EdgeType.REPLACEMENT_FOR: EdgeSource(
        origin=EdgeOrigin.DERIVED,
        engine="DecisionEngine",
        source_module="backend.recommendation.recruitment",
        source_function="recommend_replacement",
    ),
    # Player → TacticalSystem  (derived: evaluate_tactical_fit)
    EdgeType.FITS_STYLE: EdgeSource(
        origin=EdgeOrigin.DERIVED,
        engine="DecisionEngine",
        source_module="backend.recommendation.matching",
        source_function="evaluate_tactical_fit",
    ),
    # Comparison edges (direct: ComparisonResult)
    EdgeType.SHARED_STRENGTH: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="DecisionEngine",
        source_module="backend.recommendation.comparison",
        source_function="compare_players",
    ),
    EdgeType.KEY_DIFFERENCE: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="DecisionEngine",
        source_module="backend.recommendation.comparison",
        source_function="compare_players",
    ),
    # Temporal edges (direct: store profile hierarchy)
    EdgeType.SEASON_OF: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="backend.intelligence.build_store",
        source_function="SeasonBuilder",
    ),
    EdgeType.CAREER_OF: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="backend.intelligence.build_store",
        source_function="CareerBuilder",
    ),
    EdgeType.SUPERSEDES: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="backend.intelligence.build_store",
        source_function="build_store",
    ),
    # Bottleneck (team-level structural)
    EdgeType.BOTTLENECKS_INTO: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="CollectiveEngine",
        source_module="backend.collective.bottlenecks",
        source_function="identify_bottlenecks",
    ),
    # Capability → Metric (attribution)
    EdgeType.POSTED_METRIC: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="shared.schemas",
        source_function="CapabilityScore",
    ),
    # TacticalSystem → Capability (derived: evaluate_tactical_fit weights)
    EdgeType.REQUIRES: EdgeSource(
        origin=EdgeOrigin.DERIVED,
        engine="DecisionEngine",
        source_module="backend.recommendation.matching",
        source_function="evaluate_tactical_fit",
    ),
    # Archetype → Capability (definitional: ARCHETYPE_TEMPLATES)
    EdgeType.VALUES: EdgeSource(
        origin=EdgeOrigin.DIRECT,
        engine="FIE",
        source_module="backend.intelligence.archetypes",
        source_function="ARCHETYPE_TEMPLATES",
    ),
    # Depends on (inverse of fragile_on — structural dependency)
    EdgeType.DEPENDS_ON: EdgeSource(
        origin=EdgeOrigin.DERIVED,
        engine="CollectiveEngine",
        source_module="backend.collective.fragility",
        source_function="analyze_system_fragility",
    ),
}
"""Complete registry of edge types the graph builder can produce.

Every EdgeType in shared.schemas.retrieval must have an entry here.
Adding a new edge type requires:
  1. Adding it to EdgeType in shared/schemas/retrieval.py
  2. Adding an entry in EDGE_REGISTRY
  3. Implementing the projection in backend/knowledge/builder.py
"""


def get_edges_for_engine(engine: str) -> list[EdgeType]:
    """Return all edge types produced by a given engine."""
    return [
        et for et, src in EDGE_REGISTRY.items()
        if src.engine == engine
    ]
