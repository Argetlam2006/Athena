"""
scripts/audit_phase14.py

Extracts mathematical facts for Phase 14 gap analysis.
"""
import pandas as pd
import json
from backend.intelligence.store import IntelligenceStore
from shared.config import CAPABILITY_METRIC_WEIGHTS, CORE_CAPABILITIES

store = IntelligenceStore()
players = store.get_all_players()

results = {}

# 1. Feature Importance (Derived directly from static weights)
results["Feature_Importance"] = CAPABILITY_METRIC_WEIGHTS

# Build DataFrame for statistical analysis
data = []
for p in players:
    if not p.capability_profile: continue
    row = {
        "overall_rating": p.capability_profile.overall_rating,
    }
    for cap in CORE_CAPABILITIES:
        score_obj = getattr(p.capability_profile, cap)
        row[cap] = score_obj.score if score_obj else 0.0
    data.append(row)

df = pd.DataFrame(data).dropna()

# 2. Calibration Curves
percentiles = [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
calib = df.describe(percentiles=percentiles).T
# Extract only the percentiles
calib = calib[[f"{int(p*100)}%" for p in percentiles]]
results["Calibration_Curves"] = calib.to_dict(orient="index")

# 3. Correlation Matrix
corr = df[CORE_CAPABILITIES].corr().to_dict(orient="index")
results["Correlation_Matrix"] = corr

# Write out
with open("phase14_math_audit.json", "w") as f:
    json.dump(results, f, indent=2)

print("Dumped phase14_math_audit.json")
