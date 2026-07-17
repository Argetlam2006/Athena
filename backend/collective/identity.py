import numpy as np

from shared.schemas import CollectiveIdentity, PlayerProfile

# Predefined Tactical Style Vectors based on the 6 core capabilities
# [Progression, Creation, Security, Press Resistance, Defense, Threat]
# Predefined Tactical Style Vectors (Expected Z-score profiles)
# [Progression, Creation, Security, Press Resistance, Defense, Threat]
TACTICAL_VECTORS = {
    "Possession-Dominant": np.array([0.5, 0.5, 1.5, 1.0, -1.0, 0.0]),
    "High Press": np.array([0.0, 0.0, -0.5, 0.5, 1.5, 0.0]),
    "Direct and Progressive": np.array([1.5, 1.0, -1.0, 0.0, 0.0, 1.0]),
    "Counter-Attacking": np.array([1.0, 0.5, -1.5, -0.5, 0.5, 1.5]),
    "Defensive and Resilient": np.array([-1.0, -1.0, 0.5, 0.0, 1.5, -1.0])
}

def generate_collective_identity(players: list[PlayerProfile], global_pool: list[PlayerProfile] = None) -> CollectiveIdentity:
    """
    Deterministically assign a team's primary and secondary identity using Z-scores,
    and find emergent traits based on anomalous capability spikes.
    """
    if not players:
        return CollectiveIdentity("Unknown")

    # Aggregate capabilities
    caps = []
    for p in players:
        if p.capability_profile:
            cp = p.capability_profile
            caps.append([
                cp.ball_progression.score if cp.ball_progression else 0,
                cp.chance_creation.score if cp.chance_creation else 0,
                cp.ball_security.score if cp.ball_security else 0,
                cp.press_resistance.score if cp.press_resistance else 0,
                cp.defensive_activity.score if cp.defensive_activity else 0,
                cp.attacking_threat.score if cp.attacking_threat else 0,
            ])

    if not caps:
        return CollectiveIdentity("Unknown")

    team_avg = np.mean(caps, axis=0)

    # Calculate global mean and std for Z-score normalization
    if global_pool:
        global_caps = []
        for p in global_pool:
            if p.capability_profile:
                cp = p.capability_profile
                global_caps.append([
                    cp.ball_progression.score if cp.ball_progression else 0,
                    cp.chance_creation.score if cp.chance_creation else 0,
                    cp.ball_security.score if cp.ball_security else 0,
                    cp.press_resistance.score if cp.press_resistance else 0,
                    cp.defensive_activity.score if cp.defensive_activity else 0,
                    cp.attacking_threat.score if cp.attacking_threat else 0,
                ])
        if global_caps:
            global_mean = np.mean(global_caps, axis=0)
            global_std = np.std(global_caps, axis=0)
            global_std = np.where(global_std == 0, 1.0, global_std)
            z_vector = (team_avg - global_mean) / global_std
        else:
            z_vector = (team_avg - 50.0) / 10.0 # Fallback
    else:
        z_vector = (team_avg - 50.0) / 10.0 # Fallback

    similarities = []
    for style, vec in TACTICAL_VECTORS.items():
        dot = np.dot(z_vector, vec)
        norm_a = np.linalg.norm(z_vector)
        norm_b = np.linalg.norm(vec)
        if norm_a == 0 or norm_b == 0:
            similarities.append((style, 0.0))
        else:
            sim = dot / (norm_a * norm_b)
            similarities.append((style, float(sim)))

    similarities.sort(key=lambda x: x[1], reverse=True)

    primary = similarities[0][0] if similarities[0][1] > 0.6 else "Balanced"
    secondary = similarities[1][0] if len(similarities) > 1 and similarities[1][1] > 0.75 else None

    # Emergent traits (anomalous capability spikes > 80 avg)
    emergent = []
    avg_scores = np.mean(caps, axis=0)
    names = ["ball_progression", "chance_creation", "ball_security", "press_resistance", "defensive_activity", "attacking_threat"]

    for i, score in enumerate(avg_scores):
        if score > 80.0:
            emergent.append(f"Elite {names[i].replace('_', ' ').title()}")

    return CollectiveIdentity(
        primary_identity=primary,
        secondary_identity=secondary,
        emergent_traits=emergent
    )
