"""
Sanity check for pincode_cyclone_point_scores.csv -- same discipline as
validate_seismic_known_answers.py and validate_cyclone_known_answers.py.

Checks:
  1. Known-answer test: pincodes with undisputed expected outcomes.
  2. Distribution by state: coastal states should show high match rates,
     landlocked states should show ~0%. If a landlocked state shows a
     high percentage, that's the same class of bug we just fixed
     (track geometry sweeping in places it shouldn't) -- possibly not
     fully fixed yet, or a different storm's track genuinely doing
     something unusual worth checking by hand.
"""

import csv
from collections import defaultdict

SCORES_FILE = r"C:\Users\New\Downloads\pincode_cyclone_point_scores.csv"

KNOWN_ANSWERS = {
    "751001": ("nonzero frequency, HIGH max wind", "Paradip, Odisha -- hit by the 1999 Odisha super cyclone and Cyclone Fani (2019)"),
    "110001": ("0 years affected", "New Delhi -- landlocked, ~1000km+ from any coast"),
    "600001": ("nonzero frequency", "Chennai -- hit by multiple Bay of Bengal cyclones historically"),
    "560001": ("0 years affected", "Bangalore -- inland Deccan plateau, no coast nearby"),
}

# States that should show ~0% affected if the fix worked -- landlocked,
# nowhere near any coast, no plausible cyclone track within 100km.
LANDLOCKED_STATES = {
    "DELHI", "HARYANA", "PUNJAB", "RAJASTHAN", "MADHYA PRADESH",
    "CHHATTISGARH", "JHARKHAND", "UTTAR PRADESH", "UTTARAKHAND",
    "HIMACHAL PRADESH", "PUNJAB", "CHANDIGARH",
}

with open(SCORES_FILE, newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
    by_pin = {r["pincode"]: r for r in rows}

print("=== Known-answer check ===")
print(f"{'Pincode':<10}{'Expected':<40}{'Got freq%':<12}{'Got wind(kt)':<14}{'Note'}")
for pin, (expected, note) in KNOWN_ANSWERS.items():
    r = by_pin.get(pin)
    if not r:
        print(f"{pin:<10}NOT FOUND")
        continue
    freq = r["cyclone_point_frequency_pct_years"]
    wind = r["cyclone_point_intensity_max_wind_kt"] or "—"
    print(f"{pin:<10}{expected:<40}{freq:<12}{wind:<14}{note}")

print("\n=== Landlocked-state check (should all be ~0%) ===")
by_state = defaultdict(lambda: {"affected": 0, "total": 0})
for r in rows:
    st = (r.get("state") or "").strip().upper()
    by_state[st]["total"] += 1
    if float(r["cyclone_point_years_affected"] or 0) > 0:
        by_state[st]["affected"] += 1

for st in sorted(LANDLOCKED_STATES):
    d = by_state.get(st)
    if not d or d["total"] == 0:
        continue
    pct = 100 * d["affected"] / d["total"]
    flag = "  <-- SHOULD BE ~0%, CHECK THIS" if pct > 5 else ""
    print(f"{st:<20}{d['affected']:>6} / {d['total']:<6} ({pct:.1f}%){flag}")
