"""
Sanity check for pincode_landslide_point_scores.csv (script 14, COOLR),
same spirit as validate_cyclone_known_answers.py and
validate_seismic_known_answers.py.

WHY THIS EXISTS: script 14's own printed "SANITY CHECK" reminder tells
you what SHOULD be true but doesn't verify it -- with the overall
match rate coming back at just 0.6% (117 / 19,564 pincodes), it's
worth confirming that's genuine COOLR sparsity in India rather than a
coordinate/CRS bug before this layer goes in the report.

This checks THREE things:
  1. Known-answer spot checks (Rudraprayag should be nonzero, Delhi
     should be zero -- same as the script's own printed reminder, but
     actually verified against the file instead of eyeballed).
  2. Whether India-specific hits look plausible at all, by printing the
     top 15 pincodes by event count -- these should skew toward the
     Himalayan belt / Western Ghats / Northeast, same regions the
     district Atlas (script 10) already flags as landslide-prone. If
     the top hits are somewhere geographically nonsensical (e.g.
     scattered across the Deccan plateau), that's the bug signal.
  3. A rough cross-check against the district Atlas: what fraction of
     pincodes in a KNOWN Atlas top-15 district (e.g. Rudraprayag,
     Tehri Garhwal, Idukki) got a nonzero COOLR point hit? This won't
     match 1:1 (COOLR is sparser by design, see script 14's docstring)
     but a district with a #1-15 Atlas rank showing ZERO COOLR hits
     anywhere in it would be suspicious, not just "sparse."
"""

import csv
from collections import defaultdict

POINT_FILE = r"C:\Users\New\Downloads\pincode_landslide_point_scores.csv"
DISTRICT_FILE = r"C:\Users\New\Downloads\pincode_landslide_scores.csv"  # script 10 output, for cross-check

# pincode: (expected: "nonzero" or "zero", why)
KNOWN_ANSWERS = {
    "246171": ("nonzero", "Rudraprayag, Uttarakhand -- India's #1 ranked landslide district in the NRSC Atlas"),
    "110001": ("zero", "New Delhi -- flat, not in the Atlas at all"),
    "700001": ("zero", "Kolkata -- Gangetic delta, not in the Atlas at all"),
}

# A handful of districts ranked 1-15 in the Atlas (script 10), for the
# district-level cross-check (#3 above). District name spelling must
# match your pincode file's own "district" column casing.
ATLAS_TOP_DISTRICTS = ["RUDRAPRAYAG", "TEHRI GARHWAL", "THRISSUR", "RAJAURI", "PALAKKAD"]


def main():
    with open(POINT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.DictReader(f))
    by_pincode = {r["pincode"]: r for r in rows}

    print("=== 1. Known-answer spot checks ===")
    print(f"{'Pincode':<10}{'Expected':<10}{'Event count':<14}{'Note'}")
    for pin, (expected, note) in KNOWN_ANSWERS.items():
        r = by_pincode.get(pin)
        if not r:
            print(f"{pin:<10}{'NOT FOUND IN FILE'}")
            continue
        count = int(r["landslide_point_event_count"])
        got = "nonzero" if count > 0 else "zero"
        flag = "OK" if got == expected else "MISMATCH -- CHECK THIS"
        print(f"{pin:<10}{expected:<10}{count:<14}{flag}  ({note})")

    print("\n=== 2. Top 15 pincodes by COOLR event count (should skew Himalaya/Western Ghats/NE) ===")
    ranked = sorted(rows, key=lambda r: int(r["landslide_point_event_count"]), reverse=True)
    print(f"{'Pincode':<10}{'District':<25}{'State':<20}{'Event count'}")
    for r in ranked[:15]:
        print(f"{r['pincode']:<10}{r['district']:<25}{r['state']:<20}{r['landslide_point_event_count']}")

    total_hits = sum(1 for r in rows if int(r["landslide_point_event_count"]) > 0)
    total_events_matched = sum(int(r["landslide_point_event_count"]) for r in rows)
    print(f"\nTotal pincodes with >=1 COOLR hit: {total_hits} / {len(rows)} ({100*total_hits/len(rows):.1f}%)")
    print(f"Total event-hits summed across all pincodes: {total_events_matched}")
    print("(This will be HIGHER than the raw event count if events near dense pincode")
    print(" clusters get counted once per nearby pincode -- that's expected, not a bug.)")

    print("\n=== 3. Cross-check against district Atlas top-15 districts ===")
    if DISTRICT_FILE:
        try:
            with open(DISTRICT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
                district_rows = list(csv.DictReader(f))
        except FileNotFoundError:
            district_rows = []
            print(f"  (skipped -- {DISTRICT_FILE} not found)")

        for district in ATLAS_TOP_DISTRICTS:
            pins_in_district = [r["pincode"] for r in district_rows
                                 if (r.get("district") or "").strip().upper() == district]
            if not pins_in_district:
                print(f"  {district}: 0 pincodes found under this district name -- check spelling")
                continue
            hits = sum(1 for p in pins_in_district if by_pincode.get(p) and
                       int(by_pincode[p]["landslide_point_event_count"]) > 0)
            pct = 100 * hits / len(pins_in_district)
            flag = "  <-- ZERO hits in a top-15 Atlas district, worth a closer look" if hits == 0 else ""
            print(f"  {district}: {hits}/{len(pins_in_district)} pincodes got a COOLR hit ({pct:.1f}%){flag}")

    print("\nHow to read this: COOLR being sparser than the Atlas (lower % everywhere) is")
    print("EXPECTED and already documented in script 14's docstring. What would NOT be")
    print("expected: a top-15 Atlas district showing 0% here, or the top-15-by-count list")
    print("above being dominated by flat/non-mountainous states.")


if __name__ == "__main__":
    main()
