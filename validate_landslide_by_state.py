"""
Checks landslide match rate BY STATE. States that are DEFINITELY in
the 147-district Landslide Atlas list (Kerala, Uttarakhand, J&K,
Himachal, Sikkim, all NE states, coastal Karnataka, Western Ghats
Maharashtra/Goa/Tamil Nadu, West Bengal's Darjiling) should show a
majority of their pincodes MATCHED. If any of these show mostly
"Not Applicable," that's almost certainly a district naming mismatch
between the Atlas's spelling and your pincode file's spelling -- the
same class of bug as the Mumbai/Mumbai Suburban issue in cyclone.
"""

import csv
from collections import defaultdict

SCORES_FILE = r"C:\Users\New\Downloads\pincode_landslide_scores.csv"

# States where we EXPECT a meaningful share of districts to be in the
# 147-district list, based on the Atlas's own state coverage.
EXPECTED_HIGH_MATCH_STATES = {
    "KERALA", "UTTARAKHAND", "JAMMU AND KASHMIR", "HIMACHAL PRADESH",
    "SIKKIM", "ASSAM", "MEGHALAYA", "MANIPUR", "MIZORAM", "NAGALAND",
    "TRIPURA", "ARUNACHAL PRADESH", "KARNATAKA", "TAMIL NADU",
    "MAHARASHTRA", "GOA", "WEST BENGAL",
}

with open(SCORES_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
    rows = list(csv.DictReader(f))

by_state = defaultdict(lambda: {"matched": 0, "total": 0, "districts_unmatched": set()})
for r in rows:
    st = (r.get("state") or "").strip().upper()
    by_state[st]["total"] += 1
    if r["landslide_atlas_rank"]:
        by_state[st]["matched"] += 1
    else:
        by_state[st]["districts_unmatched"].add(r["district"])

print(f"{'State':<25}{'Matched':<10}{'Total':<10}{'Match %':<10}")
for st in sorted(EXPECTED_HIGH_MATCH_STATES):
    d = by_state.get(st, {"matched": 0, "total": 0, "districts_unmatched": set()})
    pct = 100 * d["matched"] / d["total"] if d["total"] else 0
    flag = "  <-- CHECK THIS" if pct < 20 and d["total"] > 0 else ""
    print(f"{st:<25}{d['matched']:<10}{d['total']:<10}{pct:.1f}%{flag}")

print("\nIf a state above shows a low match % and a flag, print its unmatched")
print("district names below to spot the naming mismatch:")
for st in sorted(EXPECTED_HIGH_MATCH_STATES):
    d = by_state.get(st)
    if d and d["total"] > 0 and (100 * d["matched"] / d["total"]) < 20:
        print(f"\n{st} unmatched districts (check these against DISTRICT_RANK spelling):")
        print(sorted(d["districts_unmatched"]))
