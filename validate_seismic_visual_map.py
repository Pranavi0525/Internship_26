"""
Plots every pincode as a dot, colored by seismic zone, so you can
visually compare against the real BIS map shape. What you SHOULD see:
  - Red/orange cluster along the Himalayan arc + all of NE India (Zone V)
  - A band across northern India (Delhi, Bihar, Gujarat's Kutch corner)
    in orange/yellow (Zone IV)
  - Most of peninsular India (Karnataka, Telangana, etc.) in green (Zone II)
If instead you see random speckling with no geographic pattern, or
one solid color everywhere, the join is wrong -- don't trust the data
yet if that's what you see.
"""

import csv
import matplotlib.pyplot as plt

INPUT_FILE = r"C:\Users\New\Downloads\pincode_master_geocoded.csv"
SCORES_FILE = r"C:\Users\New\Downloads\pincode_seismic_scores_accurate.csv"

COLOR_MAP = {"II": "#4F9D6E", "III": "#C9A227", "IV": "#D9843A", "V": "#D9756B", "UNMATCHED": "#888888"}

with open(SCORES_FILE, newline="") as f:
    scores = {r["pincode"]: r["seismic_zone"] for r in csv.DictReader(f)}

with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
    rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]

lons, lats, colors = [], [], []
for r in rows:
    zone = scores.get(r["pincode"], "UNMATCHED")
    lons.append(float(r["longitude"]))
    lats.append(float(r["latitude"]))
    colors.append(COLOR_MAP.get(zone, "#888888"))

plt.figure(figsize=(8, 9))
plt.scatter(lons, lats, c=colors, s=2, alpha=0.6)
plt.title("Pincodes colored by seismic zone -- eyeball check against known BIS map")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=c, markersize=8, label=z)
           for z, c in COLOR_MAP.items()]
plt.legend(handles=handles, title="Zone")
plt.savefig("seismic_zone_map_check.png", dpi=150, bbox_inches="tight")
print("Saved seismic_zone_map_check.png -- open it and look for the Himalayan/NE red cluster.")
plt.show()
