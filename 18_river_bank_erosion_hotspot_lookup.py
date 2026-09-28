"""
STEP 18 -- River-Bank Erosion (distinct from script 17's COASTAL erosion).

WHY THIS IS A DIFFERENT SHAPE OF SCRIPT THAN 17_coastal_erosion_district_lookup.py:
coastal erosion had one clean national source (NCCR's 26-year DSAS study,
one erosion-% figure per district, all 66 coastal districts, uniform
methodology). River-bank erosion does NOT have an equivalent. Confirmed
by search before writing this: there is no single national river-bank-
erosion dataset with one consistent methodology across India. What
exists instead is:
  1. Peer-reviewed academic case studies, each covering ONE river
     stretch (Ganga in Malda/Murshidabad; Brahmaputra across specific
     Assam districts) -- real, citable, but not comparable to each
     other (different methods, different time windows).
  2. A 2019 Lok Sabha reply (Ministry of Jal Shakti, Q.2168) with real
     government-collected district-wise erosion figures -- but ONLY for
     Assam, in mixed units (Bigha-Katha-Lessa AND Hectare in the same
     table), a 5-year window now itself 7+ years stale.

Given that, this script does NOT attempt a national ranked percentage
like coastal erosion's. Instead, same honesty pattern as landslide
(Atlas rank + slope proxy, two complementary layers because no single
source covers everything): a DOCUMENTED HOTSPOT flag (real districts
named in the sources below, not invented or estimated) combined with
the genuine POINT-LEVEL river-distance signal you already computed in
09_distance_to_coast_river.py. A pincode in a hotspot district that
also sits within 2km of the mapped river channel is a materially
different claim than one in the same district but far from any river
-- this combination is what makes the output vary pincode-by-pincode
instead of being flat across an entire district.

SOURCES (real, cited, not estimated):

  Ganga -- Malda & Murshidabad districts, West Bengal:
    Thakur, P.K., Laha, C., Aggarwal, S.P. (2012). "River bank erosion
    hazard study of river Ganga, upstream of Farakka barrage using
    remote sensing and GIS." Natural Hazards, 61(3), 967-987.
    Banerjee, M. (1999). "Report on the Impact of Farakka Barrage on
    the Human Fabric." South Asia Network on Dams, Rivers and People.
    Both districts have decades of documented, severe, recurring
    erosion (hundreds of km2 of land lost, tens of thousands displaced
    -- see script comments below for named CD blocks, though the
    pincode file's join key is district, not block).

  Brahmaputra -- Assam districts:
    Government of India, Ministry of Jal Shakti, Lok Sabha Unstarred
    Question No. 2168, answered 04.07.2019, Annexure-I: district-wise
    "area of land eroded" figures supplied by Assam's own Revenue and
    Disaster Management Department. Used here ONLY as a binary
    hotspot/not-hotspot signal (nonzero reported erosion vs. "does not
    arise" / "Nil" / "no land eroded") -- the raw quantities are NOT
    reproduced or converted, because the source table mixes Bigha-
    Katha-Lessa with Hectare inconsistently across rows, and forcing a
    unit conversion here would manufacture false precision. Districts
    the same government reply explicitly reported as having negligible
    or no erosion (Cachar, Karimganj, Kamrup Metropolitan, Karbi
    Anglong, Hojai, Hailakandi) are recorded as confirmed NOT hotspots
    -- a real negative finding, not an absence of data.
    One combined-district figure (BTAD, covering four Bodoland
    districts as one number) could not be reliably attributed to a
    single district and is deliberately excluded rather than guessed.

REQUIRES: 09_distance_to_coast_river.py must already have been run --
this script reads its output (dist_to_river_km) as a required input.

HONEST LIMITATION (say this plainly, same as every other proxy in this
pipeline): this is a documented-hotspot flag, not a measured erosion
rate. A district outside the hotspot list is "not documented as a
hotspot in the sources checked," not "confirmed zero risk" -- most of
India's river reaches are, per the literature itself, geomorphologically
stable and erosion problems are "restricted to a few places," but there
will be real, undocumented local erosion this script cannot see. This
is the same class of gap as landslide's missing true point-level layer:
a genuine national river-bank-erosion monitoring program (equivalent to
NCCR's coastal one) does not appear to exist yet as a public dataset.
"""

import csv

# ---- EDIT THESE FOR YOUR MACHINE ----
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
DISTANCE_FILE = r"D:\Internship 2026\pincode_distance_features.csv"   # step 9 output -- REQUIRED
OUTPUT_FILE = r"D:\Internship 2026\pincode_river_erosion_scores.csv"

RIVERINE_KM_THRESHOLD = 2.0   # matches script 9's own is_riverine_within_2km definition
# --------------------------------------

# Documented hotspot districts. Value = (river_system, source_note).
# Only districts with an actual named source below are included --
# nothing here is estimated or inferred from geography alone.
HOTSPOT_DISTRICTS = {
    "MALDA": ("Ganga", "Thakur et al. 2012 (Natural Hazards); Farakka-upstream erosion, "
                       "200+ km2 lost by 2004, CD blocks Manickchak/Kaliachak I-III/Ratua I-II"),
    "MURSHIDABAD": ("Ganga", "Banerjee 1999 (SANDRP); 206.6 km2 eroded 1988-1994, 14,236 families "
                             "displaced; CD blocks Farakka/Samserganj/Suti I-II/Jalangi and others"),

    "JORHAT": ("Brahmaputra", "GoI Lok Sabha Q.2168 (2019), Assam govt Revenue & Disaster Mgmt Dept"),
    "SONITPUR": ("Brahmaputra", "Same source"),
    "LAKHIMPUR": ("Brahmaputra", "Same source"),
    "DARRANG": ("Brahmaputra", "Same source"),
    "SIVASAGAR": ("Brahmaputra", "Same source (smaller reported figure)"),
    "GOALPARA": ("Brahmaputra", "Same source"),
    "BONGAIGAON": ("Brahmaputra", "Same source (smaller reported figure)"),
    "BISWANATH": ("Brahmaputra", "Same source"),
    "NALBARI": ("Brahmaputra", "Same source"),
    "MORIGAON": ("Brahmaputra", "Same source; corroborated by independent bankline-migration study "
                                "(lower Brahmaputra, left-bank erosion dominant)"),
    "DHEMAJI": ("Brahmaputra", "Same source"),
    "CHARAIDEO": ("Brahmaputra", "Same source (minor reported figure)"),
    "GOLAGHAT": ("Brahmaputra", "Same source"),
    "KAMRUP": ("Brahmaputra", "Same source (largest reported figure among these districts)"),
    "DIBRUGARH": ("Brahmaputra", "Same source"),
    "BARPETA": ("Brahmaputra", "Same source"),
    "MAJULI": ("Brahmaputra", "Same source; independently one of the most cited erosion-affected "
                              "river islands in India"),
    "NAGAON": ("Brahmaputra", "Same source"),
}

# Districts the SAME government reply explicitly reported as having
# negligible/no erosion in the study window -- a real negative finding,
# recorded so the output doesn't silently look identical to "not
# assessed" for these specific districts.
CONFIRMED_NOT_HOTSPOT = {
    "CACHAR", "KARIMGANJ", "KAMRUP METROPOLITAN", "KARBI ANGLONG", "HOJAI", "HAILAKANDI",
}


def classify(district_key, dist_to_river_km):
    is_riverine = dist_to_river_km is not None and dist_to_river_km <= RIVERINE_KM_THRESHOLD

    if district_key in CONFIRMED_NOT_HOTSPOT:
        return (
            "Confirmed_not_hotspot", "", "",
            2, "Low (government data reports negligible/no erosion in this district)",
        )

    hotspot = HOTSPOT_DISTRICTS.get(district_key)
    if hotspot is None:
        return (
            "Not_assessed", "", "",
            None,
            "Not Applicable (district not in the documented hotspot list -- most Indian "
            "river reaches are reported as geomorphologically stable; this reflects lack "
            "of a national river-erosion study, not a confirmed zero-risk assessment)",
        )

    river_system, source_note = hotspot
    if is_riverine:
        return (
            "Documented_hotspot", river_system, source_note,
            10, f"Severe (documented {river_system} erosion hotspot district, and this "
                f"pincode is within {RIVERINE_KM_THRESHOLD}km of the mapped river channel)",
        )
    else:
        return (
            "Documented_hotspot", river_system, source_note,
            6, f"Moderate-High (documented {river_system} erosion hotspot district, but this "
               f"pincode is farther than {RIVERINE_KM_THRESHOLD}km from the mapped river "
               f"channel -- erosion risk plausibly lower at this specific point)",
        )


def main():
    print("Loading pincode master file...")
    with open(PINCODE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        pin_rows = list(csv.DictReader(f))
    print(f"  {len(pin_rows)} pincodes")

    print("Loading distance-to-river file (step 9 output, REQUIRED)...")
    with open(DISTANCE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        dist_lookup = {r["pincode"]: r for r in csv.DictReader(f)}
    print(f"  {len(dist_lookup)} pincodes with distance data")

    out = []
    hotspot_count = 0
    confirmed_not_count = 0
    not_assessed_count = 0
    missing_distance_count = 0

    for r in pin_rows:
        pin = r["pincode"]
        district_key = (r.get("district") or "").strip().upper()

        dist_row = dist_lookup.get(pin)
        dist_to_river_km = None
        if dist_row is not None:
            try:
                dist_to_river_km = float(dist_row["dist_to_river_km"])
            except (ValueError, KeyError, TypeError):
                pass
        if dist_row is None:
            missing_distance_count += 1

        status, river_system, source_note, score, band = classify(district_key, dist_to_river_km)

        if status == "Documented_hotspot":
            hotspot_count += 1
        elif status == "Confirmed_not_hotspot":
            confirmed_not_count += 1
        else:
            not_assessed_count += 1

        out.append({
            "pincode": pin,
            "locality": r.get("locality", ""),
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "dist_to_river_km": dist_to_river_km if dist_to_river_km is not None else "",
            "river_erosion_status": status,
            "river_erosion_river_system": river_system,
            "river_erosion_source": source_note,
            "river_erosion_score_0_10": score if score is not None else "",
            "river_erosion_band": band,
        })

    fieldnames = ["pincode", "locality", "district", "state", "dist_to_river_km",
                  "river_erosion_status", "river_erosion_river_system",
                  "river_erosion_source", "river_erosion_score_0_10", "river_erosion_band"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"\nDone. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Documented hotspot districts (Ganga or Brahmaputra): {hotspot_count}")
    print(f"Confirmed NOT hotspot (govt data reports negligible/no erosion): {confirmed_not_count}")
    print(f"Not assessed (not in either list): {not_assessed_count}")
    if missing_distance_count:
        print(f"WARNING: {missing_distance_count} pincodes had no matching row in {DISTANCE_FILE} "
              f"-- run step 9 first if this number looks high.")
    print("\nSANITY CHECK: pincode in Malda or Murshidabad district AND within 2km of the mapped")
    print("river (dist_to_river_km <= 2.0) should show score 10. Majuli (Assam) pincodes should")
    print("show river_erosion_status = Documented_hotspot, river_system = Brahmaputra. Cachar")
    print("(Assam) pincodes should show Confirmed_not_hotspot, NOT blank/Not_assessed -- that")
    print("distinction (real negative finding vs. no data) is the point of this script.")


if __name__ == "__main__":
    main()
