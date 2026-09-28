"""
STEP 4 of 4 -- Turn raw hazard numbers into risk conclusions.

Reads the output of 03_collect_hazard_data.py (pincode_hazard_scores.csv)
and produces one row per pincode with:

  - a Low / Medium-Low / Medium-High / High percentile bucket for every
    individual metric (flood, heat, drought, warming)
  - a combined FREQUENCY x INTENSITY conclusion per hazard (flood, heat,
    drought), because frequency alone is misleading -- see the
    Assam-vs-Gujarat example: Assam floods often but mildly, Gujarat
    floods rarely but catastrophically. Ranking by frequency alone would
    call Assam riskier, which is backwards.

    UPDATE ON DROUGHT: this now has a genuine frequency/intensity split,
    matching flood and heat structurally. Frequency = % of the 20 years
    where the longest dry spell reached 21+ consecutive days (a "notable
    drought year"). Intensity = the single worst dry spell ever recorded.
    ONE HONEST CAVEAT: unlike flood's 64.5mm threshold (an official IMD
    figure), the 21-day drought threshold is NOT an official government
    cutoff -- there's no single-day drought definition as clean as the
    rainfall one. It's a defensible, clearly-stated proxy threshold, not
    an authoritative one. Say this plainly in your methodology doc.
  - one composite_risk_score (0-100) averaging percentiles across six
    metrics, with a High/Medium/Low label

Method: relative/percentile thresholds, not fixed cutoffs. Every
pincode is ranked against every OTHER pincode in your file on each
metric. This is standard practice in vulnerability indices (e.g.
CEEW-style) and auto-adapts if you add more pincodes later -- a fixed
cutoff like "flood intensity > 200mm = severe" would be arbitrary
because no Indian agency publishes an official threshold for that.

IMPORTANT LIMITATION to say out loud to your manager: this is a
HAZARD-only score (the "H" in Hazard x Exposure x Vulnerability). It
tells you how dangerous the LOCATION is, not how exposed or
vulnerable any specific asset (factory/branch/borrower) at that
location actually is. That's a separate layer, added per-asset later.
"""

import csv

# ---- EDIT THIS FOR YOUR MACHINE ----
INPUT_FILE = r"D:\Internship 2026\pincode_hazard_scores.csv"
OUTPUT_FILE = r"D:\Internship 2026\pincode_risk_conclusions.csv"
# -------------------------------------

# Metrics we rank pincodes against each other on.
# (column_name, is_higher_worse) -- all of ours are "higher = worse"
METRICS = [
    "flood_frequency_pct_years",
    "flood_intensity_max_mm",
    "heat_frequency_pct_days",
    "heat_intensity_max_c",
    "drought_frequency_pct_years",
    "drought_worst_dry_spell_days",
    "warming_trend_c_20yr",
]

# The six metrics above, in order, are what compose the final score.
COMPOSITE_METRICS = METRICS


def bucket(pctile):
    if pctile >= 75:
        return "High"
    elif pctile >= 50:
        return "Medium-High"
    elif pctile >= 25:
        return "Medium-Low"
    else:
        return "Low"


def compute_percentiles(rows, metric):
    """Return {pincode: percentile_0_to_100} for one metric, ranked
    against every other pincode in `rows`. Higher raw value = higher
    percentile = worse, for every metric we use here."""
    values = []
    for r in rows:
        try:
            values.append((r["pincode"], float(r[metric])))
        except (ValueError, KeyError):
            continue
    values.sort(key=lambda x: x[1])
    n = len(values)
    pctiles = {}
    for rank, (pin, _) in enumerate(values):
        # rank 0 = lowest value = 0th percentile; last = ~100th percentile
        pctiles[pin] = round(100 * rank / max(n - 1, 1), 1)
    return pctiles


def combine(freq_pctile, intensity_pctile):
    """Two-metric conclusion. 'Frequent' / 'severe' = at or above the
    median pincode in this dataset on that dimension."""
    frequent = freq_pctile >= 50
    severe = intensity_pctile >= 50
    if frequent and severe:
        return "Frequent and severe (highest priority)"
    elif frequent and not severe:
        return "Frequent but mild (chronic nuisance)"
    elif not frequent and severe:
        return "Rare but severe (tail risk -- easy to underrate on frequency alone)"
    else:
        return "Neither frequent nor severe (low concern)"


def composite_label(score):
    if score >= 66.7:
        return "High"
    elif score >= 33.3:
        return "Medium"
    else:
        return "Low"


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} pincodes from {INPUT_FILE}")

    # 1. Percentile rank every metric against the whole dataset.
    pctile_tables = {m: compute_percentiles(rows, m) for m in METRICS}

    out_rows = []
    for r in rows:
        pin = r["pincode"]

        flood_freq_p = pctile_tables["flood_frequency_pct_years"].get(pin)
        flood_int_p = pctile_tables["flood_intensity_max_mm"].get(pin)
        heat_freq_p = pctile_tables["heat_frequency_pct_days"].get(pin)
        heat_int_p = pctile_tables["heat_intensity_max_c"].get(pin)
        drought_p = pctile_tables["drought_frequency_pct_years"].get(pin)
        drought_int_p = pctile_tables["drought_worst_dry_spell_days"].get(pin)
        warming_p = pctile_tables["warming_trend_c_20yr"].get(pin)

        if None in (flood_freq_p, flood_int_p, heat_freq_p, heat_int_p, drought_p, drought_int_p, warming_p):
            continue  # skip rows with missing/unparseable data

        composite = round(
            (flood_freq_p + flood_int_p + heat_freq_p + heat_int_p + drought_p + drought_int_p + warming_p) / 7,
            1,
        )

        out_rows.append({
            "pincode": pin,
            "locality": r.get("locality", ""),
            "district": r.get("district", ""),
            "state": r.get("state", ""),

            "flood_frequency_bucket": bucket(flood_freq_p),
            "flood_intensity_bucket": bucket(flood_int_p),
            "flood_conclusion": combine(flood_freq_p, flood_int_p),

            "heat_frequency_bucket": bucket(heat_freq_p),
            "heat_intensity_bucket": bucket(heat_int_p),
            "heat_conclusion": combine(heat_freq_p, heat_int_p),

            "drought_frequency_bucket": bucket(drought_p),
            "drought_intensity_bucket": bucket(drought_int_p),
            "drought_conclusion": combine(drought_p, drought_int_p),
            "warming_trend_bucket": bucket(warming_p),

            "composite_risk_score": composite,
            "composite_risk_label": composite_label(composite),
        })

    # Sort worst-first so the top of the file is immediately useful.
    out_rows.sort(key=lambda r: r["composite_risk_score"], reverse=True)

    fieldnames = list(out_rows[0].keys()) if out_rows else []
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} pincode risk conclusions to {OUTPUT_FILE}")
    if out_rows:
        print("\nTop 5 highest composite risk:")
        for r in out_rows[:5]:
            print(f"  {r['pincode']} ({r['district']}, {r['state']}): "
                  f"{r['composite_risk_score']} -> {r['composite_risk_label']} | "
                  f"flood: {r['flood_conclusion']} | drought: {r['drought_conclusion']}")


if __name__ == "__main__":
    main()