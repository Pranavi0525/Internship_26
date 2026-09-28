"""
Sanity check for pincode_groundwater_point_scores.csv -- same discipline
as every other hazard layer's validation script. The main script only
PRINTS a reminder to check Punjab/Haryana; this actually checks it.
"""

import csv
from collections import defaultdict

SCORES_FILE = r"C:\Users\New\Downloads\pincode_groundwater_point_scores.csv"

# States with well-documented groundwater trends, for a sanity check.
# Punjab/Haryana: one of the most famous groundwater depletion crises in
# the world (Rodell et al. 2009, Nature -- satellite-measured decline in
# NW India). Kerala/Assam: monsoon-rich, generally less stressed --
# included as a rough contrast, not because they're guaranteed to be flat.
EXPECT_DECLINING = {"PUNJAB", "HARYANA"}
CONTRAST_STATES = {"KERALA", "ASSAM"}

with open(SCORES_FILE, newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

by_state = defaultdict(lambda: {"trends": [], "low_conf": 0, "total": 0, "no_well": 0})
for r in rows:
    st = (r.get("state") or "").strip().upper()
    by_state[st]["total"] += 1
    if r["confidence"] == "none":
        by_state[st]["no_well"] += 1
        continue
    if r["confidence"].startswith("low"):
        by_state[st]["low_conf"] += 1
    trend = r.get("groundwater_trend_m_per_year")
    if trend not in (None, ""):
        by_state[st]["trends"].append(float(trend))

print("=== Punjab/Haryana sanity check (should show clearly POSITIVE avg trend) ===")
for st in sorted(EXPECT_DECLINING):
    d = by_state.get(st)
    if not d or not d["trends"]:
        print(f"{st:<20} NO DATA")
        continue
    avg_trend = sum(d["trends"]) / len(d["trends"])
    flag = "  <-- EXPECTED POSITIVE (declining water table), CHECK IF NOT" if avg_trend <= 0.1 else "  OK -- consistent with known crisis"
    print(f"{st:<20} avg trend: {avg_trend:+.3f} m/yr, n={len(d['trends'])}{flag}")

print("\n=== Contrast states (less-documented severity, shown for comparison only) ===")
for st in sorted(CONTRAST_STATES):
    d = by_state.get(st)
    if not d or not d["trends"]:
        print(f"{st:<20} NO DATA")
        continue
    avg_trend = sum(d["trends"]) / len(d["trends"])
    print(f"{st:<20} avg trend: {avg_trend:+.3f} m/yr, n={len(d['trends'])}")

print("\n=== Confidence breakdown by state (top 10 highest low-confidence %) ===")
state_conf = []
for st, d in by_state.items():
    if d["total"] < 20:
        continue
    pct_low = 100 * (d["low_conf"] + d["no_well"]) / d["total"]
    state_conf.append((pct_low, st, d["low_conf"], d["no_well"], d["total"]))
state_conf.sort(reverse=True)
print(f"{'State':<20}{'Low-conf %':<12}{'Low-conf n':<12}{'No well':<10}{'Total'}")
for pct_low, st, low_conf, no_well, total in state_conf[:10]:
    print(f"{st:<20}{pct_low:<12.1f}{low_conf:<12}{no_well:<10}{total}")

print("\n=== National overview ===")
all_trends = [float(r["groundwater_trend_m_per_year"]) for r in rows if r.get("groundwater_trend_m_per_year") not in (None, "")]
declining = sum(1 for t in all_trends if t > 0)
print(f"Pincodes with usable trend data: {len(all_trends)} / {len(rows)}")
print(f"Showing DECLINING water table (positive trend): {declining} ({100*declining/len(all_trends):.1f}%)")
print(f"Showing STABLE/RECOVERING (trend <= 0): {len(all_trends) - declining} ({100*(len(all_trends)-declining)/len(all_trends):.1f}%)")
