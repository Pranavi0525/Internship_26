"""
20b_diagnose_forestfire_buffer.py

Diagnostic, not a pipeline step -- run this BEFORE touching BUFFER_KM in
script 20.

WHY THIS EXISTS: 05/20's sanity check showed 0 qualifying events within
5km for ALL FIVE test pincodes, including Similipal/Bandipur/Nagarhole --
known hotspots with nationally-reported fire history (e.g. Similipal 2021).
"Zero within a 5km buffer" and "zero nearby ever" are different problems
with different fixes:

  - If the NEAREST event to Similipal's pincode centroid is, say, 8-40km
    away: the buffer is just too tight for how that pincode's coordinate
    is defined (a rural/forest post office point can sit well outside the
    actual burn area of a 2,000+ sq km reserve). Fix: widen BUFFER_KM.
  - If the nearest event is hundreds of km away, or NaN: that's not a
    buffer problem, that's a data/coordinate bug (e.g. a lat/lon mix-up
    somewhere upstream) and widening the buffer would just paper over it.

This script is cheap to run because it reuses the already-saved
forestfire_qualifying_events.csv (648K rows) instead of re-touching the
26M-row raw detection cache -- no re-run of masking/filtering/clustering
needed.

Usage:
    python 20b_diagnose_forestfire_buffer.py
"""

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

# ---- EDIT THESE FOR YOUR MACHINE (same paths as script 20) ----
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
QUALIFYING_EVENTS_FILE = r"D:\Internship 2026\forestfire_qualifying_events.csv"

EARTH_RADIUS_KM = 6371.0
FINAL_BUFFER_KM = 25.0
WRITE_FINAL_OUTPUT = True

SANITY_PINCODES = {
    "Similipal, Odisha (known hotspot)": "757043",
    "Bandipur, Karnataka (known hotspot)": "571126",
    "Nagarhole, Karnataka (known hotspot)": "571121",
    "Central Delhi (urban core, no forest)": "110001",
    "Central Mumbai (urban core, no forest)": "400001",
}


def main():
    pincodes = pd.read_csv(PINCODE_FILE).dropna(subset=["latitude", "longitude"])
    pincodes["pincode"] = pincodes["pincode"].astype(str)

    events = pd.read_csv(QUALIFYING_EVENTS_FILE)
    print(f"Loaded {len(events):,} qualifying events, {len(pincodes):,} pincodes\n")

    if events.empty:
        print("Events file is empty -- nothing to measure distance to. "
              "Go back to script 20's masking/filtering/clustering steps.")
        return

    event_rad = np.radians(events[["latitude", "longitude"]].values)
    tree = BallTree(event_rad, metric="haversine")

    print(f"{'Location':45s} {'Nearest event':>15s} {'Event date':>12s}")
    print("-" * 75)
    for label, pin in SANITY_PINCODES.items():
        match = pincodes[pincodes["pincode"] == str(pin)]
        if match.empty:
            print(f"{label:45s} pincode {pin} not found in master file")
            continue

        row = match.iloc[0]
        pin_rad = np.radians([[row["latitude"], row["longitude"]]])
        dist_rad, idx = tree.query(pin_rad, k=1)
        dist_km = dist_rad[0][0] * EARTH_RADIUS_KM
        nearest_event = events.iloc[idx[0][0]]
        event_date = nearest_event.get("event_date", "?")

        print(f"{label:45s} {dist_km:>12.1f} km {str(event_date):>15s}")

    print("\nInterpretation:")
    print("  Nearest event a few / a few dozen km away at the hotspot rows")
    print("    -> buffer is genuinely too tight -- go widen BUFFER_KM and re-test.")
    print("  Nearest event hundreds+ km away, or wildly inconsistent with")
    print("    known geography -- stop, don't touch BUFFER_KM yet, there's")
    print("    likely a coordinate/data bug upstream (check pincode master")
    print("    file's lat/lon columns for that pincode, and double check")
    print("    lat/lon column order wasn't swapped anywhere in script 20).")
    print("  Urban rows (Delhi/Mumbai) should show large distances regardless")
    print("    -- that's expected and not a bug signal on its own.")


if __name__ == "__main__":
    main()
