"""
STEP 11 -- Local slope, computed PER PINCODE (not per district).

WHY THIS EXISTS: the official Landslide Atlas (step 10) only ranks
147 DISTRICTS -- every pincode in Rudraprayag gets the identical
score, because that's the actual resolution of the source table, not
a limitation of our join logic. To get real pincode-level variation,
we need a continuous, point-level physical signal instead. Steep
local terrain is a well-established landslide risk factor and,
unlike GSI's susceptibility shapefile (blocked behind a registration
wall we couldn't get through tonight), it's fully computable right
now from elevation data alone.

METHOD: for each pincode, sample elevation at its own point PLUS four
points offset ~500m north/south/east/west. If those nearby points
differ sharply in height from the center, the pincode sits on steep
terrain -> real landslide-relevant signal that varies pincode-by-
pincode, even within the same district.

SOURCE: Open-Elevation (same free, no-registration API as step 8).

BE HONEST ABOUT WHAT THIS IS (say this to your manager): slope is a
PROXY, not a substitute for GSI's actual susceptibility mapping
(which also folds in geology, soil type, rainfall triggers, and
historical inventory -- things elevation alone can't capture). It's
a genuine improvement over "same score for the whole district," but
it is not equivalent to the real susceptibility map if/when you get
Bhukosh access.

Has the same checkpointing pattern as steps 3 and 8: safe to stop
and re-run.
"""

import csv
import os
import time
import requests

# ---- EDIT THESE FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_slope_features.csv"
BATCH_SIZE = 20            # 20 pincodes x 5 points each = 100 locations/request
REQUEST_DELAY_SEC = 1.0
MAX_RETRIES = 4
OFFSET_DEGREES = 0.0045     # roughly 500m at India's latitudes
# --------------------------------------

API_URL = "https://api.open-elevation.com/api/v1/lookup"


def build_offset_points(lat, lon):
    """Returns [center, north, south, east, west] as (lat, lon) pairs."""
    return [
        (lat, lon),
        (lat + OFFSET_DEGREES, lon),
        (lat - OFFSET_DEGREES, lon),
        (lat, lon + OFFSET_DEGREES),
        (lat, lon - OFFSET_DEGREES),
    ]


def fetch_elevation_batch(locations):
    """locations: list of (lat, lon) tuples. Returns list of elevations
    in metres, same order, None where lookup failed."""
    payload = [{"latitude": lat, "longitude": lon} for lat, lon in locations]
    backoff = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, json={"locations": payload}, timeout=60)
            if resp.status_code == 200:
                results = resp.json()["results"]
                return [r.get("elevation") for r in results]
            print(f"    HTTP {resp.status_code}, retry {attempt}/{MAX_RETRIES} in {backoff}s...")
        except requests.exceptions.RequestException as e:
            print(f"    Error ({e}), retry {attempt}/{MAX_RETRIES} in {backoff}s...")
        time.sleep(backoff)
        backoff *= 2
    return [None] * len(locations)


def slope_band(max_diff_m):
    """Rough bands based on the max elevation difference across the
    ~500m sample points. Steeper = higher landslide-relevant signal."""
    if max_diff_m is None:
        return None, "Elevation data unavailable"
    if max_diff_m >= 100:
        return 10, "Very steep (possible mountainous/escarpment terrain)"
    elif max_diff_m >= 40:
        return 7, "Steep (hilly terrain)"
    elif max_diff_m >= 15:
        return 4, "Moderate slope"
    else:
        return 1, "Flat / gentle terrain"


def load_already_done():
    done = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                done.add(row["pincode"])
    return done


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        all_rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]

    already_done = load_already_done()
    to_process = [r for r in all_rows if r["pincode"] not in already_done]
    print(f"Total: {len(all_rows)} | already done: {len(already_done)} | remaining: {len(to_process)}")

    fieldnames = ["pincode", "district", "state", "elevation_center_m",
                  "max_elevation_diff_m", "slope_score_0_10", "slope_band"]
    write_header = not os.path.exists(OUTPUT_FILE)

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for i in range(0, len(to_process), BATCH_SIZE):
            batch = to_process[i:i + BATCH_SIZE]
            print(f"[{i+1}-{i+len(batch)}/{len(to_process)}] sampling elevation grid...")

            # Flatten: 5 points per pincode into one big batch request
            all_points = []
            for r in batch:
                all_points.extend(build_offset_points(float(r["latitude"]), float(r["longitude"])))

            elevations = fetch_elevation_batch(all_points)

            for idx, r in enumerate(batch):
                five = elevations[idx * 5:(idx + 1) * 5]
                center = five[0]
                valid = [e for e in five if e is not None]
                if center is not None and len(valid) >= 2:
                    max_diff = max(abs(e - center) for e in valid)
                else:
                    max_diff = None
                score, band = slope_band(max_diff)
                writer.writerow({
                    "pincode": r["pincode"], "district": r.get("district", ""),
                    "state": r.get("state", ""),
                    "elevation_center_m": center if center is not None else "",
                    "max_elevation_diff_m": round(max_diff, 1) if max_diff is not None else "",
                    "slope_score_0_10": score if score is not None else "",
                    "slope_band": band,
                })
            f.flush()
            time.sleep(REQUEST_DELAY_SEC)

    print(f"\nDone. Slope data written to {OUTPUT_FILE}")
    print("SANITY CHECK: pincode 171001 (Shimla, Himalayan hill station) should show")
    print("a HIGH max_elevation_diff_m. Pincode 700001 (Kolkata, Gangetic plain) should")
    print("show a LOW one. If either looks backwards, something's wrong with the offsets.")


if __name__ == "__main__":
    main()
