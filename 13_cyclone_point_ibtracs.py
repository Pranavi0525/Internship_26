"""
STEP 13 -- Cyclone hazard, POINT-LEVEL, with a real frequency/intensity split.

WHY THIS EXISTS: 07_cyclone_district_lookup.py gives every pincode in a
district the identical score, and that score is a single blended P1-P4
category (frequency + severity + surge all mixed into one label by the
source paper). This script fixes BOTH problems at once:

  1. POINT-LEVEL, not district-level: uses each storm's actual historical
     track (a sequence of real lat/long points), and computes how close
     that track passed to each pincode's own coordinates -- so two
     pincodes in the same district get genuinely different numbers if
     one is nearer the historical storm paths than the other.

  2. Genuine FREQUENCY + INTENSITY split, same structure as flood/heat/
     drought:
       frequency = % of years (1980-2023) with at least one storm
                   passing within RADIUS_KM of this pincode
       intensity = strongest wind speed (knots) of any storm that ever
                   passed within RADIUS_KM of this pincode

SOURCE: IBTrACS (International Best Track Archive for Climate
Stewardship), NOAA/NCEI. Public domain -- NOAA data is not subject to
copyright. https://www.ncei.noaa.gov/products/international-best-track-archive

MANUAL DOWNLOAD (usually NOT needed -- see below):
  This script now points IBTRACS_CSV at NOAA's live URL by default, and
  pandas.read_csv() can read directly from an http(s) URL -- so in most
  cases you don't need to download anything by hand.
  Confirmed working full-dataset URL (verified working with pandas):
    https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv
  If your network blocks direct downloads from a script (some corporate
  firewalls do), download that URL in your browser instead, save it to
  your Downloads folder, and change IBTRACS_CSV to the local path.
  A smaller North Indian-only subset may also exist at the same folder
  (browse https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/
  and look for a filename containing "NI") -- use it if you find it, to
  avoid parsing the full global file, but the ALL file above is the one
  that's confirmed to work, so it's the safe default.

WHY 1980 AS THE START YEAR: IBTrACS itself says observing systems and
procedures have changed a lot over its history -- pre-satellite-era
storms (especially in the Bay of Bengal / Arabian Sea before ~1980) are
much less reliably tracked. Restricting to 1980-2023 trades some history
for much more consistent data quality. State this plainly if asked why
this isn't "since 1891" like the district study.

BE HONEST ABOUT WHAT THIS IS: straight-line distance from a storm's
track to a pincode is a PROXY for exposure (closer historically passing
storms = plausibly higher risk), not a validated wind/surge model. It
doesn't account for storm size, angle of approach, or local terrain.
That's a real limitation, same spirit as every other proxy in this
pipeline -- say it plainly, don't oversell it.

Install: pip install geopandas shapely pandas requests --break-system-packages
"""

import csv
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString

# ---- EDIT THESE FOR YOUR MACHINE ----
# Pulls directly from NOAA over HTTPS by default -- no manual download
# needed. If your network blocks this, download the URL in a browser
# and point this at the local file instead (see docstring above).
IBTRACS_CSV = ("https://www.ncei.noaa.gov/data/international-best-track-archive-"
               "for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv")
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_cyclone_point_scores.csv"

RADIUS_KM = 100          # "affected" if a storm's track passed within this distance
START_YEAR = 1980        # satellite-era cutoff -- see docstring
END_YEAR = 2023
MIN_WIND_KT = 34         # standard WMO/IMD threshold for "tropical storm" strength.
                         # Applied at the TRACK-POINT level (not just "did this storm
                         # ever reach this strength") -- only the segment of each
                         # storm's path where wind was actually >= this value gets
                         # buffered. Without this, a storm's post-landfall decay
                         # tail (tracked for days as a weakening low, often deep
                         # inland) got treated as part of its "cyclone hazard"
                         # footprint, which is what caused ~90%/83% of India to
                         # falsely show as "cyclone-affected" in earlier runs.
# --------------------------------------

# Rough bounding box for India + surrounding waters, to cut down the
# storm dataset before the expensive geometry work.
INDIA_REGION_LAT = (0, 30)
INDIA_REGION_LON = (60, 100)


def load_storm_tracks():
    """IBTrACS CSVs have a units-row as row 2 -- skip it. Returns one
    LineString geometry per storm (SID), built from its own sequence of
    points, restricted to storms with at least 2 valid points."""
    try:
        df = pd.read_csv(IBTRACS_CSV, skiprows=[1], low_memory=False)
    except Exception as e:
        raise RuntimeError(
            f"Could not load IBTrACS data from '{IBTRACS_CSV}'.\n"
            f"Original error: {e}\n\n"
            "If this is a network/firewall issue, download the file yourself:\n"
            "  1. Open this URL in your browser:\n"
            "     https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv\n"
            "  2. Save it to your Downloads folder\n"
            "  3. Change IBTRACS_CSV at the top of this script to that local file path\n"
            "  4. Re-run"
        )
    df.columns = [c.strip() for c in df.columns]

    df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
    df["WMO_WIND"] = pd.to_numeric(df["WMO_WIND"], errors="coerce")
    df["SEASON"] = pd.to_numeric(df["SEASON"], errors="coerce")

    df = df[
        df["LAT"].between(*INDIA_REGION_LAT) & df["LON"].between(*INDIA_REGION_LON)
        & df["SEASON"].between(START_YEAR, END_YEAR)
    ]

    storms = []
    for sid, grp in df.groupby("SID"):
        grp = grp.sort_values("ISO_TIME")
        full_max_wind = grp["WMO_WIND"].max()
        if pd.isna(full_max_wind) or full_max_wind < MIN_WIND_KT:
            continue  # never reached tropical-storm strength at all -- skip entirely

        # KEY FIX: only keep the track points where wind was actually >= threshold.
        # Many storms make landfall, then continue for days as a weakening low
        # tracked far inland -- that inland decay tail isn't a cyclone hazard for
        # wherever it happens to cross, so it must not be part of the geometry
        # we buffer. Using the storm's FULL lifetime track (as the previous
        # version did) was the actual cause of the ~90%/83% coverage -- it swept
        # in every inland area a weakening remnant ever drifted over.
        strong_grp = grp[grp["WMO_WIND"] >= MIN_WIND_KT]
        pts = list(zip(strong_grp["LON"], strong_grp["LAT"]))
        if len(pts) == 0:
            continue
        if len(pts) == 1:
            pts = pts * 2  # shapely needs >=2 points for a LineString; a single
                            # qualifying point becomes a zero-length line, which
                            # buffers into a plain circle -- correct behavior.

        season = int(grp["SEASON"].iloc[0])
        storms.append({
            "sid": sid, "season": season,
            "max_wind_kt": full_max_wind,
            "geometry": LineString(pts),
        })
    return storms


def main():
    print("Loading pincode master file...")
    with open(PINCODE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        pin_rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]
    print(f"  {len(pin_rows)} pincodes")

    print("Loading IBTrACS storm tracks (this may take a moment)...")
    storms = load_storm_tracks()
    print(f"  {len(storms)} storm tracks in the India region, {START_YEAR}-{END_YEAR}")

    print("Building pincode point index (projected to metres, EPSG:3857)...")
    pincode_gdf = gpd.GeoDataFrame(
        pin_rows,
        geometry=[Point(float(r["longitude"]), float(r["latitude"])) for r in pin_rows],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857").reset_index(drop=True)

    radius_m = RADIUS_KM * 1000
    # Per-pincode accumulators
    years_affected = [set() for _ in range(len(pincode_gdf))]
    max_wind_seen = [None] * len(pincode_gdf)

    print(f"Checking each of {len(storms)} storm tracks against all pincodes "
          f"(buffer + spatial join, radius={RADIUS_KM}km)...")
    for i, storm in enumerate(storms):
        if i % 50 == 0:
            print(f"  storm {i+1}/{len(storms)}...")
        track_gdf = gpd.GeoSeries([storm["geometry"]], crs="EPSG:4326").to_crs("EPSG:3857")
        buffer_geom = track_gdf.iloc[0].buffer(radius_m)

        hits = pincode_gdf[pincode_gdf.geometry.within(buffer_geom)]
        for idx in hits.index:
            years_affected[idx].add(storm["season"])
            w = storm["max_wind_kt"]
            if w is not None and (max_wind_seen[idx] is None or w > max_wind_seen[idx]):
                max_wind_seen[idx] = w

    total_years = END_YEAR - START_YEAR + 1
    out = []
    for idx, r in enumerate(pin_rows):
        n_years = len(years_affected[idx])
        frequency_pct = round(100 * n_years / total_years, 1)
        intensity = max_wind_seen[idx]
        out.append({
            "pincode": r["pincode"],
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "cyclone_point_frequency_pct_years": frequency_pct,
            "cyclone_point_intensity_max_wind_kt": intensity if intensity is not None else "",
            "cyclone_point_years_affected": n_years,
            "source": f"IBTrACS_{RADIUS_KM}km_radius_{START_YEAR}-{END_YEAR}",
        })

    fieldnames = ["pincode", "district", "state", "cyclone_point_frequency_pct_years",
                  "cyclone_point_intensity_max_wind_kt", "cyclone_point_years_affected", "source"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    affected_count = sum(1 for o in out if o["cyclone_point_years_affected"] > 0)
    affected_pct = 100 * affected_count / len(out)
    print(f"\nDone. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Storms kept after {MIN_WIND_KT}kt tropical-storm filter: {len(storms)}")
    print(f"Pincodes with at least one storm within {RADIUS_KM}km, {START_YEAR}-{END_YEAR}: "
          f"{affected_count} ({affected_pct:.1f}%)")
    if affected_pct > 40:
        print(f"  ^^ WARNING: {affected_pct:.1f}% is high for a coastal hazard -- cyclones")
        print(f"     shouldn't plausibly reach anywhere near half of India's pincodes.")
        print(f"     Check MIN_WIND_KT and RADIUS_KM before trusting this file.")
    print("\nSANITY CHECK: pincode 751001 (Paradip area, Odisha -- hit by the 1999 Odisha")
    print("super cyclone and Cyclone Fani in 2019) should show nonzero frequency and a")
    print("HIGH max wind. Pincode 110001 (Delhi, landlocked) should show 0 years affected.")


if __name__ == "__main__":
    main()