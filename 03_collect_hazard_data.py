"""
STEP 3 of 4 -- Collect hazard data for every pincode.

Computes FOUR conditions per pincode, each with frequency + intensity
(or trend) where applicable:
  1. Flood / extreme rainfall
  2. Heatwave
  3. Drought (longest dry spell)
  4. Chronic temperature rise (20-year warming trend)

Two modes:
  TEST_LIMIT = small number  -> quick demo run, free tier, few pincodes
  TEST_LIMIT = None          -> full run, all pincodes in your master file

Set USE_PAID_TIER = True once your Open-Meteo commercial plan is active
(needed for full-scale runs -- free tier is 10,000 calls/day and has
no uptime guarantee, fine for demos, not for production).

Has checkpointing: safe to stop and re-run, it will skip pincodes
already written to the output file.
"""

import csv
import os
import time
import requests

# ---- EDIT THESE FOR YOUR SETUP ----
INPUT_FILE = r"D:\Internship 2026\pincode_master_geocoded.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_hazard_scores.csv"
TEST_LIMIT = 50         # set to None to run the full file
USE_PAID_TIER = False    # set True once you have an Open-Meteo commercial API key
API_KEY = "PASTE_YOUR_OPEN_METEO_API_KEY_HERE"
# ------------------------------------

START_DATE = "2004-01-01"
END_DATE = "2023-12-31"
HEAVY_RAIN_MM = 64.5        # IMD "heavy rainfall" threshold (24hr)
HEATWAVE_TEMP_C = 40.0      # IMD heatwave threshold for plains
DROUGHT_DRY_DAY_MM = 1.0    # a day counts as "dry" if rainfall < 1mm
DROUGHT_NOTABLE_SPELL_DAYS = 21   # a year counts as a "drought year" if its
                                  # longest dry spell reaches 3+ weeks.
                                  # NOTE: unlike the 64.5mm rain threshold,
                                  # this is NOT an official IMD-published
                                  # cutoff -- there is no single-day drought
                                  # threshold as clean as the rainfall one.
                                  # This is a defensible, stated proxy
                                  # (three weeks with no meaningful rain),
                                  # not an authoritative government figure.
                                  # Say this plainly in your methodology doc.

MAX_RETRIES = 5
INITIAL_BACKOFF = 5  # seconds
REQUEST_DELAY_SEC = 1.5 if not USE_PAID_TIER else 0.1


def fetch_historical_daily(lat, lon):
    if USE_PAID_TIER:
        url = "https://customer-api.open-meteo.com/v1/archive"
    else:
        url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": "precipitation_sum,temperature_2m_max",
        "timezone": "Asia/Kolkata",
    }
    if USE_PAID_TIER:
        params["apikey"] = API_KEY

    backoff = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=60)
            if resp.status_code == 429:
                print(f"    Rate limited (429). Waiting {backoff}s before retry {attempt}/{MAX_RETRIES}...")
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()["daily"]
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"    Error ({e}). Waiting {backoff}s before retry {attempt}/{MAX_RETRIES}...")
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries for lat={lat}, lon={lon}")


def compute_scores(daily):
    dates = daily["time"]
    precip = daily["precipitation_sum"]
    tmax = daily["temperature_2m_max"]

    by_year_precip, by_year_tmax = {}, {}
    for d, p, t in zip(dates, precip, tmax):
        yr = int(d[:4])
        by_year_precip.setdefault(yr, []).append(p if p is not None else 0.0)
        by_year_tmax.setdefault(yr, []).append(t if t is not None else float("nan"))

    years = sorted(by_year_precip.keys())
    n_years = len(years)

    # 1. Flood / extreme rainfall
    heavy_rain_years = set()
    max_rain = 0.0
    for d, p in zip(dates, precip):
        if p is not None:
            if p >= HEAVY_RAIN_MM:
                heavy_rain_years.add(d[:4])
            if p > max_rain:
                max_rain = p
    flood_frequency = round(100 * len(heavy_rain_years) / n_years, 1)
    flood_intensity = round(max_rain, 1)

    # 2. Heatwave
    heat_days = sum(1 for t in tmax if t is not None and t >= HEATWAVE_TEMP_C)
    max_temp = max((t for t in tmax if t is not None), default=float("nan"))
    heat_frequency = round(100 * heat_days / (n_years * 365), 2)
    heat_intensity = round(max_temp, 1)

    # 3. Drought: TWO separate dimensions now, mirroring flood's structure --
    #    FREQUENCY = fraction of years with a "notable" drought (a dry
    #    spell of 21+ days), INTENSITY = worst dry spell ever recorded.
    max_streaks = []
    drought_years = set()
    for yr in years:
        streak, longest = 0, 0
        for p in by_year_precip[yr]:
            if p < DROUGHT_DRY_DAY_MM:
                streak += 1
                longest = max(longest, streak)
            else:
                streak = 0
        max_streaks.append(longest)
        if longest >= DROUGHT_NOTABLE_SPELL_DAYS:
            drought_years.add(yr)
    drought_avg = round(sum(max_streaks) / len(max_streaks), 1)
    drought_worst = max(max_streaks)
    drought_frequency = round(100 * len(drought_years) / n_years, 1)

    # 4. Chronic temperature rise: first 5 years vs last 5 years
    early_years, late_years = years[:5], years[-5:]
    early_avg = sum(sum(by_year_tmax[y]) / len(by_year_tmax[y]) for y in early_years) / len(early_years)
    late_avg = sum(sum(by_year_tmax[y]) / len(by_year_tmax[y]) for y in late_years) / len(late_years)
    warming_trend = round(late_avg - early_avg, 2)

    return {
        "flood_frequency_pct_years": flood_frequency,
        "flood_intensity_max_mm": flood_intensity,
        "heat_frequency_pct_days": heat_frequency,
        "heat_intensity_max_c": heat_intensity,
        "drought_avg_longest_dry_spell_days": drought_avg,
        "drought_worst_dry_spell_days": drought_worst,
        "drought_frequency_pct_years": drought_frequency,
        "warming_trend_c_20yr": warming_trend,
    }


def load_already_done():
    done = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                done.add(row["pincode"])
    return done


def open_output_for_append(path, retries=6, wait_sec=5):
    """Open OUTPUT_FILE for appending, retrying if it's locked (e.g. open
    in Excel). Prevents a locked file from crashing the whole run --
    just close the file in Excel and it'll pick up automatically."""
    for attempt in range(1, retries + 1):
        try:
            return open(path, "a", newline="", encoding="utf-8-sig")
        except PermissionError:
            print(f"    Can't write to {path} -- it looks like it's open in "
                  f"Excel or another program. Close it now. "
                  f"Retrying in {wait_sec}s... ({attempt}/{retries})")
            time.sleep(wait_sec)
    raise PermissionError(
        f"Still can't write to {path} after {retries} attempts. "
        f"Make sure it isn't open in Excel or any other program, then rerun the script."
    )


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        all_rows = [r for r in csv.DictReader(f) if r.get("latitude") and r.get("longitude")]

    if TEST_LIMIT:
        all_rows = all_rows[:TEST_LIMIT]
        print(f"TEST MODE: processing {len(all_rows)} pincodes")

    already_done = load_already_done()
    to_process = [r for r in all_rows if r["pincode"] not in already_done]
    print(f"Total: {len(all_rows)} | already done: {len(already_done)} | remaining: {len(to_process)}")

    fieldnames = ["pincode", "locality", "district", "state", "flood_frequency_pct_years",
                  "flood_intensity_max_mm", "heat_frequency_pct_days", "heat_intensity_max_c",
                  "drought_avg_longest_dry_spell_days", "drought_worst_dry_spell_days",
                  "drought_frequency_pct_years", "warming_trend_c_20yr"]
    write_header = not os.path.exists(OUTPUT_FILE)

    f = open_output_for_append(OUTPUT_FILE)
    try:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for i, row in enumerate(to_process):
            pin = row["pincode"]
            print(f"[{i+1}/{len(to_process)}] {pin} ({row['locality']}, {row['district']}, {row['state']})...")
            try:
                daily = fetch_historical_daily(row["latitude"], row["longitude"])
                scores = compute_scores(daily)
                scores.update({"pincode": pin, "locality": row["locality"],
                                "district": row["district"], "state": row["state"]})
                writer.writerow(scores)
                f.flush()
            except Exception as e:
                print(f"    FAILED: {e}")
            time.sleep(REQUEST_DELAY_SEC)
    finally:
        f.close()

    print(f"\nDone. Results in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()