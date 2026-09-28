"""
STEP 2 of 4 -- Geocode the small number of pincodes that step 1
flagged as NEEDS_NOMINATIM (typically ~25-30 out of ~19,500).

Uses Nominatim (OpenStreetMap's free geocoder). Respects their usage
policy: max 1 request/second, real User-Agent required.
Policy: https://operations.osmfoundation.org/policies/nominatim/
"""

import csv
import time
import requests

# ---- EDIT THIS FOR YOUR MACHINE ----
INPUT_FILE = r"D:/Internship 2026/pincode_master_coordinates.csv"
OUTPUT_FILE = r"D:/Internship 2026/pincode_master_coordinates.csv"
# -------------------------------------

HEADERS = {"User-Agent": "climate-risk-model-project (your_email@company.com)"}


def geocode_pincode(pincode, country="India"):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"postalcode": pincode, "country": country, "format": "json", "limit": 1}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    if results:
        return results[0]["lat"], results[0]["lon"]
    return None, None


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    to_geocode = [r for r in rows if r["geocode_status"] == "NEEDS_NOMINATIM"]
    print(f"Geocoding {len(to_geocode)} pincodes via Nominatim...")

    for row in to_geocode:
        pin = row["pincode"]
        lat, lon = geocode_pincode(pin)
        if lat and lon:
            row["latitude"] = lat
            row["longitude"] = lon
            row["geocode_status"] = "from_nominatim"
            print(f"  {pin}: resolved to {lat}, {lon}")
        else:
            row["geocode_status"] = "UNRESOLVED_manual_check_needed"
            print(f"  {pin}: Nominatim found nothing -- needs manual check")
        time.sleep(1.1)  # respect 1 req/sec rate limit

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()