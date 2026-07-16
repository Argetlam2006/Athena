"""
tests/evaluation/run_full_audit.py

Queries the IntelligenceStore and DecisionEngine to dump raw decision objects for analysis.
"""

import json

from backend.intelligence.decision import DecisionEngine
from backend.intelligence.store import IntelligenceStore
from backend.recommendation.recruitment import recommend_replacement

store = IntelligenceStore()
all_players = store.get_all_players()
all_teams = store.get_all_teams()

def find_player(name_substring, season=None):
    matches = [p for p in all_players if name_substring.lower() in p.player_name.lower()]
    if season:
        matches = [p for p in matches if p.season == season]
    if matches:
        return sorted(matches, key=lambda x: x.minutes_played or 0, reverse=True)[0]
    return None

def find_team(name_substring):
    matches = [t for t in all_teams if name_substring.lower() in t.team_name.lower()]
    if matches:
        return matches[0]
    return None

results = {}

# 1. World Class vs Average
messi = find_player("Messi", "Career")
average_winger = next((p for p in all_players if p.position_group == "Forward" and p.capability_profile and p.capability_profile.overall_rating and 60 < p.capability_profile.overall_rating < 70), None)
rodri = find_player("Rodri", "Career")
average_dm = next((p for p in all_players if p.position_group == "Midfielder" and p.capability_profile and p.capability_profile.overall_rating and 60 < p.capability_profile.overall_rating < 70), None)

def get_card(player):
    if not player:
        return None
    cohort = [p for p in all_players if p.position_group == player.position_group]
    return DecisionEngine.build_player_decision_card(player, cohort).__dict__

results["WorldClass_vs_Average"] = {
    "Messi": get_card(messi),
    "Average Winger": get_card(average_winger),
    "Rodri": get_card(rodri),
    "Average DM": get_card(average_dm),
}

# 2. Closely Matched
busquets = find_player("Sergio Busquets", "Career")
casemiro = find_player("Casemiro", "Career")
kroos = find_player("Toni Kroos", "Career")
xavi = find_player("Xavi", "Career")
pedri = find_player("Pedri", "Career")
musiala = find_player("Musiala", "Career")
salah = find_player("Mohamed Salah", "Career")
robben = find_player("Robben", "Career")
kane = find_player("Harry Kane", "Career")
lewandowski = find_player("Lewandowski", "Career")
messi_11 = find_player("Messi", "2011/2012")
suarez_15 = find_player("Luis Suárez", "2015/2016")

results["Closely_Matched"] = {
    "Rodri": get_card(rodri),
    "Busquets": get_card(busquets),
    "Casemiro": get_card(casemiro),
    "Kroos": get_card(kroos),
    "Xavi": get_card(xavi),
    "Pedri": get_card(pedri),
    "Musiala": get_card(musiala),
    "Salah": get_card(salah),
    "Robben": get_card(robben),
    "Kane": get_card(kane),
    "Lewandowski": get_card(lewandowski),
    "Messi_2011": get_card(messi_11),
    "Suarez_2015": get_card(suarez_15),
}

# 3. Recruitment & Counterfactual Scenarios
def run_recruitment(target, max_results=3):
    if not target:
        return None
    replacements = recommend_replacement(target, all_players, max_results=max_results)
    return [
        {
            "player": r.player.player_name,
            "fit": r.fit_score,
            "restoration": r.restoration,
            "positive_tradeoffs": r.trade_offs_positive,
            "negative_tradeoffs": r.trade_offs_negative,
            "impact": r.overall_team_impact
        } for r in replacements
    ]

results["Recruitment"] = {
    "Replace_Rodri": run_recruitment(rodri),
    "Replace_Busquets": run_recruitment(busquets),
}

# 4. Team Dependencies & Gaps
city = find_team("Manchester City")
arsenal = find_team("Arsenal")
liverpool = find_team("Liverpool")

for team, name in [(city, "City"), (arsenal, "Arsenal"), (liverpool, "Liverpool")]:
    if team:
        squad = [p for p in all_players if p.team_name == team.team_name]
        card = DecisionEngine.build_team_decision_card(team, squad, all_teams)
        deps = {k: {"contributions": v.contributions, "key_players": v.key_players} for k, v in card.dependency_analysis.items()}
        results[f"Team_{name}"] = {
            "identity": card.tactical_identity,
            "dependencies": deps,
            "gaps": card.gap_analysis
        }

def safe_serialize(obj):
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    return str(obj)

with open("audit_results.json", "w") as f:
    json.dump(results, f, default=safe_serialize, indent=2)

print("Dumped audit_results.json")
