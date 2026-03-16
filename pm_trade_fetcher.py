#!/usr/bin/env python3
"""Fetch CLOB trade history for resolved PM mention markets.

For each resolved market in data/pm_resolved_markets.json, fetches trade
history from Polymarket's data API and computes VWAP at multiple buffer
levels (matching the Kalshi backtest approach).

Output: data/pm_markets_with_trades.json

Usage:
    python pm_trade_fetcher.py              # fetch all (incremental)
    python pm_trade_fetcher.py --limit 100  # fetch first 100 only
    python pm_trade_fetcher.py --stats      # show stats on existing data
"""

import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

DATA_PATH = Path("data/pm_resolved_markets.json")
OUT_PATH = Path("data/pm_markets_with_trades.json")
TRADES_API = "https://data-api.polymarket.com/trades"
SAVE_INTERVAL = 100  # save to disk every N markets


# ---------------------------------------------------------------------------
# VWAP computation
# ---------------------------------------------------------------------------

def compute_vwap(trades: list[dict], buffer_pct: float = 0.0) -> float | None:
    """Compute VWAP from a list of {yes_price, size, timestamp} dicts.

    buffer_pct: fraction of trading time to exclude from start and end.
    Returns None if fewer than 2 trades in the window.
    """
    if len(trades) < 2:
        return None

    t_start = trades[0]["timestamp"]
    t_end = trades[-1]["timestamp"]
    duration = t_end - t_start
    if duration <= 0:
        return None

    t_lo = t_start + buffer_pct * duration
    t_hi = t_end - buffer_pct * duration

    filtered = [t for t in trades if t_lo <= t["timestamp"] <= t_hi]
    if len(filtered) < 2:
        return None

    total_vol = sum(t["size"] for t in filtered)
    if total_vol <= 0:
        return None
    return sum(t["yes_price"] * t["size"] for t in filtered) / total_vol


def trades_to_yes_prices(raw_trades: list[dict]) -> list[dict]:
    """Convert raw API trades to YES-denominated price records.

    Each trade has an outcomeIndex (0=YES, 1=NO) and a price for that
    outcome. We convert everything to YES prices:
    - outcomeIndex=0 (YES) at price p → yes_price = p
    - outcomeIndex=1 (NO) at price p → yes_price = 1 - p
    """
    records = []
    for t in raw_trades:
        price = float(t["price"])
        size = float(t["size"])
        ts = t["timestamp"]
        idx = t.get("outcomeIndex", -1)

        if idx == 0:
            yes_price = price
        elif idx == 1:
            yes_price = 1.0 - price
        else:
            # Fallback: check outcome string
            outcome = (t.get("outcome") or "").lower()
            if outcome == "yes":
                yes_price = price
            elif outcome == "no":
                yes_price = 1.0 - price
            else:
                continue  # skip unknown

        records.append({
            "yes_price": yes_price,
            "size": size,
            "timestamp": ts,
        })

    records.sort(key=lambda x: x["timestamp"])
    return records


def enrich_market(market: dict, raw_trades: list[dict]) -> dict:
    """Add trade-derived fields to a market dict."""
    trades = trades_to_yes_prices(raw_trades)
    market["n_trades"] = len(trades)

    if not trades:
        market["vwap_no_buffer"] = None
        market["vwap_10pct_buffer"] = None
        market["vwap_25pct_buffer"] = None
        market["opening_price"] = None
        market["last_price_trade"] = None
        return market

    market["vwap_no_buffer"] = compute_vwap(trades, 0.0)
    market["vwap_10pct_buffer"] = compute_vwap(trades, 0.10)
    market["vwap_25pct_buffer"] = compute_vwap(trades, 0.25)
    market["opening_price"] = trades[0]["yes_price"]
    market["last_price_trade"] = trades[-1]["yes_price"]

    # Store compact trade list (yes_price, size, timestamp only)
    market["trades"] = [
        {"p": round(t["yes_price"], 4), "s": round(t["size"], 2), "t": t["timestamp"]}
        for t in trades
    ]

    return market


# ---------------------------------------------------------------------------
# Trade fetching
# ---------------------------------------------------------------------------

def fetch_trades_for_market(condition_id: str, max_pages: int = 20) -> list[dict]:
    """Fetch all trades for a market from the data API.

    Uses market=condition_id to get trades specific to this market
    (important for neg_risk markets that share CLOB token pools).
    """
    all_trades = []
    offset = 0
    limit = 500

    for _ in range(max_pages):
        try:
            resp = requests.get(TRADES_API, params={
                "market": condition_id,
                "limit": limit,
                "offset": offset,
            }, timeout=30)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                print(f"    Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            if resp.status_code != 200:
                print(f"    API error {resp.status_code}")
                break

            batch = resp.json()
            if not batch:
                break

            all_trades.extend(batch)
            offset += len(batch)

            if len(batch) < limit:
                break

        except requests.RequestException as e:
            print(f"    Request error: {e}")
            time.sleep(5)
            break

    return all_trades


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_existing() -> dict:
    """Load existing enriched data, keyed by condition_id."""
    if not OUT_PATH.exists():
        return {}
    with open(OUT_PATH) as f:
        data = json.load(f)
    return {m["condition_id"]: m for m in data.get("markets", [])}


def save_progress(markets: list[dict], metadata: dict):
    """Save current progress to disk."""
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"markets": markets, "metadata": metadata}, f)


def show_stats():
    """Show stats on existing enriched data."""
    if not OUT_PATH.exists():
        print(f"No data at {OUT_PATH}")
        return

    with open(OUT_PATH) as f:
        data = json.load(f)
    markets = data["markets"]
    has_trades = [m for m in markets if m.get("n_trades", 0) > 0]
    has_vwap = [m for m in markets if m.get("vwap_25pct_buffer") is not None]

    print(f"Total markets: {len(markets)}")
    print(f"With trades: {len(has_trades)} ({len(has_trades)/len(markets):.1%})")
    print(f"With VWAP 25%: {len(has_vwap)} ({len(has_vwap)/len(markets):.1%})")

    if has_vwap:
        vwaps = [m["vwap_25pct_buffer"] for m in has_vwap]
        n_trades = [m["n_trades"] for m in has_trades]
        print(f"\nVWAP 25% stats:")
        print(f"  Mean: {sum(vwaps)/len(vwaps):.4f}")
        print(f"  Min:  {min(vwaps):.4f}")
        print(f"  Max:  {max(vwaps):.4f}")
        print(f"\nTrades per market:")
        print(f"  Mean: {sum(n_trades)/len(n_trades):.1f}")
        print(f"  Median: {sorted(n_trades)[len(n_trades)//2]}")
        print(f"  Max: {max(n_trades)}")

    # By result
    for result in ["yes", "no"]:
        subset = [m for m in has_vwap if m.get("result") == result]
        if subset:
            vwaps_r = [m["vwap_25pct_buffer"] for m in subset]
            print(f"\nResult={result}: {len(subset)} markets, "
                  f"mean VWAP={sum(vwaps_r)/len(vwaps_r):.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch CLOB trades for resolved PM mention markets")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max markets to fetch (0=all)")
    parser.add_argument("--stats", action="store_true",
                        help="Show stats on existing data")
    parser.add_argument("--delay", type=float, default=0.15,
                        help="Delay between API calls (seconds)")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    # Load source data
    print("Loading resolved markets...")
    with open(DATA_PATH) as f:
        source = json.load(f)
    all_markets = source["markets"]
    print(f"  {len(all_markets)} resolved markets")

    # Load existing progress
    existing = load_existing()
    print(f"  {len(existing)} already fetched")

    # Process markets
    enriched = list(existing.values())
    enriched_ids = set(existing.keys())
    to_fetch = [m for m in all_markets if m["condition_id"] not in enriched_ids]

    if args.limit > 0:
        to_fetch = to_fetch[:args.limit]

    print(f"  {len(to_fetch)} to fetch")

    n_fetched = 0
    n_with_trades = 0
    t_start = time.time()

    for i, market in enumerate(to_fetch):
        cid = market["condition_id"]
        word = market.get("strike_word", "")[:30]

        # Fetch trades
        raw_trades = fetch_trades_for_market(cid)
        enriched_market = dict(market)  # copy
        enrich_market(enriched_market, raw_trades)

        enriched.append(enriched_market)
        enriched_ids.add(cid)
        n_fetched += 1

        if enriched_market.get("n_trades", 0) > 0:
            n_with_trades += 1

        # Progress
        if (i + 1) % 10 == 0 or i == 0:
            elapsed = time.time() - t_start
            rate = n_fetched / elapsed if elapsed > 0 else 0
            eta = (len(to_fetch) - n_fetched) / rate / 60 if rate > 0 else 0
            print(f"  [{n_fetched}/{len(to_fetch)}] "
                  f"{n_with_trades} with trades, "
                  f"{rate:.1f}/s, ETA {eta:.0f}m  "
                  f"latest: {word}")

        # Save periodically
        if n_fetched % SAVE_INTERVAL == 0:
            metadata = {
                "n_total": len(enriched),
                "n_with_trades": sum(1 for m in enriched if m.get("n_trades", 0) > 0),
                "fetched_at": datetime.now().isoformat(),
            }
            save_progress(enriched, metadata)
            print(f"  Saved progress ({len(enriched)} markets)")

        time.sleep(args.delay)

    # Final save
    metadata = {
        "n_total": len(enriched),
        "n_with_trades": sum(1 for m in enriched if m.get("n_trades", 0) > 0),
        "n_with_vwap_25": sum(1 for m in enriched
                              if m.get("vwap_25pct_buffer") is not None),
        "fetched_at": datetime.now().isoformat(),
    }
    save_progress(enriched, metadata)

    print(f"\nDone. {len(enriched)} markets saved to {OUT_PATH}")
    print(f"  {metadata['n_with_trades']} with trades, "
          f"{metadata['n_with_vwap_25']} with VWAP 25%")


if __name__ == "__main__":
    main()
