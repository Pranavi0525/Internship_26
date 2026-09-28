import csv
from collections import Counter

OUTPUT_FILE = r"C:\Users\New\Downloads\pincode_seismic_scores_accurate.csv"

with open(OUTPUT_FILE, newline="") as f:
    rows = list(csv.DictReader(f))

zone_counts = Counter(r["seismic_zone"] for r in rows)
source_counts = Counter(r["source"] for r in rows)

total = len(rows)
print(f"Total pincodes: {total}\n")

print("Zone distribution (compare loosely to published land-area %: V~11%, IV~18%, III~30%, II~rest):")
for zone, count in sorted(zone_counts.items()):
    print(f"  Zone {zone}: {count} ({100*count/total:.1f}%)")

print("\nSource breakdown:")
for source, count in source_counts.items():
    print(f"  {source}: {count} ({100*count/total:.1f}%)")

# Flag any state where 100% of pincodes fell back (suggests that state's
# shapefile polygons might all be in the unlabeled 156 -- worth knowing)
by_state_source = {}
for r in rows:
    by_state_source.setdefault(r["state"], []).append(r["source"])

print("\nStates where MOST pincodes used the fallback (real shapefile coverage was thin there):")
for state, sources in sorted(by_state_source.items()):
    fallback_pct = 100 * sum(1 for s in sources if "fallback" in s) / len(sources)
    if fallback_pct > 50:
        print(f"  {state}: {fallback_pct:.0f}% fallback ({len(sources)} pincodes)")
