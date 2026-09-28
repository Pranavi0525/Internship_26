"""
20c_buffer_sensitivity_test.py

Step 6 of the plan -- "choose and justify your buffer radius" -- run
this AFTER 20b confirmed the issue is a too-tight buffer, not a data bug.

WHAT THIS DOES: re-runs the scoring step (buffer join + frequency/
intensity) for several candidate BUFFER_KM values, WITHOUT re-touching
the 26M-row raw cache or re-running masking/filtering/clustering --
those don't depend on buffer radius at all, so this reuses the already-
saved forestfire_qualifying_events.csv (648K rows) directly. Each
candidate radius takes seconds, not the original script 20's full runtime.

20b's diagnostic already told you the floor: Nagarhole's nearest event
is 18.3km away, so anything below ~20km will structurally miss it no
matter how many other events exist. This script lets you see the
tradeoff as you widen past that floor -- more coverage at the real
hotspots, but also more "reach" into whatever surrounds urban pincodes.

HOW TO USE THE OUTPUT: for each candidate radius, look at (a) whether
all 3 known hotspots now show >=1 event, and (b) whether the urban
pincodes start picking up events too, and if so, whether that's
plausible (e.g. Mumbai has real forest in its outskirts -- Sanjay
Gandhi National Park -- so some nonzero result at wider radii isn't
automatically wrong) or a sign you've gone too wide. There's no single
"correct" answer here -- FSI doesn't mandate a pincode-buffer distance
for this exact use case, unlike IMD's 64.5mm flood threshold or WMO's
34kt cyclone threshold, which is why this is a documented judgment call,
not a computed constant.

Once you've picked a radius, set FINAL_BUFFER_KM below and re-run this
script with WRITE_FINAL_OUTPUT = True to produce the real
pincode_forestfire_scores.csv (same file path/schema script 20 writes,
so nothing downstream -- including 12_merge_all_hazards.py -- needs to
change).

Usage:
    python 20c_buffer_sensitivity_test.py
"""

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

# ---- EDIT THESE FOR YOUR MACHINE (same paths as script 20) ----
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
QUALIFYING_EVENTS_FILE = r"D:\Internship 2026\forestfire_qualifying_events.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_forestfire_scores.csv"

EARTH_RADIUS_KM = 6371.0
CURRENT_YEAR = pd.Timestamp.today().year
STUDY_START_YEAR = 2000

# Candidates to compare -- Nagarhole's nearest event is 18.3km (see 20b),
# so anything below that structurally can't catch it. Starting below that
# floor anyway to show the contrast.
CANDIDATE_RADII_KM = [5, 10, 15, 20, 25, 30]

# Once you've picked one from the comparison table, set this and flip
# WRITE_FINAL_OUTPUT to True to write the real scores file.
FINAL_BUFFER_KM = 20.0
WRITE_FINAL_OUTPUT = True

SANITY_PINCODES = {
    "Similipal, Odisha (known hotspot)": "757043",
    "Bandipur, Karnataka (known hotspot)": "571126",
    "Nagarhole, Karnataka (known hotspot)": "571121",
    "Central Delhi (urban core, no forest)": "110001",
    "Central Mumbai (urban core, no forest)": "400001",
}


def score_pincodes(pincodes: pd.DataFrame, events: pd.DataFrame, buffer_km: float) -> pd.DataFrame:
    """Same logic as script 20's score_pincodes(), parameterized on
    buffer_km instead of a module-level constant."""
    total_years = CURRENT_YEAR - STUDY_START_YEAR + 1

    event_rad = np.radians(events[["latitude", "longitude"]].values)
    tree = BallTree(event_rad, metric="haversine")
    radius_rad = buffer_km / EARTH_RADIUS_KM

    pin_rad = np.radians(pincodes[["latitude", "longitude"]].values)
    neighbor_idx = tree.query_radius(pin_rad, r=radius_rad)

    rows = []
    for i, idxs in enumerate(neighbor_idx):
        pin_events = events.iloc[idxs]
        n_events = len(pin_events)
        years_hit = pin_events["year"].nunique() if n_events else 0
        max_frp = pin_events["max_frp_mw"].max() if n_events else 0.0
        rows.append({
            "pincode": pincodes.iloc[i]["pincode"],
            "num_qualifying_events": n_events,
            "years_with_event": years_hit,
            "total_years_in_window": total_years,
            "frequency_pct": years_hit / total_years * 100,
            "max_frp_mw": round(float(max_frp), 2) if n_events else 0.0,
        })

    scores = pd.DataFrame(rows)

    # FIXED: percentiles used to be ranked across ALL 19,564 pincodes,
    # including the ~47% with zero events. That zero-mass sits at the
    # bottom of the rank, which means the MINIMUM frequency_percentile
    # among pincodes with even a single event was already ~51% -- so any
    # nonzero pincode automatically cleared the ">=50" bar for "high
    # frequency"/"high intensity" regardless of how small its actual
    # count or FRP was. That collapsed the 4-way verdict grid down to
    # effectively 2 real outcomes (event vs no event) and mislabeled
    # low-activity fire-affected pincodes as "severe".
    #
    # Now percentiles are ranked ONLY among pincodes that actually have
    # >=1 qualifying event, so "top half" means top half of fire-affected
    # areas, not top half of the whole country (most of which never had
    # a single qualifying fire). Zero-event pincodes get NaN percentiles
    # -- not meaningful for them, and their verdict is decided before
    # percentiles are even looked at (see verdict() below).
    nonzero = scores["num_qualifying_events"] > 0
    scores["frequency_percentile"] = np.nan
    scores["intensity_percentile"] = np.nan
    if nonzero.any():
        scores.loc[nonzero, "frequency_percentile"] = (
            scores.loc[nonzero, "frequency_pct"].rank(pct=True) * 100
        )
        scores.loc[nonzero, "intensity_percentile"] = (
            scores.loc[nonzero, "max_frp_mw"].rank(pct=True) * 100
        )

    def verdict(row):
        if row["num_qualifying_events"] == 0:
            return "No qualifying events in study window"
        freq_high = row["frequency_percentile"] >= 50
        int_high = row["intensity_percentile"] >= 50
        if freq_high and int_high:
            return "Frequent-and-severe"
        if freq_high and not int_high:
            return "Frequent-but-mild"
        if not freq_high and int_high:
            return "Rare-but-severe"
        return "Rare-and-mild"

    scores["verdict"] = scores.apply(verdict, axis=1)
    scores["buffer_km"] = buffer_km
    return scores


def main():
    pincodes = pd.read_csv(PINCODE_FILE).dropna(subset=["latitude", "longitude"])
    pincodes["pincode"] = pincodes["pincode"].astype(str)
    events = pd.read_csv(QUALIFYING_EVENTS_FILE)
    print(f"Loaded {len(pincodes):,} pincodes, {len(events):,} qualifying events\n")

    print(f"{'Buffer':>8s} | " + " | ".join(f"{k.split(',')[0]:>10s}" for k in SANITY_PINCODES) +
          " | Nationwide: pincodes w/ >=1 event")
    print("-" * 130)

    for radius in CANDIDATE_RADII_KM:
        scores = score_pincodes(pincodes, events, radius)
        scores["pincode"] = scores["pincode"].astype(str)

        cells = []
        for label, pin in SANITY_PINCODES.items():
            match = scores[scores["pincode"] == pin]
            n = match.iloc[0]["num_qualifying_events"] if not match.empty else "?"
            cells.append(f"{n:>10}")

        nonzero_pincodes = (scores["num_qualifying_events"] > 0).sum()
        print(f"{radius:>6.0f}km | " + " | ".join(cells) +
              f" | {nonzero_pincodes:,}/{len(scores):,}")

    print("\nColumns above are: Similipal, Bandipur, Nagarhole, Delhi, Mumbai "
          "(event counts at each buffer)")

    if WRITE_FINAL_OUTPUT:
        print(f"\nWriting final scores at BUFFER_KM={FINAL_BUFFER_KM} to {OUTPUT_FILE} ...")
        final_scores = score_pincodes(pincodes, events, FINAL_BUFFER_KM)
        final_scores.to_csv(OUTPUT_FILE, index=False)
        print(f"Done. Wrote {len(final_scores):,} pincodes -> {OUTPUT_FILE}")
        print("This is the same file/schema script 20 produces -- "
              "12_merge_all_hazards.py needs no changes.")
    else:
        print(f"\nWRITE_FINAL_OUTPUT is False -- nothing written yet. "
              f"Pick a radius from the table, set FINAL_BUFFER_KM, "
              f"flip WRITE_FINAL_OUTPUT to True, and re-run.")


if __name__ == "__main__":
    main()