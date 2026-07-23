"""
shared/schemas.py — Athena data schemas and typed dataclasses

These are the structured data contracts between every layer of the AIF pipeline.

Layer communication flow:
  ETL → PlayerRaw
  Analytics Engine → PlayerFeatureVector
  AIF / Capability Engine → CapabilityProfile
  Intelligence Layer → PlayerProfile, CollectiveProfile
  Decision Engine → RecruitmentCandidate, ComparisonResult
  AI Layer → ScoutingReport

No layer should access another layer's internal data structures directly.
Always communicate through these schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Layer 0: Core Enums
# ─────────────────────────────────────────────────────────────────────────────


class ProfileType(str, Enum):
    COMPETITION = "competition"
    SEASON = "season"
    CAREER = "career"


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1–2: Raw and Statistical Data
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerRaw:
    """
    Minimal representation of a player as loaded from StatsBomb.
    Produced by the ETL pipeline.
    """

    statsbomb_id: int
    name: str
    position: str
    team_name: str
    competition_name: str
    season_name: str

    # Optional fields populated if available
    nationality: str | None = None
    birth_date: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None


@dataclass
class MatchRaw:
    """
    Minimal match record from StatsBomb.
    """

    match_id: int
    competition_id: int
    season_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    match_date: str
    stadium: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2–3: Feature Engineering Output
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerFeatureVector:
    """
    Normalized per-90 and contextual features for a player in a given season.
    Produced by the Analytics Engine from the DuckDB warehouse output.

    These are the exact primitive statistics that feed into the 8 capabilities
    defined in the Football Intelligence Engine specification.
    """

    player_id: int
    player_name: str
    season: str
    competition: str
    position_group: str
    secondary_position_group: str | None = None
    position_confidence: float = 1.0
    profile_type: ProfileType = ProfileType.COMPETITION
    minutes_played: float | None = None
    matches_played: int | None = None
    team_name: str = ""
    birth_date: str | None = None

    @property
    def age_years(self) -> float | None:
        """
        Dynamically calculate age in years from birth_date.
        """
        if not self.birth_date:
            return None
        try:
            from datetime import datetime

            bd = datetime.strptime(str(self.birth_date).split(" ")[0], "%Y-%m-%d")
            today = datetime.now()
            return round((today - bd).days / 365.25, 1)
        except Exception:
            return None

    # Ball Progression (4)
    progressive_passes_p90: float = 0.0
    progressive_carries_p90: float = 0.0
    carry_distance_p90: float = 0.0
    switches_p90: float = 0.0

    # Chance Creation (4)
    shot_assists_p90: float = 0.0
    goal_assists_p90: float = 0.0
    through_balls_p90: float = 0.0
    crosses_p90: float = 0.0

    # Ball Security (4)
    pass_accuracy_pct: float = 0.0
    dribble_success_pct: float = 0.0
    passes_p90: float = 0.0
    avg_pass_length_m: float = 0.0

    # Press Resistance (2)
    pressure_pct: float = 0.0
    events_under_pressure_p90: float = 0.0

    # Defensive Activity (6)
    pressures_p90: float = 0.0
    recoveries_p90: float = 0.0
    clearances_p90: float = 0.0
    tackles_p90: float = 0.0
    interceptions_p90: float = 0.0
    tackles_won_p90: float = 0.0

    # Internal Defensive Components (Phase B)
    dribbled_past_p90: float = 0.0
    errors_leading_to_shot_p90: float = 0.0
    aerials_won_p90: float = 0.0
    aerials_total_p90: float = 0.0

    # Attacking Threat (5)
    npxg_p90: float = 0.0
    goals_p90: float = 0.0
    xg_per_shot: float = 0.0
    shot_accuracy_pct: float = 0.0
    goals_minus_xg: float = 0.0

    # Derived Attacking Threat
    npxg_per_shot: float = 0.0

    # Extensibility for Future-Proofing & Presentation
    # Canonical location for presentation-only cumulative statistics (e.g., total goals, assists).
    # These exist strictly to enrich the UI and must NOT influence intelligence modelling.
    raw_metrics: dict | None = None

    # Tactical Versatility (1)
    positions_played_count: int = 1

    def to_vector(self) -> list[float]:
        """
        Return all numeric features as a flat list for ML computations.
        Matches the 23 explicit metrics from the FIE spec.
        """
        return [
            # Ball Progression (4)
            self.progressive_passes_p90,
            self.progressive_carries_p90,
            self.carry_distance_p90,
            self.switches_p90,
            # Chance Creation (4)
            self.shot_assists_p90,
            self.goal_assists_p90,
            self.through_balls_p90,
            self.crosses_p90,
            # Ball Security (4)
            self.pass_accuracy_pct,
            self.dribble_success_pct,
            self.passes_p90,
            self.avg_pass_length_m,
            # Press Resistance (2)
            self.pressure_pct,
            self.events_under_pressure_p90,
            # Defensive Activity (6)
            self.pressures_p90,
            self.recoveries_p90,
            self.clearances_p90,
            self.tackles_p90,
            self.interceptions_p90,
            self.tackles_won_p90,
            # Attacking Threat (5)
            self.npxg_p90,
            self.goals_p90,
            self.xg_per_shot,
            self.shot_accuracy_pct,
            self.goals_minus_xg,
            # Contextual (1)
            float(self.positions_played_count),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2.5: Player Attributes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerAttributes:
    """
    Contextual properties that describe a player without inflating their football ability rating.
    """

    tactical_versatility: float | None = None
    minutes_reliability: str | None = None
    availability_rating: float | None = None
    positional_history: list[str] = field(default_factory=list)
    seasons_indexed: int = 1
    competitions_indexed: int = 1


@dataclass
class RatingPresentation:
    """
    Display-friendly representation of the player's overall rating.
    """

    raw_rating: float
    display_rating: float
    rating_percentile: float
    z_score: float


@dataclass
class ArchetypeProfile:
    """
    Result of deterministic style matching.
    """

    primary_archetype: str
    confidence: float
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    contributing_capabilities: list[str] = field(default_factory=list)


@dataclass
class SystemCompatibilityContext:
    """
    Decomposed deterministic reasoning for tactical fit.
    """

    capability_alignment: float
    tactical_identity_preservation: float
    dependency_relief: float
    contextual_trade_offs: float
    availability_impact: float
    overall_compatibility: float


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Capability Scores
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SupportingMetric:
    """
    Structured evidence proving exactly how a capability score was derived.
    """

    metric_name: str
    raw_value: float
    percentile: float
    contribution_weight: float
    explanation: str


@dataclass
class CapabilityScore:
    """
    A single capability score with supporting evidence.

    score: 0–100, higher is better (always)
    confidence: 0–1, based on sample size and data completeness
    evidence: List of SupportingMetric for deterministic traceability
    """

    capability: str
    score: float
    confidence: float
    evidence: list[SupportingMetric] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 100.0):
            raise ValueError(f"Capability score must be 0–100, got {self.score}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be 0–1, got {self.confidence}")


@dataclass
class CapabilityProfile:
    """
    Complete capability profile for a player.
    The primary output of the Athena Intelligence Framework.

    All 8 capabilities must be present. None may be skipped.
    """

    player_id: int
    player_name: str
    season: str
    competition: str
    position_group: str
    secondary_position_group: str | None = None
    position_confidence: float = 1.0
    minutes_played: float | None = None
    profile_type: ProfileType = ProfileType.COMPETITION

    # The 6 capabilities
    ball_progression: CapabilityScore | None = None
    chance_creation: CapabilityScore | None = None
    ball_security: CapabilityScore | None = None
    press_resistance: CapabilityScore | None = None
    defensive_activity: CapabilityScore | None = None
    attacking_threat: CapabilityScore | None = None

    overall_rating: float | None = None

    def as_radar_dict(self) -> dict[str, float]:
        """
        Returns a canonical dictionary of capabilities formatted for visualization.
        """
        return {
            "Ball Progression": self.ball_progression.score
            if self.ball_progression
            else 0.0,
            "Chance Creation": self.chance_creation.score
            if self.chance_creation
            else 0.0,
            "Ball Security": self.ball_security.score if self.ball_security else 0.0,
            "Press Resistance": self.press_resistance.score
            if self.press_resistance
            else 0.0,
            "Defensive Activity": self.defensive_activity.score
            if self.defensive_activity
            else 0.0,
            "Attacking Threat": self.attacking_threat.score
            if self.attacking_threat
            else 0.0,
        }

    def overall_confidence(self) -> float:
        """Returns the minimum confidence across all instantiated capabilities."""
        from shared.config.capabilities import CORE_CAPABILITIES

        confs = [
            getattr(self, cap).confidence
            for cap in CORE_CAPABILITIES
            if getattr(self, cap) is not None
        ]
        return min(confs) if confs else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Layer 4: Player Intelligence
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerProfile:
    """
    Complete player intelligence profile.

    Combines:
      - Biographical metadata
      - Feature vector (statistics)
      - Capability profile
      - Archetype label

    This is the primary object consumed by the UI and Decision Engine.
    """

    player_id: int
    player_name: str
    position_group: str
    team_name: str
    competition: str
    season: str
    secondary_position_group: str | None = None
    position_confidence: float = 1.0
    profile_type: ProfileType = ProfileType.SEASON
    birth_date: str | None = None
    minutes_played: float | None = None

    capability_profile: CapabilityProfile | None = None
    feature_vector: PlayerFeatureVector | None = None
    player_attributes: PlayerAttributes | None = None

    @property
    def age_years(self) -> float | None:
        if not self.birth_date:
            return None
        try:
            from datetime import datetime

            # StatsBomb dates are usually YYYY-MM-DD
            bd = datetime.strptime(str(self.birth_date).split(" ")[0], "%Y-%m-%d")
            today = datetime.now()
            return round((today - bd).days / 365.25, 1)
        except Exception:
            return None

    rating_presentation: RatingPresentation | None = None
    archetype_profile: ArchetypeProfile | None = None

    @property
    def display_archetype(self) -> str:
        """Canonical accessor for UI to safely get the primary archetype."""
        if self.archetype_profile:
            return self.archetype_profile.primary_archetype
        return "Unknown"

    @property
    def archetype_description(self) -> str:
        """Canonical accessor for UI to get archetype description."""
        # Optional: retrieve from a config/mapping if we have one.
        # For now, it returns a placeholder or empty string.
        if (
            self.archetype_profile
            and self.archetype_profile.primary_archetype != "Unknown"
        ):
            return f"Specialist acting as a {self.archetype_profile.primary_archetype}."
        return "Not enough data to categorize playing style."

    # Generated decision signals
    decision_signals: list[str] = field(default_factory=list)

    def as_radar_dict(self) -> dict[str, float]:
        """Returns the canonical visualization radar dictionary for the player."""
        if self.capability_profile:
            return self.capability_profile.as_radar_dict()
        return {
            "Ball Progression": 0.0,
            "Chance Creation": 0.0,
            "Ball Security": 0.0,
            "Press Resistance": 0.0,
            "Defensive Activity": 0.0,
            "Attacking Threat": 0.0,
        }

    # Similarity results (populated on demand)
    similar_players: list[dict[str, Any]] = field(default_factory=list)

    def is_analytically_sufficient(self) -> bool:
        """True if player has enough minutes for reliable analytics."""
        from shared.constants import MIN_MINUTES_THRESHOLD

        return self.minutes_played >= MIN_MINUTES_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# Layer 5.5: Collective Intelligence (Phase 15)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CollectiveIdentity:
    """
    Deterministically derived tactical identity of a team.
    """

    primary_identity: str
    secondary_identity: str | None = None
    emergent_traits: list[str] = field(default_factory=list)


@dataclass
class CapabilityConcentration:
    """
    Measures the distribution (or over-centralization) of a capability across a squad using HHI.
    """

    capability_name: str
    hhi_score: float
    is_over_centralized: bool
    top_contributors: list[tuple[str, float]] = field(
        default_factory=list
    )  # (player_name, percentage)


@dataclass
class SystemFragility:
    """
    Deterministic measurement of capability collapse when a player is removed.
    """

    player_name: str
    player_id: int
    replaceability_index: float
    structural_deficit: float
    capability_loss: dict[str, float] = field(default_factory=dict)


@dataclass
class CapabilityBottleneck:
    """
    Identifies where upstream capabilities fail to convert into downstream value.
    """

    upstream_capability: str
    downstream_capability: str
    severity: float
    diagnosis: str


@dataclass
class CollectiveProfile:
    """
    The output of the Collective Intelligence Engine.
    Explains the structural realities, fragilities, and identity of a team.
    """

    team_id: int
    team_name: str
    competition: str
    season: str
    squad_size: int = 0
    avg_age: float | None = None

    identity: CollectiveIdentity | None = None
    concentration: list[CapabilityConcentration] = field(default_factory=list)
    fragility_map: list[SystemFragility] = field(default_factory=list)
    bottlenecks: list[CapabilityBottleneck] = field(default_factory=list)

    avg_capabilities: dict[str, float] = field(default_factory=dict)

    def as_radar_dict(self) -> dict[str, float]:
        """Returns the canonical visualization radar dictionary for the team."""
        from shared.config.capabilities import CORE_CAPABILITIES

        result = {}
        for cap in CORE_CAPABILITIES:
            name = cap.replace("_", " ").title()
            result[name] = self.avg_capabilities.get(cap, 0.0)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Layer 6: Decision Intelligence
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RecruitmentCriteria:
    """
    Strongly typed criteria for finding and ranking recruitment candidates.
    """

    position: str | None = None
    min_minutes: float = 0.0
    tactical_style: str | None = None
    required_capabilities: dict[str, float] = field(default_factory=dict)
    preferred_capabilities: dict[str, float] = field(default_factory=dict)
    excluded_player_ids: set[int] = field(default_factory=set)
    max_results: int = 10


@dataclass
class CapabilityExplanation:
    """
    Explains a capability using layered contributing factors.
    e.g. Ball Progression -> Progressive Passing (98th percentile), etc.
    """

    capability_name: str
    score: float
    drivers: dict[str, str] = field(
        default_factory=dict
    )  # e.g. {"Progressive Passes": "98th percentile"}


@dataclass
class PlayerDecisionCard:
    """
    Deterministic football reasoning for a player.
    """

    player: PlayerProfile
    primary_role: str
    elite_traits: list[CapabilityExplanation] = field(default_factory=list)
    weak_areas: list[CapabilityExplanation] = field(default_factory=list)
    playing_style: str | None = None
    player_attributes: PlayerAttributes | None = None


@dataclass
class DependencyAnalysis:
    """
    Exact percentage contribution per player for a capability.
    """

    capability_name: str
    contributions: dict[str, float] = field(
        default_factory=dict
    )  # e.g., {"Rodri": 32.5}
    key_players: list[str] = field(default_factory=list)


@dataclass
class CounterfactualResult:
    """
    Measures capability delta when removing/adding a player.
    """

    capability_name: str
    original_score: float
    new_score: float

    @property
    def delta(self) -> float:
        return round(self.new_score - self.original_score, 1)

    @property
    def retained_pct(self) -> float:
        if self.original_score == 0:
            return 100.0
        return round((self.new_score / self.original_score) * 100, 1)


@dataclass
class TeamDecisionCard:
    """
    Deterministic football reasoning for a team.
    """

    team: CollectiveProfile
    tactical_identity: str
    biggest_strengths: list[CapabilityExplanation] = field(default_factory=list)
    biggest_weaknesses: list[CapabilityExplanation] = field(default_factory=list)
    dependency_analysis: dict[str, DependencyAnalysis] = field(default_factory=dict)
    gap_analysis: dict[str, float] = field(
        default_factory=dict
    )  # Capability vs Elite Benchmark gap


@dataclass
class RecruitmentCandidate:
    """
    A ranked recruitment candidate explaining WHY they are recommended (Capability Restoration).
    """

    player: PlayerProfile
    fit_score: float = 0.0
    rank: int = 0
    system_compatibility: SystemCompatibilityContext | None = None
    player_attributes: PlayerAttributes | None = None

    # Capability Restoration (Counterfactual impact)
    restoration: dict[str, str] = field(
        default_factory=dict
    )  # e.g. {"Ball Progression": "83%"}
    trade_offs_positive: list[str] = field(default_factory=list)
    trade_offs_negative: list[str] = field(default_factory=list)

    overall_team_impact: str = ""
    confidence: str = "medium"
    explanation_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """
    Side-by-side comparison of two or more players explaining WHY they differ.
    """

    players: list[PlayerProfile]

    shared_strengths: list[str] = field(default_factory=list)
    key_differences: list[str] = field(default_factory=list)
    capability_comparison: dict[str, dict[str, float]] = field(default_factory=dict)
    recommendation_summary: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Layer 7: AI / Explanation Output
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScoutingReport:
    """
    AI-generated scouting report for a player.

    The LLM produces this only after receiving a structured context
    containing capability scores, feature vectors, and evidence.
    The report must reference analytical evidence — never invent statistics.
    """

    player_name: str
    season: str
    report_type: str  # "player" | "team" | "recruitment" | "comparison"

    # Structured sections
    overview: str = ""
    strengths: str = ""
    weaknesses: str = ""
    recommendation: str = ""
    risks: str = ""

    # The structured context injected into the prompt (for auditability)
    analytical_context: dict[str, Any] = field(default_factory=dict)

    # Confidence in the report (derived from data quality)
    confidence_level: str = "medium"  # "low" | "medium" | "high"


# ─────────────────────────────────────────────────────────────────────────────
# Validation utilities
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """
    Result of a data validation check.
    """

    dataset: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        True if there are no invalid rows AND no errors.

        Checking invalid_rows alone is insufficient: a file-not-found error
        sets invalid_rows=0 (there were no rows to invalidate) but the result
        is definitely not valid.
        """
        return self.invalid_rows == 0 and len(self.errors) == 0

    @property
    def validity_pct(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return round(self.valid_rows / self.total_rows * 100, 2)
