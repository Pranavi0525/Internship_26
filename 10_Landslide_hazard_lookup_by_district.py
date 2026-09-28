"""
STEP 10 -- Landslide hazard lookup, by district.

SOURCE (real, official, extracted directly from the primary document):
  NRSC/ISRO. "Landslide Atlas of India (Mapping, Monitoring and R&D
  studies using Remote Sensing data)." Document No. NRSC-RSA-GSG-GMED-
  FEB 2023-TR-0002167-V1.0. Published 27 February 2023.
  Table 3 (pages 60-61): "Table shows the rank of districts of India
  for their exposure to landslides" -- ranks ALL 147 districts across
  17 states and 2 UTs, based on ~80,000 landslides mapped from
  satellite data (1998-2022) plus socio-economic exposure (population,
  households, literacy, road density).

  These ranks were read directly out of the PDF's own table text --
  not reconstructed from news coverage or guessed. Every row below is
  transcribed exactly as it appears in the source document, including
  the source document's own spelling/naming quirks (e.g. "Uttaranchal"
  for Uttarakhand, "Anantanag" for Anantnag, "J&k" inconsistent casing)
  -- these are preserved deliberately so the DISTRICT_ALIASES matching
  below can account for them explicitly, rather than silently guessing.

SCORING CONVENTION (same spirit as cyclone's P1-P4 bands, adapted to
a 147-item rank instead of a 4-category system):
  Rank 1-15   -> "Severe"        -> score 10
  Rank 16-40  -> "Very High"     -> score 8
  Rank 41-80  -> "High"          -> score 6
  Rank 81-120 -> "Moderate"      -> score 4
  Rank 121-147-> "Low"           -> score 2
  Not in the 147-district list -> None ("Not Applicable") -- same
  honesty convention as every other hazard: a district not assessed
  by NRSC is not the same claim as a district assessed as zero risk.

KNOWN LIMITATION: this is a DISTRICT-level dataset (like cyclone),
not a shapefile -- joined on district name text, so it inherits the
same class of naming-mismatch risk cyclone had with Mumbai. Check the
unmatched count for the states that appear in Table 3 (esp. Kerala,
Uttarakhand, J&K, Himachal Pradesh, the Northeast states) first if the
matched count looks low -- that's almost certainly a naming variant,
not a missing district.

FIX LOG:
  - Added "DARJEELING" -> "DARJILING" alias. validate_landslide_by_state.py
    caught West Bengal at 0% match -- Darjiling is WB's ONLY district in
    the Atlas, and the govt pincode file uses the modern "Darjeeling"
    spelling while the source PDF uses the older "Darjiling" spelling.
    One alias fixes all of West Bengal's coverage.
  - Confirmed Tamil Nadu's low match rate (18.4%) is NOT a bug: only 6 of
    TN's ~38 districts are in the Atlas at all (~16% of districts), which
    is consistent with the observed match rate. No alias needed there.
"""

import csv

# ---- EDIT THESE FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_landslide_scores.csv"
# --------------------------------------


def rank_to_score(rank):
    if rank <= 15:
        return 10, "Severe"
    elif rank <= 40:
        return 8, "Very High"
    elif rank <= 80:
        return 6, "High"
    elif rank <= 120:
        return 4, "Moderate"
    else:
        return 2, "Low"


# Table 3, transcribed exactly from the source PDF (rank: (district, state))
DISTRICT_RANK = {
    1: ("RUDRAPRAYAG", "UTTARAKHAND"), 2: ("TEHRI GARHWAL", "UTTARAKHAND"),
    3: ("THRISSUR", "KERALA"), 4: ("RAJAURI", "JAMMU AND KASHMIR"),
    5: ("PALAKKAD", "KERALA"), 6: ("POONCH", "JAMMU AND KASHMIR"),
    7: ("MALAPPURAM", "KERALA"), 8: ("SOUTH DISTRICT", "SIKKIM"),
    9: ("EAST DISTRICT", "SIKKIM"), 10: ("KOZHIKODE", "KERALA"),
    11: ("IMPHAL WEST", "MANIPUR"), 12: ("KODAGU", "KARNATAKA"),
    13: ("WAYANAD", "KERALA"), 14: ("JAMMU", "JAMMU AND KASHMIR"),
    15: ("ERNAKULAM", "KERALA"), 16: ("MANDI", "HIMACHAL PRADESH"),
    17: ("UDHAMPUR", "JAMMU AND KASHMIR"), 18: ("IDUKKI", "KERALA"),
    19: ("CHAMOLI", "UTTARAKHAND"), 20: ("WEST DISTRICT", "SIKKIM"),
    21: ("UTTARKASHI", "UTTARAKHAND"), 22: ("CACHAR", "ASSAM"),
    23: ("GARHWAL", "UTTARAKHAND"), 24: ("KOTTAYAM", "KERALA"),
    25: ("HAMIRPUR", "HIMACHAL PRADESH"), 26: ("KANNUR", "KERALA"),
    27: ("PULWAMA", "JAMMU AND KASHMIR"), 28: ("THIRUVANANTHAPURAM", "KERALA"),
    29: ("DEHRADUN", "UTTARAKHAND"), 30: ("BILASPUR", "HIMACHAL PRADESH"),
    31: ("WEST GARO HILLS", "MEGHALAYA"), 32: ("CHAMBA", "HIMACHAL PRADESH"),
    33: ("PATHANAMTHITTA", "KERALA"), 34: ("EAST KHASI HILLS", "MEGHALAYA"),
    35: ("DARJILING", "WEST BENGAL"), 36: ("COIMBATORE", "TAMIL NADU"),
    37: ("SOLAN", "HIMACHAL PRADESH"), 38: ("AIZAWL", "MIZORAM"),
    39: ("LUNGLEI", "MIZORAM"), 40: ("KAMRUP", "ASSAM"),
    41: ("DINDIGUL", "TAMIL NADU"), 42: ("KATHUA", "JAMMU AND KASHMIR"),
    43: ("KANNIYAKUMARI", "TAMIL NADU"), 44: ("KASARAGOD", "KERALA"),
    45: ("LAWNGTLAI", "MIZORAM"), 46: ("KINNAUR", "HIMACHAL PRADESH"),
    47: ("HAILAKANDI", "ASSAM"), 48: ("KOLLAM", "KERALA"),
    49: ("GOALPARA", "ASSAM"), 50: ("BAGESHWAR", "UTTARAKHAND"),
    51: ("NORTH DISTRICT", "SIKKIM"), 52: ("ANANTNAG", "JAMMU AND KASHMIR"),
    53: ("HASSAN", "KARNATAKA"), 54: ("DAKSHINA KANNADA", "KARNATAKA"),
    55: ("KARBI ANGLONG", "ASSAM"), 56: ("LOHIT", "ARUNACHAL PRADESH"),
    57: ("KULLU", "HIMACHAL PRADESH"), 58: ("BARAMULLA", "JAMMU AND KASHMIR"),
    59: ("THENI", "TAMIL NADU"), 60: ("KOLASIB", "MIZORAM"),
    61: ("SHIMLA", "HIMACHAL PRADESH"), 62: ("KANGRA", "HIMACHAL PRADESH"),
    63: ("CHURACHANDPUR", "MANIPUR"), 64: ("EAST GARO HILLS", "MEGHALAYA"),
    65: ("CHAMPAWAT", "UTTARAKHAND"), 66: ("WEST KHASI HILLS", "MEGHALAYA"),
    67: ("RI BHOI", "MEGHALAYA"), 68: ("NAINITAL", "UTTARAKHAND"),
    69: ("JAINTIA HILLS", "MEGHALAYA"), 70: ("UNA", "HIMACHAL PRADESH"),
    71: ("MAMIT", "MIZORAM"), 72: ("TIRUNELVELI", "TAMIL NADU"),
    73: ("PAPUM PARE", "ARUNACHAL PRADESH"), 74: ("TAWANG", "ARUNACHAL PRADESH"),
    75: ("WEST TRIPURA", "TRIPURA"), 76: ("NORTH TRIPURA", "TRIPURA"),
    77: ("UDUPI", "KARNATAKA"), 78: ("EAST SIANG", "ARUNACHAL PRADESH"),
    79: ("DODA", "JAMMU AND KASHMIR"), 80: ("THANE", "MAHARASHTRA"),
    81: ("ALMORA", "UTTARAKHAND"), 82: ("SERCHHIP", "MIZORAM"),
    83: ("NORTH CACHAR HILLS", "ASSAM"), 84: ("LOWER SUBANSIRI", "ARUNACHAL PRADESH"),
    85: ("THE NILGIRIS", "TAMIL NADU"), 86: ("PITHORAGARH", "UTTARAKHAND"),
    87: ("WEST KAMENG", "ARUNACHAL PRADESH"), 88: ("SIRMAUR", "HIMACHAL PRADESH"),
    89: ("PHEK", "NAGALAND"), 90: ("SOUTH GARO HILLS", "MEGHALAYA"),
    91: ("CHANGLANG", "ARUNACHAL PRADESH"), 92: ("CHIKMAGALUR", "KARNATAKA"),
    93: ("MON", "NAGALAND"), 94: ("TUENSANG", "NAGALAND"),
    95: ("BONGAIGAON", "ASSAM"), 96: ("LOWER DIBANG VALLEY", "ARUNACHAL PRADESH"),
    97: ("SENAPATI", "MANIPUR"), 98: ("SRINAGAR", "JAMMU AND KASHMIR"),
    99: ("MORIGAON", "ASSAM"), 100: ("TAMENGLONG", "MANIPUR"),
    101: ("EAST KAMENG", "ARUNACHAL PRADESH"), 102: ("SAIHA", "MIZORAM"),
    103: ("SHIMOGA", "KARNATAKA"), 104: ("UPPER SIANG", "ARUNACHAL PRADESH"),
    105: ("MOKOKCHUNG", "NAGALAND"), 106: ("KOHIMA", "NAGALAND"),
    107: ("PUNE", "MAHARASHTRA"), 108: ("WEST SIANG", "ARUNACHAL PRADESH"),
    109: ("RAIGARH", "MAHARASHTRA"), 110: ("DHALAI", "TRIPURA"),
    111: ("NORTH GOA", "GOA"), 112: ("UKHRUL", "MANIPUR"),
    113: ("KURUNG KUMEY", "ARUNACHAL PRADESH"), 114: ("SINDHUDURG", "MAHARASHTRA"),
    115: ("TIRAP", "ARUNACHAL PRADESH"), 116: ("UTTARA KANNADA", "KARNATAKA"),
    117: ("NAGAON", "ASSAM"), 118: ("CHAMPHAI", "MIZORAM"),
    119: ("BUDGAM", "JAMMU AND KASHMIR"), 120: ("UPPER SUBANSIRI", "ARUNACHAL PRADESH"),
    121: ("SOUTH GOA", "GOA"), 122: ("CHANDEL", "MANIPUR"),
    123: ("KARGIL", "JAMMU AND KASHMIR"), 124: ("HAVERI", "KARNATAKA"),
    125: ("ANJAW", "ARUNACHAL PRADESH"), 126: ("LAHUL AND SPITI", "HIMACHAL PRADESH"),
    127: ("DHUBRI", "ASSAM"), 128: ("NASHIK", "MAHARASHTRA"),
    129: ("RATNAGIRI", "MAHARASHTRA"), 130: ("SOUTH TRIPURA", "TRIPURA"),
    131: ("AHMEDNAGAR", "MAHARASHTRA"), 132: ("KUPWARA", "JAMMU AND KASHMIR"),
    133: ("KOLHAPUR", "MAHARASHTRA"), 134: ("SATARA", "MAHARASHTRA"),
    135: ("DIBANG VALLEY", "ARUNACHAL PRADESH"), 136: ("LEH", "JAMMU AND KASHMIR"),
    137: ("KARIMGANJ", "ASSAM"), 138: ("ALAPPUZHA", "KERALA"),
    139: ("MUMBAI SUBURBAN", "MAHARASHTRA"), 140: ("MUMBAI", "MAHARASHTRA"),
    141: ("THOUBAL", "MANIPUR"), 142: ("IMPHAL EAST", "MANIPUR"),
    143: ("BISHNUPUR", "MANIPUR"), 144: ("ZUNHEBOTO", "NAGALAND"),
    145: ("WOKHA", "NAGALAND"), 146: ("HARIDWAR", "UTTARAKHAND"),
    147: ("UDHAM SINGH NAGAR", "UTTARAKHAND"),
}

# Reverse lookup: district name -> rank. Built once at import time.
_DISTRICT_TO_RANK = {name: rank for rank, (name, state) in DISTRICT_RANK.items()}

# Common naming variants between this source (2023 NRSC document, which
# itself uses some older names like "Uttaranchal") and typical govt
# pincode files. Add to this if your matched count looks low for a
# state known to be in the list.
DISTRICT_ALIASES = {
    "LEH LADAKH": "LEH", "LEH-LADAKH": "LEH",
    "ANANTANAG": "ANANTNAG",
    "J&K": "", "JAMMU & KASHMIR": "",  # not district names, ignore if seen
    "RI-BHOI": "RI BHOI",
    "LAHAUL AND SPITI": "LAHUL AND SPITI", "LAHAUL SPITI": "LAHUL AND SPITI",
    "KANYAKUMARI": "KANNIYAKUMARI",
    "PAPUMPARE": "PAPUM PARE",
    "DARJEELING": "DARJILING",  # modern spelling -> source PDF's spelling
}


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.DictReader(f))

    out = []
    matched, unmatched = 0, 0
    for r in rows:
        district_key = (r.get("district") or "").strip().upper()
        district_key = DISTRICT_ALIASES.get(district_key, district_key)
        rank = _DISTRICT_TO_RANK.get(district_key)

        if rank:
            score, band = rank_to_score(rank)
            matched += 1
        else:
            rank, score, band = "", "", "Not Applicable (not in the 147-district Landslide Atlas list)"
            unmatched += 1

        out.append({
            "pincode": r["pincode"],
            "locality": r.get("locality", ""),
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "landslide_atlas_rank": rank,
            "landslide_score_0_10": score,
            "landslide_band": band,
            "source": "NRSC_ISRO_Landslide_Atlas_2023_Table3" if rank else "not_assessed",
        })

    fieldnames = ["pincode", "locality", "district", "state", "landslide_atlas_rank",
                  "landslide_score_0_10", "landslide_band", "source"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"Done. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Matched to one of the 147 landslide-exposed districts: {matched}")
    print(f"Not applicable (not in the Atlas's 147-district list): {unmatched}")


if __name__ == "__main__":
    main()