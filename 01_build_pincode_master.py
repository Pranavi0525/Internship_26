"""
STEP 1 of 4, v2 -- Build the pincode master table.

WHY THIS VERSION EXISTS: the visual map check on the seismic zone
output revealed that ~2,602 rows in the raw government file have
physically impossible coordinates (latitude > 90, or points sitting
outside India entirely). Investigation showed most of these are a
common, specific error: latitude and longitude are SWAPPED in the
source data (e.g. a Telangana post office listed as lat=79.0,
lon=17.0 instead of the correct lat=17.0, lon=79.0).

This version detects and auto-corrects that swap, and separately
flags the smaller number of rows that are broken in a way swapping
can't fix (e.g. coordinates that land in Afghanistan, or duplicate
lat=lon values) so they get treated the same as "no coordinate found"
rather than silently poisoning your data with a wrong location.

Source of the raw file:
  https://www.data.gov.in/catalog/all-india-pincode-directory
"""

import csv
from collections import defaultdict

# ---- EDIT THIS FOR YOUR MACHINE ----
RAW_PINCODE_FILE = r"D:/Internship 2026/5c2f62fe-5afa-4119-a499-fec9d604d5bd (1).csv"
OUTPUT_FILE = r"D:/Internship 2026/pincode_master_coordinates.csv"
# -------------------------------------

# India's real bounding box, generously -- anything outside this is a
# swap, a data entry error, or a genuinely broken row.
INDIA_LAT_RANGE = (6, 38)
INDIA_LON_RANGE = (68, 98)


def is_valid_coord(value):
    return value.strip() not in ("NA", "", "0", "NaN")


def in_india_bounds(lat, lon):
    return INDIA_LAT_RANGE[0] <= lat <= INDIA_LAT_RANGE[1] and INDIA_LON_RANGE[0] <= lon <= INDIA_LON_RANGE[1]


def resolve_coordinate(lat_str, lon_str):
    """Returns (lat, lon, status). Tries the value as given, then tries
    it with lat/long swapped, then gives up."""
    try:
        lat, lon = float(lat_str), float(lon_str)
    except ValueError:
        return None, None, "unparseable"

    if in_india_bounds(lat, lon):
        return lat, lon, "ok"
    if in_india_bounds(lon, lat):
        return lon, lat, "swapped_corrected"
    return None, None, "out_of_bounds_unfixable"


def main():
    pin_rows = defaultdict(list)
    with open(RAW_PINCODE_FILE, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [fn.strip().lower() for fn in reader.fieldnames]
        for row in reader:
            row = {k.strip().lower(): v for k, v in row.items()}
            pin_rows[row["pincode"]].append(row)

    master = []
    stats = defaultdict(int)

    for pin, rows in sorted(pin_rows.items()):
        chosen = None
        for r in rows:
            if not (is_valid_coord(r["latitude"]) and is_valid_coord(r["longitude"])):
                continue
            lat, lon, status = resolve_coordinate(r["latitude"], r["longitude"])
            if lat is not None:
                chosen = (r, lat, lon, status)
                break

        if chosen:
            r, lat, lon, status = chosen
            master.append({
                "pincode": pin, "locality": r["officename"], "district": r["district"],
                "state": r["statename"], "latitude": lat, "longitude": lon,
                "geocode_status": "from_govt_file" if status == "ok" else status,
            })
            stats[status] += 1
        else:
            first = rows[0]
            master.append({
                "pincode": pin, "locality": first["officename"], "district": first["district"],
                "state": first["statename"], "latitude": "", "longitude": "",
                "geocode_status": "NEEDS_NOMINATIM",
            })
            stats["needs_nominatim"] += 1

    fieldnames = ["pincode", "locality", "district", "state", "latitude", "longitude", "geocode_status"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(master)

    print(f"Total unique pincodes: {len(master)}")
    print(f"Clean, valid as-is: {stats['ok']}")
    print(f"Auto-corrected (lat/long were swapped in source): {stats['swapped_corrected']}")
    print(f"Needs geocoding (no usable coordinate found anywhere): {stats['needs_nominatim']}")
    print(f"Written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()