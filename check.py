

import csv

with open(r"C:\Users\New\Downloads\pincode_master_geocoded.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):

        if row["pincode"] == "400001":

            print(row["district"])
import csv
from collections import Counter
with open(r"C:\Users\New\Downloads\pincode_seismic_scores_accurate.csv", newline="") as f:
    pins = [r["pincode"] for r in csv.DictReader(f)]
dupes = {p: c for p, c in Counter(pins).items() if c > 1}
print(f"Duplicate pincodes: {len(dupes)}")
print(list(dupes.items())[:10])