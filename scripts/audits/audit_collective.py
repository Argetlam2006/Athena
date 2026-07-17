import logging

from backend.intelligence.store import IntelligenceStore
from shared.schemas import CollectiveProfile

logging.basicConfig(level=logging.INFO)

def run_audit():
    store = IntelligenceStore()
    collectives = store.get_all_collectives()

    if not collectives:
        print("No collective profiles found in store.")
        return

    print(f"Loaded {len(collectives)} Collective Profiles.")

    # Analyze Top 5 teams (for simplicity, we pick 5 known top teams, or sort by a capability)
    # Since we have avg_capabilities, we can sort by avg_ball_progression or something

    # Sort by avg attacking threat + ball security
    def team_score(c: CollectiveProfile):
        return c.avg_capabilities.get("attacking_threat", 0) + c.avg_capabilities.get("ball_security", 0)

    top_teams = sorted(collectives, key=team_score, reverse=True)[:5]

    with open("collective_intelligence_report.md", "w") as f:
        f.write("# Phase 15: Collective Intelligence Validation Audit\n\n")
        f.write("This report validates the deterministic extraction of Identity, Concentration, Fragility, and Bottlenecks from the Football Intelligence Engine.\n\n")

        for team in top_teams:
            f.write(f"## {team.team_name}\n")
            f.write(f"**Primary Identity:** {team.identity.primary_identity if team.identity else 'Unknown'}\n")

            f.write("### Capability Bottlenecks\n")
            if team.bottlenecks:
                for b in team.bottlenecks:
                    f.write(f"- **{b.upstream_capability} ➔ {b.downstream_capability}**: {b.diagnosis} (Severity: {b.severity})\n")
            else:
                f.write("- No major structural bottlenecks detected.\n")

            f.write("\n### System Fragility (Top 3)\n")
            if team.fragility_map:
                top_frag = sorted(team.fragility_map, key=lambda x: x.structural_deficit, reverse=True)[:3]
                for frag in top_frag:
                    f.write(f"- **{frag.player_name}** (Deficit: {frag.structural_deficit})\n")
                    f.write(f"  - Replaceability Index: {frag.replaceability_index}\n")
                    for cap, loss in frag.capability_loss.items():
                        f.write(f"  - Lost {cap.replace('_', ' ').title()}: -{loss}\n")
            else:
                f.write("- No severe fragilities detected.\n")

            f.write("\n### Capability Concentration\n")
            for c in team.concentration:
                if c.is_over_centralized:
                    f.write(f"- **WARNING: {c.capability_name.replace('_', ' ').title()} is over-centralized** (HHI: {c.hhi_score})\n")
                    for top, share in c.top_contributors:
                        f.write(f"  - {top}: {share}%\n")

            f.write("\n---\n\n")

    print("Generated collective_intelligence_report.md successfully.")

if __name__ == "__main__":
    run_audit()
