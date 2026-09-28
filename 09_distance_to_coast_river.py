"""
STEP 9, v3 -- Distance to coastline and distance to nearest river.
(v2 was faster-but-arbitrary; v3 replaces the flat 10km/2km cutoffs
with tiered bands grounded in published, cited research. See CHANGE
NOTE below.)

WHY THIS ONE MATTERS MOST: this is the feature that finally breaks the
"every pincode in the same district gets the same cyclone/flood score"
ceiling from steps 05/07. Two pincodes in the same district can now get
genuinely different numbers, because distance to a real coastline/river
geometry is computed per-point, not looked up in a table.

BE HONEST ABOUT WHAT THIS IS: a distance-based PROXY for exposure, not
a validated hazard probability. Closer to the coast plausibly means
more cyclone/storm-surge exposure; closer to a river plausibly means
more flood exposure. That's a reasonable assumption to build a feature
on -- it is NOT the same as a hydrological model, and it hasn't been
checked against real outcomes here. Say this plainly in your
methodology doc, same as every other caveat you've already been
flagging.

CHANGE NOTE (v3) -- WHY THE FLAT 10km / 2km CUTOFFS WERE REPLACED:
v2 used "dc <= 10000" and "dr <= 2000" -- two hardcoded round numbers
with no source, no different in kind from an arbitrary guess. Checked
against actual Indian regulatory standards first: India's enacted CRZ
(Coastal Regulation Zone) buffers operate at 20-500m, and river/lake
buffer rules at 30-100m -- both roughly two orders of magnitude smaller
than the old cutoffs and not a good match. The only km-scale precedent
close in spirit is the draft (not yet enacted) River Regulation Zone's
proposed 5km floodplain buffer -- closer, but still not the 2km used.

So instead of one flat number, this version bands both distances using
real published field/model data, mirroring the tiered structure already
used for cyclone (P1-P4) and landslide (Severe/Very High/../Low):

  COASTAL band -- based on actual observed storm-surge inundation extent
  on the Indian east coast:
    - Aila (2009), a well-documented "typical severe" cyclone: average
      inland inundation ~350m, max ~600m at low-lying points.
      (Source: Mandal & Ray, 2015, "Numerical study of storm surge and
      associated coastal inundation for 2009 Aila cyclone in the head
      Bay of Bengal," Weather and Climate Extremes.
      https://www.sciencedirect.com/science/article/pii/S2214241X15000553)
    - The 1999 Odisha Super Cyclone -- the most extreme cyclone on
      record for the Indian coast -- produced inundation up to 45km
      inland, submerging 1,100+ sq km 1-2m deep.
      (Source: Storm Surge Hazard Assessment Along the East Coast of
      India Using Geospatial Techniques, ResearchGate/Research Square,
      2020. https://www.researchgate.net/publication/343928202)
    These two real events anchor a 4-tier band (0-1 / 1-5 / 5-15 /
    15-45km) instead of one flat line.

  RIVERINE band -- based on a peer-reviewed AHP flood-hazard study of
  the Kosi River Basin, Bihar, using historical flood records:
    - Flood hazard is highest within 1,000m of the river network and
      reduces substantially beyond 5,000m.
      (Source: Kumar et al., "Flood risk assessment of the Kosi River
      Basin in North Bihar using SAR data and AHP approach,"
      ScienceDirect, 2025.
      https://www.sciencedirect.com/science/article/pii/S2666592125000150)
    This gives a real two-breakpoint band (0-1 / 1-5 / >5km).

HONEST CAVEAT THAT STILL APPLIES (say this in your methodology doc):
  - The coastal bands are calibrated to Bay of Bengal / east-coast
    supercyclone behavior (Odisha, West Bengal, Andhra Pradesh). Cyclones
    on India's west coast (Arabian Sea -- Gujarat, Maharashtra, Kerala)
    are climatologically less intense on average, so applying the same
    45km "Low" outer band there likely OVERSTATES west-coast risk at
    the fringes. If anyone challenges this, that's the honest answer --
    a single national coastal band is a simplification, not a claim
    that every coastline behaves like Odisha.
  - The riverine bands come from one basin study (Kosi/Bihar), not a
    national one -- treated as the best available real anchor, not a
    universal Indian river threshold. Rivers with different flow
    regimes, embankments, or floodplain geometry may behave differently.
  - Neither band is a substitute for an actual hydrological or storm-
    surge model at the pincode level. It's a defensible, cited proxy --
    a real improvement over an unsourced round number, not a finished
    hazard model.

(v2 CHANGE NOTE, still relevant): uses gpd.sjoin_nearest, which uses an
STRtree spatial index internally, so it scales to a big Asia-wide river
network far better than computing .distance() against one giant unioned
geometry.

MANUAL DOWNLOADS REQUIRED (no API for either -- one-time only):

1. Coastline shapefile (Natural Earth, public domain, no login):
   https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-coastline/
   Direct file: ne_10m_coastline.zip -- unzip, point COASTLINE_SHP at the .shp

2. River network shapefile (HydroRIVERS, WWF/HydroSHEDS, free, no login):
   https://www.hydrosheds.org/products/hydrorivers -- download the "Asia"
   row under "Shapefile" (not Geodatabase, not Global). Unzip, point
   RIVERS_SHP at the .shp.

Install:
    pip install geopandas shapely --break-system-packages
"""

import csv
import geopandas as gpd
from shapely.geometry import Point

# ---- EDIT THESE FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_geocoded.csv"
COASTLINE_SHP = r"D:\Internship 2026\ne_10m_coastline\ne_10m_coastline.shp"
RIVERS_SHP = r"D:\Internship 2026\HydroRIVERS_v10_as_shp\HydroRIVERS_v10_as_shp\HydroRIVERS_v10_as.shp"
OUTPUT_FILE = r"D:\Internship 2026\pincode_distance_features.csv"
# --------------------------------------


def coastal_band(dist_km):
    """4-tier band, anchored to real observed storm-surge inundation
    extents (Aila 2009 ~350-600m; 1999 Odisha Super Cyclone 45km).
    See the module docstring for sources and the east/west-coast
    calibration caveat."""
    if dist_km <= 1:
        return 10, "Severe (within typical-event surge reach, even moderate cyclones)"
    elif dist_km <= 5:
        return 8, "High (within Aila-type severe-cyclone inundation extent)"
    elif dist_km <= 15:
        return 5, "Moderate (reached only by stronger-than-typical cyclones)"
    elif dist_km <= 45:
        return 2, "Low (reached only in worst-case supercyclone scenarios, e.g. 1999 Odisha)"
    else:
        return None, "Not Applicable (beyond the most extreme documented Indian cyclone inundation extent)"


def riverine_band(dist_km):
    """3-tier band, anchored to the Kosi River Basin (Bihar) AHP flood
    study: hazard highest <1km, reduces substantially beyond 5km. See
    the module docstring for the source and single-basin caveat."""
    if dist_km <= 1:
        return 8, "High (within the zone the Kosi Basin study found flood hazard highest)"
    elif dist_km <= 5:
        return 5, "Moderate (within the zone the same study found hazard declining)"
    else:
        return 2, "Low (beyond the zone that study found hazard substantially reduced)"


def main():
    print("Loading pincode master file...")
    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]
    print(f"  {len(rows)} pincodes with coordinates")

    print("Building point geometries (reprojecting to metres, EPSG:3857)...")
    points_gdf = gpd.GeoDataFrame(
        rows,
        geometry=[Point(float(r["longitude"]), float(r["latitude"])) for r in rows],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857")
    points_gdf = points_gdf.reset_index(drop=True)

    print("Loading coastline shapefile...")
    coastline = gpd.read_file(COASTLINE_SHP).to_crs("EPSG:3857")

    print("Loading river network shapefile (this can take a minute -- it's a big file)...")
    rivers = gpd.read_file(RIVERS_SHP).to_crs("EPSG:3857")

    # sjoin_nearest uses a spatial index (STRtree) internally, so it scales
    # to a big Asia-wide river network far better than computing .distance()
    # against one giant unioned geometry -- same result, much faster.
    print("Computing nearest-coast distances (indexed nearest-neighbor join)...")
    nearest_coast = gpd.sjoin_nearest(points_gdf, coastline[["geometry"]], distance_col="dist_coast_m")
    nearest_coast = nearest_coast[~nearest_coast.index.duplicated(keep="first")]
    dist_coast_m = nearest_coast["dist_coast_m"].reindex(points_gdf.index)

    print("Computing nearest-river distances (indexed nearest-neighbor join)...")
    nearest_river = gpd.sjoin_nearest(points_gdf, rivers[["geometry"]], distance_col="dist_river_m")
    nearest_river = nearest_river[~nearest_river.index.duplicated(keep="first")]
    dist_river_m = nearest_river["dist_river_m"].reindex(points_gdf.index)

    out = []
    for idx, r in enumerate(rows):
        dc_km = round(dist_coast_m.iloc[idx] / 1000, 2)
        dr_km = round(dist_river_m.iloc[idx] / 1000, 2)

        coast_score, coast_label = coastal_band(dc_km)
        river_score, river_label = riverine_band(dr_km)

        out.append({
            "pincode": r["pincode"],
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "dist_to_coast_km": dc_km,
            "dist_to_river_km": dr_km,
            "coastal_score_0_10": coast_score if coast_score is not None else "",
            "coastal_band": coast_label,
            "riverine_score_0_10": river_score,
            "riverine_band": river_label,
        })

    fieldnames = ["pincode", "district", "state", "dist_to_coast_km", "dist_to_river_km",
                  "coastal_score_0_10", "coastal_band", "riverine_score_0_10", "riverine_band"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"\nDone. Wrote {len(out)} pincodes to {OUTPUT_FILE}")

    from collections import Counter
    coast_counts = Counter(o["coastal_band"] for o in out)
    river_counts = Counter(o["riverine_band"] for o in out)
    print("\nCoastal band distribution:")
    for label, count in coast_counts.items():
        print(f"  {count:>6}  ({100*count/len(out):5.1f}%)  {label}")
    print("\nRiverine band distribution:")
    for label, count in river_counts.items():
        print(f"  {count:>6}  ({100*count/len(out):5.1f}%)  {label}")

    print("\nSANITY CHECK before trusting this: pincode 400001 (Mumbai) should show")
    print("dist_to_coast_km well under 5km -> coastal_score 8 or 10. Pincode 110001")
    print("(Delhi, landlocked) should show dist_to_coast_km in the hundreds -> Not")
    print("Applicable. If either looks wrong, check your CRS (EPSG:3857 distances are")
    print("only accurate-ish near the equator -- fine for India, but don't reuse this")
    print("script unmodified for a global dataset).")
    print("\nRemember the calibration caveat in the module docstring: the coastal bands")
    print("are anchored to east-coast (Bay of Bengal) supercyclone behavior and may")
    print("overstate risk at the outer bands for west-coast (Arabian Sea) pincodes.")


if __name__ == "__main__":
    main()