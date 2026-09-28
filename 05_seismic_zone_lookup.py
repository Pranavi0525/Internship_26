"""
STEP 5, v2 -- Pincode-ACCURATE earthquake/seismic zone lookup.

Unlike the state-level version, this checks each pincode's actual
lat/long against the real BIS seismic zone polygons -- a proper
spatial join, not a state-name guess. This fixes exactly the
Kutch/Konkan/Darjeeling problem flagged in v1.

REQUIRES:
  1. Download the shapefile zip from:
     https://www.data.gov.in/resource/shape-file-seismic-zones
     Unzip it -- you'll get .shp/.shx/.dbf/.prj files.
  2. pip install geopandas shapely --break-system-packages
     (geopandas can be fussy to install on Windows -- if it fails,
     try: pip install geopandas --break-system-packages first, and
     if THAT fails, search "install geopandas windows" for the
     conda-forge route, which is usually more reliable on Windows.)

FIRST RUN: run once with INSPECT_ONLY = True to see the actual
column names in the shapefile's attribute table -- every publisher
names the "zone" column differently (could be "ZONE", "Seismic_Zo",
"zone_no", etc). You MUST fill in ZONE_COLUMN_NAME below before the
real run will work.
"""

import csv
import geopandas as gpd
from shapely.geometry import Point

# ---- EDIT THESE FOR YOUR SETUP ----
SHAPEFILE_PATH = r"D:\Internship 2026\Seismic_Zones\Seismic_Zones.shp"  # point at the .shp after unzipping
INPUT_FILE = r"D:\Internship 2026\pincode_master_geocoded.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_seismic_scores_accurate.csv"

INSPECT_ONLY = False
ZONE_COLUMN_NAME = "seismic_zo"   # confirmed real column -- holds "Seismic Zone-V" etc.
# --------------------------------------

# Fallback table for pincodes that land inside one of the ~156 UNLABELED
# polygons in the government shapefile (a real gap in their data, not
# ours). Same state-level table as 05_seismic_zone_lookup.py v1.
STATE_FALLBACK = {
    "JAMMU AND KASHMIR": ("V", 9, "Extreme"), "LADAKH": ("V", 9, "Extreme"),
    "HIMACHAL PRADESH": ("V", 9, "Extreme"), "UTTARAKHAND": ("V", 9, "Extreme"),
    "SIKKIM": ("IV", 6, "Moderate-High"), "ASSAM": ("V", 9, "Extreme"),
    "MEGHALAYA": ("V", 9, "Extreme"), "MANIPUR": ("V", 9, "Extreme"),
    "MIZORAM": ("V", 9, "Extreme"), "NAGALAND": ("V", 9, "Extreme"),
    "TRIPURA": ("V", 9, "Extreme"), "ARUNACHAL PRADESH": ("V", 9, "Extreme"),
    "ANDAMAN AND NICOBAR ISLANDS": ("V", 9, "Extreme"), "BIHAR": ("IV", 6, "Moderate-High"),
    "DELHI": ("IV", 6, "Moderate-High"), "HARYANA": ("IV", 6, "Moderate-High"),
    "PUNJAB": ("IV", 6, "Moderate-High"), "UTTAR PRADESH": ("IV", 6, "Moderate-High"),
    "WEST BENGAL": ("III", 4, "Moderate-Low"), "GUJARAT": ("IV", 6, "Moderate-High"),
    "RAJASTHAN": ("III", 4, "Moderate-Low"), "MAHARASHTRA": ("III", 4, "Moderate-Low"),
    "GOA": ("III", 4, "Moderate-Low"), "MADHYA PRADESH": ("III", 4, "Moderate-Low"),
    "CHHATTISGARH": ("III", 4, "Moderate-Low"), "JHARKHAND": ("III", 4, "Moderate-Low"),
    "ODISHA": ("III", 4, "Moderate-Low"), "ANDHRA PRADESH": ("III", 4, "Moderate-Low"),
    "TELANGANA": ("II", 2, "Low"), "KARNATAKA": ("II", 2, "Low"),
    "TAMIL NADU": ("III", 4, "Moderate-Low"), "KERALA": ("III", 4, "Moderate-Low"),
    "PUDUCHERRY": ("III", 4, "Moderate-Low"), "CHANDIGARH": ("IV", 6, "Moderate-High"),
    "LAKSHADWEEP": ("III", 4, "Moderate-Low"),
    "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU": ("III", 4, "Moderate-Low"),
}

# Same 0-10 scale as v1, just applied per-point instead of per-state now
ZONE_SCORE = {
    "II": (2, "Low"),
    "III": (4, "Moderate-Low"),
    "IV": (6, "Moderate-High"),
    "V": (9, "Extreme"),
}


def inspect_shapefile():
    gdf = gpd.read_file(SHAPEFILE_PATH)
    print("Shapefile loaded successfully.")
    print(f"Number of zone polygons: {len(gdf)}")
    print(f"Coordinate reference system: {gdf.crs}")
    print(f"\nColumn names in the attribute table:")
    print(list(gdf.columns))
    print(f"\nFirst few rows (to see what the zone values actually look like):")
    print(gdf.head())
    print("\n--> Find which column holds the zone number/name (e.g. 'II','III','IV','V'),")
    print("    set ZONE_COLUMN_NAME to that column, set INSPECT_ONLY = False, and re-run.")


def main():
    print("Loading pincode master file...")
    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]

    print(f"Loading seismic zone shapefile ({len(rows)} pincodes to match)...")
    zones_gdf = gpd.read_file(SHAPEFILE_PATH)

    # Build a GeoDataFrame of all pincode points, in the SAME coordinate
    # reference system as the zone shapefile (critical -- mismatched CRS
    # silently gives wrong/empty results, doesn't error).
    points = [Point(float(r["longitude"]), float(r["latitude"])) for r in rows]
    pincode_gdf = gpd.GeoDataFrame(rows, geometry=points, crs="EPSG:4326")
    if zones_gdf.crs != pincode_gdf.crs:
        pincode_gdf = pincode_gdf.to_crs(zones_gdf.crs)

    print("Running spatial join (this checks every pincode against every zone polygon)...")
    joined = gpd.sjoin(pincode_gdf, zones_gdf[[ZONE_COLUMN_NAME, "geometry"]],
                        how="left", predicate="within")

    out = []
    unmatched = 0
    fallback_used = 0
    for _, row in joined.iterrows():
        zone_raw = row.get(ZONE_COLUMN_NAME)
        source = "shapefile_spatial_join"

        if zone_raw and str(zone_raw).strip().lower() != "nan":
            # e.g. "Seismic Zone-V" -> "V"
            zone = str(zone_raw).strip().upper().replace("SEISMIC ZONE-", "").replace("SEISMIC ZONE", "").strip("- ")
            score, band = ZONE_SCORE.get(zone, (None, "Zone label not recognized -- check raw value"))
        else:
            # Landed inside one of the ~156 unlabeled polygons -- the
            # shapefile itself has no data here. Fall back to state-level.
            zone, score, band = STATE_FALLBACK.get(row["state"].strip().upper(), (None, None, "No fallback available"))
            source = "state_fallback_shapefile_gap"
            if score is not None:
                fallback_used += 1

        if score is None:
            unmatched += 1

        out.append({
            "pincode": row["pincode"],
            "locality": row.get("locality", ""),
            "district": row["district"],
            "state": row["state"],
            "seismic_zone": zone or "UNMATCHED",
            "seismic_score_0_10": score,
            "seismic_band": band,
            "source": source,
        })

    fieldnames = ["pincode", "locality", "district", "state", "seismic_zone",
                  "seismic_score_0_10", "seismic_band", "source"]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"\nDone. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"From real shapefile polygons: {len(out) - fallback_used - unmatched}")
    print(f"From state-level fallback (shapefile gap): {fallback_used}")
    print(f"Still unmatched (no fallback either -- check manually): {unmatched}")


if __name__ == "__main__":
    if INSPECT_ONLY:
        inspect_shapefile()
    else:
        main()