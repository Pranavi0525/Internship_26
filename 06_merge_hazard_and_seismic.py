"""
Merges the weather-based hazard scores (flood/heat/drought/warming)
and the seismic scores into ONE table per pincode. Run this after
both 03_collect_hazard_data.py and 05_seismic_zone_lookup.py have
produced their output files.

This does NOT replace 04_classify_pincode_risk.py -- that script
still does the percentile ranking on the weather hazards. Run this
merge AFTER classification, so the final file has everything:
weather hazard conclusions + seismic score, side by side.
"""

import csv

# ---- EDIT THESE FOR YOUR MACHINE ----
RISK_CONCLUSIONS_FILE = r"D:\Internship 2026\pincode_risk_conclusions.csv"   # output of step 4
SEISMIC_FILE = r"D:\Internship 2026\pincode_seismic_scores_accurate.csv"     # output of step 5
OUTPUT_FILE = r"D:\Internship 2026\pincode_final_combined.csv"
# --------------------------------------


def main():
    with open(SEISMIC_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        seismic = {r["pincode"]: r for r in csv.DictReader(f)}

    with open(RISK_CONCLUSIONS_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        risk_rows = list(csv.DictReader(f))

    merged = []
    missing_seismic = 0
    for row in risk_rows:
        pin = row["pincode"]
        s = seismic.get(pin)
        if s:
            row["seismic_zone"] = s["seismic_zone"]
            row["seismic_score_0_10"] = s["seismic_score_0_10"]
            row["seismic_band"] = s["seismic_band"]
            row["seismic_source"] = s["source"]
        else:
            row["seismic_zone"] = ""
            row["seismic_score_0_10"] = ""
            row["seismic_band"] = "No seismic data for this pincode"
            row["seismic_source"] = ""
            missing_seismic += 1
        merged.append(row)

    fieldnames = list(merged[0].keys())
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    print(f"Merged {len(merged)} pincodes -> {OUTPUT_FILE}")
    print(f"Pincodes with weather hazard scores but NO seismic match: {missing_seismic}")
    print("(Expected: seismic covers all 19,564 pincodes; weather hazards cover only")
    print(" however many you've run through step 3 so far -- this merge only outputs")
    print(" pincodes that HAVE weather scores, with seismic attached where available.)")


if __name__ == "__main__":
    main()
