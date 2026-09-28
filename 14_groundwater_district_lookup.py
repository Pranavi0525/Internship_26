"""
STEP 14 -- Groundwater depletion, district/assessment-unit lookup.

SAME PATTERN AS 07_cyclone_district_lookup.py AND
10_Landslide_hazard_lookup_by_district.py: a real, transcribed table
from an official government source, joined on district/assessment-unit
name -- NOT a synthetic or invented dataset.

STATUS: THIS IS A SCAFFOLD. The scoring logic, matching logic, honesty
conventions, and output structure are all ready and consistent with the
rest of the pipeline. What's MISSING is the actual data: fill in
ASSESSMENT_UNIT_CATEGORY below once you have the real CGWB Dynamic
Groundwater Resource Assessment report (2024, or 2023 if 2024 isn't
out yet).

HOW TO GET THE REAL SOURCE:
  Search "CGWB Dynamic Groundwater Resource Assessment 2024 report pdf"
  or check ingres.iith.ac.in / cgwb.gov.in directly. The report contains
  a ~6,750-row table of assessment units (roughly block/taluk-level,
  finer than district in most states) each classified as:
    Safe / Semi-Critical / Critical / Over-Exploited / Saline
  plus a numeric "stage of extraction" percentage.

  Upload that report (or the specific table/appendix) the same way you
  did the Landslide Atlas PDF, and the real ASSESSMENT_UNIT_CATEGORY
  dict below gets filled in by transcription, not estimation.

WHY ASSESSMENT-UNIT, NOT DISTRICT: CGWB's actual reporting unit is
typically the block/taluk (sub-district), which is MORE granular than
the district-level joins used for cyclone/landslide -- but the pincode
file's district column is our only reliable join key without a
block-to-pincode mapping. If the report is only usable at assessment-
unit granularity, this script's matching key may need to become
"district + block name" rather than "district" alone -- flag this once
you see the real report's structure, since it may need slightly
different join logic than cyclone/landslide had.

SCORING CONVENTION (same 0-10 scale spirit as every other hazard):
  Over-Exploited -> score 10 ("Extreme" -- more water withdrawn annually
                    than recharges naturally)
  Critical       -> score 7  ("High")
  Semi-Critical  -> score 4  ("Moderate")
  Safe           -> score 2  ("Low")
  Saline         -> handled separately -- salinity is a water-quality
                    issue, not a depletion-rate issue; flag it as its
                    own category rather than forcing it onto the same
                    0-10 depletion scale, since a "safe" saline aquifer
                    and a "critical" saline aquifer are different claims
                    the source report may or may not distinguish.
  Not in the report's list -> None ("Not Applicable" / not assessed)
"""

import csv

# ---- EDIT THESE FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_groundwater_scores.csv"
# --------------------------------------

CATEGORY_SCORE = {
    "OVER-EXPLOITED": (10, "Extreme (Over-Exploited -- extraction exceeds natural recharge)"),
    "CRITICAL": (7, "High (Critical)"),
    "SEMI-CRITICAL": (4, "Moderate (Semi-Critical)"),
    "SAFE": (2, "Low (Safe)"),
    "SALINE": (None, "Saline -- water-quality issue, not depletion rate; see docstring"),
}

# ---- FILL THIS IN FROM THE REAL CGWB REPORT ----
# Format: "DISTRICT NAME": "CATEGORY"  (or, if the real report requires
# assessment-unit/block granularity: "DISTRICT|BLOCK": "CATEGORY" --
# decide once you see the actual report structure).
#
# PLACEHOLDER ONLY -- these are NOT real CGWB figures, they exist purely
# to prove the script runs end-to-end. DELETE this placeholder block
# entirely once real data is transcribed in; do not present output from
# this placeholder as real data to anyone.
ASSESSMENT_UNIT_CATEGORY = {
    # "EXAMPLE DISTRICT": "OVER-EXPLOITED",
}

PLACEHOLDER_DATA_ACTIVE = True   # set False once ASSESSMENT_UNIT_CATEGORY has real data


def main():
    if PLACEHOLDER_DATA_ACTIVE:
        print("=" * 70)
        print("WARNING: PLACEHOLDER_DATA_ACTIVE = True")
        print("ASSESSMENT_UNIT_CATEGORY has no real CGWB data yet.")
        print("Every pincode will be written as 'Not Applicable (no data)'.")
        print("This run is only useful to confirm the script itself works --")
        print("do NOT treat pincode_groundwater_scores.csv as real until")
        print("real data is transcribed in and this flag is set to False.")
        print("=" * 70)

    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.DictReader(f))

    out = []
    matched, unmatched = 0, 0
    for r in rows:
        district_key = (r.get("district") or "").strip().upper()
        category = None if PLACEHOLDER_DATA_ACTIVE else ASSESSMENT_UNIT_CATEGORY.get(district_key)

        if category:
            score, band = CATEGORY_SCORE.get(category, (None, f"Unrecognized category '{category}' -- check spelling"))
            matched += 1
        else:
            score, band = None, "Not Applicable (not assessed, or placeholder data active)"
            unmatched += 1

        out.append({
            "pincode": r["pincode"],
            "locality": r.get("locality", ""),
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "groundwater_category": category or "",
            "groundwater_score_0_10": score if score is not None else "",
            "groundwater_band": band,
            "source": "CGWB_Dynamic_Groundwater_Assessment" if category else "not_assessed_or_placeholder",
        })

    fieldnames = ["pincode", "locality", "district", "state", "groundwater_category",
                  "groundwater_score_0_10", "groundwater_band", "source"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"\nDone. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Matched to a real assessment category: {matched}")
    print(f"Not applicable / placeholder: {unmatched}")


if __name__ == "__main__":
    main()
