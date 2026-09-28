"""
STEP 15 -- Groundwater depletion, POINT-LEVEL, using real CGWB monitoring wells.

WHY THIS REPLACES THE DISTRICT-LOOKUP SCAFFOLD (script 14): rather than
a district-level Safe/Semi-Critical/Critical/Over-Exploited category
(which needed the full CGWB Dynamic Groundwater Resource Assessment
report we hadn't sourced yet), this uses individual monitoring wells
with real lat/long -- the same "skip the district lookup, go straight
to point data" upgrade we did for cyclone (IBTrACS) over the district
Mohapatra classification.

SOURCE (real, peer-reviewed, open access, CC-BY 4.0):
  Kuruva, S.K. et al. "Quality controlled, reliable groundwater level
  data with corresponding specific yield over India." Scientific Data
  12, 1609 (2025). https://doi.org/10.1038/s41597-025-05899-5
  Data: https://doi.org/10.6084/m9.figshare.29293877.v3
  File: CGWB_India_qualiy_controlled_GWLs_ref_sy_2000_2022.csv
  2,759 CGWB monitoring wells, quality-controlled seasonal (Jan/May/Aug/Nov)
  depth-to-water-level readings, 2000-2022, in metres below ground level
  (m bgl). Underlying raw readings are CGWB's own official measurements
  (via India-WRIS); this paper's contribution is rigorous filtering down
  to 2,759 wells with reliable, continuous records.

MANUAL DOWNLOAD REQUIRED (one-time, no login):
  Visit https://doi.org/10.6084/m9.figshare.29293877.v3 and download
  CGWB_India_qualiy_controlled_GWLs_ref_sy_2000_2022.csv (2,760 rows x
  113 columns). Point WELLS_CSV at it.

METHOD:
  1. For each well, compute two numbers from its seasonal time series:
     - depletion_trend_m_per_year: average depth-to-water-level in the
       LAST 3 available years of data minus the FIRST 3 available years,
       divided by the number of years between them. POSITIVE = water
       table getting deeper (worse); negative = recovering (better).
     - current_depth_m_bgl: the well's most recent available reading --
       an absolute severity signal (how deep is the water table right
       now), though note this varies naturally by region/aquifer type,
       so it's not perfectly comparable across very different geologies.
  2. For each pincode, find the NEAREST well (geometric distance, same
     sjoin_nearest technique as script 09's coast/river distance) and
     inherit that well's trend + current depth.
  3. CRITICALLY: also report the distance to that nearest well. With
     only 2,759 wells for 19,586 pincodes, some pincodes' "nearest well"
     could be uncomfortably far away -- flagged here explicitly (a
     NEAREST_WELL_MAX_KM cutoff marks distant matches as low-confidence)
     rather than silently presenting a 150km-away reading as if it were
     local, the same honesty principle as every other proxy in this
     pipeline.

BE HONEST ABOUT WHAT THIS IS: a nearest-neighbor inheritance from a
real but sparse well network -- genuine point data, but coverage is
uneven (poor in J&K, Himachal, Uttarakhand, Assam per the source
paper's own validation). This is a real upgrade over a district
category, but "nearest well" is not the same claim as "measured at
this exact pincode."

Install: pip install pandas geopandas shapely --break-system-packages
"""

import csv
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# ---- EDIT THESE FOR YOUR MACHINE ----
WELLS_CSV = r"D:\Internship 2026\Quality_controlled_groundwater_levels_over_India\Output\Filtered_GWLs_2000_2024\CGWB_filtered_wells_2000_2022.csv"
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_groundwater_point_scores.csv"

NEAREST_WELL_MAX_KM = 50   # beyond this, flag the match as low-confidence
# --------------------------------------


def compute_well_trend(row, season_cols):
    """Returns (depletion_trend_m_per_year, current_depth_m_bgl) for one
    well, using whichever of its seasonal columns have real numbers."""
    # season_cols are named like 'Jan-00', 'May-00', ..., in chronological
    # order already (the source file's own column order).
    values = [(col, row[col]) for col in season_cols if pd.notna(row[col])]
    if len(values) < 4:
        return None, None

    current_depth = values[-1][1]

    # crude year parse from column name suffix, e.g. 'Jan-00' -> 2000, 'Nov-22' -> 2022
    def year_of(colname):
        yy = int(colname.split("-")[-1])
        return 2000 + yy if yy < 50 else 1900 + yy

    first_years = values[:3]
    last_years = values[-3:]
    first_avg = sum(v for _, v in first_years) / len(first_years)
    last_avg = sum(v for _, v in last_years) / len(last_years)
    year_span = year_of(last_years[-1][0]) - year_of(first_years[0][0])
    if year_span <= 0:
        return None, current_depth

    trend = round((last_avg - first_avg) / year_span, 3)
    return trend, round(current_depth, 2)


def band_for_trend(trend):
    """POSITIVE trend = water table getting deeper = worse."""
    if trend is None:
        return None, "No trend data"
    if trend >= 0.5:
        return 10, "Extreme (rapid decline, >=0.5m/yr deeper)"
    elif trend >= 0.2:
        return 7, "High (declining, 0.2-0.5m/yr deeper)"
    elif trend >= -0.2:
        return 4, "Moderate (roughly stable, -0.2 to 0.2m/yr)"
    else:
        return 2, "Low (recovering, water table rising)"


def main():
    print("Loading CGWB well data...")
    df = pd.read_csv(WELLS_CSV, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    # Season columns are everything that looks like 'Jan-00', 'May-00', etc.
    season_cols = [c for c in df.columns if "-" in c and c.split("-")[0] in
                   ("Jan", "May", "Aug", "Nov") and c.split("-")[-1].isdigit()]
    print(f"  {len(df)} wells, {len(season_cols)} seasonal columns detected")

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df = df.dropna(subset=["Latitude", "Longitude"])

    wells = []
    for _, row in df.iterrows():
        trend, current_depth = compute_well_trend(row, season_cols)
        if trend is None and current_depth is None:
            continue
        wells.append({
            "station_name": row.get("Station Name", ""),
            "lat": row["Latitude"], "lon": row["Longitude"],
            "trend": trend, "current_depth": current_depth,
        })
    print(f"  {len(wells)} wells have usable trend/depth data")

    print("Loading pincode master file...")
    with open(PINCODE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        pin_rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]
    print(f"  {len(pin_rows)} pincodes")

    print("Finding nearest well for each pincode (indexed nearest-neighbor join)...")
    pincode_gdf = gpd.GeoDataFrame(
        pin_rows,
        geometry=[Point(float(r["longitude"]), float(r["latitude"])) for r in pin_rows],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857").reset_index(drop=True)

    wells_gdf = gpd.GeoDataFrame(
        wells,
        geometry=[Point(w["lon"], w["lat"]) for w in wells],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857").reset_index(drop=True)

    nearest = gpd.sjoin_nearest(pincode_gdf, wells_gdf[["trend", "current_depth", "station_name", "geometry"]],
                                 distance_col="dist_m")
    nearest = nearest[~nearest.index.duplicated(keep="first")]

    out = []
    low_confidence_count = 0
    for idx, r in enumerate(pin_rows):
        match = nearest.loc[idx] if idx in nearest.index else None
        if match is None:
            out.append({
                "pincode": r["pincode"], "district": r.get("district", ""), "state": r.get("state", ""),
                "nearest_well_km": "", "groundwater_trend_m_per_year": "",
                "groundwater_current_depth_m_bgl": "", "groundwater_score_0_10": "",
                "groundwater_band": "No well found nearby", "confidence": "none",
            })
            continue

        dist_km = round(match["dist_m"] / 1000, 1)
        trend = match["trend"]
        score, band = band_for_trend(trend if pd.notna(trend) else None)
        confidence = "low (nearest well is far away)" if dist_km > NEAREST_WELL_MAX_KM else "normal"
        if confidence.startswith("low"):
            low_confidence_count += 1

        out.append({
            "pincode": r["pincode"], "district": r.get("district", ""), "state": r.get("state", ""),
            "nearest_well_km": dist_km,
            "groundwater_trend_m_per_year": trend if pd.notna(trend) else "",
            "groundwater_current_depth_m_bgl": match["current_depth"] if pd.notna(match["current_depth"]) else "",
            "groundwater_score_0_10": score if score is not None else "",
            "groundwater_band": band,
            "confidence": confidence,
        })

    fieldnames = ["pincode", "district", "state", "nearest_well_km", "groundwater_trend_m_per_year",
                  "groundwater_current_depth_m_bgl", "groundwater_score_0_10", "groundwater_band", "confidence"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    print(f"\nDone. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Pincodes where nearest well is >{NEAREST_WELL_MAX_KM}km away (low confidence): "
          f"{low_confidence_count} ({100*low_confidence_count/len(out):.1f}%)")
    print("\nSANITY CHECK: Punjab/Haryana pincodes should show a strongly POSITIVE trend")
    print("(declining water table) -- this is one of the most well-documented groundwater")
    print("crises in the world (Rodell et al. 2009, Nature). If Punjab/Haryana show flat")
    print("or negative trends, something's wrong with the trend calculation.")


if __name__ == "__main__":
    main()
