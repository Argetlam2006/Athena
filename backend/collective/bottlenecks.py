from shared.schemas import CapabilityBottleneck


def identify_bottlenecks(avg_caps: dict[str, float]) -> list[CapabilityBottleneck]:
    """
    Identify structural bottlenecks where upstream capabilities fail
    to convert into downstream value.
    """
    bottlenecks = []

    # Threshold for a bottleneck (e.g. 20 point drop-off)
    SEVERITY_THRESHOLD = 20.0

    # 1. Progression to Threat Bottleneck
    prog = avg_caps.get("ball_progression", 0)
    threat = avg_caps.get("attacking_threat", 0)
    if prog - threat > SEVERITY_THRESHOLD:
        bottlenecks.append(CapabilityBottleneck(
            upstream_capability="Ball Progression",
            downstream_capability="Attacking Threat",
            severity=round(prog - threat, 1),
            diagnosis="The team progresses the ball effectively but struggles to convert territory into tangible goal threat."
        ))

    # 2. Creation to Threat Bottleneck
    creation = avg_caps.get("chance_creation", 0)
    if creation - threat > SEVERITY_THRESHOLD:
        bottlenecks.append(CapabilityBottleneck(
            upstream_capability="Chance Creation",
            downstream_capability="Attacking Threat",
            severity=round(creation - threat, 1),
            diagnosis="The team creates high volumes of chances but suffers from poor finishing or shot execution."
        ))

    # 3. Defensive Activity to Ball Security
    defense = avg_caps.get("defensive_activity", 0)
    security = avg_caps.get("ball_security", 0)
    if defense - security > SEVERITY_THRESHOLD:
        bottlenecks.append(CapabilityBottleneck(
            upstream_capability="Defensive Activity",
            downstream_capability="Ball Security",
            severity=round(defense - security, 1),
            diagnosis="The team presses and recovers well but immediately turns the ball back over due to poor security."
        ))

    return bottlenecks
