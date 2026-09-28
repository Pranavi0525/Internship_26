"""
STEP 8 -- Elevation lookup for every pincode.

WHY: elevation is a real, point-level physical measurement (not a
district guess) and is a genuine input signal for flood and landslide
risk -- lower elevation near a river/coast = higher flood exposure;
steep local elevation change = landslide signal (see step 9 for slope).

SOURCE: Open-Elevation (https://open-elevation.com) -- free, public,
no API key, backed by SRTM 30m data. No registration, unlike Bhukosh.
Rate limits are informal/generous but not guaranteed -- this script is
conservative (batches of 100, small delay) to avoid getting throttled
on a 19,500-pincode run.

Has the same checkpointing pattern as 03_collect_hazard_data.py: safe
to stop and re-run, skips pincodes already written to the output file.
"""

import csv
import os
import time
import requests

# ---- EDIT THESE FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_geocoded.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_elevation.csv"
BATCH_SIZE = 100          # Open-Elevation accepts batched POST requests
REQUEST_DELAY_SEC = 1.0
MAX_RETRIES = 4
# --------------------------------------

API_URL = "https://api.open-elevation.com/api/v1/lookup"


def fetch_elevation_batch(rows):
    """rows: list of dicts with 'latitude','longitude'. Returns list of
    elevations in metres, same order, None where lookup failed."""
    locations = [{"latitude": float(r["latitude"]), "longitude": float(r["longitude"])} for r in rows]
    backoff = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, json={"locations": locations}, timeout=60)
            if resp.status_code == 200:
                results = resp.json()["results"]
                return [r.get("elevation") for r in results]
            print(f"    HTTP {resp.status_code}, retry {attempt}/{MAX_RETRIES} in {backoff}s...")
        except requests.exceptions.RequestException as e:
            print(f"    Error ({e}), retry {attempt}/{MAX_RETRIES} in {backoff}s...")
        time.sleep(backoff)
        backoff *= 2
    return [None] * len(rows)


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

    fieldnames = ["pincode", "district", "state", "latitude", "longitude", "elevation_m"]
    write_header = not os.path.exists(OUTPUT_FILE)

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for i in range(0, len(to_process), BATCH_SIZE):
            batch = to_process[i:i + BATCH_SIZE]
            print(f"[{i+1}-{i+len(batch)}/{len(to_process)}] fetching elevation...")
            elevations = fetch_elevation_batch(batch)
            for r, elev in zip(batch, elevations):
                writer.writerow({
                    "pincode": r["pincode"], "district": r.get("district", ""),
                    "state": r.get("state", ""), "latitude": r["latitude"],
                    "longitude": r["longitude"], "elevation_m": elev if elev is not None else "",
                })
            f.flush()
            time.sleep(REQUEST_DELAY_SEC)

    print(f"\nDone. Elevation data written to {OUTPUT_FILE}")
    print("NOTE: elevation alone doesn't tell you flood risk -- it needs to be")
    print("combined with distance-to-river/coast (step 9) to mean anything.")
    print("A pincode at 5m elevation next to a river is very different from")
    print("5m elevation in the middle of a flat plateau far from any water body.")


if __name__ == "__main__":
    main()
