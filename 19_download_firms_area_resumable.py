"""
04_download_firms_area_resumable.py

Step 3 of the Forest Fire pipeline: pull the full historical active-fire
archive for India from FIRMS via the live API (not Download Request),
resumably.

WHY THE LIVE API FOR THIS, GIVEN FIRMS STAFF RECOMMEND DOWNLOAD REQUEST:
- /api/country/ genuinely rejects historical dates ("Invalid API call" on
  every date we tried, old or recent) -- confirmed broken, not used here.
- /api/area/ DOES document historical [DATE] support officially. FIRMS
  staff's guidance was that Download Request is FASTER, not that the API
  doesn't work -- this script trades a longer runtime for a fully scripted,
  re-runnable pipeline, which matters more for an auditable internal
  pipeline than for a one-off pull.
- The checkpoint file makes the long runtime a non-issue: kill the script
  anytime, re-run the same command, it picks up where it left off.

FIXED FROM THE PREVIOUS VERSION:
The old fetch_chunk() treated an actual API error ("Invalid...") and a
genuinely fire-free week as the SAME outcome (empty DataFrame), and the
caller marked both as "done" identically. That's exactly the kind of
false-zero-vs-missing-data confusion this pipeline has been careful to
avoid everywhere else. Now: a text response containing "Invalid" raises
an exception, which is NOT marked done and WILL be retried on the next run.
Only a response that parses as valid, structured CSV with zero data rows
counts as a confirmed "no fires this week."

Usage:
    python 04_download_firms_area_resumable.py             # resume/continue the pull
    python 04_download_firms_area_resumable.py --status     # show progress %, no network calls
"""

import argparse
import io
import json
import os
import time
from datetime import date, timedelta
from math import ceil

import pandas as pd
import requests

# ---- EDIT THESE FOR YOUR MACHINE ----
MAP_KEY = os.environ.get("FIRMS_MAP_KEY")   # set via env var, never hardcode -- see step 2
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
RAW_DETECTIONS_CACHE = r"D:\Internship 2026\forestfire_raw_detections.csv"
PROGRESS_FILE = r"D:\Internship 2026\forestfire_pull_progress.json"

INDIA_BBOX = "68,6,98,38"   # west,south,east,north -- a loose box; the eventual
                            # pincode buffer join naturally drops points that
                            # don't land near any real Indian pincode, so we
                            # don't need to clip precisely to the border here.

SENSORS = {
    "MODIS_SP":        date(2000, 11, 1),
    "VIIRS_SNPP_SP":   date(2012, 1, 20),
    "VIIRS_NOAA20_SP": date(2018, 4, 1),
}

DAY_RANGE = 10   # /api/area/ documents 1..10 as valid -- if chunks start
                  # failing consistently, drop this to 5 and re-run (retries
                  # pick up automatically via the checkpoint).
REQUEST_SLEEP_SEC = 0.15   # ~6.6 req/sec, under FIRMS' ~8/sec (5000/10min) cap
SESSION = requests.Session()


def load_progress() -> set:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_progress(done: set):
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(sorted(done), f)
    os.replace(tmp, PROGRESS_FILE)


def append_chunk_to_cache(df: pd.DataFrame):
    if df.empty:
        return
    file_exists = os.path.exists(RAW_DETECTIONS_CACHE)
    df.to_csv(RAW_DETECTIONS_CACHE, mode="a", header=not file_exists, index=False)


def date_chunks(start: date, end: date, step_days: int):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=step_days)


def fetch_chunk(sensor: str, start_date: date) -> pd.DataFrame:
    """Fetch one chunk. Raises on ANY error response (including FIRMS'
    text-based "Invalid..." errors, which come back with HTTP 200 -- a
    normal status-code check alone would miss these). A genuinely empty
    but well-formed CSV (header row only, zero data rows) is the ONLY
    thing that counts as a confirmed zero-fire week."""
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{MAP_KEY}/{sensor}/{INDIA_BBOX}/{DAY_RANGE}/{start_date.isoformat()}"
    )
    resp = SESSION.get(url, timeout=60)
    resp.raise_for_status()
    text = resp.text.strip()

    if not text:
        raise RuntimeError("Empty response body (not a valid zero-fire CSV)")
    if text.lower().startswith("invalid"):
        raise RuntimeError(f"FIRMS returned an error string: {text[:150]}")

    df = pd.read_csv(io.StringIO(text))
    return df   # may legitimately have 0 rows -- that's a confirmed zero-fire week


def pull_all_detections(done: set):
    today = date.today()

    for sensor, start_date in SENSORS.items():
        total_chunks = ceil(((today - start_date).days + 1) / DAY_RANGE)
        print("\n" + "=" * 80)
        print(f"Pulling {sensor}  ({start_date} -> {today}, {total_chunks:,} chunks)")
        print("=" * 80)

        for i, chunk_start in enumerate(date_chunks(start_date, today, DAY_RANGE), start=1):
            key = f"{sensor}|{chunk_start.isoformat()}"
            if key in done:
                continue

            percent = (i / total_chunks) * 100
            print(f"[{sensor}] Chunk {i:>4}/{total_chunks} ({percent:6.2f}%) "
                  f"Start: {chunk_start}", flush=True)

            try:
                df = fetch_chunk(sensor, chunk_start)
            except (requests.RequestException, RuntimeError) as e:
                print(f"   FAILED ({e}) -- NOT marked done, will retry next run")
                time.sleep(REQUEST_SLEEP_SEC)
                continue   # key NOT added to done -- guarantees a retry, not a silent gap

            if not df.empty:
                df["sensor_source"] = sensor
                append_chunk_to_cache(df)
                print(f"   -> {len(df):,} detections saved")
            else:
                print("   -> Confirmed zero detections this window")

            done.add(key)   # only reached after a successful, distinguishable outcome
            if i % 20 == 0:
                save_progress(done)

            time.sleep(REQUEST_SLEEP_SEC)

        save_progress(done)
        print(f"\nFinished {sensor}.\n")

    print("\nAll sensors complete. Raw cache is ready for step 4 (cleaning).")


def show_status(done: set):
    today = date.today()
    print("Progress by sensor:")
    for sensor, start_date in SENSORS.items():
        total_chunks = ceil(((today - start_date).days + 1) / DAY_RANGE)
        done_for_sensor = sum(1 for k in done if k.startswith(f"{sensor}|"))
        pct = done_for_sensor / total_chunks * 100 if total_chunks else 0
        print(f"  {sensor:18s}: {done_for_sensor:>5,}/{total_chunks:,} chunks ({pct:5.1f}%)")


def main():
    if not MAP_KEY:
        raise SystemExit(
            "ERROR: FIRMS_MAP_KEY environment variable not set.\n"
            "setx FIRMS_MAP_KEY \"your_key_here\"   (Windows, then open a NEW terminal)"
        )

    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true",
                         help="Show progress percentage per sensor and exit -- no network calls.")
    args = parser.parse_args()

    done = load_progress()

    if args.status:
        show_status(done)
        return

    print(f"Resuming: {len(done):,} chunks already completed in previous runs.")
    pull_all_detections(done)


if __name__ == "__main__":
    main()
