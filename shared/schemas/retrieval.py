"""
shared/schemas/retrieval.py — Retrieval architecture contracts for Athena.

This module is the single source of truth for the retrieval layer's typed
contracts.  It contains ONLY stable schema definitions — no business logic,
no graph construction, no validation algorithms, no execution behaviour.

Layer communication flow (retrieval architecture):

  Intent Classification → StructuredIntent
  Strategy Selection    → RetrievalPlan (via RetrievalStep)
  Graph Execution       → Claim + EvidenceBundle
  Prompt Assembly       → EvidenceBundle

Architectural invariants enforced by these contracts:

  1. Every graph edge is deterministic and reproducible.
  2. Claims never introduce new football knowledge.
  3. Every Claim has provenance.
  4. Every RetrievalPlan is deterministic and serializable.
  5. Plans describe *what* to retrieve, never *how* to execute it.
  6. Every EvidenceBundle contains explicit coverage information.
  7. The LLM only reasons over Claims contained within an EvidenceBundle.

No module should import from here unless it is part of the retrieval layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Version
# ─────────────────────────────────────────────────────────────────────────────

RETRIEVAL_SCHEMA_VERSION: str = "1.0.0"
"""Single version string for all retrieval-layer schema contracts."""

# ─────────────────────────────────────────────────────────────────────────────
# Entity Graph — node and edge types
# ─────────────────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    """Canonical entity types in the retrieval knowledge graph.

    Each member corresponds to a class of football entity that the
    deterministic intelligence engine already produces or references.
    """

    PLAYER = "player"
    TEAM = "team"
    CAPABILITY = "capability"
    ARCHE_TYPE = "archetype"
    TACTICAL_SYSTEM = "tactical_system"
    SIGNAL = "signal"
    METRIC = "metric"
    COMPETITION = "competition"
    POSITION_GROUP = "position_group"


class EdgeType(str, Enum):
    """Canonical relationship types in the retrieval knowledge graph.

    Every edge is deterministic: it represents a relationship that the
    football intelligence engine (FIE, DecisionEngine, or CollectiveEngine)
    already computes — never a relationship introduced by the retrieval layer.
    """

    # Player → Player
    SIMILAR_TO = "similar_to"
    REPLACEMENT_FOR = "replacement_for"

    # Player → Team
    MEMBER_OF = "member_of"

    # Player → Capability / Archetype / Signal / System
    HAS_CAPABILITY = "has_capability"
    CLASSIFIED_AS = "classified_as"
    TRIGGERS = "triggers"
    FITS_STYLE = "fits_style"

    # Player → Metric
    POSTED_METRIC = "posted_metric"

    # Team → Player (structural)
    FRAGILE_ON = "fragile_on"
    DEPENDS_ON = "depends_on"

    # Team → Capability
    HAS_SQUAD_CAPABILITY = "has_squad_capability"

    # Team → structural concepts
    HAS_BOTTLENECK = "has_bottleneck"
    HAS_CONCENTRATION = "has_concentration"

    # Capability ↔ Capability
    BOTTLENECKS_INTO = "bottlenecks_into"

    # Archetype → Capability
    VALUES = "values"

    # TacticalSystem → Capability
    REQUIRES = "requires"

    # Comparison
    SHARED_STRENGTH = "shared_strength"
    KEY_DIFFERENCE = "key_difference"

    # Temporal
    SEASON_OF = "season_of"
    CAREER_OF = "career_of"
    SUPERSEDES = "supersedes"


@dataclass(frozen=True)
class EntityRef:
    """A typed reference to a single graph entity.

    This is an identifier, not a data container.  Domain data lives in the
    intelligence engine's own schemas (PlayerProfile, CollectiveProfile, …);
    EntityRef exists solely to name and locate an entity within the graph.
    """

    node_type: NodeType
    """Which kind of entity this refers to."""

    entity_id: str
    """Unique identifier within its node type (e.g. player_id as string)."""

    def __str__(self) -> str:
        return f"{self.node_type.value}:{self.entity_id}"


@dataclass(frozen=True)
class Edge:
    """A single deterministic relationship between two graph entities.

    The ``edge_type`` carries the semantics of the relationship; the optional
    ``weight`` carries a pre-computed strength when the engine produces one.
    """

    source: EntityRef
    target: EntityRef
    edge_type: EdgeType
    weight: float | None = None
    """Pre-computed relationship strength from the engine (0–1 scale or None)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional deterministic fields the engine attaches to this relationship.
    Content depends on edge_type — e.g. severity for BOTTLENECKS_INTO,
    confidence for SIMILAR_TO, restoration map for REPLACEMENT_FOR."""


# ─────────────────────────────────────────────────────────────────────────────
# Reasoning — Claims
# ─────────────────────────────────────────────────────────────────────────────


class ClaimType(str, Enum):
    """Canonical types of deterministic assertions the engine can produce.

    Each claim type corresponds to a kind of football assertion the
    intelligence engine already makes.  Adding a new claim type here
    requires a corresponding projection method and registry entry in
    the retrieval executor.

    The enum IS the single source of truth: strategies reference these
    values, plans carry them, the executor dispatches on them, and
    coverage tracks them.
    """

    CAPABILITY = "capability"
    ARCHE_TYPE = "archetype"
    SIGNAL = "signal"
    ROLE_FIT = "role_fit"
    SHARED_STRENGTH = "shared_strength"
    KEY_DIFFERENCE = "key_difference"
    FRAGILITY = "fragility"
    RECRUITMENT_FIT = "recruitment_fit"

    # Team-level claims (planned for TeamAnalysis strategy)
    TEAM_CAPABILITY = "team_capability"
    TEAM_FRAGILITY = "team_fragility"
    TEAM_BOTTLENECK = "team_bottleneck"


class QualifierKind(str, Enum):
    """Taxonomy of qualifying conditions that contextualise a claim.

    Each member represents a category of caveat the deterministic engine
    already computes (via confidence bands, threshold checks, etc.).
    Qualifiers are never speculative; they are pre-computed facts about
    the evidence underlying the claim.
    """

    SAMPLE_SIZE = "sample_size"
    LEAGUE_CONTEXT = "league_context"
    REGRESSION_RISK = "regression_risk"
    ROLE_DEPENDENCE = "role_dependence"
    DATA_COVERAGE = "data_coverage"
    OVERPERFORMANCE_CAVEAT = "overperformance_caveat"


class Severity(str, Enum):
    """How materially a qualifier affects interpretation of the claim."""

    INFORMATIONAL = "informational"
    CAUTIONARY = "cautionary"
    MATERIAL = "material"


@dataclass(frozen=True)
class ClaimQualifier:
    """A single qualifying condition attached to a claim.

    ``kind``, ``severity``, and ``statement`` are all derived from existing
    deterministic engine outputs — never from LLM judgment or retrieval-layer
    heuristics.
    """

    kind: QualifierKind
    severity: Severity
    statement: str


@dataclass(frozen=True)
class ClaimProvenance:
    """Full audit trail for a claim.

    Every claim must carry provenance so that its origin can be traced back
    to a specific engine, version, and store-fingerprinted build.
    """

    engine: str
    """Which engine produced the source data this claim projects."""

    version_lineage: str
    """Engine version string(s) that produced this claim."""

    store_fingerprint: str
    """IntelligenceStore fingerprint under which this claim was built."""

    rule_refs: list[str] = field(default_factory=list)
    """Spec section IDs, signal IDs, or threshold rules that produced this claim."""


@dataclass(frozen=True)
class Claim:
    """A single atomic, deterministic assertion about an entity.

    Claims are the ONLY reasoning artifact the LLM ever receives.  They are
    projections of the engine's output — they never introduce new football
    knowledge.

    Every Claim carries:
      • identity — which entity/relationship it is about
      • predicate — what is being asserted
      • assessment — the engine's judgment (strength, confidence, basis)
      • supports — the metric-level traceability chain
      • qualifiers — pre-computed caveats
      • provenance — full audit trail
    """

    # Identity — what this claim is about
    claim_id: str
    """Deterministic hash of (about_entity, predicate_key, store_fingerprint)."""

    about_entity: EntityRef
    """The primary entity this claim asserts something about."""

    claim_type: str
    """Canonical category of the assertion (e.g. 'capability', 'signal')."""

    predicate_key: str
    """Machine identifier for the specific assertion within its type."""

    statement: str
    """One-line human-readable assertion."""

    # Assessment — the engine's quantitative judgment
    strength: float | None = None
    """0–100 score or null for qualitative claims."""

    confidence: str = "medium"
    """low | medium | high — from the engine's confidence bands."""

    confidence_basis: str = ""
    """Why this confidence level was assigned (e.g. '12 matches played')."""

    # Supports — the metric-level traceability chain
    supports: list[dict[str, Any]] = field(default_factory=list)
    """List of SupportingMetric-like dicts (metric_name, raw_value, percentile,
    contribution_weight, explanation).  These are the same traceability chain
    the engine already produces in CapabilityScore.evidence."""

    # Qualifiers — pre-computed caveats
    qualifiers: list[ClaimQualifier] = field(default_factory=list)

    # Provenance
    provenance: ClaimProvenance | None = None

    # Optional second entity (only when claim describes a relationship)
    about_relation: EntityRef | None = None
    """Optional second entity when the claim describes a relationship."""

    # Relations — typed edges to related entities
    related_entity_refs: list[EntityRef] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Intent — contract for strategy dispatch
# ─────────────────────────────────────────────────────────────────────────────


class IntentType(str, Enum):
    """Primary categories of analytical intent.

    Each member describes the kind of football question the user is asking.
    """

    PLAYER_ANALYSIS = "player_analysis"
    TEAM_ANALYSIS = "team_analysis"
    COMPARE_PLAYERS = "compare_players"
    RECRUITMENT = "recruitment"
    COUNTERFACTUAL = "counterfactual"
    SQUAD_DIAGNOSIS = "squad_diagnosis"
    GENERAL = "general"


@dataclass(frozen=True)
class StructuredIntent:
    """The resolved, structured representation of what a user query requires.

    This is the primary contract between intent classification and strategy
    selection.  It is intentionally forward-looking: fields are present that
    will be populated as classification improves, but they are optional for
    early implementations.

    ``primary_type`` determines which RetrievalStrategy is selected.
    ``entities`` determines the seeds for graph traversal.
    ``filters`` constrains the retrieval scope.
    """

    primary_type: IntentType
    """The resolved intent category."""

    entities: dict[str, str] = field(default_factory=dict)
    """Entity references keyed by role (e.g. {'focus_player': '42',
    'compare_player': '17', 'team': '7', 'competition': 'La Liga'})."""

    filters: dict[str, Any] = field(default_factory=dict)
    """Additional constraints (e.g. {'season': '2015/2016',
    'position': 'Midfielder', 'min_matches': 5})."""

    raw_text: str = ""
    """Original user query for audit / debugging."""


# ─────────────────────────────────────────────────────────────────────────────
# Planning — RetrievalPlan
# ─────────────────────────────────────────────────────────────────────────────


class RetrievalStepType(str, Enum):
    """Primitive operations the retrieval executor understands.

    These are the atoms of the retrieval language.  Plans are sequences of
    these steps.  Adding a new step type requires extending both the
    planning language and the executor — it is a versioned change to the
    RetrievalPlan schema.
    """

    GET_ENTITY = "get_entity"
    TRAVERSE_EDGES = "traverse_edges"
    PROJECT_CLAIMS = "project_claims"


@dataclass(frozen=True)
class RetrievalStep:
    """A single deterministic step in a retrieval plan.

    Steps describe *what* to retrieve, not *how* to execute it.
    The execution engine decides traversal algorithms, caching, and
    optimisation strategies independently.
    """

    step_type: RetrievalStepType
    """The kind of operation to perform."""

    entity_ref: EntityRef | None = None
    """Entity to fetch or start traversal from."""

    edge_type: EdgeType | None = None
    """Edge type to traverse (for TRAVERSE_EDGES steps)."""

    claim_types: list[str] = field(default_factory=list)
    """Claim types to project from resolved entities (for PROJECT_CLAIMS)."""

    max_hops: int = 1
    """Maximum traversal depth from the seed entity."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Strategy-specific guidance for this step (must not contain execution
    instructions)."""


@dataclass(frozen=True)
class RetrievalPlan:
    """A serialisable, deterministic, replayable description of what to retrieve.

    The RetrievalPlan is the Intermediate Representation (IR) of the retrieval
    architecture.  It separates *planning* (selecting what to retrieve) from
    *execution* (traversing the graph and projecting claims).

    Key properties:
      • Deterministic — same plan_id + same graph → same claims
      • Serializable — JSON round-trips without loss
      • Auditable — every traversal is explicitly listed
      • Replayable — the plan alone can be re-run against a different graph state
    """

    plan_id: str
    """Deterministic hash of (strategy, intent, store_fingerprint)."""

    strategy_name: str
    """Name of the strategy that produced this plan."""

    intent: StructuredIntent
    """The intent this plan was built from."""

    steps: list[RetrievalStep] = field(default_factory=list)
    """Ordered sequence of retrieval operations."""

    expected_claim_types: list[str] = field(default_factory=list)
    """Claim types the strategy expects to receive after execution."""

    store_fingerprint: str = ""
    """IntelligenceStore fingerprint the plan was built for."""

    entity_count: int = 0
    """Number of distinct entities the plan will touch."""

    traversal_count: int = 0
    """Number of edge traversals the plan requires."""


# ─────────────────────────────────────────────────────────────────────────────
# Evidence — Coverage and EvidenceBundle
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Coverage:
    """Records which claim types were sought and which were satisfied.

    The coverage map is the mechanism by which Athena enforces honest
    uncertainty.  If a claim type was sought but not produced, the LLM
    is instructed to refuse to answer questions that depend on that
    missing evidence rather than fabricating it.
    """

    total_sought: int = 0
    """Number of claim types the plan required."""

    satisfied: list[str] = field(default_factory=list)
    """Claim types that were successfully projected."""

    missing: list[str] = field(default_factory=list)
    """Claim types that were sought but not found."""

    partial: list[str] = field(default_factory=list)
    """Claim types that were partially satisfied (some entities missing)."""

    @property
    def is_complete(self) -> bool:
        """True when every sought claim type is fully satisfied."""
        return len(self.missing) == 0 and len(self.partial) == 0


@dataclass(frozen=True)
class EvidenceBundle:
    """The validated handoff between deterministic retrieval and LLM reasoning.

    The EvidenceBundle is the ONLY input the prompt builder should consume
    from the retrieval layer.  It wraps the complete retrieval output along
    with coverage metadata that lets the prompt builder (and downstream
    systems) verify that the LLM has sufficient evidence to answer the user's
    question.

    Architectural invariants:
      • The LLM reasons ONLY over claims in the claims list.
      • The prompt builder MUST check coverage.is_complete before proceeding.
      • The store_fingerprint MUST match the current IntelligenceStore state
        or the bundle is stale.
    """

    intent: StructuredIntent
    """The intent the retrieval plan was built from."""

    claims: list[Claim] = field(default_factory=list)
    """Retrieved claims, ranked by relevance to the intent."""

    plan_id: str = ""
    """The plan_id of the RetrievalPlan that produced this bundle."""

    store_fingerprint: str = ""
    """The IntelligenceStore fingerprint at retrieval time."""

    coverage: Coverage = field(default_factory=Coverage)
    """Which claim types were sought vs. found."""

    execution_time_ms: float = 0.0
    """Wall-clock time for the full retrieval-execution pipeline."""

    traversal_count: int = 0
    """Total edge traversals executed."""
