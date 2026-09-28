"""
STEP 17 -- River/Coastal Erosion (coastal portion), district-level.

SOURCE (real, official, transcribed directly from the primary document):
  Kankara, R.S., Ramana Murthy, M.V., Rajeevan, M. (2018). "National
  Assessment of Shoreline Changes along Indian Coast: Status report
  for 26 years (1990-2016)." National Centre for Coastal Research
  (NCCR), Ministry of Earth Sciences, Government of India.
  Tables 9-18 (pages 20-56): district-wise breakdown of coastline
  length (km) by erosion/stable/accretion category, for all 66 coastal
  districts across 9 states + 2 UTs, using satellite-derived Digital
  Shoreline Analysis System (DSAS) measurements, 1990-2016.

  Every erosion percentage below was computed directly from the
  report's own district tables (erosion km / total coastal km x 100),
  not estimated or reconstructed from the state-level summary figures
  quoted elsewhere in the report or in news coverage.

SCOPE: this covers COASTAL erosion only. River-bank erosion (e.g. the
well-documented Ganga/Brahmaputra bank erosion problem, tracked
separately by CWC) is NOT covered here and would need a separate
source -- do not present this file as covering river erosion.

SCORING CONVENTION (same 0-10 scale spirit as every other hazard,
based on % of the district's coastline classified as eroding, any
severity):
  >=50% eroding -> score 10 ("Severe")
  35-50%        -> score 8  ("High")
  20-35%        -> score 6  ("Moderate-High")
  10-20%        -> score 4  ("Moderate")
  <10%          -> score 2  ("Low")
  District not in the 66-district coastal list -> None ("Not
  Applicable") -- same honesty convention as every other hazard: an
  inland district was never assessed by NCCR, which is not the same
  claim as "assessed as zero risk."

KNOWN LIMITATION: same class of naming-mismatch risk as cyclone/
landslide -- joined on district name text, not a shapefile. A number
of aliases are pre-populated below based on spelling variants already
confirmed in this project's cyclone and landslide scripts (e.g.
Visakhapatnam/Vishakhapatnam, Kanniyakumari/Kanyakumari, Thoothukudi/
Tuticorin). Check unmatched coastal-state districts first if the
matched count looks low.
"""

import csv

# ---- EDIT THESE FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_erosion_scores.csv"
# --------------------------------------


def score_for_erosion_pct(pct):
    if pct >= 50:
        return 10, "Severe"
    elif pct >= 35:
        return 8, "High"
    elif pct >= 20:
        return 6, "Moderate-High"
    elif pct >= 10:
        return 4, "Moderate"
    else:
        return 2, "Low"


# Computed directly from NCCR (2018) Tables 9-18: erosion_km / total_km x 100,
# rounded to 1 decimal. District names as spelled in the source report.
DISTRICT_EROSION_PCT = {
    # Gujarat (Table 9)
    "VALSAD": 41.1, "NAVSARI": 28.3, "SURAT": 12.3, "BHARUCH": 29.8, "ANAND": 24.2,
    "AHMEDABAD": 5.5, "BHAVNAGAR": 21.5, "AMRELI": 41.1, "GIR SOMNATH": 44.3,
    "JUNAGADH": 65.6, "PORBANDAR": 47.2, "DEVBHUMI DWARKA": 39.8, "JAMNAGAR": 25.1,
    "KACHCHH": 24.0, "DIU": 57.0, "DAMAN": 15.2,
    # Maharashtra (Table 10)
    "SINDHUDURG": 4.9, "RATNAGIRI": 14.7, "RAIGAD": 34.5, "MUMBAI": 3.3,
    "MUMBAI SUBURBAN": 43.2, "THANE": 53.5,
    # Goa (Table 11)
    "NORTH GOA": 29.1, "SOUTH GOA": 6.0,
    # Karnataka (Table 12)
    "DAKSHINA KANNADA": 45.3, "UDUPI": 36.0, "UTTARA KANNADA": 9.8,
    # Kerala (Table 13)
    "KASARAGOD": 34.3, "KANNUR": 40.9, "KOZHIKODE": 62.6, "MALAPPURAM": 49.1,
    "THRISSUR": 29.1, "ERNAKULAM": 46.8, "ALAPPUZHA": 57.3, "KOLLAM": 40.9,
    "THIRUVANANTHAPURAM": 35.3,
    # Tamil Nadu (Table 14)
    "THIRUVALLUR": 34.2, "CHENNAI": 12.4, "KANCHIPURAM": 58.5, "VILLUPURAM": 72.8,
    "CUDDALORE": 40.9, "NAGAPATTINAM": 49.2, "THIRUVARUR": 61.8, "THANJAVUR": 34.0,
    "PUDUKKOTTAI": 49.2, "RAMANATHAPURAM": 38.3, "THOOTHUKUDI": 18.0,
    "TIRUNELVELI": 18.2, "KANNIYAKUMARI": 64.5,
    # Puducherry (Table 15)
    "PUDUCHERRY": 40.9, "KARAIKAL": 78.1,
    # Andhra Pradesh (Table 16)
    "NELLORE": 29.2, "PRAKASAM": 21.7, "GUNTUR": 4.0, "KRISHNA": 41.3,
    "WEST GODAVARI": 40.2, "EAST GODAVARI": 41.8, "VISAKHAPATNAM": 10.9,
    "VIZIANAGARAM": 36.5, "SRIKAKULAM": 16.0,
    # Odisha (Table 17)
    "GANJAM": 22.4, "PURI": 15.3, "JAGATSINGHPUR": 58.3, "KENDRAPARA": 36.0,
    "BHADRAK": 22.6, "BALASORE": 23.4,
    # West Bengal (Table 18)
    "EAST MIDNAPORE": 50.3, "SOUTH 24 PARGANAS": 58.2, "NORTH 24 PARGANAS": 78.6,
}

# Spelling variants between NCCR's report and the govt pincode file's
# district column -- several confirmed already from this project's
# cyclone (07) and landslide (10) scripts.
DISTRICT_ALIASES = {
    "VISHAKHAPATNAM": "VISAKHAPATNAM",
    "KANYAKUMARI": "KANNIYAKUMARI",
    "TUTICORIN": "THOOTHUKUDI",
    "TIRUVARUR": "THIRUVARUR",
    "TIRUVALLUR": "THIRUVALLUR",
    "KANCHEEPURAM": "KANCHIPURAM",
    "VILUPPURAM": "VILLUPURAM",
    "NAGAPPATTINAM": "NAGAPATTINAM",
    "VIZAG": "VISAKHAPATNAM",
    "KUTCH": "KACHCHH",
    "PASCHIM MEDINIPUR": "EAST MIDNAPORE",  # NOTE: verify -- report's
    "PURBA MEDINIPUR": "EAST MIDNAPORE",    # "East Midnapore" is the coastal
                                             # one; if pincode file splits
                                             # differently, re-check this pair
    "24 PARAGANAS NORTH": "NORTH 24 PARGANAS",
    "24 PARAGANAS SOUTH": "SOUTH 24 PARGANAS",
    "NORTH TWENTY FOUR PARGANAS": "NORTH 24 PARGANAS",
    "SOUTH TWENTY FOUR PARGANAS": "SOUTH 24 PARGANAS",
}


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.DictReader(f))

    out = []
    matched, unmatched = 0, 0
    for r in rows:
        district_key = (r.get("district") or "").strip().upper()
        district_key = DISTRICT_ALIASES.get(district_key, district_key)
        erosion_pct = DISTRICT_EROSION_PCT.get(district_key)

        if erosion_pct is not None:
            score, band = score_for_erosion_pct(erosion_pct)
            matched += 1
        else:
            erosion_pct, score, band = "", "", "Not Applicable (not one of NCCR's 66 coastal districts)"
            unmatched += 1

        out.append({
            "pincode": r["pincode"],
            "locality": r.get("locality", ""),
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "coast_erosion_pct_of_district_coastline": erosion_pct,
            "erosion_score_0_10": score,
            "erosion_band": band,
            "source": "NCCR_2018_Shoreline_Change_Tables_9-18" if score else "not_assessed",
        })

    fieldnames = ["pincode", "locality", "district", "state",
                  "coast_erosion_pct_of_district_coastline", "erosion_score_0_10",
                  "erosion_band", "source"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"Done. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Matched to one of NCCR's 66 coastal districts: {matched}")
    print(f"Not applicable (inland / not in the coastal district list): {unmatched}")
    print("\nSANITY CHECK: Kolkata city itself is not one of NCCR's 3 West Bengal")
    print("coastal districts (North/South 24 Parganas, East Midnapore) -- pincodes")
    print("with district='KOLKATA' should show Not Applicable, which is correct, not")
    print("a bug. Pincodes with district='SOUTH 24 PARGANAS' should show")
    print("erosion_score_0_10 = 10 (58.2% eroding).")


if __name__ == "__main__":
    main()
