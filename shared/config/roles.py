"""
shared/config/roles.py — Role classifications for Player Intelligence.
"""

# Priority ordered list of role classification rules
# Engine evaluates these in order, taking the first match.
ROLE_DEFINITIONS: list[dict[str, str]] = [
    {
        "id": "elite_goal_scorer",
        "label": "Elite Goal Scorer",
        "description": "Top 15% of position peers for direct goal threat",
    },
    {
        "id": "creative_playmaker",
        "label": "Creative Playmaker",
        "description": "High chance creation combined with progressive passing",
    },
    {
        "id": "deep_lying_playmaker",
        "label": "Deep-Lying Playmaker",
        "description": "Excellent ball security with strong progressive passing",
    },
    {
        "id": "box_to_box_midfielder",
        "label": "Box-to-Box Midfielder",
        "description": "Contributes strongly in both progression and defensive phases",
    },
    {
        "id": "progressive_fullback",
        "label": "Progressive Fullback",
        "description": "Attacking fullback who drives forward and creates",
    },
    {
        "id": "defensive_specialist",
        "label": "Defensive Specialist",
        "description": "Elite defensive contribution with secure possession",
    },
    {
        "id": "press_resistant_anchor",
        "label": "Press-Resistant Anchor",
        "description": "Maintains control when pressed aggressively",
    },
    {
        "id": "high_energy_presser",
        "label": "High-Energy Presser",
        "description": "Relentless defensively and tactically versatile",
    },
    {
        "id": "versatile_asset",
        "label": "Versatile Asset",
        "description": "Effective across multiple roles and systems",
    },
    {
        "id": "all_round_contributor",
        "label": "All-Round Contributor",
        "description": "Well-rounded profile with no material weaknesses",
    },
    {
        "id": "developing_profile",
        "label": "Developing Profile",
        "description": "Developing statistical profile (often due to sample size)",
    },
]
