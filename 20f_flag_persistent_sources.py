"""
20f_flag_persistent_sources.py

Fix for a real finding, not a hypothetical: the Mumbai sanity-check anomaly
traced to ONGC's Uran gas processing plant -- a real industrial site with
documented fires and routine flaring, sitting against mangrove vegetation
that clears Hansen's canopy threshold. This is a known, documented
contaminant class in satellite active-fire products generally (gas flares,
refineries, similar stationary combustion sources), not specific to Mumbai
-- so this filter is applied NATIONALLY, not as a one-off patch.

THE SIGNAL THAT SEPARATES THIS FROM REAL WILDFIRE: recurrence at nearly the
identical location across many SEPARATE years. Real wildfires consume fuel
and need years to regrow before the same exact spot can burn again; a
stationary industrial source (flare stack, furnace) recurs indefinitely at
the same coordinate. This is the same logic dedicated gas-flare detection
research (e.g. VIIRS Nightfire) uses -- persistent nightly/annual detection
at a fixed point is the signature of stationary combustion, not spreading
fire.

METHOD: snap each qualifying event to a coarse ~1km grid cell (rounding
lat/lon to 2 decimal places), then flag any grid cell that has qualifying
events in >= PERSISTENT_YEAR_THRESHOLD separate years. Those events are
excluded before pincode scoring. This is a heuristic, not a definitive
industrial-site database -- it will occasionally flag a genuinely
fire-prone forest patch that burns unusually often (unlikely at this
threshold, but possible), and it won't catch an industrial source that
happens to have fewer than the threshold's worth of qualifying years in
the study window. Both are documented limitations, same treatment as
every other placeholder/threshold in this pipeline.

Usage:
    python 20f_flag_persistent_sources.py
"""

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

# ---- EDIT THESE FOR YOUR MACHINE ----
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
QUALIFYING_EVENTS_FILE = r"D:\Internship 2026\forestfire_qualifying_events.csv"
CLEAN_EVENTS_OUT = r"D:\Internship 2026\forestfire_qualifying_events_industrial_excluded.csv"
FLAGGED_SOURCES_OUT = r"D:\Internship 2026\forestfire_flagged_industrial_sources.csv"
PREVIEW_OUTPUT_FILE = r"D:\Internship 2026\pincode_forestfire_scores_PREVIEW_industrial_excluded.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_forestfire_scores.csv"

# SAFETY GATE: after the 18.7%-removal incident, this script no longer
# overwrites the real scores file by default. It writes a clearly-named
# PREVIEW file instead. Only flip this to True -- after you've personally
# reviewed FLAGGED_SOURCES_OUT and are confident the exclusions are
# correct -- to let it overwrite the real pincode_forestfire_scores.csv.
OVERWRITE_REAL_OUTPUT = False

EARTH_RADIUS_KM = 6371.0
BUFFER_KM = 20.0   # matches script 20c's final value
CURRENT_YEAR = pd.Timestamp.today().year
STUDY_START_YEAR = 2000

# A real forest patch can legitimately burn in many years -- that alone
# isn't suspicious, and a flat year-count threshold badly over-generalizes
# from the one confirmed case (Uran) that motivated this script: a first
# attempt at this filter with PERSISTENT_YEAR_THRESHOLD=5 removed 18.7% of
# ALL qualifying events nationally, including large numbers of locations in
# the Terai Sal forest belt, Western Ghats, and Northeast jhum-cultivation
# areas -- genuinely fire-prone ecosystems that reburn by nature, not
# industrial contamination. That run should NOT be trusted; this threshold
# is intentionally much stricter, calibrated against Uran's own actual
# numbers (9 distinct years out of the ~15-year VIIRS-era window, i.e.
# ~60% of years, in a ~1km-tight cluster) rather than picked arbitrarily.
#
# THIS SCRIPT'S OUTPUT IS A CANDIDATE LIST FOR MANUAL REVIEW, NOT AN
# AUTOMATIC NATIONAL EXCLUSION. Do not treat pincode_forestfire_scores.csv
# from this script as final without first opening FLAGGED_SOURCES_OUT and
# checking a sample of locations yourself -- ideally cross-referencing a
# few against a map or a known-industrial-sites list, the same way Uran
# was confirmed rather than assumed.
PERSISTENT_YEAR_FRACTION = 0.5   # >=50% of years since a location's FIRST
                                   # detection, not a flat count -- this
                                   # scales correctly whether a location's
                                   # first detection was 2012 or 2024
PERSISTENT_MIN_YEARS = 8          # AND at least this many distinct years,
                                   # so a location seen in only 2 of its
                                   # first 3 possible years doesn't qualify
                                   # just because 2/3 clears 50%
GRID_DECIMALS = 3   # ~110m grid cells -- tighter than the original 2
                     # decimals (~1.1km), matching how tightly Uran's own
                     # events actually clustered (within ~1km of each
                     # other, but a 110m cell size avoids merging separate
                     # nearby-but-distinct forest patches into one false
                     # "persistent" cell the way a coarser grid would


def flag_persistent_sources(events: pd.DataFrame):
    events = events.copy()
    events["_grid_lat"] = events["latitude"].round(GRID_DECIMALS)
    events["_grid_lon"] = events["longitude"].round(GRID_DECIMALS)

    grid_stats = (
        events.groupby(["_grid_lat", "_grid_lon"])["year"]
        .agg(distinct_years="nunique", first_year="min", last_year="max")
        .reset_index()
    )
    grid_stats["window_years"] = grid_stats["last_year"] - grid_stats["first_year"] + 1
    grid_stats["year_fraction"] = grid_stats["distinct_years"] / grid_stats["window_years"]

    persistent_cells = grid_stats[
        (grid_stats["year_fraction"] >= PERSISTENT_YEAR_FRACTION)
        & (grid_stats["distinct_years"] >= PERSISTENT_MIN_YEARS)
    ]

    pct_of_all_cells = len(persistent_cells) / len(grid_stats) * 100 if len(grid_stats) else 0
    print(f"Found {len(persistent_cells)} grid cell(s) ({pct_of_all_cells:.2f}% of all "
          f"{len(grid_stats)} occupied cells) meeting BOTH: detected in >= "
          f"{PERSISTENT_YEAR_FRACTION*100:.0f}% of years since first detection, "
          f"AND >= {PERSISTENT_MIN_YEARS} distinct years total.\n")

    if persistent_cells.empty:
        return events.drop(columns=["_grid_lat", "_grid_lon"]), pd.DataFrame()

    flagged_mask = events.set_index(["_grid_lat", "_grid_lon"]).index.isin(
        persistent_cells.set_index(["_grid_lat", "_grid_lon"]).index
    )

    flagged_events = events[flagged_mask].copy()
    clean_events = events[~flagged_mask].drop(columns=["_grid_lat", "_grid_lon"])

    pct_events_removed = len(flagged_events) / len(events) * 100
    print(f"This would remove {len(flagged_events):,} of {len(events):,} events "
          f"({pct_events_removed:.2f}% of all data).")
    if pct_events_removed > 2.0:
        print(f"  ** WARNING: {pct_events_removed:.1f}% is a lot to remove as 'industrial' **")
        print(f"  ** Sanity-check FLAGGED_SOURCES_OUT carefully before trusting this. **\n")

    summary = (
        flagged_events.groupby(["_grid_lat", "_grid_lon"])
        .agg(distinct_years=("year", "nunique"),
             total_events=("year", "size"),
             max_frp_mw=("max_frp_mw", "max"),
             first_year=("year", "min"),
             last_year=("year", "max"))
        .reset_index()
        .sort_values("distinct_years", ascending=False)
    )
    print("Flagged locations (cross-check these against a map before trusting the exclusion):")
    print(summary.to_string(index=False))
    print()

    return clean_events, summary


def score_pincodes(pincodes: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Same scoring logic as script 20c -- percentiles ranked only among
    pincodes with >=1 qualifying event."""
    total_years = CURRENT_YEAR - STUDY_START_YEAR + 1

    event_rad = np.radians(events[["latitude", "longitude"]].values)
    tree = BallTree(event_rad, metric="haversine")
    radius_rad = BUFFER_KM / EARTH_RADIUS_KM

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
    scores["buffer_km"] = BUFFER_KM
    return scores


def main():
    pincodes = pd.read_csv(PINCODE_FILE).dropna(subset=["latitude", "longitude"])
    pincodes["pincode"] = pincodes["pincode"].astype(str)
    events = pd.read_csv(QUALIFYING_EVENTS_FILE)
    print(f"Loaded {len(events):,} qualifying events, {len(pincodes):,} pincodes\n")

    clean_events, flagged_summary = flag_persistent_sources(events)
    print(f"{len(events):,} -> {len(clean_events):,} events after excluding "
          f"likely industrial/stationary sources "
          f"({len(events) - len(clean_events):,} removed)\n")

    clean_events.to_csv(CLEAN_EVENTS_OUT, index=False)
    if not flagged_summary.empty:
        flagged_summary.to_csv(FLAGGED_SOURCES_OUT, index=False)
        print(f"Flagged-source summary saved to {FLAGGED_SOURCES_OUT} -- "
              f"review before treating any exclusion as final.")

    print("\nRe-scoring pincodes with cleaned events...")
    scores = score_pincodes(pincodes, clean_events)

    if OVERWRITE_REAL_OUTPUT:
        scores.to_csv(OUTPUT_FILE, index=False)
        print(f"Wrote {len(scores):,} pincodes -> {OUTPUT_FILE} (REAL output file overwritten)")
    else:
        scores.to_csv(PREVIEW_OUTPUT_FILE, index=False)
        print(f"Wrote {len(scores):,} pincodes -> {PREVIEW_OUTPUT_FILE} (PREVIEW only --")
        print(f"  the real {OUTPUT_FILE} was NOT touched. Review the flagged-sources")
        print(f"  list above first; set OVERWRITE_REAL_OUTPUT = True only once you")
        print(f"  trust the exclusions.)")

    print("\nRe-checking the sanity-check pincodes with industrial sources excluded:")
    checks = {
        "Similipal": "757043", "Bandipur": "571126", "Nagarhole": "571121",
        "Central Delhi": "110001", "Central Mumbai": "400001",
    }
    for label, pin in checks.items():
        match = scores[scores["pincode"] == pin]
        if not match.empty:
            r = match.iloc[0]
            print(f"  {label} ({pin}): {r['num_qualifying_events']} events, "
                  f"verdict: {r['verdict']}")


if __name__ == "__main__":
    main()