"""
20e_investigate_sanity_check_anomalies.py

Diagnostic, not a pipeline step. The merged output's sanity check came back
mixed, not a clean pass -- three specific things worth looking at before
calling forest fire validated:

  1. Mumbai (400001), our urban negative control, showed 32 qualifying
     events over 9 years ("Frequent-but-mild"), not the near-zero result
     Delhi showed. Central Mumbai is ~25-30km from Sanjay Gandhi National
     Park -- OUTSIDE the 20km buffer -- so "of course SGNP is nearby"
     isn't a satisfying explanation on its own. Something needs checking:
     either there's real, legitimate forest-adjacent fire activity within
     20km of this specific pincode's coordinate that we're not aware of,
     or the pincode's own lat/lon (from the master coordinates file) is
     off, or the forest mask is passing something it shouldn't near a
     dense urban area.

  2. Bandipur (571126) showed max_frp_mw = 4,252 -- the same "thousands
     of MW" outlier range 20d already flagged for Mizoram/Nagaland, but
     this is Karnataka, a location the master doc doesn't currently call
     out. Same question as before: real severe wildfire pixel, or a
     non-wildfire heat source / sensor artifact?

  3. Similipal (757043) -- the case that most directly motivated adding
     this hazard, given the widely-reported 2021 fire crisis -- came back
     "Frequent-but-mild" with max_frp_mw of only 31. That's low for what
     was a major, sustained fire event. Worth seeing whether the buffer/
     clustering is actually capturing the severe portion of that fire,
     or missing it.

This script prints every qualifying event within each of these three
pincodes' buffers, sorted, so you can look at the actual dates/locations
yourself rather than trusting the single aggregate max_frp_mw number.

Usage:
    python 20e_investigate_sanity_check_anomalies.py
"""

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

# ---- EDIT THESE FOR YOUR MACHINE (same paths as script 20/20b/20c) ----
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
QUALIFYING_EVENTS_FILE = r"D:\Internship 2026\forestfire_qualifying_events.csv"

EARTH_RADIUS_KM = 6371.0
BUFFER_KM = 20.0   # matches the final buffer chosen in script 20c

TARGETS = {
    "Mumbai (400001) -- unexpected non-zero urban control": "400001",
    "Bandipur (571126) -- 4,252 MW outlier": "571126",
    "Similipal (757043) -- surprisingly low max FRP for a known severe fire": "757043",
}


def main():
    pincodes = pd.read_csv(PINCODE_FILE).dropna(subset=["latitude", "longitude"])
    pincodes["pincode"] = pincodes["pincode"].astype(str)

    events = pd.read_csv(QUALIFYING_EVENTS_FILE)
    if "event_date" in events.columns:
        events["event_date"] = pd.to_datetime(events["event_date"])
    print(f"Loaded {len(events):,} qualifying events, {len(pincodes):,} pincodes\n")

    event_rad = np.radians(events[["latitude", "longitude"]].values)
    tree = BallTree(event_rad, metric="haversine")
    radius_rad = BUFFER_KM / EARTH_RADIUS_KM

    for label, pin in TARGETS.items():
        print("=" * 90)
        print(label)
        print("=" * 90)

        match = pincodes[pincodes["pincode"] == pin]
        if match.empty:
            print(f"  Pincode {pin} not found in master file -- can't proceed for this one.\n")
            continue

        row = match.iloc[0]
        print(f"  Pincode coordinate on file: lat={row['latitude']:.5f}, lon={row['longitude']:.5f}")
        print(f"  (Cross-check this against a map yourself -- if it's not actually where")
        print(f"   {pin} should be, that alone would explain a lot.)\n")

        pin_rad = np.radians([[row["latitude"], row["longitude"]]])
        idxs = tree.query_radius(pin_rad, r=radius_rad)[0]

        if len(idxs) == 0:
            print("  No qualifying events found within buffer -- inconsistent with the merged")
            print("  output showing nonzero events. Re-check BUFFER_KM and file paths above.\n")
            continue

        nearby = events.iloc[idxs].copy()
        dist_rad = np.radians(nearby[["latitude", "longitude"]].values)
        # distance from THIS pincode to each event, for sorting/context
        from sklearn.metrics.pairwise import haversine_distances
        dists_km = haversine_distances(pin_rad, dist_rad)[0] * EARTH_RADIUS_KM
        nearby["dist_from_pincode_km"] = dists_km
        nearby = nearby.sort_values("max_frp_mw", ascending=False)

        cols = [c for c in ["event_date", "latitude", "longitude", "dist_from_pincode_km",
                             "pixel_count", "max_frp_mw", "year"] if c in nearby.columns]
        with pd.option_context("display.max_rows", None, "display.width", 160):
            print(nearby[cols].to_string(index=False))
        print(f"\n  {len(nearby)} total qualifying events within {BUFFER_KM}km.\n")

    print("What to actually do with this:")
    print("  - For Mumbai: look up each event's lat/lon on a map. Real forest patch")
    print("    (e.g. Sanjay Gandhi NP, Aarey, Powai hills) within 20km of Fort/Colaba,")
    print("    or something else -- a stray point in the wrong place, a coordinate")
    print("    that doesn't look like Mumbai at all?")
    print("  - For Bandipur: is the 4,252 MW single reading's pixel_count near the")
    print("    FSI minimum of 3 (small event, one extreme pixel dominating) or a large")
    print("    genuinely severe cluster? The former is more suspicious than the latter.")
    print("  - For Similipal: are there OTHER high-FRP events in the list that the")
    print("    aggregate 'max' should have caught but something's off, or does the")
    print("    2021 crisis genuinely show up as many moderate-intensity detections")
    print("    rather than one extreme pixel (plausible -- FRP is per-pixel, and a")
    print("    fire that spread across a wide forested area rather than concentrating")
    print("    can legitimately show moderate per-pixel readings throughout)?")


if __name__ == "__main__":
    main()