"""PM Mentions Grid Filter Strategy — Self-Contained

Drop this file + base_rates.json into any paper trading system.
No dependencies beyond requests + numpy.

Strategy: Buy NO on mention markets where YES is overpriced relative
to historical base rates. Filter: edge >= 10c, base rate <= 50%,
>= 10 prior markets. Quarter-Kelly sizing. Exclude earnings.

Usage:
    from pm_mentions_strategy import (
        load_base_rates,
        fetch_active_kalshi,
        compute_signals,
        size_position,
        compute_settlement_pnl,
    )

    rates = load_base_rates("base_rates.json")
    markets = fetch_active_kalshi(rates)
    signals = compute_signals(markets, rates)

    for sig in signals:
        n_contracts, cost = size_position(sig, capital=1000)
        # ... submit to your execution system ...

    # On settlement:
    pnl = compute_settlement_pnl(entry_price=0.80, result="no")
"""

import json
import time
from pathlib import Path

import numpy as np
import requests

# ---------------------------------------------------------------------------
# Strategy parameters (optimized — see optimized_strategy_report.pdf)
# ---------------------------------------------------------------------------
CONFIG = {
    "grid_edge_min": 0.10,       # min edge (YES price - base rate) to trade
    "grid_br_max": 0.50,         # max base rate to trade
    "min_history": 10,           # min settled markets in series before trading
    "max_yes_price": 0.75,       # skip high-YES markets (75-95% bucket has no edge)
    "exclude_earnings": True,    # earnings markets lose money (-7.6c avg)
    "kelly_fraction": 0.25,      # quarter-Kelly sizing
    "max_position_pct": 0.05,    # max 5% of capital per position
    "max_total_exposure_pct": 0.80,
    "max_per_event_pct": 0.20,
    "kalshi_fee_rt": 0.02,       # $0.02 round-trip per contract
    "slippage": 0.01,            # 1 cent assumed slippage
}

# ---------------------------------------------------------------------------
# Base rates
# ---------------------------------------------------------------------------
def load_base_rates(path: str = "base_rates.json") -> dict:
    """Load historical base rates per series.

    Expected format: {series_ticker: {base_rate: float, n_markets: int}}
    Generate this from your settled market data — for each series, compute:
        base_rate = count(result=="yes") / count(all)
        n_markets = count(all)
    """
    with open(path) as f:
        return json.load(f)


SERIES_EQUIVALENCES = {
    "KXFEDMENTION": "KXPOWELLMENTION",
    "KXJPOWMENTION": "KXPOWELLMENTION",
    "KXTRUMPMENTIONB": "KXTRUMPMENTION",
    "KXSTARMERMENTIONB": "KXSTARMERMENTION",
    "KXTRUMPMENTIONDURATION": "KXTRUMPMENTION",
}


def _find_series_rate(series: str, rates: dict) -> dict | None:
    """Look up base rate for a series, trying equivalences."""
    if series in rates:
        return rates[series]
    # Strip trailing letter (e.g., KXSTARMERMENTIONB → KXSTARMERMENTION)
    if series[-1:].isalpha() and series[-1] != "N":
        base = series[:-1]
        if base in rates:
            return rates[base]
    if series in SERIES_EQUIVALENCES:
        equiv = SERIES_EQUIVALENCES[series]
        if equiv in rates:
            return rates[equiv]
    return None


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

        info = _find_series_rate(series, rates)
        if not info:
            continue

        n = info.get("n_markets", 0)
        if n < cfg["min_history"]:
            continue

        br = info["base_rate"]
        edge = yes_mid - br

        # GRID FILTER: the entire trading rule
        if edge < cfg["grid_edge_min"] or br > cfg["grid_br_max"]:
            continue

        # --- Expected PnL and Kelly sizing ---
        fee = cfg["kalshi_fee_rt"] if mkt.get("source") == "kalshi" else 0.0
        slip = cfg["slippage"]
        eff_yes = max(0.01, yes_mid - slip)
        no_cost = 1.0 - eff_yes

        p_no = 1.0 - br
        epnl = p_no * eff_yes - br * no_cost - fee

        if epnl > 0:
            b = eff_yes / no_cost if no_cost > 0 else 0
            kelly_full = (p_no * b - br) / b if b > 0 else 0
            kelly_q = max(0.0, kelly_full * cfg["kelly_fraction"])
        else:
            kelly_q = 0.0

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
            "volume": mkt.get("volume", 0),
            "close_time": mkt.get("close_time", ""),
        })

    signals.sort(key=lambda s: s["expected_pnl"], reverse=True)
    return signals


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------
def size_position(
    signal: dict,
    capital: float,
    config: dict | None = None,
) -> tuple[int, float]:
    """Compute number of contracts and total cost for a signal.

    Returns (n_contracts, total_cost).
    Returns (0, 0) if position too small.
    """
    cfg = config or CONFIG
    max_size = capital * cfg["max_position_pct"]
    kelly_size = capital * signal["kelly_quarter"]
    position_size = min(kelly_size, max_size)

    if position_size < 1.0:
        return 0, 0.0

    slip = cfg["slippage"]
    eff_yes = max(0.01, signal["yes_mid"] - slip)
    no_cost = 1.0 - eff_yes
    n_contracts = int(position_size / no_cost)

    if n_contracts < 1:
        return 0, 0.0

    total_cost = n_contracts * no_cost
    return n_contracts, total_cost


# ---------------------------------------------------------------------------
# Settlement PnL
# ---------------------------------------------------------------------------
def compute_settlement_pnl(
    entry_price: float,
    result: str,
    side: str = "NO",
    n_contracts: int = 1,
    config: dict | None = None,
) -> float:
    """Compute realized PnL when a market settles.

    Args:
        entry_price: YES mid price at entry
        result: "yes" or "no"
        side: "NO" (default) or "YES"
        n_contracts: number of contracts
    Returns:
        Total PnL in dollars
    """
    cfg = config or CONFIG
    slip = cfg["slippage"]
    fee = cfg["kalshi_fee_rt"]
    eff_yes = max(0.01, entry_price - slip)
    no_cost = 1.0 - eff_yes

    if side == "NO":
        pnl_per = (eff_yes - fee) if result == "no" else (-no_cost - fee)
    else:
        pnl_per = ((1.0 - eff_yes) - fee) if result == "yes" else (-eff_yes - fee)

    return pnl_per * n_contracts


# ---------------------------------------------------------------------------
# Kalshi API helpers (adapt to your own API client)
# ---------------------------------------------------------------------------
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


def _kalshi_get(path: str, params: dict | None = None) -> dict | None:
    """GET from Kalshi API with retry."""
    url = f"{KALSHI_BASE}{path}"
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=30,
                                headers={"Accept": "application/json"})
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", 5)))
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt < 2:
                time.sleep(2)
            else:
                return None
    return None


def fetch_active_kalshi(rates: dict, delay: float = 0.3) -> list[dict]:
    """Fetch all active mention markets from Kalshi.

    Replace this with your own market data source if you already have one.
    """
    data = _kalshi_get("/series", {"limit": 1000})
    if not data:
        return []

    mention_series = [s["ticker"] for s in data.get("series", [])
                      if "MENTION" in s.get("ticker", "").upper()]

    active = []
    for series in mention_series:
        time.sleep(delay)
        ev_data = _kalshi_get("/events", {
            "series_ticker": series, "status": "open", "limit": 50,
        })

        if not ev_data or not ev_data.get("events"):
            mkt_data = _kalshi_get("/markets", {
                "status": "open", "limit": 100, "series_ticker": series,
            })
            if mkt_data:
                for m in mkt_data.get("markets", []):
                    if m.get("status") in ("open", "active"):
                        parsed = _parse_kalshi_market(m, series)
                        if parsed:
                            active.append(parsed)
            continue

        for event in ev_data["events"]:
            time.sleep(delay)
            mkt_data = _kalshi_get("/markets", {
                "event_ticker": event["event_ticker"], "limit": 200,
            })
            if not mkt_data:
                continue
            for m in mkt_data.get("markets", []):
                if m.get("status") in ("open", "active", "trading"):
                    parsed = _parse_kalshi_market(m, series, event)
                    if parsed:
                        active.append(parsed)

    return active


def _parse_kalshi_market(m: dict, series: str, event: dict | None = None) -> dict | None:
    yes_bid = m.get("yes_bid", 0) / 100.0
    yes_ask = m.get("yes_ask", 0) / 100.0
    last = m.get("last_price", 0) / 100.0

    if yes_bid > 0 and yes_ask > 0 and yes_ask < 1:
        mid = (yes_bid + yes_ask) / 2
    elif last > 0:
        mid = last
    else:
        return None

    if mid <= 0.05 or mid > 0.95:
        return None

    strike = (m.get("custom_strike", {}).get("Word", "") or
              m.get("no_sub_title", "") or
              m.get("subtitle", ""))

    return {
        "source": "kalshi",
        "ticker": m.get("ticker", ""),
        "series": series,
        "event_ticker": m.get("event_ticker", ""),
        "event_title": event.get("title", "") if event else m.get("title", ""),
        "strike_word": strike,
        "yes_mid": mid,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "volume": m.get("volume", 0),
        "close_time": m.get("close_time", ""),
    }


def check_settlement(ticker: str) -> str | None:
    """Check if a Kalshi market has settled. Returns "yes", "no", or None."""
    data = _kalshi_get(f"/markets/{ticker}")
    if data and isinstance(data, dict):
        mkt = data.get("market", data)
        result = mkt.get("result")
        if result in ("yes", "no"):
            return result
    return None


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from datetime import datetime

    print(f"PM Mentions Grid Filter — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"Config: edge>={CONFIG['grid_edge_min']*100:.0f}c, "
          f"BR<={CONFIG['grid_br_max']:.0%}, "
          f"maxYES<={CONFIG['max_yes_price']:.0%}, "
          f"no earnings, 1/4 Kelly")
    print()

    # Load base rates
    br_path = Path("base_rates.json")
    if not br_path.exists():
        # Try repo path
        br_path = Path("data/real_markets/kalshi_all_series.json")
        if br_path.exists():
            print("Building base rates from kalshi_all_series.json...")
            from collections import defaultdict
            with open(br_path) as f:
                raw = json.load(f)
            by_series = defaultdict(lambda: {"outcomes": [], "mids": []})
            for m in raw.get("markets", []):
                op = m.get("opening_price")
                result = m.get("result")
                if op and 0 < op < 1 and result in ("yes", "no"):
                    s = m.get("series", "")
                    by_series[s]["outcomes"].append(1 if result == "yes" else 0)
            rates = {}
            for s, d in by_series.items():
                n = len(d["outcomes"])
                if n > 0:
                    rates[s] = {"base_rate": float(np.mean(d["outcomes"])), "n_markets": n}
            # Save for next time
            with open("base_rates.json", "w") as f:
                json.dump(rates, f, indent=2)
            print(f"  Saved {len(rates)} series to base_rates.json")
        else:
            print("ERROR: No base_rates.json found. Create one with:")
            print('  {"SERIES_TICKER": {"base_rate": 0.35, "n_markets": 50}, ...}')
            sys.exit(1)
    else:
        rates = load_base_rates(str(br_path))
        print(f"Loaded {len(rates)} series from {br_path}")

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
            n, cost = size_position(s, capital)
            print(f"{i+1:>3}  {s['strike_word'][:33]:<35s}  "
                  f"{s['yes_mid']:>4.0%}  {s['base_rate']:>4.0%}  "
                  f"{s['edge']:>+5.0%}  {s['expected_pnl']:>+6.3f}  "
                  f"{n:>5}  ${cost:>5.1f}")
