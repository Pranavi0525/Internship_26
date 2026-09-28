"""
05_clean_and_score_forestfire.py

Steps 4-5 of the Forest Fire pipeline: turn the raw detection cache from
step 3 into pincode-level frequency/intensity scores.

WHAT THIS ADDS ON TOP OF THE EARLIER VERSION:

1. FOREST-COVER MASK (was a declared-but-unused flag before -- now actually
   applied). Every raw detection is checked against a forest-cover layer
   BEFORE anything else happens. Without this, agricultural stubble burning
   (Punjab/Haryana especially) gets scored as forest fire risk -- the same
   class of error as the "90% of India flagged" bug in the Cyclone script.
   You need to supply the path to your existing Bhuvan/ISRO forest-cover
   layer (the one already used for the Landslide slope-proxy work) --
   set FOREST_MASK_PATH below. Supports either a polygon layer (shapefile/
   geopackage via geopandas) or a raster (GeoTIFF via rasterio); the
   mask_to_forest() function below has a branch for each -- keep whichever
   matches your file and delete the other.

2. FSI'S "LARGE FOREST FIRE" THRESHOLD (was missing entirely before --
   confidence filtering alone is not the same thing). Per FSI's own
   operational definition, a qualifying fire event needs >= 3 proximate
   pixels detected close together in space and time. This script clusters
   same-day detections that are near each other (DBSCAN, haversine metric)
   and keeps only clusters of size >= 3 as qualifying "events" -- turning
   raw pixel noise into government-recognized fire events, the same role
   IMD's 64.5mm threshold plays for flood and WMO's 34kt plays for cyclone.

BUFFER RADIUS: 5km is a placeholder pending the sensitivity test we
discussed -- NOT government-mandated (see the earlier design conversation).
Change BUFFER_KM and re-run to compare.
"""

import os
import numpy as np
import pandas as pd
import rasterio
from sklearn.cluster import DBSCAN
from sklearn.neighbors import BallTree

# ---- EDIT THESE FOR YOUR MACHINE ----
PINCODE_FILE = r"D:\Internship 2026\pincode_master_coordinates.csv"
RAW_DETECTIONS_CACHE = r"D:\Internship 2026\forestfire_raw_detections.csv"
FOREST_MASK_DIR = r"D:\Internship 2026\hansen_tiles"   # dir of *_forestmask.tif from script 06
OUTPUT_FILE = r"D:\Internship 2026\pincode_forestfire_scores.csv"
QUALIFYING_EVENTS_OUT = r"D:\Internship 2026\forestfire_qualifying_events.csv"

# ---- Study parameters ----
BUFFER_KM = 5.0                  # pincode<->fire buffer -- placeholder, sensitivity-test this
EVENT_CLUSTER_KM = 0.5           # max gap between pixels to count as "proximate" (~1-2 VIIRS
                                   # pixel-widths; VIIRS pixels are 375m, so pixels sharing an
                                   # edge or corner fall well inside this)
FSI_MIN_PIXELS_PER_EVENT = 3     # FSI's official "Large Forest Fire" definition
MODIS_CONF_MIN = 30              # MODIS confidence is numeric 0-100%; FIRMS' own ATBD
                                   # bands this as low 0-29%, nominal 30-79%, high 80-100%
                                   # -- 30 keeps nominal+high, drops low
VIIRS_CONF_QUALIFY = {"n", "h"}  # VIIRS confidence is CATEGORICAL (l/n/h), not numeric --
                                   # this was backwards in the previous version, which is
                                   # why the confidence filter silently dropped 100% of
                                   # VIIRS rows (pd.to_numeric('l'/'n'/'h') -> NaN -> False)
EARTH_RADIUS_KM = 6371.0
CURRENT_YEAR = pd.Timestamp.today().year
STUDY_START_YEAR = 2000          # earliest sensor (MODIS) start -- adjust if you drop MODIS


# ---------------------------------------------------------------------
# STEP 4a -- Forest-cover mask (THE PART THAT WAS MISSING)
# ---------------------------------------------------------------------
def mask_to_forest(detections: pd.DataFrame) -> pd.DataFrame:
    """Keep only detections that fall inside forest-cover pixels, sampled
    across 16 small per-tile masks (see script 06) rather than one merged
    file -- merging them into a single mosaic is what caused the earlier
    ~25GB out-of-memory crash. Each point is routed to its containing tile
    by simple lat/lon arithmetic (tiles are a regular 10x10 degree grid),
    then sampled in one batched rasterio .sample() call per tile.

    FIXED: the tile-key computation was previously done with
    detections.apply(lambda row: ..., axis=1) -- that calls a Python
    function once per row, 26+ million times, which is one of the slowest
    possible patterns in pandas (that's why the run looked "stuck"). This
    version computes both label columns as vectorized numpy operations
    across the whole column at once -- milliseconds instead of
    (realistically) tens of minutes for this dataset size."""
    import glob
    tile_files = glob.glob(os.path.join(FOREST_MASK_DIR, "*_forestmask_*.tif"))
    if not tile_files:
        raise FileNotFoundError(
            f"No *_forestmask_*.tif files found in {FOREST_MASK_DIR}. "
            "Run 06_build_forest_mask_hansen.py first -- do not skip this step."
        )

    detections = detections.copy()

    # Vectorized tile-label assignment -- operates on the whole column at
    # once via numpy, not row-by-row via .apply(). Same labeling logic as
    # before (Hansen tiles are named by their NW corner), just fast now.
    n_vals = (np.ceil(detections["latitude"].values / 10) * 10).astype(int)
    e_vals = (np.floor(detections["longitude"].values / 10) * 10).astype(int)
    detections["_n_label"] = [f"{v:02d}N" for v in n_vals]
    detections["_e_label"] = [f"{v:03d}E" for v in e_vals]

    before = len(detections)
    forest_flags = np.zeros(len(detections), dtype=bool)

    # groupby is far faster than re-filtering the full 26M-row frame once
    # per tile (16 separate full-dataframe scans vs. one grouped pass)
    grouped = detections.groupby(["_n_label", "_e_label"])

    for tile_path in tile_files:
        fname = os.path.basename(tile_path)
        parts = fname.replace(".tif", "").split("_")
        n_label, e_label = parts[-2], parts[-1]

        try:
            subset = grouped.get_group((n_label, e_label))
        except KeyError:
            continue   # no detections fall in this tile -- nothing to sample

        print(f"  Sampling {len(subset):,} detections against tile {n_label}_{e_label}...")
        with rasterio.open(tile_path) as src:
            coords = list(zip(subset["longitude"], subset["latitude"]))
            values = [v[0] for v in src.sample(coords)]
        forest_flags[detections.index.get_indexer(subset.index)] = [v > 0 for v in values]

    masked = detections[forest_flags].drop(columns=["_n_label", "_e_label"])
    after = len(masked)
    pct_dropped = (before - after) / before * 100 if before else 0
    print(f"Forest-cover mask: {before:,} -> {after:,} detections "
          f"({pct_dropped:.1f}% dropped as non-forest, likely agricultural/industrial)")
    return masked


# ---------------------------------------------------------------------
# STEP 4b -- Confidence filter (per-pixel noise reduction, same as before)
# ---------------------------------------------------------------------
def confidence_filter(df: pd.DataFrame) -> pd.DataFrame:
    """FIXED: MODIS confidence is numeric (0-100%); VIIRS confidence is
    categorical (l/n/h) -- these were swapped in the previous version,
    which silently zeroed out every VIIRS row (the vast majority of this
    dataset) since pd.to_numeric() on 'l'/'n'/'h' strings returns NaN,
    and NaN >= 50 is always False."""
    is_modis = df["sensor_source"].str.startswith("MODIS")

    if "type" in df.columns:
        modis_type_ok = is_modis & (df["type"] == 0)
    else:
        modis_type_ok = pd.Series(False, index=df.index)

    conf_ok = pd.Series(False, index=df.index)
    if "confidence" in df.columns:
        modis_conf_numeric = pd.to_numeric(df["confidence"], errors="coerce")
        modis_ok = is_modis & modis_type_ok & (modis_conf_numeric >= MODIS_CONF_MIN)

        viirs_conf_str = df["confidence"].astype(str).str.lower()
        viirs_ok = ~is_modis & viirs_conf_str.isin(VIIRS_CONF_QUALIFY)

        conf_ok = modis_ok | viirs_ok

    kept = df[conf_ok].copy()
    print(f"Confidence filter: {len(df):,} -> {len(kept):,} detections")
    return kept


# ---------------------------------------------------------------------
# STEP 4c -- FSI event clustering (THE OTHER PART THAT WAS MISSING)
# ---------------------------------------------------------------------
def cluster_into_events(df: pd.DataFrame) -> pd.DataFrame:
    """Group same-day, spatially-proximate pixels into fire events, and
    keep only events with >= FSI_MIN_PIXELS_PER_EVENT pixels -- FSI's own
    definition of a Large Forest Fire. Returns one row per QUALIFYING
    EVENT (not per pixel), with the event's max FRP and a representative
    lat/lon (its centroid) for the pincode buffer join."""
    df = df.copy()
    df["acq_date"] = pd.to_datetime(df["acq_date"])

    event_rows = []
    eps_rad = EVENT_CLUSTER_KM / EARTH_RADIUS_KM

    for acq_date, day_df in df.groupby("acq_date"):
        if len(day_df) < FSI_MIN_PIXELS_PER_EVENT:
            continue  # can't possibly form a qualifying event with fewer pixels than the threshold

        coords_rad = np.radians(day_df[["latitude", "longitude"]].values)
        clustering = DBSCAN(eps=eps_rad, min_samples=1, metric="haversine").fit(coords_rad)
        day_df = day_df.assign(_cluster=clustering.labels_)

        for cluster_id, cluster_df in day_df.groupby("_cluster"):
            if len(cluster_df) < FSI_MIN_PIXELS_PER_EVENT:
                continue
            event_rows.append({
                "event_date": acq_date,
                "year": acq_date.year,
                "pixel_count": len(cluster_df),
                "latitude": cluster_df["latitude"].mean(),
                "longitude": cluster_df["longitude"].mean(),
                "max_frp_mw": cluster_df["frp"].max() if "frp" in cluster_df else np.nan,
            })

    events = pd.DataFrame(event_rows)
    print(f"Event clustering: {len(df):,} qualifying pixels -> {len(events):,} "
          f"events with >= {FSI_MIN_PIXELS_PER_EVENT} proximate pixels (FSI Large Forest Fire)")
    return events


# ---------------------------------------------------------------------
# STEP 5 -- Buffer to pincodes and score (same scoring logic as before,
# now operating on real EVENTS instead of raw pixels)
# ---------------------------------------------------------------------
def score_pincodes(pincodes: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    total_years = CURRENT_YEAR - STUDY_START_YEAR + 1

    if events.empty:
        print("WARNING: zero qualifying events after masking/filtering/clustering. "
              "Check FOREST_MASK_PATH and thresholds before trusting this output.")
        scores = pincodes[["pincode"]].copy()
        scores["num_qualifying_events"] = 0
        scores["years_with_event"] = 0
        scores["frequency_pct"] = 0.0
        scores["max_frp_mw"] = 0.0
        scores["verdict"] = "No qualifying events in study window"
        scores["buffer_km"] = BUFFER_KM
        return scores

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
    scores["frequency_percentile"] = scores["frequency_pct"].rank(pct=True) * 100
    scores["intensity_percentile"] = scores["max_frp_mw"].rank(pct=True) * 100

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


def run_sanity_checks(scores: pd.DataFrame):
    print("\n" + "=" * 70)
    print("SANITY CHECKS")
    print("=" * 70)
    checks = {
        "Similipal, Odisha (known hotspot -- expect non-zero)": "757043",
        "Bandipur, Karnataka (known hotspot -- expect non-zero)": "571126",
        "Nagarhole, Karnataka (known hotspot -- expect non-zero)": "571121",
        "Central Delhi (urban core, no forest -- expect 0/NA)": "110001",
        "Central Mumbai (urban core, no forest -- expect 0/NA)": "400001",
    }
    for label, pincode in checks.items():
        match = scores[scores["pincode"].astype(str) == pincode]
        if match.empty:
            print(f"  {label}: pincode {pincode} not found in master file")
        else:
            r = match.iloc[0]
            print(f"  {label}: {r['num_qualifying_events']} events, "
                  f"{r['frequency_pct']:.1f}% of years, max FRP {r['max_frp_mw']} MW")
    print("=" * 70)


def main():
    pincodes = pd.read_csv(PINCODE_FILE).dropna(subset=["latitude", "longitude"])
    print(f"Loaded {len(pincodes):,} pincodes")

    raw = pd.read_csv(RAW_DETECTIONS_CACHE)
    print(f"Loaded {len(raw):,} raw detections from cache")

    forest_only = mask_to_forest(raw)
    confident = confidence_filter(forest_only)
    events = cluster_into_events(confident)
    events.to_csv(QUALIFYING_EVENTS_OUT, index=False)
    print(f"Saved {len(events):,} qualifying events to {QUALIFYING_EVENTS_OUT}")

    scores = score_pincodes(pincodes, events)
    scores.to_csv(OUTPUT_FILE, index=False)
    print(f"\nWrote scores for {len(scores):,} pincodes to {OUTPUT_FILE}")

    run_sanity_checks(scores)


if __name__ == "__main__":
    main()