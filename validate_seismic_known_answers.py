"""
Sanity check: compares your pincode_seismic_scores_accurate.csv output
against pincodes whose correct seismic zone is well-documented and
undisputed. If these don't match, something is wrong with the join
(likely a CRS mismatch or wrong column) -- fix that before trusting
the other 19,000+ rows.
"""

import csv

OUTPUT_FILE = r"C:\Users\New\Downloads\pincode_seismic_scores_accurate.csv"

# pincode: (expected zone, why it's undisputed)
KNOWN_ANSWERS = {
    "110001": ("IV", "New Delhi -- textbook Zone IV example"),
    "400001": ("III", "Mumbai -- textbook Zone III example"),
    "781001": ("V", "Guwahati, Assam -- entire NE India is Zone V"),
    "560001": ("II", "Bangalore -- stable Deccan plateau, Zone II"),
    "700001": ("III", "Kolkata -- Zone III"),
    "160001": ("IV", "Chandigarh -- Zone IV"),
}

with open(OUTPUT_FILE, newline="") as f:
    rows = {r["pincode"]: r for r in csv.DictReader(f)}

print(f"{'Pincode':<10}{'Expected':<10}{'Got':<10}{'Match?':<8}{'Note'}")
for pin, (expected, note) in KNOWN_ANSWERS.items():
    if pin in rows:
        got = rows[pin]["seismic_zone"]
        match = "YES" if got == expected else "NO -- CHECK THIS"
        print(f"{pin:<10}{expected:<10}{got:<10}{match:<8}{note}")
    else:
        print(f"{pin:<10}{expected:<10}{'NOT FOUND':<10}{'--':<8}{note}")
