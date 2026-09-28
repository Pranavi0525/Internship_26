"""
Diagnostic: WHICH specific storms are hitting Jharkhand/Chhattisgarh/MP
in pincode_cyclone_point_scores.csv, by name and year?

This exists because "55.4% of Jharkhand affected" could be a real result
(strong landfalling systems, especially the 1999 Odisha Super Cyclone,
are documented to remain tropical-storm-strength well inland) OR a
remaining bug -- the only honest way to tell the difference is to name
the actual storms and check them against known history, not guess.

HOW TO USE THE OUTPUT: for each flagged state, you'll get a list of
(year, storm name, max wind). Cross-check a few of these against a
quick search for "[storm name] [year] track" -- if the named storms are
real, well-documented systems known to have affected that region (e.g.
the 1999 Odisha Super Cyclone reaching into Jharkhand/Chhattisgarh is
well documented), the data is doing its job. If you see storms that
have NO business being anywhere near that state, that's the bug signal.
"""

import csv
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString

IBTRACS_CSV = ("https://www.ncei.noaa.gov/data/international-best-track-archive-"
               "for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv")
PINCODE_FILE = r"C:\Users\New\Downloads\pincode_master_geocoded.csv"

RADIUS_KM = 100
START_YEAR = 1980
END_YEAR = 2023
MIN_WIND_KT = 34

INDIA_REGION_LAT = (0, 30)
INDIA_REGION_LON = (60, 100)

STATES_TO_CHECK = ["JHARKHAND", "CHHATTISGARH", "MADHYA PRADESH"]


def main():
    print("Loading pincode master file...")
    with open(PINCODE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        pin_rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")
                    and (r.get("state") or "").strip().upper() in STATES_TO_CHECK]
    print(f"  {len(pin_rows)} pincodes across {STATES_TO_CHECK}")

    print("Loading IBTrACS (this takes a moment)...")
    df = pd.read_csv(IBTRACS_CSV, skiprows=[1], low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
    df["WMO_WIND"] = pd.to_numeric(df["WMO_WIND"], errors="coerce")
    df["SEASON"] = pd.to_numeric(df["SEASON"], errors="coerce")
    df = df[
        df["LAT"].between(*INDIA_REGION_LAT) & df["LON"].between(*INDIA_REGION_LON)
        & df["SEASON"].between(START_YEAR, END_YEAR)
    ]

    pincode_gdf = gpd.GeoDataFrame(
        pin_rows,
        geometry=[Point(float(r["longitude"]), float(r["latitude"])) for r in pin_rows],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857")

    radius_m = RADIUS_KM * 1000
    hits = []  # (season, name, max_wind, n_pincodes_hit)

    for sid, grp in df.groupby("SID"):
        grp = grp.sort_values("ISO_TIME")
        full_max_wind = grp["WMO_WIND"].max()
        if pd.isna(full_max_wind) or full_max_wind < MIN_WIND_KT:
            continue
        strong_grp = grp[grp["WMO_WIND"] >= MIN_WIND_KT]
        pts = list(zip(strong_grp["LON"], strong_grp["LAT"]))
        if len(pts) == 0:
            continue
        if len(pts) == 1:
            pts = pts * 2

        line = gpd.GeoSeries([LineString(pts)], crs="EPSG:4326").to_crs("EPSG:3857").iloc[0]
        buf = line.buffer(radius_m)
        n_hit = pincode_gdf[pincode_gdf.geometry.within(buf)].shape[0]
        if n_hit > 0:
            name = grp["NAME"].iloc[0] if "NAME" in grp.columns else "UNNAMED"
            season = int(grp["SEASON"].iloc[0])
            hits.append((season, name, full_max_wind, n_hit))

    hits.sort()
    print(f"\n{len(hits)} storms have at least one qualifying (>= {MIN_WIND_KT}kt) track point "
          f"within {RADIUS_KM}km of a pincode in {STATES_TO_CHECK}:\n")
    print(f"{'Year':<8}{'Storm name':<20}{'Max wind (kt)':<16}{'Pincodes hit'}")
    for season, name, wind, n_hit in hits:
        print(f"{season:<8}{name:<20}{wind:<16.0f}{n_hit}")

    print("\nNext step: pick 3-4 of these storm names and search")
    print("'[name] [year] cyclone track Jharkhand OR Chhattisgarh OR Madhya Pradesh'")
    print("to confirm they're real, documented systems known to have reached that far inland.")


if __name__ == "__main__":
    main()
