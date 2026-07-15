# Athena Football Intelligence Engine
## Design Specification — Phase 3

**Version:** 1.0  
**Status:** Design — Pending Architectural Review  
**Scope:** Intelligence framework design only. No implementation.

---

## Table of Contents

1. [Purpose and Context](#1-purpose-and-context)
2. [System Position](#2-system-position)
3. [Intelligence Framework Overview](#3-intelligence-framework-overview)
4. [The Eight Capabilities](#4-the-eight-capabilities)
   - 4.1 [Ball Progression](#41-ball-progression)
   - 4.2 [Chance Creation](#42-chance-creation)
   - 4.3 [Ball Security](#43-ball-security)
   - 4.4 [Press Resistance](#44-press-resistance)
   - 4.5 [Defensive Activity](#45-defensive-activity)
   - 4.6 [Attacking Threat](#46-attacking-threat)
   - 4.7 [Physical Availability](#47-physical-availability)
   - 4.8 [Tactical Versatility](#48-tactical-versatility)
5. [Feature Mapping](#5-feature-mapping)
6. [Player Intelligence Model](#6-player-intelligence-model)
7. [Team Intelligence Model](#7-team-intelligence-model)
8. [Decision Signals](#8-decision-signals)
9. [Explainability Framework](#9-explainability-framework)
10. [Data Constraints and Honest Limitations](#10-data-constraints-and-honest-limitations)
11. [Design Decisions Log](#11-design-decisions-log)

---

## 1. Purpose and Context

The **Football Intelligence Engine (FIE)** is Athena's analytical core. It translates raw football events — passes, shots, carries, dribbles — into interpretable football intelligence that scouts, analysts, and coaches can act on.

Football statistics in their raw form are not football intelligence. A player with 500 passes per season is not necessarily a better passer than one with 200 — context, accuracy, intent, and pressure all matter. A striker with 10 goals may have underperformed their expected output while another with 7 may have outperformed it significantly.

The FIE exists to close this gap: to convert statistics into **capability scores** that respect football context, support cross-player comparison, and remain fully explainable at every step.

### Core Design Principles

**Determinism.** Every capability score is produced by an explicit formula applied to real event data. Given the same inputs, the FIE always produces the same outputs. There is no model, no training data, no latent representation.

**Explainability.** Every score traces back through capabilities → metrics → events. A scout asking "why is this player rated 82 for Ball Progression?" must receive a specific, traceable answer in football terms.

**Position relativity.** A striker's 300 passes per season is evaluated against striker peers, not midfielders. All capability scores are percentile ranks within position group.

**Honest about uncertainty.** Small sample sizes produce low-confidence scores. The FIE documents its confidence alongside every score rather than hiding it.

**StatsBomb-grounded.** Every metric is derivable from StatsBomb Open Data event taxonomy. No metric depends on data that is not available.

---

## 2. System Position

```
┌─────────────────────────────────┐
│      Analytics Warehouse        │  vw_player_summary, vw_team_summary
│         (DuckDB / SQL)          │  vw_player_percentiles, vw_match_summary
└────────────────┬────────────────┘
                 │  structured DataFrames
                 ▼
┌─────────────────────────────────┐
│   Football Intelligence Engine  │  ← THIS DOCUMENT
│                                 │
│  • Capability computation       │
│  • Position-relative scoring    │
│  • Confidence weighting         │
│  • Player / Team profile gen.   │
│  • Decision signal derivation   │
└────────────────┬────────────────┘
                 │  CapabilityProfile, PlayerProfile, TeamProfile
                 ▼
┌─────────────────────────────────┐
│      Decision Intelligence      │  Recruitment ranking, comparison
└────────────────┬────────────────┘
                 │  RecruitmentCandidate, ComparisonResult
                 ▼
┌─────────────────────────────────┐
│       AI Explanation Layer      │  ScoutingReport, narrative generation
└─────────────────────────────────┘
```

The FIE is a **pure transformation layer**. It receives DataFrames from the warehouse and produces typed capability profiles. It does not read from raw files, does not write to the database, and does not communicate with the AI layer directly.

---

## 3. Intelligence Framework Overview

### Domains of Intelligence

The eight capabilities are grouped into five conceptual domains. These domains improve explainability and UI organization by providing a higher-level framework for understanding a player's profile.

* **Technical Intelligence**: Ball Progression, Ball Security, Press Resistance
* **Creative Intelligence**: Chance Creation, Attacking Threat
* **Defensive Intelligence**: Defensive Activity
* **Availability Intelligence**: Physical Availability
* **Adaptability Intelligence**: Tactical Versatility

### The Capability System

Athena evaluates every outfield player across eight capabilities. Each capability represents a football-meaningful dimension of performance, is scored 0–100 relative to position peers, and is composed of 2–5 supporting metrics with documented weights.

| # | Capability | Football Question Answered |
|---|---|---|
| 1 | **Ball Progression** | How effectively does this player advance play? |
| 2 | **Chance Creation** | How dangerous are this player's contributions in the final third? |
| 3 | **Ball Security** | How well does this player protect possession? |
| 4 | **Press Resistance** | How does this player perform when under defensive pressure? |
| 5 | **Defensive Activity** | How active is this player in defensive phases? |
| 6 | **Attacking Threat** | How directly dangerous is this player as a goal-scoring threat? |
| 7 | **Physical Availability** | How consistently available is this player? |
| 8 | **Tactical Versatility** | How adaptable is this player across roles and situations? |

### Scoring Architecture

```
Raw Events (StatsBomb)
        │
        ▼
Derived Statistics (vw_player_summary)
  pass_accuracy_pct, xg_p90, progressive_passes_p90, ...
        │
        ▼
Percentile Ranks (vw_player_percentiles)
  xg_p90_pct_in_position, pass_acc_pct_in_position, ...
        │
        ▼
Capability Score (FIE computation)
  Σ(metric_percentile × metric_weight), 0–100
        │
        ▼
CapabilityProfile (typed dataclass)
  8 scores + confidence ratings + decision signals
        │
        ▼
PlayerProfile / TeamProfile
```

### Capability Score Formula

For each capability **C** composed of metrics **m₁...mₙ** with weights **w₁...wₙ**:

```
C_score = Σ(percentile_rank(mᵢ, position_group) × wᵢ)
```

Where `percentile_rank` returns a value in [0, 100], and `Σwᵢ = 1.0`.

The resulting score is already on a 0–100 scale and requires no further normalization.

---

## 4. The Eight Capabilities

---

### 4.1 Ball Progression

#### Scout Question
*Can this player reliably move the ball into dangerous areas?*

#### Purpose
Measure a player's ability to advance the ball purposefully from less dangerous to more dangerous areas of the pitch — whether by carrying, passing forward, or driving through pressure.

#### Football Interpretation
Ball progression is one of the most valued skills in modern football. Teams that progress effectively reach the final third more often, create more chances, and expose defensive shape. A high-scoring Ball Progressor is a player who regularly advances play — through line-breaking carries, switches of play, or splitting passes through compact defensive blocks.

This is distinct from raw passing volume. A player completing 100 backward passes contributes less to progression than one completing 30 forward line-breaking passes.

#### Supporting StatsBomb Metrics

| Metric | Source | Role in Capability |
|---|---|---|
| Progressive passes per 90 | `progressive_passes_p90` | Primary volume indicator |
| Progressive carries per 90 | `progressive_carries_p90` | Ball-carrying advance |
| Total carry distance per 90 | `total_carry_distance_m / (minutes_played / 90)` | Carries into space |
| Switches per 90 | `switches / (minutes_played / 90)` | Width exploitation |

**Definition of "Progressive" (Athena v1.0):**
- **Progressive pass:** `pass_end_x > location_x AND pass_length >= 10m AND pass_end_x > 60` — the ball moves at least 10m forward and reaches the middle or attacking third.
- **Progressive carry:** `carry_end_x > location_x AND (carry_end_x - location_x) >= 10m` — the player carries the ball at least 10m forward.

#### Weighting Methodology

| Metric | Weight | Justification |
|---|---|---|
| Progressive passes per 90 | 0.35 | The most reliable repeatable progression action |
| Progressive carries per 90 | 0.35 | Carries are higher-risk, higher-reward — equally weighted |
| Carry distance per 90 | 0.15 | Total distance covered supplements frequency |
| Switches per 90 | 0.15 | Field-switching is a key progression mechanism |

#### Normalization Strategy
All metrics are expressed per 90 minutes before computing percentile rank within position group. This ensures a central midfielder with 80 minutes in 15 matches is fairly compared to one with 90 minutes in 20 matches.

Position groups: Forward / Midfielder / Defender / Goalkeeper (Goalkeepers excluded from this capability).

#### Confidence Considerations
- **High confidence:** ≥ 10 matches. The per-90 rate stabilizes.
- **Medium confidence:** 5–9 matches. Score shown with a confidence flag.
- **Low confidence:** < 5 matches. Score is computed but surfaced with a warning.

Confidence modifier: `confidence_factor = min(1.0, matches_played / 10)`. Applied to display, not to the score itself.

#### Limitations
- "Progressive" is defined by spatial coordinates, not football intent. A sideways pass that happens to advance 10m is counted.
- Carry distance is computed as Euclidean displacement, not true path length.
- Long-range switches may count as "progressive" even when they are tactically defensive.
- No data on off-ball movement or runs that create progressive passing lanes.

#### Recruitment and Evaluation Value
Ball Progression is the primary filter for **deep-lying playmakers**, **box-to-box midfielders**, and **progressive fullbacks**. A high score here combined with high Chance Creation identifies players who progress *and* create — the most valued profile in possession-dominant systems.

---

### 4.2 Chance Creation

#### Scout Question
*Can this player consistently create opportunities for teammates?*

#### Purpose
Measure a player's ability to create goalscoring opportunities for teammates through the quality and frequency of creative actions in and around the final third.

#### Football Interpretation
Not all passes into the final third are equal. A chip over the defensive line to a striker's feet is worth far more than a sideways pass into midfield. Chance Creation measures the *quality* of opportunities created, not just their frequency.

This capability distinguishes the player who makes things happen in dangerous areas — the one defenders most need to track — from the player who passes a lot but rarely unlocks defences.

#### Supporting StatsBomb Metrics

| Metric | Source | Role in Capability |
|---|---|---|
| Shot assists per 90 | `shot_assists / (minutes_played / 90)` | Directly created shot attempts |
| Goal assists per 90 | `goal_assists_p90` | Converted creative actions |
| Through balls per 90 | `through_balls / (minutes_played / 90)` | Line-breaking intent |
| Crosses per 90 | `crosses / (minutes_played / 90)` | Wide creative volume |

> **Note on xA (Expected Assists):** For any pass that results in a shot, the xG of that shot is attributed to the passer as xA. This is the highest-quality measure of creative output available in StatsBomb data. It will be computed in Phase 3 via event linkage (pass event id → subsequent shot event).

#### Weighting Methodology

| Metric | Weight (Central) | Weight (Wide) | Justification |
|---|---|---|---|
| Shot assists per 90 | 0.40 | 0.35 | Volume of direct chance creation |
| Goal assists per 90 | 0.30 | 0.25 | Executed creative output |
| Through balls per 90 | 0.20 | 0.15 | Intent to unlock defensive lines |
| Crosses per 90 | 0.10 | 0.25 | Elevated for wide positions |

Position group modulation: the cross weight is elevated to 0.25 for wide positions (Right Wing, Left Wing, Right Back, Left Back) and reduced to 0.10 for central positions, with the difference redistributed to shot_assists.

#### Normalization Strategy
Per 90 normalization, then percentile rank within position group. A winger at the 75th percentile for crosses is compared against other wingers, not midfielders.

#### Confidence Considerations
Shot assists stabilize faster (per 5–7 matches) than goal assists (per 10+ matches). In low-match samples, the score is weighted toward shot assists.

#### Limitations
- Crosses that are blocked or miscontrolled count equally to those that create clear chances.
- A player in a system that never crosses may score lower despite being tactically excellent.
- Assistless seasons do not mean uncreative players — finishing quality of teammates affects goal assist counts.
- xA implementation deferred to Phase 3 (requires event linkage not yet in ETL).

#### Recruitment and Evaluation Value
Chance Creation is the primary filter for **attacking midfielders**, **wide forwards**, and **second strikers**. Combined with Attacking Threat it identifies genuine dual-threat forwards. Used in isolation it finds playmakers who create for others rather than shooting themselves.

---

### 4.3 Ball Security

#### Scout Question
*Can this player retain possession under pressure?*

#### Purpose
Measure how reliably a player protects possession — both under pressure and in open play — through accurate passing, successful dribbling, and disciplined decision-making.

#### Football Interpretation
Possession is not just a statistic — it is territory. Teams that lose the ball in poor areas concede more goals. Ball Security captures the player who can be trusted on the ball: who completes their passes, wins their dribbles, and does not give the ball away in dangerous positions.

This is particularly important for **central defenders building from the back**, **defensive midfielders in transition**, and any player asked to receive under a heavy press.

#### Supporting StatsBomb Metrics

| Metric | Source | Role in Capability |
|---|---|---|
| Pass accuracy (%) | `pass_accuracy_pct` | Primary possession metric |
| Dribble success rate (%) | `dribble_success_pct` | 1v1 ball retention |
| Total passes per 90 | `passes_p90` | Volume baseline — context for accuracy |
| Average pass length (m) | `avg_pass_length_m` | Risk proxy — longer passes are inherently harder |

#### Weighting Methodology

| Metric | Weight | Justification |
|---|---|---|
| Pass accuracy (%) | 0.50 | The clearest direct measure of ball security |
| Dribble success rate (%) | 0.25 | Retaining ball in tight situations |
| Passes per 90 | 0.15 | High volume with high accuracy = elite; adjusts for context |
| Avg pass length | 0.10 | Risk-adjusted difficulty bonus for longer completion |

> The avg pass length weight is a positive adjustment. A player completing 40-yard diagonal passes at 80% accuracy is more impressive than one completing 5-yard passes at the same rate. The adjustment uses the percentile rank of avg pass length as a difficulty modifier.

#### Normalization Strategy
Pass accuracy and dribble success are already ratios (0–100%). These are percentile-ranked within position group. The pass-length difficulty adjustment adds a small positive modifier to players who attempt longer, harder passes successfully.

#### Confidence Considerations
Pass accuracy is one of the most stable per-match metrics — reliable from 4–5 matches onwards. Dribble success requires more volume (at least 10 dribble attempts) to stabilize.

#### Limitations
- Pass accuracy does not distinguish between difficulty levels of passes.
- Short passes to easily-available options inflate accuracy scores.
- Ball loss data (dispossessions, failed controls) would significantly improve this capability but is not directly available without custom event derivation in Phase 3.
- No data on spatial quality of retained possession.

#### Recruitment and Evaluation Value
Ball Security is critical for **defensive midfielders**, **center backs**, and **deep-lying playmakers** — roles where losing possession is immediately costly. It is also used as a **risk-adjustment filter**: high-capability players with low Ball Security may be brilliant but costly in possession-based systems.

---

### 4.4 Press Resistance

#### Scout Question
*Can this player maintain control when pressed aggressively?*

#### Purpose
Measure how effectively a player performs technical actions — passing, carrying, dribbling — when actively pressured by an opponent.

#### Football Interpretation
Modern football is dominated by high pressing. The ability to receive the ball under pressure and emerge with possession is one of the most valuable skills in the contemporary game. This is what separates technically elite players from statistically similar but physically overmatched ones.

StatsBomb uniquely tags events with an `under_pressure` flag — making this the rare football metric that is nearly impossible to derive from traditional statistics but is directly available in event data.

#### Supporting StatsBomb Metrics

| Metric | Derivation | Role |
|---|---|---|
| Actions under pressure per 90 | `events_under_pressure / (minutes_played / 90)` | Exposure to press (volume) |
| Pressure rate | `events_under_pressure / total_events` | How frequently is this player pressured? |
| Pass accuracy (overall proxy) | `pass_accuracy_pct` | Technical execution quality |

> **Phase 3 extension:** The current warehouse stores `events_under_pressure` as a match-level aggregate. Phase 3 will add granular under-pressure breakdowns by event type (passes under pressure accuracy, carries under pressure count, dribbles under pressure success rate), enabling far more precise computation of this capability.

#### Weighting Methodology — Phase 2.2 Proxy

| Metric | Weight | Justification |
|---|---|---|
| Pressure rate (events under pressure %) | 0.40 | High pressure rate = frequently trusted ball receiver |
| Total action quality (pass accuracy) | 0.35 | Best available proxy for technical execution under press |
| Events under pressure per 90 (volume) | 0.25 | Absolute count context |

#### Phase 3 Target Weights

| Metric | Target Weight |
|---|---|
| Press resistance rate (under-pressure success %) | 0.40 |
| Pass accuracy under pressure specifically | 0.35 |
| Carries under pressure per 90 | 0.15 |
| Dribbles under pressure per 90 | 0.10 |

#### Normalization Strategy
The pressure rate (events_under_pressure / total_events) is percentile-ranked within position group. Volume metrics supplement the rate. A minimum threshold of 50 under-pressure events across the sample is recommended for high-confidence scores.

#### Confidence Considerations
Typically met after 8–10 matches for central midfielders. Strikers and wide players may accumulate under-pressure events more slowly due to positional exposure patterns.

#### Limitations
- `under_pressure` is a binary flag. It does not capture the degree of pressure or the number of pressers.
- Positional differences are significant: a deep midfielder may receive 300 under-pressure events; a striker may receive 30. Position-group normalization is essential.
- Success rate under pressure can be inflated by a player who consistently plays the safest available option when pressured.

#### Recruitment and Evaluation Value
Press Resistance is the defining filter for recruiting into **high-pressing leagues and systems**. A technically excellent player with low Press Resistance will struggle in a Bundesliga-style press environment. This capability is also the key differentiator between similar players when recommending for specific tactical contexts.

---

### 4.5 Defensive Activity

#### Scout Question
*How much defensive value does this player contribute?*

#### Purpose
Measure a player's contribution to the team's defensive phase through pressing, recovering loose balls, disrupting opposition build-up, and defensive actions.

#### Football Interpretation
Modern football demands that attacking players defend as well as attack. The high press requires every player to be an active defensive participant. Defensive Activity does not only capture traditional defenders — it identifies the forward who presses relentlessly, the midfielder who wins the ball in dangerous areas, and the winger who tracks back.

#### Supporting StatsBomb Metrics

| Metric | StatsBomb Event Type | Role |
|---|---|---|
| Pressures per 90 | `Pressure` event | Pressing intensity |
| Ball recoveries per 90 | `Ball Recovery` event | Winning loose balls |
| Clearances per 90 | `Clearance` event | Positional defensive clearing |

> **Phase 3 extension:** Pressure success rate — a press leading to a turnover — requires event linkage between a Pressure event and the subsequent possession change. Tackles and interceptions are derivable from `Dribbled Past` and `Ball Recovery` events with additional filtering. These refine the capability materially.

#### Weighting Methodology

| Metric | Default Weight | Defender Weight | Forward Weight |
|---|---|---|---|
| Pressures per 90 | 0.45 | 0.35 | 0.55 |
| Ball recoveries per 90 | 0.35 | 0.35 | 0.35 |
| Clearances per 90 | 0.20 | 0.30 | 0.10 |

Position group modulation ensures that a forward is not penalized for having few clearances, and a defender is not over-credited for pressing volume that their role naturally constrains.

#### Normalization Strategy
All metrics are per-90 normalized, then percentile-ranked within position group. A forward in the top 10% for pressures is an exceptional pressing asset regardless of absolute count relative to midfielders.

#### Confidence Considerations
Pressure events are one of the most reliably tagged event types in StatsBomb data. Ball recoveries can vary by team context — teams that press more generate more recovery opportunities. System-adjustment is a Phase 4 consideration.

#### Limitations
- Defensive quality is notoriously hard to quantify from events alone. A defender who reads the game perfectly and always intercepts before the tackle is needed will score lower than a reactive defender making 5 tackles per game.
- No off-ball defensive positioning data is available.
- System-dependency: a low block produces fewer pressure events than a high press, regardless of individual defensive quality.

#### Recruitment and Evaluation Value
Defensive Activity is the primary signal for **pressing-forward recruitment**, **high-energy midfielders**, and **pressing defenders**. When combined with Ball Progression (high in both = box-to-box midfielder profile), it identifies the complete modern footballer.

---

### 4.6 Attacking Threat

#### Scout Question
*Does this player consistently generate scoring value?*

#### Purpose
Measure a player's direct contribution as a goal-scoring threat — the frequency, quality, and conversion of shots on goal.

#### Football Interpretation
Expected Goals (xG) is the most validated metric in football analytics. It measures the probability of a shot resulting in a goal based on historical shot data, accounting for location, assist type, and game situation. A player consistently scoring above their xG is outperforming their expected output — a marker of genuine finishing quality.

Attacking Threat is the capability most directly correlated with the thing football ultimately cares about: goals.

#### Supporting StatsBomb Metrics

| Metric | Source | Role |
|---|---|---|
| Non-penalty xG per 90 | `npxg_p90` | Shot quality, position-neutral, outlier-resistant |
| Goals per 90 | `goals_p90` | Direct output |
| Shots per 90 | `shots_p90` | Volume of threat |
| Shot accuracy (%) | `shot_accuracy_pct` | Discipline and decision-making |
| Goals minus xG | `goals_minus_xg` | Over/under-performance indicator |
| xG per shot | `xg_per_shot` | Average shot quality — are they getting into good positions? |

> **npxG (Non-Penalty xG):** Penalties are excluded because they are context-dependent and do not reflect open-play attacking quality. StatsBomb tags shot type (`shot_type`), allowing penalty filtering directly from the events table.

#### Weighting Methodology

| Metric | Weight | Justification |
|---|---|---|
| npxG per 90 | 0.35 | The gold standard — position-independent shot quality |
| Goals per 90 | 0.25 | Actual output — what teams pay for |
| xG per shot | 0.20 | Shot selection quality |
| Shot accuracy (%) | 0.15 | On target or wasted — discipline metric |
| Goals minus xG | 0.05 | Finishing bonus only (never a penalty) |

> The goals_minus_xg component is capped at 0 on the downside. A player who underperforms their xG is not penalized twice — their xG score already captures it. The component serves only as a positive differentiator for clinical finishers.

#### Normalization Strategy
xG metrics are inherently position-relative when percentile-ranked within position group. A striker with 0.40 npxG/90 is compared to striker peers, not midfielders.

Small-sample adjustment: in seasons with fewer than 8 matches, the goals_p90 weight drops to 0.10 and npxg_p90 weight rises to 0.40, because goals stabilize more slowly than xG at short sample sizes.

#### Confidence Considerations
xG stabilizes faster than goals at the player level — reliable from 8–10 matches. Goals per 90 requires 15+ matches for most players.

#### Limitations
- StatsBomb xG model is proprietary. Open data xG values are available but the precise model calibration details are not public.
- xG does not account for the player creating their own chance via carry or dribble before shooting.
- Goalkeeper quality affects shot outcomes, distorting goals_minus_xg.
- Players who are "target men" (hold-up play, link-up) may score low here despite high tactical value. This is captured in Chance Creation instead.

#### Recruitment and Evaluation Value
Attacking Threat is the primary filter for **striker recruitment**, **second striker evaluation**, and **any forward position**. It is the most directly monetizable capability — goals win games. Combined with Chance Creation it identifies the complete attacker.

---

### 4.7 Physical Availability

#### Scout Question
*Can this player be relied upon across a season?*

#### Purpose
Measure a player's consistency and reliability in terms of match participation — their ability to stay available, start games, and contribute across a season.

#### Football Interpretation
The best player in the world contributes nothing while injured. Physical availability — the ability to stay on the pitch and participate consistently — is a practical filter that scouts apply before deep performance analysis.

#### Supporting StatsBomb Metrics

| Metric | Derivation | Role |
|---|---|---|
| Matches played | `matches_played` from lineups | Raw participation count |
| Competition coverage rate | `matches_played / total_competition_matches` | Season participation rate |

> **Total competition matches** is derived from the matches table: `COUNT(DISTINCT match_id) WHERE competition_id = X AND season_id = Y`. This gives the total matches played in the dataset for that competition-season, used as the denominator for coverage rate.

#### Weighting Methodology

| Metric | Weight | Justification |
|---|---|---|
| Competition coverage rate | 0.60 | Core — what percentage of matches did the player participate in? |
| Matches played (absolute) | 0.40 | Absolute count — 35 starts in a 38-game season vs 15 |

**Coverage rate formula:**
```
coverage_rate = matches_played / total_matches_in_competition_season
physical_availability_score = (coverage_rate × 100 × 0.60) + (percentile_rank(matches_played) × 0.40)
```

#### Normalization Strategy
Physical Availability uses a blended approach: 60% direct score (coverage_rate × 100 — absolute), 40% percentile rank within position. This preserves the interpretability of the raw coverage rate while adding relative context.

#### Confidence Considerations
In competitions with fewer than 10 matches in the dataset, this score is suppressed from public display and shown only in raw form with an explicit caveat.

#### Limitations
- StatsBomb Open Data is event-based, not squad-list-based. We cannot distinguish injury absence from tactical omission or rotation.
- A player in multiple competitions may have a higher match count but lower coverage within each individual competition.
- This capability is the most data-limited of the eight and should be used as a filter, not a ranking metric.

#### Recruitment and Evaluation Value
Physical Availability functions primarily as a **recruitment risk filter**. A player with excellent other capabilities but low availability is a medical risk. Athena makes this filter explicit and data-driven rather than leaving it as an implicit assumption.

---

### 4.8 Tactical Versatility

#### Scout Question
*Can this player perform multiple tactical roles?*

#### Purpose
Measure the breadth of a player's functional contribution across football contexts — their ability to contribute effectively in multiple positions, across different phases of play, and in varied tactical situations.

#### Football Interpretation
Squad planning increasingly rewards versatile players. A player who can operate at right back and right midfield gives a manager flexibility. A midfielder who contributes in both build-up and pressing phases is more valuable than a specialist. Tactical Versatility is not about being average at everything — it is about being effective across contexts.

#### Supporting StatsBomb Metrics and Derived Dimensions

**Dimension 1 — Positional Breadth:**  
`COUNT(DISTINCT starting_position)` from the lineups table, filtered to positions with at least 3 appearances (to exclude tactical experiments).

Stepped scale: 1 position = 0, 2 positions = 40, 3 positions = 70, 4+ positions = 100.

**Dimension 2 — Capability Profile Breadth:**

```
capability_breadth = 100 × (1 - std_dev(all_8_capability_scores) / 50)
```

A player with all capabilities at 50 has breadth = 100 (perfectly even profile).  
A player with one capability at 100 and all others at 0 has breadth = 0 (extreme specialist).  
A player with 6 capabilities above 70 and 2 below 40 has breadth ≈ 78.

**Dimension 3 — Phase Contribution Balance:**

```
attack_score = weighted_mean(Ball Progression × 0.35, Chance Creation × 0.35, Attacking Threat × 0.30)
defense_score = weighted_mean(Defensive Activity × 0.60, Press Resistance × 0.40)
phase_balance = (min(attack_score, defense_score) / max(attack_score, defense_score)) × 100
```

A player equally strong in both phases scores 100. A pure specialist scores toward 0.

#### Weighting Methodology

| Dimension | Weight | Justification |
|---|---|---|
| Capability profile breadth | 0.40 | Most data-rich, most stable dimension |
| Phase contribution balance | 0.35 | Two-way contribution is the core of versatility |
| Positional breadth | 0.25 | Direct multi-role evidence — sparse in short samples |

#### Normalization Strategy
Each dimension produces a 0–100 value. The capability breadth and phase balance dimensions are computed directly; positional breadth uses the stepped scale. The weighted sum of all three dimensions is the final score.

In low-match samples (fewer than 8 matches), the positional breadth weight drops to 0.10 and capability profile breadth rises to 0.55, because positional variety is unlikely to manifest in short windows.

#### Confidence Considerations
Positional breadth requires multiple distinct position appearances. Capability profile breadth is available from any sample where the other 7 capabilities are computed, making it the most reliable Versatility dimension.

#### Limitations
- "Playing in multiple positions" is based on lineup assignments, which vary in granularity in the StatsBomb taxonomy (e.g., "Right Center Back" vs "Right Back" could be the same player covering for injury).
- A player who plays two positions badly is not tactically versatile in any useful sense. The minimum-appearance threshold (3) partially mitigates this.
- Phase balance is a structural artifact of position: defenders will always be more defensive; forwards more attacking. Position-group normalization of the phase balance dimension is applied to account for this.

#### Recruitment and Evaluation Value
Tactical Versatility is critical for **squad depth recruitment** (one player covering multiple positions) and **system-change adaptation** (a new manager changing tactical shape). It is also a long-term development signal: young players with high versatility have greater adaptation potential across careers.

---

## 5. Feature Mapping

### Complete Data Lineage: Events to Capability Scores

| Capability | Raw Event Type(s) | Derived Statistic | Normalized Metric | Score |
|---|---|---|---|---|
| **Ball Progression** | `Pass`, `Carry` | `progressive_passes`, `progressive_carries`, `carry_distance_m` | `prog_passes_p90_pct_in_pos`, `prog_carries_p90_pct_in_pos` | Weighted sum → 0–100 |
| **Chance Creation** | `Pass` | `shot_assists`, `goal_assists`, `through_balls`, `crosses` | `shot_assists_p90_pct`, `goal_assists_p90_pct` | Weighted sum → 0–100 |
| **Ball Security** | `Pass`, `Dribble` | `pass_accuracy_pct`, `dribble_success_pct`, `avg_pass_length_m` | `pass_acc_pct_in_position`, `dribble_pct_in_position` | Weighted sum → 0–100 |
| **Press Resistance** | All (under_pressure=True) | `events_under_pressure`, `pressure_pct` | `pressure_pct` percentile rank | Weighted sum → 0–100 |
| **Defensive Activity** | `Pressure`, `Ball Recovery`, `Clearance` | `pressures_p90`, `recoveries_p90`, `clearances_p90` | percentile ranks per metric | Weighted sum → 0–100 |
| **Attacking Threat** | `Shot` | `xg_total`, `goals`, `shots_on_target`, `xg_per_shot` | `xg_p90_pct_in_position`, `goals_p90_pct_overall` | Weighted sum → 0–100 |
| **Physical Availability** | `lineups` + `matches` | `matches_played`, `coverage_rate` | `coverage_rate × 100` (60%) + percentile rank (40%) | Blended → 0–100 |
| **Tactical Versatility** | All events + `lineups` | `positions_played`, capability profile, phase balance | stepped scale + breadth score | Weighted sum → 0–100 |

### Warehouse View Dependency Map

```
vw_player_summary
    → Ball Progression  (progressive_passes_p90, progressive_carries_p90, carry_distance)
    → Chance Creation   (shot_assists, goal_assists, through_balls, crosses)
    → Ball Security     (pass_accuracy_pct, dribble_success_pct, avg_pass_length_m)
    → Attacking Threat  (xg_total, npxg_total, goals, shots_on_target, xg_per_shot)
    → Physical Avail.   (matches_played, minutes_played)

vw_player_percentiles
    → All 8 capabilities (provides percentile_rank values for each metric)

vw_match_summary
    → Physical Availability (total match count for coverage rate denominator)

lineups (base table)
    → Tactical Versatility  (positional breadth: COUNT DISTINCT starting_position)

events (base table, Phase 3 extensions)
    → Press Resistance      (granular under_pressure filtering by event type)
    → Defensive Activity    (Pressure, Ball Recovery, Clearance event counts)
    → Chance Creation       (shot-to-assist linkage for xA)
```

### Events Required in Phase 3 ETL

| Event Type | Phase 3 Action | Capability Benefit |
|---|---|---|
| `Pressure` | Aggregate count per player per match | Defensive Activity (primary metric) |
| `Ball Recovery` | Aggregate count per player per match | Defensive Activity |
| `Clearance` | Aggregate count per player per match | Defensive Activity |
| Under-pressure breakdown by event type | Granular filtering in normalize.py | Press Resistance (refined from proxy) |
| Shot → Assist event linkage | Pass-to-shot join in pipeline | Chance Creation (xA computation) |
| `Substitution` timing | Parse minute + player_id | Physical Availability (exact minutes) |
| `Miscontrol`, `Dispossessed` | Count per player per match | Ball Security (ball loss data) |

---

## 6. Player Intelligence Model

### 6.1 Player Profile Structure

```python
@dataclass
class CapabilityProfile:
    """Eight capability scores for one player in one competition-season."""
    # Identity
    player_id:             int
    player_name:           str
    player_nickname:       str | None
    team_name:             str
    competition_name:      str
    season_name:           str
    position_name:         str    # primary position from vw_player_summary

    # Sample info
    matches_played:        int
    minutes_played:        int

    # The eight capabilities (0–100, position-relative percentile)
    ball_progression:      float
    chance_creation:       float
    ball_security:         float
    press_resistance:      float
    defensive_activity:    float
    attacking_threat:      float
    physical_availability: float
    tactical_versatility:  float

    # Confidence per capability
    confidence: dict[str, str]    # capability_name → "high" | "medium" | "low"

    # Derived fields
    capability_profile_score: float  # position-weighted mean (see 6.2)
    role_label:            str    # see Role Interpretation (6.5)
    decision_signals:      list[str]  # see Section 8


@dataclass
class PlayerProfile:
    """Complete player intelligence package — ready for UI and AI layer."""
    capability_profile:   CapabilityProfile
    strengths:            list[str]         # capabilities scoring >= 75
    development_areas:    list[str]         # capabilities scoring <= 25
    characteristics:      list[str]         # capabilities 26–74
    radar_data:           dict[str, float]  # {capability_name: score} for radar chart
    key_stats:            dict[str, float]  # top 5 supporting metrics for display
    peer_comparison:      pd.DataFrame      # top-10 most similar players
    percentile_summary:   dict[str, float]  # percentile context for key metrics
```

### 6.2 Capability Profile (Aggregate)

The capability profile score is a **position-adjusted weighted mean** of all eight capability scores. Weights reflect which capabilities matter most for each position group.

| Position Group | Ball Prog | Chance Cre | Ball Sec | Press Res | Def Act | Att Threat | Phys Avail | Tact Vers |
|---|---|---|---|---|---|---|---|---|
| **Forward** | 0.10 | 0.20 | 0.08 | 0.10 | 0.07 | 0.28 | 0.10 | 0.07 |
| **Midfielder** | 0.18 | 0.15 | 0.15 | 0.15 | 0.13 | 0.08 | 0.10 | 0.06 |
| **Defender** | 0.12 | 0.07 | 0.18 | 0.12 | 0.25 | 0.05 | 0.13 | 0.08 |

All weights sum to 1.0. The capability profile score is a recruiting convenience metric — it is always shown alongside the full capability breakdown so that no nuance is obscured by the aggregate.

### 6.3 Radar Dimensions

The player radar is an octagon with eight equal axes, one per capability:

```
              Ball Progression (12 o'clock)
             /                            \
  Tactical                              Chance
  Versatility                           Creation
  (10 o'clock)                          (2 o'clock)
  |                                           |
  Physical                               Ball
  Availability                           Security
  (8 o'clock)                            (4 o'clock)
             \                            /
      Defensive Activity          Press Resistance
             (7 o'clock)          (5 o'clock)
                      \          /
                   Attacking Threat (6 o'clock)
```

Each axis spans 0–100. The zero-point is at the centre. A perfectly median player (50th percentile on all capabilities) fills exactly half of each axis.

**The radar shows position-normalised standings.** A score of 50 on any axis = median for that position group. This is stated explicitly in the UI to prevent misinterpretation.

### 6.4 Strengths, Development Areas, and Characteristics

| Band | Score Range | Label | Football Meaning |
|---|---|---|---|
| **Elite** | 85–100 | Elite strength | Top 15% of position peers |
| **Strength** | 75–84 | Notable strength | Top 25% of position peers |
| **Characteristic** | 40–74 | Part of profile | Middle — not a differentiator |
| **Development Area** | 25–39 | Below-average | Bottom 25% — notable gap |
| **Critical Gap** | 0–24 | Significant gap | Bottom 15% — material weakness |

**Strengths list:** capabilities with score ≥ 75 (Strength + Elite bands).  
**Development Areas list:** capabilities with score ≤ 25 (Critical Gap only in default display; Development Area on request).  
**Characteristics list:** all remaining capabilities — middle ground that defines the player's normal operation without being a differentiator.

A player with no capabilities above 75 is a **well-rounded contributor** — this is documented positively, not treated as a weakness.

### 6.5 Role Interpretation

The FIE assigns a role label using a **priority-ordered rule classifier**. Rules are evaluated in the order shown; the first match determines the label.

| Priority | Role Label | Conditions |
|---|---|---|
| 1 | **Elite Goal Scorer** | Attacking Threat ≥ 85 |
| 2 | **Creative Playmaker** | Chance Creation ≥ 80 AND Ball Progression ≥ 65 |
| 3 | **Deep-Lying Playmaker** | Ball Security ≥ 80 AND Ball Progression ≥ 75 |
| 4 | **Box-to-Box Midfielder** | Ball Progression ≥ 70 AND Defensive Activity ≥ 70 |
| 5 | **Progressive Fullback** | Ball Progression ≥ 75 AND Chance Creation ≥ 65 AND position ∈ {RB, LB, RWB, LWB} |
| 6 | **Defensive Specialist** | Defensive Activity ≥ 85 AND Ball Security ≥ 70 |
| 7 | **Press-Resistant Anchor** | Press Resistance ≥ 85 AND Ball Security ≥ 75 |
| 8 | **High-Energy Presser** | Defensive Activity ≥ 80 AND Tactical Versatility ≥ 65 |
| 9 | **Versatile Asset** | Tactical Versatility ≥ 85 |
| 10 | **All-Round Contributor** | No capability below 40 AND at least 4 capabilities above 60 |
| 11 | **Developing Profile** | Confidence = "low" for majority of capabilities, OR no rules matched |

Labels are always shown alongside their top 2 supporting data points in the UI — not as bare assertions.

### 6.6 Comparison Logic

Player comparisons use **Euclidean distance** in 8-dimensional capability space, normalised to a 0–100 similarity score:

```
similarity = 100 × (1 - (euclidean_distance(v₁, v₂) / max_possible_distance))
max_possible_distance = √(8 × 100²) ≈ 283.0
```

**Constraints:**
- Default: restricted to same position group.
- Cross-position comparisons require explicit override and are surfaced with a UI caveat.
- A similarity score below 60 is considered "low similarity" and not surfaced in primary recommendations.

**Peer finding:** Given a target player, the system returns the top-N most similar players (similarity ≥ 60), enabling the "players like X" discovery feature. This powers the comparison table and the "find similar profiles" recruitment workflow.

---

## 7. Team Intelligence Model

### 7.1 Team Capability Aggregation

Team capabilities are derived from the **appearances-weighted mean** of all players who contributed meaningful minutes (≥ 5 appearances in that competition-season):

```
team_capability_C = Σ(player_C_score × player_matches_played) / Σ(player_matches_played)
```

Players with more appearances contribute proportionally more to the team's capability profile. This ensures that a team's attacking threat reflects its regular attackers, not squad players with 1–2 appearances.

### 7.2 Team Profile Structure

```python
@dataclass
class TeamProfile:
    # Identity
    team_id:               int
    team_name:             str
    competition_name:      str
    season_name:           str
    matches_played:        int

    # Aggregated team capabilities (appearances-weighted mean of player capabilities)
    ball_progression:      float
    chance_creation:       float
    ball_security:         float
    press_resistance:      float
    defensive_activity:    float
    attacking_threat:      float
    physical_availability: float    # mean player availability across squad
    tactical_versatility:  float    # squad-wide versatility

    # Match-level stats (from vw_team_summary — direct observation)
    xg_for_per_match:      float
    xg_against_per_match:  float
    xg_difference:         float
    pass_accuracy_pct:     float
    wins:                  int
    draws:                 int
    losses:                int
    points:                int
    goal_difference:       int

    # Intelligence
    playing_style:         str     # see 7.3
    tactical_identity:     str     # see 7.4
    squad_depth_score:     float   # see 7.5
```

### 7.3 Playing Style Classification

| Playing Style | Primary Conditions | Football Meaning |
|---|---|---|
| **Possession-Dominant** | Ball Security ≥ 70 AND Ball Progression ≥ 70 | Retains and advances the ball deliberately |
| **High Press** | Defensive Activity ≥ 75 AND Press Resistance ≥ 65 | Presses relentlessly and can handle counter-press |
| **Direct and Progressive** | Ball Progression ≥ 70 AND avg_pass_length > competition median | Advances quickly through direct passing |
| **Counter-Attacking** | Attacking Threat ≥ 70 AND Defensive Activity ≥ 65 AND Ball Security ≤ 55 | Defends deep and transitions quickly |
| **Defensive and Resilient** | Defensive Activity ≥ 80 AND Attacking Threat ≤ 50 | Organised defensively; limited attacking threat |
| **Balanced** | No dimension above 70 OR below 40 | Tactically neutral — no dominant characteristic |

Playing styles are not mutually exclusive in football, but the classifier assigns the highest-priority matching style for display simplicity.

### 7.4 Tactical Identity Narrative

Tactical identity is a structured composite string assembled from three components:

```
tactical_identity = "{playing_style}, {dominant_position_profile}, {pressing_intensity}"
```

**Dominant position profile** examples:
- High Ball Progression among defenders → "progressive backline"
- High Chance Creation among forwards → "creative attack"
- High Ball Security among midfielders → "technically secure midfield"

**Pressing intensity:**
- Defensive Activity (team aggregate) ≥ 75 → "high-intensity pressing"
- 50–74 → "moderate pressing"
- < 50 → "low-block defensive structure"

Example outputs:
- *"High-pressing, possession-based team with a progressive backline"*
- *"Counter-attacking team with creative attack and low-block defensive structure"*
- *"Balanced team with technically secure midfield and moderate pressing"*

The AI Explanation Layer converts this structured string into flowing prose for scouting reports.

### 7.5 Squad Depth Score

```
squad_depth = 100 × (1 - mean(std_dev_per_capability_across_eligible_players) / 50)
```

Where `eligible_players` = players with ≥ 5 appearances.

A low standard deviation in capability scores across players means consistent performers at each capability — high depth. A high standard deviation means performance gaps between starters and rotation players.

A squad depth score of 80+ indicates that rotation players are close in quality to starters across all capabilities. A score below 40 indicates heavy reliance on first-choice performers.

### 7.6 Team Radar

The team radar uses the same 8-axis octagon as the player radar. Each axis shows the team's aggregate score versus the **competition average** for that capability (not position-adjusted — this is team versus team across the same league), enabling visual comparison of how a team's identity compares to its competitors' baseline.

### 7.7 Team Comparison

Teams are compared using Euclidean distance on the 8-capability team vector, normalized to a 0–100 similarity score (same formula as player comparisons). This enables:
- "Find teams with a similar profile to Barcelona to identify where [player] would fit best."
- "Identify the competition's most similar team to [target team] for scouting reference."
- "Which teams most need a player with [capability profile]?"

---

## 8. Decision Signals

Decision signals are **deterministic, explainable binary labels** derived from capability scores and metric thresholds. They are not machine learning predictions — they are rule-based analytical conclusions.

### Design Contract

Every signal must be:
- **Traceable:** directly to specific metrics and numeric thresholds
- **Reproducible:** same inputs always produce the same signal
- **Explainable in football language:** a scout must understand the signal without statistical knowledge
- **Displayable with evidence:** the supporting data points are always shown alongside the signal

### 8.1 Attacking Signals

| Signal | Threshold Conditions | Football Meaning |
|---|---|---|
| **Elite Goal Scorer** | Attacking Threat ≥ 85 | Top 15% of position peers for direct goal threat |
| **Strong Chance Creator** | Chance Creation ≥ 80 | Top 20% for creating opportunities |
| **Clinical Finisher** | goals_minus_xg > 0 AND goals ≥ 3 | Consistently converts beyond statistical expectation |
| **xG-Efficient Attacker** | xg_per_shot > 0.10 AND total_shots ≥ 10 | Positions into high-quality chances — shot selection is excellent |
| **Dual Threat Forward** | Attacking Threat ≥ 70 AND Chance Creation ≥ 70 | Scores and creates — a complete forward |

### 8.2 Progression Signals

| Signal | Threshold Conditions | Football Meaning |
|---|---|---|
| **Elite Ball Progressor** | Ball Progression ≥ 85 | Top 15% for advancing play in position group |
| **Progressive Fullback** | Ball Progression ≥ 75 AND Chance Creation ≥ 60 AND position ∈ {RB, LB} | Attacking fullback who drives forward and creates |
| **Line-Breaking Passer** | `prog_pass_pct_in_position` ≥ 80 | Regularly beats defensive lines with passes |
| **Ball-Carrying Threat** | `prog_carry_pct_in_position` ≥ 80 | Drives play forward with the ball at feet |

### 8.3 Technical Signals

| Signal | Threshold Conditions | Football Meaning |
|---|---|---|
| **High Press Resistant** | Press Resistance ≥ 80 | Top 20% for performing under defensive pressure |
| **Technical Ball Retainer** | Ball Security ≥ 80 | Top 20% for possession protection |
| **Reliable Passer** | pass_accuracy_pct > 85 AND passes_p90 > position-group median | High-accuracy, high-volume — a safe pair of hands |

### 8.4 Defensive Signals

| Signal | Threshold Conditions | Football Meaning |
|---|---|---|
| **Defensive Specialist** | Defensive Activity ≥ 85 | Top 15% for defensive contribution in position group |
| **High-Intensity Presser** | `pressures_p90` ≥ 80th percentile for position | Above-average pressing volume — relentless defensively |
| **Ball Winner** | `recoveries_p90` ≥ 75th percentile for position | Consistently wins loose balls and transitions |

### 8.5 Profile Signals

| Signal | Threshold Conditions | Football Meaning |
|---|---|---|
| **Tactically Versatile** | Tactical Versatility ≥ 80 | Multi-position or multi-phase effectiveness |
| **Box-to-Box Profile** | Ball Progression ≥ 70 AND Defensive Activity ≥ 70 | Contributes meaningfully in both attack and defense |
| **Complete Midfielder** | Ball Progression ≥ 65 AND Chance Creation ≥ 65 AND Ball Security ≥ 65 AND Defensive Activity ≥ 65 | All midfield capabilities above position median |
| **Reliable Starter** | Physical Availability ≥ 80 | Consistent match availability — low injury risk |

### 8.6 Data Quality Signals

| Signal | Condition | Meaning |
|---|---|---|
| **Limited Data** | matches_played < 5 | Scores are provisional — insufficient sample |
| **Developing Sample** | 5 ≤ matches_played < 10 | Scores are indicative — treat with caution |

### 8.7 Signal Display Rules

When multiple signals apply to a player, they are displayed in priority order:

1. **Specialist signals** — highest information density (Elite Goal Scorer, Defensive Specialist)
2. **Progression and technical signals** — system-fit indicators
3. **Profile signals** — broad characterization
4. **Data quality caveats** — always shown last, never suppressed

**Maximum 4 signals** are surfaced in the primary profile card to avoid cognitive overload. All signals are available in the full profile.

---

## 9. Explainability Framework

### 9.1 The Traceability Chain

Every piece of intelligence Athena produces is traceable through a complete, human-readable chain from signal to event. This is a non-negotiable design constraint.

**Example: "Elite Ball Progressor" signal for a midfielder**

```
Signal: "Elite Ball Progressor"
        │
        ▼
Capability Score: Ball Progression = 87
  → Top 13% of midfielders in competition-season
        │
        ├── Progressive passes per 90:   6.2  →  84th percentile in position  [weight: 0.35]
        ├── Progressive carries per 90:  4.1  →  89th percentile in position  [weight: 0.35]
        ├── Carry distance per 90:      180m  →  78th percentile in position  [weight: 0.15]
        └── Switches per 90:             1.3  →  72nd percentile in position  [weight: 0.15]
        │
        ▼
Underlying Statistics (from vw_player_summary):
        ├── Total progressive passes:    52 across 12 matches (≈ 1,080 minutes)
        ├── Total progressive carries:   34
        └── Total carry distance:       2,156m
        │
        ▼
Event Definitions (what was measured):
        ├── Progressive pass: Pass WHERE pass_end_x > location_x
        │                     AND pass_length >= 10m AND pass_end_x > 60
        └── Progressive carry: Carry WHERE (carry_end_x - location_x) >= 10m
```

This chain is **constructible programmatically** for any capability, any player, any metric. The AI Explanation Layer receives this structured chain and converts it to narrative prose.

### 9.2 The LLM's Role: Communication, Not Analysis

This is the fundamental AI design principle of Athena:

> **Athena performs the analysis. The LLM communicates the analysis.**

The LLM receives:
- Structured capability scores with confidence levels
- Ranked metrics with percentile values
- Decision signals and their triggering thresholds
- Comparison data (similar players, team context)

The LLM outputs:
- Readable prose expressing what the data shows
- Natural language explanations of statistical relationships
- Scouting-style narrative summaries

The LLM does **not**:
- Compute capability scores
- Make predictions about future performance
- Compare players without being given pre-computed comparison data
- Speculate about player psychology, character, or effort
- Invent statistics — it only restates what the FIE computed

### 9.3 Explanation Templates

The Intelligence Engine defines structured explanation templates. The AI Layer populates them — it never invents values or inferences.

**Capability explanation template:**

```
[PLAYER_NAME]'s [CAPABILITY_NAME] score is [SCORE]/100,
placing them in the [PERCENTILE_DESCRIPTION] among [POSITION_GROUP]s
in [COMPETITION_NAME] [SEASON_NAME].

The primary driver is [TOP_METRIC_LABEL]: [VALUE] [UNIT] ([PERCENTILE]th percentile
within position). Supporting this is [SECOND_METRIC]: [VALUE2] [UNIT2]
at the [PERCENTILE2]th percentile, and [THIRD_METRIC] at the [PERCENTILE3]th.

In football terms: [FOOTBALL_INTERPRETATION — drawn from capability definition].
```

**Confidence caveat template:**

```
Note: This score is based on [N] matches, which is below the recommended threshold
for high statistical reliability. The score will stabilize with additional data.
Treat this profile as indicative, not definitive.
```

### 9.4 Explainability Anti-Patterns — What Athena Never Does

| Anti-Pattern | Why It Is Rejected |
|---|---|
| "Player X will score 20 goals next season" | Future prediction from past events without disclosed model. Rejected completely. |
| "Player X is better than Player Y" | "Better" requires a context — better for what system, what role? Athena provides comparisons and signals; the scout makes the judgment. |
| "This player has high potential" | Potential is not in the data. StatsBomb events describe what happened, not what could happen. |
| Unexplained capability score | Every score must trace to specific events. If the chain breaks, the score is not shown. |
| Confidence without caveats | Small sample sizes always produce caveated scores. No score is presented as certain when it is not. |
| Cross-position comparisons without caveats | Comparing a striker to a midfielder on the same capability without noting the positional adjustment is misleading. Always caveated explicitly. |
| LLM-invented statistics | The AI layer may only use statistics explicitly provided to it by the FIE output. |

---

## 10. Data Constraints and Honest Limitations

### 10.1 StatsBomb Open Data Coverage

| Constraint | FIE Impact |
|---|---|
| Limited competition coverage | Cross-competition normalization required for fair multi-league comparison |
| No injury records | Physical Availability approximated from appearances only |
| No physical metrics (sprint speed, distance covered per match) | Physical attributes not capturable in v1.0 |
| Goalkeeper event taxonomy differs fundamentally | Goalkeepers excluded from all 8 capabilities in v1.0 |
| No video data | Cannot verify contextual quality of events |

### 10.2 Event Taxonomy Limitations

| Metric / Event | Known Limitation |
|---|---|
| `under_pressure` flag | Binary — degree of press and number of pressers unknown |
| Progressive pass (Athena definition) | Spatial approximation; football intent not capturable |
| `minutes_played` | Approximated as matches × 90; exact substitution times are Phase 3 |
| Defensive events | Less richly annotated than attacking events in StatsBomb |
| Ball loss events (`Miscontrol`, `Dispossessed`) | Available in raw events but not yet in Phase 2.2 ETL |

### 10.3 Small Sample Size Policy

| Scenario | FIE Behaviour |
|---|---|
| < 3 matches | Score not computed — "Insufficient Data" displayed |
| 3–4 matches | Score computed with "Limited Data" signal — Low confidence |
| 5–9 matches | Score computed with "Developing Sample" signal — Medium confidence |
| ≥ 10 matches | Score computed — High confidence, no caveat |

### 10.4 Position Group Assignment

Position groups are derived from the most common `starting_position` in the lineup data (see `vw_player_summary` QUALIFY logic).

| StatsBomb Position(s) | FIE Position Group |
|---|---|
| Center Forward, Left Wing, Right Wing, Left Center Forward, Right Center Forward, Attacking Midfield | **Forward** |
| Center Midfield, Left/Right Center Midfield, Left/Right Midfield, Left/Right Defensive Midfield, Center Defensive Midfield | **Midfielder** |
| Center Back, Left/Right Back, Left/Right Center Back, Left/Right Wing Back | **Defender** |
| Goalkeeper | **Goalkeeper** — excluded from all 8 capabilities in v1.0 |

### 10.5 Phase 4 Planned Extensions

| Extension | Capability Benefit |
|---|---|
| Goalkeeper-specific capability system (5 caps) | Goalkeepers included in Athena |
| Pressure success rate (press-to-turnover linkage) | Defensive Activity precision |
| xA (expected assists via shot-to-pass linkage) | Chance Creation quality |
| Team-adjusted metrics (correcting for system effects) | All capabilities |
| Career trajectory view (multi-season) | Physical Availability and development |

---

## 11. Design Decisions Log

| Decision | Rationale | Alternative Considered |
|---|---|---|
| **Percentile rank over z-score** | Interpretable 0–100 scale, robust to outliers, matches human intuition ("top 20%") | Z-score rejected: requires distributional assumptions; produces unintuitive values for non-statisticians |
| **Position-group relative scoring** | A striker with 0.5 xG/90 and a midfielder with 0.5 xG/90 are both exceptional — but relative to different peer sets | Absolute scoring penalizes structurally lower-volume positions |
| **Deterministic signals over ML clustering** | Explainability is non-negotiable for a scouting tool. Every signal traces to a specific, communicable fact | ML clustering considered for Phase 4 as a complement, not replacement |
| **Eight capabilities** | Cognitive load ceiling for radar charts and UI. Eight axes is at the limit of human readability | 12-capability system prototyped — reduced for clarity and actionability |
| **npxG as primary shooting metric** | Goals have high variance at short sample sizes. npxG stabilizes faster and reflects shot-quality | Goals remain in the metric mix but at 0.25 weight, not primary |
| **90-minute approximation for minutes_played** | Substitution timing requires Phase 3 event linkage. Better to document and ship an approximation than delay all 8 capabilities | Exact minutes deferred explicitly — noted on every affected score |
| **Goalkeepers excluded from v1.0** | Goalkeepers have fundamentally different event profiles; including them in percentile calculations distorts all position groups | Phase 4 will define 5 goalkeeper-specific capabilities |
| **Capability breadth as primary Versatility dimension (40%)** | Most data-rich and stable dimension. Positional breadth is sparse in short-season samples | Positional breadth included but at lower weight (25%) than breadth score (40%) |
| **LLM as communicator, not analyst** | The analytical conclusions must be pre-determined by the FIE before the LLM is invoked. This prevents hallucination of statistics and ensures full audit trails | Alternative (LLM generates analysis directly) rejected: black-box risk, unverifiable statistics |

---

*This document is the authoritative design specification for the Athena Football Intelligence Engine.*

*Phase 3 implementation must not begin until this specification receives architectural review and explicit approval.*

*Every implementation decision must trace back to a section of this document.*

*If an implementation requires a choice not addressed here, update the specification first, then implement.*
