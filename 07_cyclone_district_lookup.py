"""
STEP -- Cyclone hazard lookup, by district.

SOURCE (real, peer-reviewed, publicly citable):
  Mohapatra, M. (2015). "Cyclone hazard proneness of districts of India."
  Journal of Earth System Science, 124(3), 515-526. Indian Academy of Sciences.
  https://www.ias.ac.in/public/Volumes/jess/124/03/0515-0526.pdf

  Built from official IMD cyclone track data (1891-2010), classifying 96
  districts -- 72 touching the coast + 24 within 100km of it -- into four
  categories based on frequency of cyclones, frequency of severe cyclones,
  wind strength, storm surge, and rainfall. This is a DISTRICT-level dataset
  (not a shapefile/polygon), so we join on district name rather than doing
  a spatial join like we did for seismic.

CATEGORIES (from the paper):
  P1 = Very highly prone   -> score 10 ("Extreme")
  P2 = Highly prone        -> score 7  ("High")
  P3 = Moderately prone    -> score 4  ("Moderate")
  P4 = Less prone          -> score 2  ("Low")

Districts NOT in this table were not assessed by the source at all -- they
are inland districts with no meaningful cyclone exposure. These get
score = None ("Not Applicable"), same honesty convention as every other
hazard we haven't built: excluded from any average, never filled in as
zero-risk, because "not assessed" and "assessed as zero risk" are different
claims and only one of them is true here.

KNOWN LIMITATION: the paper's district names are from ~2015 (pre-dating
some district splits in a few states). A handful of name variants are
mapped in DISTRICT_ALIASES below. If your matched count looks low, check
unmatched coastal-state districts first -- that's almost certainly a
naming mismatch, not a missing district.
"""

import csv

# ---- EDIT THESE FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_geocoded.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_cyclone_scores.csv"
# --------------------------------------

CATEGORY_SCORE = {
    "P1": (10, "Extreme (Very highly prone)"),
    "P2": (7, "High (Highly prone)"),
    "P3": (4, "Moderate (Moderately prone)"),
    "P4": (2, "Low (Less prone)"),
}

# Table 4 + Table 5 from Mohapatra (2015), district : category
# District names uppercased, matched against the govt pincode file's
# "district" column, also uppercased.
DISTRICT_CATEGORY = {
    # Table 4 -- districts touching the coast
    "NELLORE": "P1", "EAST GODAVARI": "P1", "KRISHNA": "P1",
    "BALASORE": "P1", "KENDRAPARA": "P1", "JAGATSINGHPUR": "P1", "BHADRAK": "P1",
    "YANAM": "P1", "SOUTH 24 PARGANAS": "P1", "SOUTH TWENTY FOUR PARGANAS": "P1",
    "MEDINIPUR": "P1", "PURBA MEDINIPUR": "P1", "PASCHIM MEDINIPUR": "P1",
    "SRIKAKULAM": "P2", "GUNTUR": "P2", "VISAKHAPATNAM": "P2", "WEST GODAVARI": "P2",
    "PRAKASAM": "P2", "VIZIANAGARAM": "P2", "DIU": "P2", "DAMAN": "P2",
    "NORTH GOA": "P2", "SOUTH GOA": "P2", "JUNAGADH": "P2", "AHMEDABAD": "P2",
    "KACHCHH": "P2", "KUTCH": "P2", "BHAVNAGAR": "P2", "JAMNAGAR": "P2",
    "ANAND": "P2", "NAVSARI": "P2", "SURAT": "P2", "BHARUCH": "P2",
    "VALSAD": "P2", "RAJKOT": "P2", "PORBANDAR": "P2", "LAKSHADWEEP": "P2",
    "THANE": "P2", "MUMBAI SUBURBAN": "P2", "RAIGARH": "P2", "RAIGAD": "P2",
    "GANJAM": "P2", "PURI": "P2", "KHORDHA": "P2", "KARAIKAL": "P2",
    "PUDUCHERRY": "P2", "PONDICHERRY": "P2", "PUDUKKOTTAI": "P2", "CUDDALORE": "P2",
    "KANCHIPURAM": "P2", "TIRUVARUR": "P2", "NAGAPPATTINAM": "P2", "CHENNAI": "P2",
    "THOOTHUKUDI": "P2", "TUTICORIN": "P2", "VILUPPURAM": "P2", "VILLUPURAM": "P2",
    "A AND N ISLANDS": "P3", "ANDAMAN AND NICOBAR ISLANDS": "P3", "VADODARA": "P3",
    "AMRELI": "P3", "UDUPI": "P3", "UTTARA KANNADA": "P3", "DAKSHINA KANNADA": "P3",
    "KOZHIKODE": "P3", "MALAPPURAM": "P3", "THRISSUR": "P3", "KANNUR": "P3",
    "KOLLAM": "P3", "ALAPPUZHA": "P3", "THIRUVANANTHAPURAM": "P3",
    "RATNAGIRI": "P3", "SINDHUDURG": "P3", "MAHE": "P3",
    "RAMANATHAPURAM": "P3", "TIRUNELVELI": "P3", "THANJAVUR": "P3",
    "TIRUVALLUR": "P3", "KANYAKUMARI": "P3",
    "KASARAGOD": "P4", "ERNAKULAM": "P4","MUMBAI": "P2",  # South Mumbai -- same coastal exposure as Mumbai Suburban, just a different district split in the govt file,

    # Table 5 -- districts within 100km of coast but not touching it
    "NORTH 24 PARGANAS": "P1", "NORTH TWENTY FOUR PARGANAS": "P1", "KOLKATA": "P1",
    "CHITTOOR": "P2", "HOWRAH": "P2",
    "DADRA AND NAGAR HAVELI": "P3", "MAYURBHANJ": "P3", "CUTTACK": "P3",
    "NAYAGARH": "P3", "GAJAPATI": "P3", "JAJPUR": "P3", "KEONJHAR": "P3",
    "HOOGHLY": "P3", "HOOGLY": "P3", "PURBA BARDHAMAN": "P3", "BARDHAMAN": "P3",
    "SURENDRANAGAR": "P4", "KHEDA": "P4", "WAYANAD": "P4", "PALAKKAD": "P4",
    "KOTTAYAM": "P4", "IDUKKI": "P4", "PATHANAMTHITTA": "P4", "DHENKANAL": "P4",
    "ARIYALUR": "P4", "TIRUVANNAMALAI": "P4", "SIVAGANGA": "P4",
}


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.DictReader(f))

    out = []
    matched, unmatched = 0, 0
    for r in rows:
        district_key = (r.get("district") or "").strip().upper()
        category = DISTRICT_CATEGORY.get(district_key)

        if category:
            score, band = CATEGORY_SCORE[category]
            matched += 1
        else:
            score, band = None, "Not Applicable (inland or not classified as cyclone-prone)"
            unmatched += 1

        out.append({
            "pincode": r["pincode"],
            "locality": r.get("locality", ""),
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "cyclone_category": category or "",
            "cyclone_score_0_10": score if score is not None else "",
            "cyclone_band": band,
            "source": "Mohapatra_2015_district_classification" if category else "not_assessed",
        })

    fieldnames = ["pincode", "locality", "district", "state", "cyclone_category",
                  "cyclone_score_0_10", "cyclone_band", "source"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"Done. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Matched to a cyclone-prone district: {matched}")
    print(f"Not applicable (inland / not in the 96-district study): {unmatched}")
    print("\nIf a coastal state (Gujarat, Maharashtra, Goa, Karnataka, Kerala, TN, AP, Odisha,")
    print("WB, Puducherry) has an unexpectedly high 'not applicable' share, check for a district")
    print("naming mismatch first -- add the variant to DISTRICT_ALIASES-style entries above.")


if __name__ == "__main__":
    main()
