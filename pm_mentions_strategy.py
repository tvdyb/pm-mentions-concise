"""PM Mentions Grid Filter Strategy — Original

Strategy: Buy NO on mention markets where YES is overpriced relative
to historical base rates. Filter: edge >= 10c, base rate <= 50%,
>= 10 prior markets. Quarter-Kelly sizing. Earnings markets are
tradeable using LibFrog word-level transcript base rates.

Usage:
    from pm_mentions_strategy import compute_signals, CONFIG
    from shared import load_base_rates, fetch_active_kalshi, size_position

    rates = load_base_rates("base_rates.json")
    markets = fetch_active_kalshi(rates)
    signals = compute_signals(markets, rates)

    for sig in signals:
        n_contracts, cost = size_position(sig, capital=1000, config=CONFIG)
        print(f"{sig['ticker']}: {n_contracts} NO @ ${cost:.2f}")
"""

from shared import (
    load_base_rates,
    find_series_rate,
    find_word_rate,
    size_position,
    compute_settlement_pnl,
    fetch_active_kalshi,
    check_settlement,
    compute_expected_pnl,
    SERIES_EQUIVALENCES,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
CONFIG = {
    "grid_edge_min": 0.10,       # min edge (YES price - base rate) to trade
    "grid_br_max": 0.50,         # max base rate to trade
    "min_history": 10,           # min settled markets in series before trading
    "max_yes_price": 0.75,       # skip high-YES markets (75-95% bucket has no edge)
    "exclude_earnings": False,   # LibFrog word-level rates make earnings tradeable
    "kelly_fraction": 0.25,      # quarter-Kelly sizing
    "max_position_pct": 0.05,    # max 5% of capital per position
    "max_total_exposure_pct": 0.80,
    "max_per_event_pct": 0.20,
    "kalshi_fee_rt": 0.02,       # $0.02 round-trip per contract
    "slippage": 0.01,            # 1 cent assumed slippage
}


# ---------------------------------------------------------------------------
# Signal computation (THE STRATEGY)
# ---------------------------------------------------------------------------
def compute_signals(
    active_markets: list[dict],
    rates: dict,
    config: dict | None = None,
) -> list[dict]:
    """Apply grid filter to active markets. Returns qualifying NO signals.

    Each market dict needs at minimum:
        ticker, series, yes_mid, source, event_ticker

    Optional fields (used for display/tracking):
        event_title, strike_word, yes_bid, yes_ask, volume, close_time

    For earnings markets, word-level LibFrog rates from base_rates.json
    (keyed as "SERIES|word") override the series-level rate when available
    with n_calls >= 10.
    """
    cfg = config or CONFIG
    signals = []

    for mkt in active_markets:
        series = mkt["series"]
        yes_mid = mkt["yes_mid"]

        # --- Filters ---
        if yes_mid > cfg["max_yes_price"] or yes_mid < 0.05:
            continue

        if cfg.get("exclude_earnings") and "EARNINGS" in series.upper():
            continue

        # --- Rate lookup: word-level first, then series-level ---
        strike_word = mkt.get("strike_word", "")
        word_info, rate_source = find_word_rate(series, strike_word, rates)

        if word_info is not None:
            br = word_info["base_rate"]
            n = word_info.get("n_calls", 0)
        else:
            info = find_series_rate(series, rates)
            if not info:
                continue
            br = info["base_rate"]
            n = info.get("n_markets", 0)
            rate_source = "series"

        if n < cfg["min_history"]:
            continue

        edge = yes_mid - br

        # GRID FILTER: the entire trading rule
        if edge < cfg["grid_edge_min"] or br > cfg["grid_br_max"]:
            continue

        # --- Expected PnL and Kelly sizing ---
        fee = cfg["kalshi_fee_rt"] if mkt.get("source") == "kalshi" else 0.0
        slip = cfg["slippage"]
        epnl, kelly_q = compute_expected_pnl(
            yes_mid, br, fee=fee, slippage=slip,
            kelly_fraction=cfg["kelly_fraction"])

        signals.append({
            "ticker": mkt.get("ticker", ""),
            "series": series,
            "event_ticker": mkt.get("event_ticker", ""),
            "event_title": mkt.get("event_title", ""),
            "strike_word": mkt.get("strike_word", ""),
            "source": mkt.get("source", ""),
            "side": "NO",
            "yes_mid": yes_mid,
            "base_rate": br,
            "edge": edge,
            "expected_pnl": epnl,
            "kelly_quarter": kelly_q,
            "n_history": n,
            "rate_source": rate_source,
            "volume": mkt.get("volume", 0),
            "close_time": mkt.get("close_time", ""),
        })

    signals.sort(key=lambda s: s["expected_pnl"], reverse=True)
    return signals


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys
    from datetime import datetime
    from pathlib import Path

    import numpy as np

    print(f"PM Mentions Grid Filter — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"Config: edge>={CONFIG['grid_edge_min']*100:.0f}c, "
          f"BR<={CONFIG['grid_br_max']:.0%}, "
          f"maxYES<={CONFIG['max_yes_price']:.0%}, "
          f"LibFrog word rates, 1/4 Kelly")
    print()

    br_path = Path("base_rates.json")
    if not br_path.exists():
        print("ERROR: No base_rates.json found.")
        sys.exit(1)

    rates = load_base_rates(str(br_path))
    print(f"Loaded {len(rates)} entries from {br_path}")

    print("\nFetching active Kalshi markets...")
    markets = fetch_active_kalshi(rates)
    print(f"  {len(markets)} active markets")

    signals = compute_signals(markets, rates)
    print(f"  {len(signals)} signals pass grid filter\n")

    if signals:
        capital = 1000.0
        print(f"{'#':>3}  {'Market':<35s}  {'YES':>5}  {'BR':>5}  "
              f"{'Edge':>6}  {'E[PnL]':>7}  {'Ctrs':>5}  {'Cost':>6}")
        print("-" * 90)
        for i, s in enumerate(signals[:20]):
            n, cost = size_position(s, capital, CONFIG)
            print(f"{i+1:>3}  {s['strike_word'][:33]:<35s}  "
                  f"{s['yes_mid']:>4.0%}  {s['base_rate']:>4.0%}  "
                  f"{s['edge']:>+5.0%}  {s['expected_pnl']:>+6.3f}  "
                  f"{n:>5}  ${cost:>5.1f}")
