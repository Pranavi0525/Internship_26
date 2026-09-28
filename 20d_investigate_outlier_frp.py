"""
20d_investigate_outlier_frp.py

Diagnostic, not a pipeline step. Run this to look at the handful of
extreme max_frp_mw values that showed up identically across several
neighboring pincodes in pincode_forestfire_scores.csv (e.g. 7,513.7 MW
repeated across four 798xxx Mizoram pincodes, 5,182.0 MW repeated across
several 796xxx Nagaland pincodes).

WHY THE REPEATS ACROSS PINCODES AREN'T THE CONCERN: with a 25km buffer,
one extreme single-pixel FRP reading can legitimately fall inside
several neighboring pincodes' buffers at once, so it becomes each of
their "max" independently. That part is expected, not a bug.

WHAT IS WORTH CHECKING: whether 5,000-7,500 MW for a single VIIRS/MODIS
pixel is a real wildfire signal or something else. Typical wildfire FRP
per pixel is more commonly in the tens to low hundreds of MW; values in
the thousands are exceptional and, in other contexts, are sometimes
associated with non-wildfire heat sources (gas flares, large industrial
fires) or sensor artifacts, rather than forest fire specifically. This
region (Mizoram/Nagaland) is also known for jhum (shifting) cultivation
burning inside secondary-forest land that can still clear Hansen's
>=10% canopy threshold -- i.e. land the forest mask wouldn't necessarily
screen out, unlike Punjab/Haryana stubble burning on open agricultural
land.

This script pulls out the underlying event rows for manual inspection --
date, exact lat/lon, pixel count, sensor -- so you can judge for
yourself (e.g. cross-check the lat/lon against a map, or against known
industrial sites in the area) rather than trusting the aggregate number
blindly.

Usage:
    python 20d_investigate_outlier_frp.py
"""

import pandas as pd

# ---- EDIT THIS FOR YOUR MACHINE (same path as script 20) ----
QUALIFYING_EVENTS_FILE = r"D:\Internship 2026\forestfire_qualifying_events.csv"

# Threshold for "worth a manual look" -- typical wildfire pixel FRP is
# tens to low hundreds of MW; this flags anything well above that.
FRP_FLAG_THRESHOLD_MW = 1000


def main():
    events = pd.read_csv(QUALIFYING_EVENTS_FILE)
    print(f"Loaded {len(events):,} qualifying events\n")

    print("Overall max_frp_mw distribution:")
    print(events["max_frp_mw"].describe())
    print()

    flagged = events[events["max_frp_mw"] >= FRP_FLAG_THRESHOLD_MW].copy()
    flagged = flagged.sort_values("max_frp_mw", ascending=False)
    print(f"{len(flagged):,} of {len(events):,} events have max_frp_mw >= "
          f"{FRP_FLAG_THRESHOLD_MW} MW ({100*len(flagged)/len(events):.3f}% of all events)\n")

    if flagged.empty:
        print("Nothing above the threshold -- the earlier pincode-level "
              "extreme values must come from events below this cutoff. "
              "Lower FRP_FLAG_THRESHOLD_MW and re-run.")
        return

    # Distinct underlying events -- this tells you whether the repeated
    # pincode-level numbers you saw trace back to a handful of individual
    # extreme readings (expected, buffer overlap) or genuinely many.
    dedup_cols = [c for c in ["event_date", "latitude", "longitude", "max_frp_mw"]
                  if c in flagged.columns]
    distinct = flagged.drop_duplicates(subset=dedup_cols)
    print(f"These trace back to {len(distinct):,} distinct underlying event(s) "
          f"(same event can be the 'max' for multiple nearby pincodes' buffers "
          f"-- that repetition itself is expected, not a bug).\n")

    print("Distinct flagged events, highest FRP first:")
    cols_to_show = [c for c in
                     ["event_date", "latitude", "longitude", "pixel_count", "max_frp_mw", "year"]
                     if c in distinct.columns]
    with pd.option_context("display.max_rows", None, "display.width", 140):
        print(distinct[cols_to_show].to_string(index=False))

    print("\nNext steps if any of these look wrong:")
    print("  - Cross-check lat/lon on a map -- is it inside actual forest,")
    print("    or does it land on/near a known industrial site, gas flare,")
    print("    quarry, or built-up area the forest mask might have missed?")
    print("  - If it's inside a jhum (shifting cultivation) belt, consider")
    print("    whether that counts as 'forest fire' for your purposes at all")
    print("    -- FSI's canopy-based mask doesn't distinguish primary forest")
    print("    from forest-fallow shifting-cultivation land.")
    print("  - If pixel_count is very low (e.g. 3, right at the FSI minimum)")
    print("    for an extreme FRP reading, that combination (barely-qualifying")
    print("    event size + extreme intensity) is worth extra scrutiny --")
    print("    a single anomalous pixel could be inflating an otherwise")
    print("    marginal event.")


if __name__ == "__main__":
    main()