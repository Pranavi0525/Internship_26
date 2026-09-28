"""
STEP 16 -- Sea Level Rise, point-level, from real PSMSL tide gauge records.

SOURCE (real, official, peer-reviewed data bank): Permanent Service for
Mean Sea Level (PSMSL) -- the same organization NOAA itself uses for its
own published sea-level-trend product. Free, public, no login. Data
authority for the Indian stations is the Survey of India.
  https://psmsl.org/

NO MANUAL DOWNLOAD NEEDED: PSMSL serves each station's annual mean sea
level record over a simple HTTPS URL, so this script fetches it directly
(same spirit as Open-Meteo), rather than requiring you to download a
file by hand first.

STATIONS: 15 real India tide gauge stations, IDs/coordinates verified
directly against PSMSL's own database (not typed from memory or
estimated). This is NOT exhaustive -- PSMSL lists ~20 India stations in
total; these 15 are the ones with confirmed IDs and coordinates as of
this build. Add more station IDs to STATIONS below if you locate them
(browse https://psmsl.org/data/obtaining/ and filter for "IND (INDIA)").

METHOD (mirrors 15_groundwater_point_level.py's honesty pattern, since
this is the same class of problem -- a sparse real point network, not
full coverage):
  1. Download each station's annual RLR (Revised Local Reference) mean
     sea level record. RLR puts all years on one consistent vertical
     datum so trend calculation is valid across the record; "missing
     year" is coded -99999 in PSMSL's own format and is dropped, not
     treated as zero.
  2. Compute trend_mm_per_year via ordinary least-squares linear
     regression across all valid years (PSMSL's own recommended method
     for a single trend estimate -- see their Sea Level Trend Methods
     page). POSITIVE = sea level rising.
  3. ONLY coastal pincodes get a value. Uses dist_to_coast_km from
     09_distance_to_coast_river.py -- if a pincode is more than
     COASTAL_APPLICABILITY_KM from the coast, sea level rise is
     genuinely Not Applicable to it, not zero. Requires
     pincode_distance_features.csv to already exist (run script 9 first).
  4. For each coastal pincode, inherit the NEAREST station's trend, and
     report the distance to that station. With only 15 stations for
     ~3,700+ coastal pincodes, many "nearest station" distances will be
     large -- flagged explicitly as low-confidence beyond
     NEAREST_STATION_MAX_KM, same honesty convention as groundwater.

BE HONEST ABOUT WHAT THIS IS: local relative sea level trend at the
nearest real tide gauge, inherited across potentially large stretches
of coastline between gauges. This is NOT the same claim as "measured at
this exact pincode" -- coastal geomorphology, land subsidence, and
estuarine effects can differ significantly within that gap. It IS a
genuine, real, peer-reviewed-quality measurement, just a sparse one.

Install: pip install requests geopandas shapely --break-system-packages
"""

import csv
import time
import requests
import geopandas as gpd
from shapely.geometry import Point

# ---- EDIT THESE FOR YOUR MACHINE ----
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
DISTANCE_FILE = r"D:\Internship 2026\pincode_distance_features.csv"   # step 9 output -- REQUIRED
OUTPUT_FILE = r"D:\Internship 2026\pincode_sealevel_scores.csv"

COASTAL_APPLICABILITY_KM = 50   # beyond this, sea level rise is "Not Applicable", not zero
NEAREST_STATION_MAX_KM = 150    # beyond this, flag the nearest-station match as low-confidence
                                  # (larger than groundwater's 50km cutoff -- tide gauges are
                                  # sparser than groundwater wells, 15 vs 2,759 stations)
# --------------------------------------

RLR_ANNUAL_URL = "https://psmsl.org/data/obtaining/rlr.annual.data/{id}.rlrdata"

# Verified directly against https://psmsl.org/data/obtaining/ -- station
# ID, name, lat, lon all confirmed on PSMSL's own pages, not estimated.
STATIONS = {
    43:   ("MUMBAI / BOMBAY (APOLLO BANDAR)", 18.917000, 72.833000),
    48:   ("KIDDERPORE", 22.533000, 88.333000),
    49:   ("DUBLAT (SAUGOR IS.)", 21.633000, 88.133000),
    205:  ("CHENNAI", 13.100000, 80.300000),
    206:  ("PORT BLAIR", 11.683000, 92.767000),
    212:  ("BOMBAY (PRINCES DOCK)", 18.950000, 72.833000),
    369:  ("GARDEN REACH", 22.550000, 88.300000),
    414:  ("VISAKHAPATNAM", 17.683000, 83.283000),
    417:  ("SAUGOR / SAGAR", 21.650000, 88.050000),
    420:  ("BHAVNAGAR", 21.800000, 72.300000),
    438:  ("COCHIN (WILLINGDON IS.)", 9.967000, 76.267000),
    543:  ("DIAMOND HARBOUR", 22.200000, 88.167000),
    596:  ("KANDLA", 23.016667, 70.216667),
    1161: ("PARADIP", 20.266667, 86.700000),
    1395: ("OKHA", 22.466667, 69.083333),
}

MISSING_CODE = -99999


def fetch_station_series(station_id):
    """Downloads one station's annual RLR record. Returns list of
    (year, height_mm) for valid years only. PSMSL's own format:
    'year;height;interpolated_flag;missing_flag', semicolon-delimited,
    missing years coded -99999 -- dropped here, never treated as 0."""
    url = RLR_ANNUAL_URL.format(id=station_id)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    series = []
    for line in resp.text.strip().splitlines():
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 2:
            continue
        try:
            year = int(float(parts[0]))
            height = float(parts[1])
        except ValueError:
            continue
        if height == MISSING_CODE:
            continue
        series.append((year, height))
    return series


def linear_trend_mm_per_year(series):
    """Ordinary least-squares slope, in mm/year. PSMSL's own Sea Level
    Trend Methods page uses linear regression as the standard single-
    trend estimate -- this is that, not a custom method."""
    if len(series) < 10:
        return None  # too short a record to trust a trend
    years = [y for y, _ in series]
    heights = [h for _, h in series]
    n = len(years)
    mean_x = sum(years) / n
    mean_y = sum(heights) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(years, heights))
    den = sum((x - mean_x) ** 2 for x in years)
    if den == 0:
        return None
    slope = num / den
    return round(slope, 2)


def band_for_trend(trend):
    """POSITIVE trend = sea level rising = worse. Bands loosely follow
    the global-average context: IPCC AR6 gives a recent global mean rate
    around 3.7mm/yr (2006-2018) -- used here only to anchor what counts
    as 'above global average' for India's own gauges, not as an
    official Indian-government threshold (no such threshold is
    published), so this is a stated proxy, not an authoritative cutoff."""
    if trend is None:
        return None, "Insufficient station record to compute a trend"
    if trend >= 5.0:
        return 10, "Extreme (>=5.0 mm/yr, well above global average rise)"
    elif trend >= 3.5:
        return 7, "High (3.5-5.0 mm/yr, at or above global average rise)"
    elif trend >= 1.5:
        return 4, "Moderate (1.5-3.5 mm/yr, rising but below global average)"
    else:
        return 2, "Low (<1.5 mm/yr or stable/falling at this gauge)"


def main():
    print(f"Downloading real annual sea-level records for {len(STATIONS)} India PSMSL stations...")
    station_data = []
    for sid, (name, lat, lon) in STATIONS.items():
        try:
            series = fetch_station_series(sid)
            trend = linear_trend_mm_per_year(series)
            n_years = len(series)
            print(f"  {name} (ID {sid}): {n_years} years of data, trend = "
                  f"{trend if trend is not None else 'N/A (too short)'} mm/yr")
            station_data.append({"id": sid, "name": name, "lat": lat, "lon": lon,
                                  "trend": trend, "n_years": n_years})
        except requests.exceptions.RequestException as e:
            print(f"  {name} (ID {sid}): FAILED to download -- {e}")
        time.sleep(0.5)

    usable_stations = [s for s in station_data if s["trend"] is not None]
    print(f"\n{len(usable_stations)}/{len(STATIONS)} stations have a usable trend")

    print("\nLoading pincode master + distance-to-coast files...")
    with open(PINCODE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        pin_rows = {r["pincode"]: r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")}

    with open(DISTANCE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        dist_rows = {r["pincode"]: r for r in csv.DictReader(f)}

    coastal_pins = []
    for pin, r in pin_rows.items():
        d = dist_rows.get(pin)
        if d is None:
            continue
        try:
            dist_km = float(d["dist_to_coast_km"])
        except (ValueError, KeyError):
            continue
        if dist_km <= COASTAL_APPLICABILITY_KM:
            coastal_pins.append(pin)
    print(f"  {len(coastal_pins)} pincodes within {COASTAL_APPLICABILITY_KM}km of the coast "
          f"(sea level rise applicable)")

    print("Finding nearest tide gauge for each coastal pincode...")
    coastal_gdf = gpd.GeoDataFrame(
        [{"pincode": p} for p in coastal_pins],
        geometry=[Point(float(pin_rows[p]["longitude"]), float(pin_rows[p]["latitude"])) for p in coastal_pins],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857").reset_index(drop=True)

    stations_gdf = gpd.GeoDataFrame(
        usable_stations,
        geometry=[Point(s["lon"], s["lat"]) for s in usable_stations],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857").reset_index(drop=True)

    nearest = gpd.sjoin_nearest(coastal_gdf, stations_gdf[["name", "trend", "n_years", "geometry"]],
                                 distance_col="dist_m")
    nearest = nearest[~nearest.index.duplicated(keep="first")]

    out = []
    low_confidence_count = 0
    for pin in pin_rows:
        if pin not in coastal_pins:
            out.append({
                "pincode": pin, "district": pin_rows[pin].get("district", ""),
                "state": pin_rows[pin].get("state", ""),
                "dist_to_coast_km": dist_rows.get(pin, {}).get("dist_to_coast_km", ""),
                "nearest_tide_gauge": "", "nearest_gauge_km": "",
                "sealevel_trend_mm_per_year": "", "sealevel_score_0_10": "",
                "sealevel_band": "Not Applicable (inland, beyond "
                                 f"{COASTAL_APPLICABILITY_KM}km from coast)",
                "confidence": "not_applicable",
            })
            continue

        idx = coastal_pins.index(pin)
        if idx not in nearest.index:
            continue
        match = nearest.loc[idx]
        dist_km = round(match["dist_m"] / 1000, 1)
        trend = match["trend"]
        score, band = band_for_trend(trend)
        confidence = "low (nearest tide gauge is far away)" if dist_km > NEAREST_STATION_MAX_KM else "normal"
        if confidence.startswith("low"):
            low_confidence_count += 1

        out.append({
            "pincode": pin, "district": pin_rows[pin].get("district", ""),
            "state": pin_rows[pin].get("state", ""),
            "dist_to_coast_km": dist_rows.get(pin, {}).get("dist_to_coast_km", ""),
            "nearest_tide_gauge": match["name"], "nearest_gauge_km": dist_km,
            "sealevel_trend_mm_per_year": trend, "sealevel_score_0_10": score,
            "sealevel_band": band, "confidence": confidence,
        })

    fieldnames = ["pincode", "district", "state", "dist_to_coast_km", "nearest_tide_gauge",
                  "nearest_gauge_km", "sealevel_trend_mm_per_year", "sealevel_score_0_10",
                  "sealevel_band", "confidence"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    applicable = sum(1 for o in out if o["confidence"] != "not_applicable")
    print(f"\nDone. Wrote {len(out)} pincodes to {OUTPUT_FILE}")
    print(f"Sea level rise applicable (coastal): {applicable} ({100*applicable/len(out):.1f}%)")
    print(f"Of those, low-confidence (nearest gauge >{NEAREST_STATION_MAX_KM}km away): "
          f"{low_confidence_count}")
    print("\nSANITY CHECK: Kolkata-area pincodes (Diamond Harbour, Kidderpore, Garden Reach,")
    print("Dublat, Saugor all cluster in the Hooghly estuary) should show LOW nearest-gauge")
    print("distance and a trend broadly consistent with published Bay of Bengal estimates.")
    print("Mumbai pincodes should map to the Apollo Bandar or Princes Dock gauge, both in")
    print("South Mumbai -- a pincode in a distant Mumbai suburb will show a larger gauge")
    print("distance, which is honest, not a bug.")


if __name__ == "__main__":
    main()