"""
Sanity check for pincode_cyclone_scores.csv, same spirit as
validate_seismic_known_answers.py: compare against pincodes whose
correct cyclone classification is undisputed.

NOTE ON MUMBAI: India Post's district field for Mumbai pincodes can be
"MUMBAI" (city/South Mumbai) or "MUMBAI SUBURBAN" depending on the exact
pincode. The source paper only classifies "Mumbai Suburban" as coastal
(P2). If pincode 400001 shows as Not Applicable, check whether its district
field says "MUMBAI" rather than "MUMBAI SUBURBAN" -- that's a real naming
gap to fix in DISTRICT_CATEGORY, not a bug in the join logic itself.
"""

import csv

OUTPUT_FILE = r"C:\Users\New\Downloads\pincode_cyclone_scores.csv"

KNOWN_ANSWERS = {
    "110001": ("Not Applicable", "New Delhi -- landlocked, correctly excluded from the 96-district study"),
    "700001": ("P1", "Kolkata -- one of the 12 'very highly prone' districts in the source paper"),
    "600001": ("P2", "Chennai -- classified 'highly prone' (P2) in the source paper"),
    "560001": ("Not Applicable", "Bangalore Urban -- inland, Karnataka's only coastal districts are Udupi/Uttara Kannada/Dakshina Kannada"),
    "781001": ("Not Applicable", "Guwahati, Assam -- not one of the 13 cyclone-affected coastal states/UTs"),
    "400001": ("P2 (or check district name)", "Mumbai -- see NOTE above if this shows Not Applicable"),
}

with open(OUTPUT_FILE, newline="", encoding="utf-8-sig") as f:
    rows = {r["pincode"]: r for r in csv.DictReader(f)}

print(f"{'Pincode':<10}{'Expected':<28}{'Got category':<15}{'Got band'}")
for pin, (expected, note) in KNOWN_ANSWERS.items():
    if pin in rows:
        got_cat = rows[pin]["cyclone_category"] or "Not Applicable"
        got_band = rows[pin]["cyclone_band"]
        print(f"{pin:<10}{expected:<28}{got_cat:<15}{got_band}")
        print(f"           -> {note}")
    else:
        print(f"{pin:<10}{'NOT FOUND IN FILE':<28}")
