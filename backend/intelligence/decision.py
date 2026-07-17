"""
backend/intelligence/decision.py — Decision Intelligence Engine

The canonical Single Source of Truth for football reasoning.
Generates deterministic explanations, dependency maps, and counterfactuals.
"""


import numpy as np

from shared.schemas import (
    CapabilityExplanation,
    CollectiveProfile,
    DependencyAnalysis,
    PlayerDecisionCard,
    PlayerProfile,
    TeamDecisionCard,
)


class DecisionEngine:

    @staticmethod
    def _calculate_percentile(value: float, values: list[float]) -> int:
        if not values:
            return 0
        arr = np.array(values)
        if len(arr) == 0:
            return 0
        return int(np.round(np.sum(arr < value) / len(arr) * 100))

    @staticmethod
    def explain_capability(profile: PlayerProfile, capability_name: str, cohort: list[PlayerProfile]) -> CapabilityExplanation:
        """
        Dynamically explains a capability using cohort percentiles (Explainability Tree).
        """
        cap_map = {
            "Ball Progression": profile.capability_profile.ball_progression,
            "Chance Creation": profile.capability_profile.chance_creation,
            "Ball Security": profile.capability_profile.ball_security,
            "Press Resistance": profile.capability_profile.press_resistance,
            "Defensive Activity": profile.capability_profile.defensive_activity,
            "Attacking Threat": profile.capability_profile.attacking_threat,
        }

        cap_score_obj = cap_map.get(capability_name)
        if not cap_score_obj:
            return CapabilityExplanation(capability_name=capability_name, score=0.0)

        score = cap_score_obj.score
        evidence = cap_score_obj.evidence

        drivers = {}
        # Since evidence is now a list of SupportingMetric, we can directly read the precomputed percentiles
        for metric in evidence:
            drivers[metric.metric_name] = f"{int(round(metric.percentile))}th percentile"

        return CapabilityExplanation(
            capability_name=capability_name,
            score=round(score, 1),
            drivers=drivers
        )

    @staticmethod
    def build_player_decision_card(profile: PlayerProfile, cohort: list[PlayerProfile]) -> PlayerDecisionCard:
        """
        Generates deterministic reasoning for a player.
        """
        if not profile.capability_profile:
            return PlayerDecisionCard(player=profile, primary_role="Unknown")

        capabilities = [
            "Ball Progression", "Chance Creation", "Ball Security", "Press Resistance",
            "Defensive Activity", "Attacking Threat"
        ]

        elite_traits = []
        weak_areas = []

        for cap_name in capabilities:
            cap_score_obj = getattr(profile.capability_profile, cap_name.lower().replace(" ", "_"), None)
            if cap_score_obj:
                score = cap_score_obj.score
                cohort_scores = []
                for p in cohort:
                    p_cap = getattr(p.capability_profile, cap_name.lower().replace(" ", "_"), None)
                    if p_cap:
                        cohort_scores.append(p_cap.score)

                if cohort_scores:
                    pct = DecisionEngine._calculate_percentile(score, cohort_scores)
                    explanation = DecisionEngine.explain_capability(profile, cap_name, cohort)
                    if pct >= 85:
                        elite_traits.append(explanation)
                    elif pct <= 35:
                        weak_areas.append(explanation)

        elite_traits.sort(key=lambda x: x.score, reverse=True)
        weak_areas.sort(key=lambda x: x.score)

        return PlayerDecisionCard(
            player=profile,
            primary_role=profile.display_archetype,
            elite_traits=elite_traits[:3],  # Top 3
            weak_areas=weak_areas[:3],      # Bottom 3
            playing_style=profile.display_archetype,
            player_attributes=profile.player_attributes
        )

    @staticmethod
    def analyze_team_dependency(team: CollectiveProfile, squad: list[PlayerProfile]) -> dict[str, DependencyAnalysis]:
        """
        Calculates exact percentage contributions per player for every core capability.
        """
        capabilities = [
            "ball_progression", "chance_creation", "ball_security", "press_resistance",
            "defensive_activity", "attacking_threat"
        ]

        dependencies = {}
        for cap in capabilities:
            cap_name = cap.replace("_", " ").title()

            # Use raw un-normalized sum of scores
            scores = {}
            for p in squad:
                cap_obj = getattr(p.capability_profile, cap, None)
                if cap_obj:
                    scores[p.player_name] = cap_obj.score

            total_score = sum(scores.values())

            contributions = {}
            if total_score > 0:
                for p_name, score in scores.items():
                    pct = (score / total_score) * 100
                    contributions[p_name] = round(pct, 1)

            contributions = dict(sorted(contributions.items(), key=lambda item: item[1], reverse=True))
            key_players = list(contributions.keys())[:2]

            dependencies[cap_name] = DependencyAnalysis(
                capability_name=cap_name,
                contributions=contributions,
                key_players=key_players
            )

        return dependencies

    @staticmethod
    def build_team_decision_card(team: CollectiveProfile, squad: list[PlayerProfile], cohort_teams: list[CollectiveProfile]) -> TeamDecisionCard:
        """
        Builds deterministic team reasoning.
        """
        dependencies = DecisionEngine.analyze_team_dependency(team, squad)

        gap_analysis = {}
        capabilities = [
            "avg_ball_progression", "avg_chance_creation", "avg_ball_security", "avg_press_resistance",
            "avg_defensive_activity", "avg_attacking_threat"
        ]

        # Calculate strengths and weaknesses based on top/bottom quartile gap analysis
        strengths = []
        weaknesses = []

        for cap in capabilities:
            cap_name = cap.replace("avg_", "").replace("_", " ").title()
            cohort_scores = [getattr(t, cap, 0.0) for t in cohort_teams if getattr(t, cap, 0.0) > 0.0]

            team_score = getattr(team, cap, 0.0)

            if cohort_scores:
                top_quartile = np.percentile(cohort_scores, 75)
                median = np.percentile(cohort_scores, 50)
                gap_analysis[cap_name] = round(team_score - top_quartile, 1)

                # Derive strengths/weaknesses deterministically
                if team_score >= top_quartile:
                    # Construct pseudo-explanation for team
                    strengths.append(CapabilityExplanation(
                        capability_name=cap_name,
                        score=team_score,
                        drivers={"Advantage vs Top Quartile": f"+{round(team_score - top_quartile, 1)} points"}
                    ))
                elif team_score < median:
                    weaknesses.append(CapabilityExplanation(
                        capability_name=cap_name,
                        score=team_score,
                        drivers={"Deficit vs Median": f"{round(team_score - median, 1)} points"}
                    ))

        return TeamDecisionCard(
            team=team,
            tactical_identity=team.identity.primary_identity if team.identity else "Balanced",
            biggest_strengths=sorted(strengths, key=lambda x: x.score, reverse=True)[:3],
            biggest_weaknesses=sorted(weaknesses, key=lambda x: x.score)[:3],
            dependency_analysis=dependencies,
            gap_analysis=gap_analysis
        )
