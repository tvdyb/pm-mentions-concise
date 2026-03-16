#!/usr/bin/env python3
"""Build empirical calibration curves from resolved Polymarket mention markets.

Instead of series-level base rates (which don't map across platforms),
this computes actual YES resolution rates bucketed by YES price. The edge
for a market priced at YES=8% is: edge = 0.08 - actual_yes_rate(0.05-0.10 bucket).

Usage:
    python pm_base_rates.py              # build and save calibration
    python pm_base_rates.py --show       # show calibration without saving
"""

import json
import argparse
import numpy as np
from collections import defaultdict
from pathlib import Path

DATA_PATH = Path("data/pm_resolved_markets.json")
OUT_PATH = Path("data/pm_calibration.json")

# Price bucket boundaries — narrower at the low end where our edge lives
BUCKET_EDGES = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.00]


def bucket_label(lo: float, hi: float) -> str:
    return f"{lo:.0%}-{hi:.0%}"


def find_bucket(price: float) -> str | None:
    """Find which bucket a price falls into."""
    for i in range(len(BUCKET_EDGES) - 1):
        lo, hi = BUCKET_EDGES[i], BUCKET_EDGES[i + 1]
        if lo <= price < hi:
            return bucket_label(lo, hi)
    return None


def build_calibration(markets: list[dict]) -> dict:
    """Build calibration curves from resolved markets.

    Returns dict with:
        global: {bucket: {actual_yes_rate, n, ...}}
        by_speaker: {speaker: {bucket: {...}}}
        by_category: {category: {bucket: {...}}}
    """
    resolved = [m for m in markets if m.get("result") in ("yes", "no")]

    # We don't have historical YES prices for resolved markets (they settle
    # to 0 or 1). But we can't use last_yes_price because it's also 0 or 1
    # for resolved markets. We need a different approach.
    #
    # The insight: we use the volume and market characteristics to build
    # speaker-level and category-level base rates, then combine with
    # price-based calibration from active/recent markets.
    #
    # For the calibration, we compute:
    # 1. Speaker-level base rates (like series-level, but PM-native)
    # 2. Overall platform base rate
    # These become the "base rate" that we compare against current YES prices.

    # Speaker-level rates
    speaker_data = defaultdict(lambda: {"yes": 0, "no": 0})
    for m in resolved:
        sp = _normalize_speaker(m.get("speaker", ""))
        if not sp:
            continue
        speaker_data[sp][m["result"]] += 1

    speaker_rates = {}
    for sp, counts in speaker_data.items():
        total = counts["yes"] + counts["no"]
        if total >= 10:
            speaker_rates[sp] = {
                "base_rate": counts["yes"] / total,
                "n_markets": total,
                "yes": counts["yes"],
                "no": counts["no"],
            }

    # Category-level rates
    cat_data = defaultdict(lambda: {"yes": 0, "no": 0})
    for m in resolved:
        cat = m.get("category", "other")
        cat_data[cat][m["result"]] += 1

    category_rates = {}
    for cat, counts in cat_data.items():
        total = counts["yes"] + counts["no"]
        category_rates[cat] = {
            "base_rate": counts["yes"] / total,
            "n_markets": total,
        }

    # Overall rate
    total_yes = sum(1 for m in resolved if m["result"] == "yes")
    overall_rate = total_yes / len(resolved) if resolved else 0.5

    return {
        "overall": {
            "base_rate": overall_rate,
            "n_markets": len(resolved),
        },
        "by_speaker": speaker_rates,
        "by_category": category_rates,
        "metadata": {
            "n_markets": len(resolved),
            "n_speakers": len(speaker_rates),
            "bucket_edges": BUCKET_EDGES,
        },
    }


# Speaker normalization — merge variants like "trump"/"donald trump"
SPEAKER_ALIASES = {
    "donald trump": "trump",
    "jd vance": "vance",
    "j.d. vance": "vance",
    "kamala harris": "kamala",
    "joe biden": "biden",
    "keir starmer": "starmer",
    "karoline leavitt": "leavitt",
    "jerome powell": "powell",
    "jensen huang": "jensen huang",
    "elon musk": "elon",
    "tucker carlson": "tucker",
    "bernie sanders": "sanders",
    "zohran mamdani": "mamdani",
    "tim walz": "walz",
    "ross ulbricht": "ulbricht",
    "brian armstrong": "armstrong",
    "bill ackman": "ackman",
    "nancy pelosi": "pelosi",
    "gretchen whitmer": "whitmer",
    "pete buttigieg": "buttigieg",
    "luigi mangione": "mangione",
    "bill clinton": "clinton",
    "hillary clinton": "h_clinton",
    "kathy hochul": "hochul",
    "jim cramer": "cramer",
    "rfk jr.": "rfk",
    "david sacks": "sacks",
    "sam altman": "altman",
    "warren buffett": "buffett",
    "mark rutte": "rutte",
    "bryan johnson": "b_johnson",
    "daniel radcliffe": "radcliffe",
    "steve bannon": "bannon",
    "jimmy kimmel": "kimmel",
    "ariana grande": "grande",
    "glen powell": "g_powell",
    "taylor swift": "swift",
    "sabrina carpenter": "carpenter",
    "bad bunny": "bad_bunny",
    "shane gillis": "gillis",
    "secretary hegseth or brad cooper": "hegseth",
    "trump or melania": "trump_melania",
    "trump and elon": "trump_elon",
    "trump/elon": "trump_elon",
    "kamala and trump both": "kamala_trump",
}


def _normalize_speaker(speaker: str) -> str:
    """Normalize speaker name to canonical form."""
    sp = speaker.strip().lower()
    return SPEAKER_ALIASES.get(sp, sp)


def load_calibration(path: str = str(OUT_PATH)) -> dict:
    """Load calibration data from disk."""
    with open(path) as f:
        return json.load(f)


def find_speaker_rate(
    speaker: str,
    calibration: dict,
    min_n: int = 20,
) -> dict | None:
    """Look up speaker-level base rate from calibration.

    Returns {base_rate, n_markets} or None if insufficient data.
    """
    sp = _normalize_speaker(speaker)
    by_speaker = calibration.get("by_speaker", {})

    if sp in by_speaker and by_speaker[sp]["n_markets"] >= min_n:
        return by_speaker[sp]

    # Try partial match
    for key, data in by_speaker.items():
        if (sp in key or key in sp) and data["n_markets"] >= min_n:
            return data

    return None


def find_category_rate(category: str, calibration: dict) -> dict | None:
    """Look up category-level base rate."""
    return calibration.get("by_category", {}).get(category)


def print_calibration(cal: dict):
    """Pretty-print calibration data."""
    print(f"Overall: BR={cal['overall']['base_rate']:.3f} "
          f"(n={cal['overall']['n_markets']})")

    print(f"\nSpeaker rates ({cal['metadata']['n_speakers']} speakers):")
    by_sp = cal["by_speaker"]
    for sp, data in sorted(by_sp.items(),
                           key=lambda x: -x[1]["n_markets"])[:25]:
        print(f"  {sp:<20s}  BR={data['base_rate']:.3f}  "
              f"n={data['n_markets']}")

    print(f"\nCategory rates:")
    for cat, data in sorted(cal["by_category"].items(),
                            key=lambda x: -x[1]["n_markets"]):
        print(f"  {cat:<20s}  BR={data['base_rate']:.3f}  "
              f"n={data['n_markets']}")


def main():
    parser = argparse.ArgumentParser(
        description="Build PM mention market calibration curves")
    parser.add_argument("--show", action="store_true",
                        help="Show calibration without saving")
    args = parser.parse_args()

    if not DATA_PATH.exists():
        print(f"No data at {DATA_PATH}. Run pm_data_collector.py first.")
        return

    print("Loading resolved markets...")
    with open(DATA_PATH) as f:
        data = json.load(f)
    markets = data["markets"]
    print(f"  {len(markets)} markets")

    print("Building calibration...")
    cal = build_calibration(markets)

    print_calibration(cal)

    if not args.show:
        with open(OUT_PATH, "w") as f:
            json.dump(cal, f, indent=2)
        print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
