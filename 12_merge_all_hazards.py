"""
STEP 12, v4 -- Merge ALL hazard layers into one final table per pincode.

CHANGE FROM v3: adds Forest Fire (script 20 output,
pincode_forestfire_scores.csv). Same left-join, always-present-columns
pattern as before -- if that file doesn't exist yet, the forestfire_*
columns stay blank and a "SKIPPING" note prints, same as any other layer.

NOTE ON forestfire_frequency_percentile / forestfire_intensity_percentile:
script 20's score_pincodes() ranks these ONLY among pincodes that have
at least one qualifying event (not the whole country) -- otherwise the
~47% of pincodes with zero fire events would drag the ranking down so
far that almost any pincode with even one event automatically cleared
the "high frequency/intensity" bar. Zero-event pincodes get blank
values for these two columns here too, which is expected, not a merge
bug -- their verdict is decided before percentiles are even looked at.

v3's own change was adding Sea Level Rise (script 16), Coastal Erosion
(script 17), and River-Bank Erosion (script 18) -- v2's base file and
printed reminder said "re-run this anytime as sea-level-rise/erosion
get built" but v2's file list never actually grew to include them.

Same left-join, always-present-columns pattern throughout (a layer that
hasn't been run yet is skipped, columns stay blank, printed note says
so).

NAMING NOTE: script 17's own output column is called "erosion_score_0_10"
and script 18's is "river_erosion_score_0_10" -- kept as
"coastal_erosion_score_0_10" / "river_erosion_score_0_10" here so the
two don't collide or get confused with each other in the merged file,
since they measure genuinely different things (coastline retreat vs.
riverbank retreat) and a pincode could in principle be flagged by both
(e.g. a delta district near both a coastline and a major river mouth).

Uses left_join semantics throughout, same as v2/v3. Re-run this anytime
a new hazard layer is added -- it always reflects whatever files
currently exist.
"""

import csv
import os

# ---- EDIT THESE FOR YOUR MACHINE ----
BASE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"              # full ~19,586-row master
WEATHER_FILE = r"D:\Internship 2026\pincode_risk_conclusions.csv"          # step 4 output
SEISMIC_FILE = r"D:\Internship 2026\pincode_seismic_scores_accurate.csv"   # step 5
CYCLONE_DISTRICT_FILE = r"D:\Internship 2026\pincode_cyclone_scores.csv"          # step 7
CYCLONE_POINT_FILE = r"D:\Internship 2026\pincode_cyclone_point_scores.csv"       # step 13
LANDSLIDE_FILE = r"D:\Internship 2026\pincode_landslide_scores.csv"        # step 10
SLOPE_FILE = r"D:\Internship 2026\pincode_slope_features.csv"             # step 11
DISTANCE_FILE = r"D:\Internship 2026\pincode_distance_features.csv"       # step 9
GROUNDWATER_FILE = r"D:\Internship 2026\pincode_groundwater_point_scores.csv"  # step 15
SEALEVEL_FILE = r"D:\Internship 2026\pincode_sealevel_scores.csv"              # step 16 -- NEW
COASTAL_EROSION_FILE = r"D:\Internship 2026\pincode_erosion_scores.csv"        # step 17 -- NEW
RIVER_EROSION_FILE = r"D:\Internship 2026\pincode_river_erosion_scores.csv"    # step 18 -- NEW
FORESTFIRE_FILE = r"D:\Internship 2026\pincode_forestfire_scores.csv"          # step 20 -- NEW
# NOTE: pincode_groundwater_scores.csv (step 14, district scaffold) is
# deliberately NOT included -- superseded by the point-level version.
OUTPUT_FILE = r"D:\Internship 2026\pincode_master_all_hazards.csv"
# --------------------------------------


def load_lookup(path, key="pincode"):
    """Returns {pincode: row_dict} if the file exists, else None (with
    a printed note) so the merge can proceed without that layer."""
    if not os.path.exists(path):
        print(f"  SKIPPING (not found yet): {path}")
        return None
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = {r[key]: r for r in csv.DictReader(f)}
        if rows:
            sample_cols = list(next(iter(rows.values())).keys())
            print(f"  Loaded {len(rows)} rows from {os.path.basename(path)} -- "
                  f"columns: {sample_cols}")
        return rows


def main():
    print("Loading base file (full pincode master -- NOT the weather file)...")
    with open(BASE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        base_rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]
    print(f"  {len(base_rows)} pincodes in base")

    print("\nLoading all hazard layers...")
    weather = load_lookup(WEATHER_FILE)
    seismic = load_lookup(SEISMIC_FILE)
    cyclone_d = load_lookup(CYCLONE_DISTRICT_FILE)
    cyclone_p = load_lookup(CYCLONE_POINT_FILE)
    landslide = load_lookup(LANDSLIDE_FILE)
    slope = load_lookup(SLOPE_FILE)
    distance = load_lookup(DISTANCE_FILE)
    groundwater = load_lookup(GROUNDWATER_FILE)
    sealevel = load_lookup(SEALEVEL_FILE)
    coastal_erosion = load_lookup(COASTAL_EROSION_FILE)
    river_erosion = load_lookup(RIVER_EROSION_FILE)
    forestfire = load_lookup(FORESTFIRE_FILE)

    # Fixed column list, defined up front -- every row gets every one of
    # these keys (blank if that layer has no data for this pincode).
    fieldnames = [
        "pincode", "locality", "district", "state", "latitude", "longitude",
        "weather_status",
        "flood_frequency_bucket", "flood_intensity_bucket", "flood_conclusion",
        "heat_frequency_bucket", "heat_intensity_bucket", "heat_conclusion",
        "drought_frequency_bucket", "drought_intensity_bucket", "drought_conclusion",
        "warming_trend_bucket", "weather_composite_score", "weather_composite_label",
        "seismic_zone", "seismic_score_0_10", "seismic_band",
        "cyclone_district_category", "cyclone_district_score_0_10", "cyclone_district_band",
        "cyclone_point_frequency_pct_years", "cyclone_point_intensity_max_wind_kt",
        "cyclone_point_years_affected",
        "landslide_atlas_rank", "landslide_score_0_10", "landslide_band",
        "elevation_center_m", "slope_max_elevation_diff_m", "slope_score_0_10", "slope_band",
        "dist_to_coast_km", "dist_to_river_km",
"coastal_score_0_10", "coastal_band", "riverine_score_0_10", "riverine_band",
        "groundwater_nearest_well_km", "groundwater_trend_m_per_year",
        "groundwater_current_depth_m_bgl", "groundwater_score_0_10", "groundwater_band",
        "groundwater_confidence",
        # NEW -- sea level rise (script 16)
        "nearest_tide_gauge", "nearest_gauge_km", "sealevel_trend_mm_per_year",
        "sealevel_score_0_10", "sealevel_band", "sealevel_confidence",
        # NEW -- coastal erosion (script 17)
        "coast_erosion_pct_of_district_coastline", "coastal_erosion_score_0_10", "coastal_erosion_band",
        # NEW -- river-bank erosion (script 18)
        "river_erosion_status", "river_erosion_river_system", "river_erosion_source",
        "river_erosion_score_0_10", "river_erosion_band",
        # NEW -- forest fire (script 20)
        "forestfire_num_qualifying_events", "forestfire_years_with_event",
        "forestfire_frequency_pct", "forestfire_max_frp_mw",
        "forestfire_frequency_percentile", "forestfire_intensity_percentile",
        "forestfire_verdict", "forestfire_buffer_km",
    ]

    weather_matched = 0
    merged = []
    for row in base_rows:
        pin = row["pincode"]
        out = {k: "" for k in fieldnames}  # every column present, blank by default
        out["pincode"] = pin
        out["locality"] = row.get("locality", "")
        out["district"] = row.get("district", "")
        out["state"] = row.get("state", "")
        out["latitude"] = row.get("latitude", "")
        out["longitude"] = row.get("longitude", "")

        if weather and pin in weather:
            w = weather[pin]
            out["flood_frequency_bucket"] = w.get("flood_frequency_bucket", "")
            out["flood_intensity_bucket"] = w.get("flood_intensity_bucket", "")
            out["flood_conclusion"] = w.get("flood_conclusion", "")
            out["heat_frequency_bucket"] = w.get("heat_frequency_bucket", "")
            out["heat_intensity_bucket"] = w.get("heat_intensity_bucket", "")
            out["heat_conclusion"] = w.get("heat_conclusion", "")
            out["drought_frequency_bucket"] = w.get("drought_frequency_bucket", "")
            out["drought_intensity_bucket"] = w.get("drought_intensity_bucket", "")
            out["drought_conclusion"] = w.get("drought_conclusion", "")
            out["warming_trend_bucket"] = w.get("warming_trend_bucket", "")
            out["weather_composite_score"] = w.get("composite_risk_score", "")
            out["weather_composite_label"] = w.get("composite_risk_label", "")
            weather_matched += 1
        else:
            out["weather_status"] = "Not yet collected (Open-Meteo free-tier limit -- pending paid tier)"

        if seismic and pin in seismic:
            s = seismic[pin]
            out["seismic_zone"] = s.get("seismic_zone", "")
            out["seismic_score_0_10"] = s.get("seismic_score_0_10", "")
            out["seismic_band"] = s.get("seismic_band", "")

        if cyclone_d and pin in cyclone_d:
            c = cyclone_d[pin]
            out["cyclone_district_category"] = c.get("cyclone_category", "")
            out["cyclone_district_score_0_10"] = c.get("cyclone_score_0_10", "")
            out["cyclone_district_band"] = c.get("cyclone_band", "")

        if cyclone_p and pin in cyclone_p:
            cp = cyclone_p[pin]
            out["cyclone_point_frequency_pct_years"] = cp.get("cyclone_point_frequency_pct_years", "")
            out["cyclone_point_intensity_max_wind_kt"] = cp.get("cyclone_point_intensity_max_wind_kt", "")
            out["cyclone_point_years_affected"] = cp.get("cyclone_point_years_affected", "")

        if landslide and pin in landslide:
            l = landslide[pin]
            out["landslide_atlas_rank"] = l.get("landslide_atlas_rank", "")
            out["landslide_score_0_10"] = l.get("landslide_score_0_10", "")
            out["landslide_band"] = l.get("landslide_band", "")

        if slope and pin in slope:
            sl = slope[pin]
            out["elevation_center_m"] = sl.get("elevation_center_m", "")
            out["slope_max_elevation_diff_m"] = sl.get("max_elevation_diff_m", "")
            out["slope_score_0_10"] = sl.get("slope_score_0_10", "")
            out["slope_band"] = sl.get("slope_band", "")

        if distance and pin in distance:
            d = distance[pin]
            out["dist_to_coast_km"] = d.get("dist_to_coast_km", "")
            out["dist_to_river_km"] = d.get("dist_to_river_km", "")
            out["coastal_score_0_10"] = d.get("coastal_score_0_10", "")
            out["coastal_band"] = d.get("coastal_band", "")
            out["riverine_score_0_10"] = d.get("riverine_score_0_10", "")
            out["riverine_band"] = d.get("riverine_band", "")

        if groundwater and pin in groundwater:
            g = groundwater[pin]
            out["groundwater_nearest_well_km"] = g.get("nearest_well_km", "")
            out["groundwater_trend_m_per_year"] = g.get("groundwater_trend_m_per_year", "")
            out["groundwater_current_depth_m_bgl"] = g.get("groundwater_current_depth_m_bgl", "")
            out["groundwater_score_0_10"] = g.get("groundwater_score_0_10", "")
            out["groundwater_band"] = g.get("groundwater_band", "")
            out["groundwater_confidence"] = g.get("confidence", "")

        if sealevel and pin in sealevel:
            sr = sealevel[pin]
            out["nearest_tide_gauge"] = sr.get("nearest_tide_gauge", "")
            out["nearest_gauge_km"] = sr.get("nearest_gauge_km", "")
            out["sealevel_trend_mm_per_year"] = sr.get("sealevel_trend_mm_per_year", "")
            out["sealevel_score_0_10"] = sr.get("sealevel_score_0_10", "")
            out["sealevel_band"] = sr.get("sealevel_band", "")
            out["sealevel_confidence"] = sr.get("confidence", "")

        if coastal_erosion and pin in coastal_erosion:
            ce = coastal_erosion[pin]
            out["coast_erosion_pct_of_district_coastline"] = ce.get(
                "coast_erosion_pct_of_district_coastline", "")
            out["coastal_erosion_score_0_10"] = ce.get("erosion_score_0_10", "")
            out["coastal_erosion_band"] = ce.get("erosion_band", "")

        if river_erosion and pin in river_erosion:
            re_ = river_erosion[pin]
            out["river_erosion_status"] = re_.get("river_erosion_status", "")
            out["river_erosion_river_system"] = re_.get("river_erosion_river_system", "")
            out["river_erosion_source"] = re_.get("river_erosion_source", "")
            out["river_erosion_score_0_10"] = re_.get("river_erosion_score_0_10", "")
            out["river_erosion_band"] = re_.get("river_erosion_band", "")

        if forestfire and pin in forestfire:
            ff = forestfire[pin]
            out["forestfire_num_qualifying_events"] = ff.get("num_qualifying_events", "")
            out["forestfire_years_with_event"] = ff.get("years_with_event", "")
            out["forestfire_frequency_pct"] = ff.get("frequency_pct", "")
            out["forestfire_max_frp_mw"] = ff.get("max_frp_mw", "")
            out["forestfire_frequency_percentile"] = ff.get("frequency_percentile", "")
            out["forestfire_intensity_percentile"] = ff.get("intensity_percentile", "")
            out["forestfire_verdict"] = ff.get("verdict", "")
            out["forestfire_buffer_km"] = ff.get("buffer_km", "")

        merged.append(out)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    print(f"\nDone. Wrote {len(merged)} pincodes -> {OUTPUT_FILE}")
    print(f"Weather coverage: {weather_matched}/{len(merged)} "
          f"({100*weather_matched/len(merged):.1f}%) -- everything else is ~national")
    print(f"Total columns in final file: {len(fieldnames)}")
    print("\nRe-run this script anytime a new hazard layer is added, or as weather")
    print("coverage grows -- it always reflects whatever files currently exist.")


if __name__ == "__main__":
    main()