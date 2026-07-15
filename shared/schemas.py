"""
shared/schemas.py — Athena data schemas and typed dataclasses

These are the structured data contracts between every layer of the AIF pipeline.

Layer communication flow:
  ETL → PlayerRaw
  Analytics Engine → PlayerFeatureVector
  AIF / Capability Engine → CapabilityProfile
  Intelligence Layer → PlayerProfile, TeamProfile
  Decision Engine → RecruitmentCandidate, ComparisonResult
  AI Layer → ScoutingReport

No layer should access another layer's internal data structures directly.
Always communicate through these schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    minutes_played: float
    matches_played: int

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

    # Defensive Activity (3)
    pressures_p90: float = 0.0
    recoveries_p90: float = 0.0
    clearances_p90: float = 0.0

    # Attacking Threat (5)
    npxg_p90: float = 0.0
    goals_p90: float = 0.0
    xg_per_shot: float = 0.0
    shot_accuracy_pct: float = 0.0
    goals_minus_xg: float = 0.0

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
            # Defensive Activity (3)
            self.pressures_p90,
            self.recoveries_p90,
            self.clearances_p90,
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
# Layer 3: Capability Scores
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CapabilityScore:
    """
    A single capability score with supporting evidence.

    score: 0–100, higher is better (always)
    confidence: 0–1, based on sample size and data completeness
    evidence: dict of metric_name → raw_value for traceability
    """

    capability: str
    score: float
    confidence: float
    evidence: dict[str, float] = field(default_factory=dict)

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
    minutes_played: float

    # The 8 capabilities
    ball_progression: CapabilityScore | None = None
    chance_creation: CapabilityScore | None = None
    ball_security: CapabilityScore | None = None
    press_resistance: CapabilityScore | None = None
    defensive_activity: CapabilityScore | None = None
    attacking_threat: CapabilityScore | None = None
    physical_availability: CapabilityScore | None = None
    tactical_versatility: CapabilityScore | None = None

    def as_radar_dict(self) -> dict[str, float]:
        """Return capability scores suitable for radar chart rendering."""
        return {
            "Ball Progression":     self.ball_progression.score if self.ball_progression else 0.0,
            "Chance Creation":      self.chance_creation.score if self.chance_creation else 0.0,
            "Ball Security":        self.ball_security.score if self.ball_security else 0.0,
            "Press Resistance":     self.press_resistance.score if self.press_resistance else 0.0,
            "Defensive Activity":   self.defensive_activity.score if self.defensive_activity else 0.0,
            "Attacking Threat":     self.attacking_threat.score if self.attacking_threat else 0.0,
            "Physical Availability": self.physical_availability.score if self.physical_availability else 0.0,
            "Tactical Versatility": self.tactical_versatility.score if self.tactical_versatility else 0.0,
        }

    def overall_confidence(self) -> float:
        """Mean confidence across all populated capabilities."""
        scores = [
            cap.confidence
            for cap in [
                self.ball_progression, self.chance_creation, self.ball_security,
                self.press_resistance, self.defensive_activity, self.attacking_threat,
                self.physical_availability, self.tactical_versatility,
            ]
            if cap is not None
        ]
        return sum(scores) / len(scores) if scores else 0.0


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
    age_years: float
    minutes_played: float

    capability_profile: CapabilityProfile | None = None
    feature_vector: PlayerFeatureVector | None = None

    # Computed by rule-based archetype engine
    archetype: str | None = None
    archetype_description: str | None = None

    # Generated decision signals
    decision_signals: list[str] = field(default_factory=list)

    # Similarity results (populated on demand)
    similar_players: list[dict[str, Any]] = field(default_factory=list)

    def is_analytically_sufficient(self) -> bool:
        """True if player has enough minutes for reliable analytics."""
        from shared.constants import MIN_MINUTES_THRESHOLD
        return self.minutes_played >= MIN_MINUTES_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# Layer 5: Team Intelligence
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TeamProfile:
    """
    Team intelligence profile.

    Aggregates player capabilities into collective tactical characteristics.
    """

    team_id: int
    team_name: str
    competition: str
    season: str
    squad_size: int

    # Average capability scores across squad
    avg_ball_progression: float = 0.0
    avg_chance_creation: float = 0.0
    avg_ball_security: float = 0.0
    avg_press_resistance: float = 0.0
    avg_defensive_activity: float = 0.0
    avg_attacking_threat: float = 0.0
    avg_physical_availability: float = 0.0
    avg_tactical_versatility: float = 0.0

    # Squad composition
    avg_age: float = 0.0
    position_distribution: dict[str, int] = field(default_factory=dict)

    # Identified tactical identity (derived from capability profile)
    style_label: str | None = None
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    def as_radar_dict(self) -> dict[str, float]:
        """Return average capability scores for radar chart rendering."""
        return {
            "Ball Progression":      self.avg_ball_progression,
            "Chance Creation":       self.avg_chance_creation,
            "Ball Security":         self.avg_ball_security,
            "Press Resistance":      self.avg_press_resistance,
            "Defensive Activity":    self.avg_defensive_activity,
            "Attacking Threat":      self.avg_attacking_threat,
            "Physical Availability": self.avg_physical_availability,
            "Tactical Versatility":  self.avg_tactical_versatility,
        }


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
class RecruitmentCandidate:
    """
    A ranked recruitment candidate produced by the Decision Engine.

    Self-contained for the AI Explanation Layer.
    """
    player: PlayerProfile
    fit_score: float = 0.0
    rank: int = 0

    # Explicit inclusions for explanation
    decision_signals: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    trade_offs: list[str] = field(default_factory=list)
    confidence: str = "medium"
    
    # Traceability context
    explanation_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """
    Side-by-side comparison of two or more players.
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
