"""
06_build_forest_mask_hansen.py

Builds the forest-cover mask that 05_clean_and_score_forestfire.py needs
(FOREST_MASK_PATH) -- this didn't exist yet, so we're sourcing it here
rather than guessing at a path a second time.

SOURCE: Hansen Global Forest Change (Hansen et al. 2013, Science 342) --
University of Maryland / Google. Chosen because it's directly downloadable
with no login and no email-wait, unlike everything else we fought through
today. It's an academic/global product, not an Indian government one --
flag that distinction if this ends up cited in a CareEdge-facing document,
the same way you'd footnote any non-primary source elsewhere in the report.

THRESHOLD: >= 10% tree canopy cover (treecover2000 band) = "forest".
This is not an arbitrary cutoff -- it's FSI's own official forest cover
definition used in every India State of Forest Report: any land over one
hectare with tree canopy density above 10%, regardless of ownership or
legal status. Using the same number here means this mask is defined
consistently with the rest of your pipeline's government-sourced logic,
even though the underlying imagery is Hansen's, not FSI's.

TILES NEEDED: Hansen data is tiled in 10x10 degree GeoTIFFs, named by
their NW corner. India (~lat 6N-38N, lon 68E-98E) requires 16 tiles:
  N labels: 10N, 20N, 30N, 40N
  E labels: 60E, 70E, 80E, 90E

Usage:
    python 06_build_forest_mask_hansen.py
"""

import os
import requests
import numpy as np
import rasterio
from rasterio.merge import merge

# ---- EDIT THIS FOR YOUR MACHINE ----
TILE_DOWNLOAD_DIR = r"D:\Internship 2026\hansen_tiles"
# NOTE: there is no single merged output file -- by design, to avoid the OOM
# crash (see mosaic_and_threshold() docstring). The 16 *_forestmask_*.tif
# tiles are written straight into TILE_DOWNLOAD_DIR, which is exactly where
# script 20's FOREST_MASK_DIR expects to find them. Nothing else to set here.

GFC_VERSION = "GFC-2024-v1.12"   # latest stable full release at time of writing
BASE_URL = f"https://storage.googleapis.com/earthenginepartners-hansen/{GFC_VERSION}"

CANOPY_THRESHOLD_PCT = 10   # FSI's official forest-cover definition -- see docstring

N_LABELS = ["10N", "20N", "30N", "40N"]
E_LABELS = ["060E", "070E", "080E", "090E"]


def tile_urls():
    for n in N_LABELS:
        for e in E_LABELS:
            fname = f"Hansen_{GFC_VERSION}_treecover2000_{n}_{e}.tif"
            yield fname, f"{BASE_URL}/{fname}"


def download_tiles():
    os.makedirs(TILE_DOWNLOAD_DIR, exist_ok=True)
    local_paths = []
    for fname, url in tile_urls():
        local_path = os.path.join(TILE_DOWNLOAD_DIR, fname)
        if os.path.exists(local_path):
            print(f"Already have {fname}, skipping")
            local_paths.append(local_path)
            continue
        print(f"Downloading {fname} ...")
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        local_paths.append(local_path)
        print(f"  -> saved ({os.path.getsize(local_path) / 1e6:.0f} MB)")
    return local_paths


def mosaic_and_threshold(tile_paths):
    """
    FIXED: the original version called rasterio.merge() first, which builds
    the ENTIRE combined mosaic in memory before any thresholding happens --
    for India's 4x4 tile grid that's a 160,000 x 160,000 array, ~25.6 GB by
    itself, then another ~25.6 GB for the boolean mask on top. That's why
    it crashed with ArrayMemoryError.

    This version thresholds each tile SEPARATELY (each tile alone is at
    most a couple GB, manageable one at a time) and writes 16 small
    forest-mask tiles instead of one giant merged file. No re-download
    needed -- it reuses the tiles you already have on disk.
    """
    os.makedirs(TILE_DOWNLOAD_DIR, exist_ok=True)
    mask_tile_paths = []

    for tile_path in tile_paths:
        fname = os.path.basename(tile_path)
        mask_fname = fname.replace("treecover2000", "forestmask")
        # FIXED: write mask tiles into TILE_DOWNLOAD_DIR (hansen_tiles). The
        # old version wrote them one directory up instead (the parent
        # "Internship 2026" folder), so glob.glob(*_forestmask_*.tif) in
        # script 20's FOREST_MASK_DIR (hansen_tiles) always found nothing,
        # even after this script ran successfully.
        mask_path = os.path.join(TILE_DOWNLOAD_DIR, mask_fname)

        if os.path.exists(mask_path):
            print(f"Already thresholded {fname}, skipping")
            mask_tile_paths.append(mask_path)
            continue

        print(f"Thresholding {fname} ...")
        with rasterio.open(tile_path) as src:
            canopy = src.read(1)   # one tile at a time -- max ~1.6 GB, not 25+ GB
            forest = (canopy >= CANOPY_THRESHOLD_PCT).astype(np.uint8)
            meta = src.meta.copy()
            meta.update(dtype="uint8", count=1, compress="lzw", nodata=None)

            with rasterio.open(mask_path, "w", **meta) as dst:
                dst.write(forest, 1)

        pct = forest.mean() * 100
        print(f"  -> {pct:.1f}% forest in this tile, saved to {mask_fname}")
        mask_tile_paths.append(mask_path)

    print(f"\nDone. {len(mask_tile_paths)} thresholded forest-mask tiles ready in "
          f"{TILE_DOWNLOAD_DIR}")
    return mask_tile_paths


def main():
    tile_paths = download_tiles()
    mask_tile_paths = mosaic_and_threshold(tile_paths)
    print("\nThese are the 16 files 05_clean_and_score_forestfire.py needs.")
    print("Next: use the multi-tile FOREST_MASK_DIR version of mask_to_forest()")
    print("(see the follow-up patch) instead of a single FOREST_MASK_PATH --")
    print("there is no single merged file anymore, by design, to avoid the OOM crash.")
    for p in mask_tile_paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()