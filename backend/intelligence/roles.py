"""
backend/intelligence/roles.py - Role Family Abstraction

Maps archetypes to broad Role Families to ensure sufficient statistical
cohort sizes for rating normalization. Defines capability importance vectors.
"""

ROLE_FAMILIES = {
    "Creative Attacker": {
        "archetypes": ["Creative Forward", "Creative Playmaker", "Creative Winger"],
        "importance_vector": {
            "chance_creation": 3.0,
            "attacking_threat": 2.0,
            "ball_progression": 2.0,
            "ball_security": 1.0,
            "press_resistance": 1.0,
            "defensive_activity": 0.5,
        },
    },
    "Goal Scorer": {
        "archetypes": [
            "Elite Goal Scorer",
            "Target Man",
            "Complete Forward",
            "Direct Winger",
        ],
        "importance_vector": {
            "attacking_threat": 3.5,
            "chance_creation": 1.5,
            "ball_progression": 1.0,
            "ball_security": 1.0,
            "press_resistance": 1.5,
            "defensive_activity": 0.5,
        },
    },
    "Midfield Controller": {
        "archetypes": ["Deep-Lying Playmaker", "Box-to-Box Engine"],
        "importance_vector": {
            "ball_progression": 3.0,
            "ball_security": 3.0,
            "press_resistance": 2.5,
            "chance_creation": 1.5,
            "defensive_activity": 1.5,
            "attacking_threat": 0.5,
        },
    },
    "Midfield Destroyer": {
        "archetypes": ["Press-Resistant Anchor", "Midfield Destroyer"],
        "importance_vector": {
            "defensive_activity": 3.5,
            "ball_security": 2.0,
            "press_resistance": 2.0,
            "ball_progression": 1.0,
            "chance_creation": 0.5,
            "attacking_threat": 0.2,
        },
    },
    "Progressive Defender": {
        "archetypes": ["Ball-Playing Defender", "Progressive Fullback"],
        "importance_vector": {
            "defensive_activity": 2.5,
            "ball_progression": 2.5,
            "ball_security": 2.0,
            "press_resistance": 1.5,
            "chance_creation": 1.0,
            "attacking_threat": 0.5,
        },
    },
    "Traditional Defender": {
        "archetypes": ["Traditional Defender", "Defensive Fullback"],
        "importance_vector": {
            "defensive_activity": 4.0,
            "ball_security": 1.5,
            "press_resistance": 1.5,
            "ball_progression": 1.0,
            "chance_creation": 0.2,
            "attacking_threat": 0.2,
        },
    },
    "Goalkeeper": {
        "archetypes": [],
        "importance_vector": {
            "ball_progression": 1.0,
            "chance_creation": 1.0,
            "ball_security": 1.0,
            "press_resistance": 1.0,
            "defensive_activity": 1.0,
            "attacking_threat": 1.0,
        },
    },
    "Balanced": {
        "archetypes": ["Unknown", "General"],
        "importance_vector": {
            "ball_progression": 1.0,
            "chance_creation": 1.0,
            "ball_security": 1.0,
            "press_resistance": 1.0,
            "defensive_activity": 1.0,
            "attacking_threat": 1.0,
        },
    },
}


def get_role_family(archetype: str) -> str:
    """Returns the Role Family for a given archetype."""
    if not archetype:
        return "Balanced"
    for role, data in ROLE_FAMILIES.items():
        if archetype in data["archetypes"]:
            return role
    return "Balanced"


def get_role_importance_vector(role_family: str) -> dict[str, float]:
    """Returns the unnormalized importance vector for a role family."""
    role_data = ROLE_FAMILIES.get(role_family)
    if role_data:
        return role_data["importance_vector"]
    return ROLE_FAMILIES["Balanced"]["importance_vector"]
