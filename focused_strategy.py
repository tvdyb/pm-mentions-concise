"""PM Mentions Focused Strategy — Targets Profitable Segments Only

Tighter version of pm_mentions_strategy.py based on honest backtest findings:
- Caps YES price at 50c (50-75c bucket has zero edge)
- Excludes political_person category (negative PnL)
- Tiered edge thresholds: lower for LibFrog (more reliable), higher for rolling series
- Stricter min history for rolling series rates

Drop this file + base_rates.json into any paper trading system.
No dependencies beyond requests + numpy.

Usage:
    from focused_strategy import (
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
        print(f"{sig['ticker']}: {n_contracts} NO @ ${cost:.2f} "
              f"(rate_source={sig['rate_source']})")
"""

import json
import time
from pathlib import Path

import numpy as np
import requests

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
FOCUSED_CONFIG = {
    # Core grid filter
    "grid_edge_min": 0.10,       # default edge floor (overridden by tiered thresholds)
    "grid_br_max": 0.50,

    # Tighter YES price cap — the 50-75c bucket has zero edge in honest backtest
    "max_yes_price": 0.50,

    # Category exclusions
    "exclude_categories": ["political_person"],

    # Series blocklist
    "blocked_series": [],

    # Tiered edge thresholds by rate source
    "edge_min_libfrog": 0.08,    # LibFrog rates are precise → can trade thinner edge
    "edge_min_rolling": 0.12,    # Rolling series rates are noisier → need more edge

    # Tiered min history by rate source
    "min_history_libfrog": 10,   # 10 transcript calls is sufficient for LibFrog
    "min_history_rolling": 15,   # need more series history for noisier rates

    # Position sizing
    "kelly_fraction": 0.25,
    "max_position_pct": 0.05,
    "max_total_exposure_pct": 0.80,
    "max_per_event_pct": 0.20,

    # Costs
    "kalshi_fee_rt": 0.02,
    "slippage": 0.01,
}

# ---------------------------------------------------------------------------
# Base rates
# ---------------------------------------------------------------------------
def load_base_rates(path: str = "base_rates.json") -> dict:
    """Load historical base rates per series and word-level LibFrog rates.

    Format: series-level entries keyed by series ticker:
        {series: {base_rate: float, n_markets: int}}
    Word-level entries keyed as "SERIES|word":
        {"SERIES|word": {base_rate: float, n_calls: int, source: "libfrog"}}
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
    if series in rates and "base_rate" in rates[series]:
        return rates[series]
    if series[-1:].isalpha() and series[-1] != "N":
        base = series[:-1]
        if base in rates and "base_rate" in rates[base]:
            return rates[base]
    if series in SERIES_EQUIVALENCES:
        equiv = SERIES_EQUIVALENCES[series]
        if equiv in rates and "base_rate" in rates[equiv]:
            return rates[equiv]
    return None


def _find_word_rate(series: str, strike_word: str, rates: dict,
                    min_calls: int = 10) -> tuple[dict | None, str]:
    """Look up a word-level LibFrog rate for a (series, strike_word) pair."""
    key = f"{series}|{strike_word}"
    if key in rates:
        entry = rates[key]
        if entry.get("source") == "libfrog" and entry.get("n_calls", 0) >= min_calls:
            return entry, "libfrog"

    if " / " in strike_word:
        for part in strike_word.split(" / "):
            alt_key = f"{series}|{part.strip()}"
            if alt_key in rates:
                entry = rates[alt_key]
                if entry.get("source") == "libfrog" and entry.get("n_calls", 0) >= min_calls:
                    return entry, "libfrog"

    return None, "series"


# ---------------------------------------------------------------------------
# Signal computation
# ---------------------------------------------------------------------------
def compute_signals(
    active_markets: list[dict],
    rates: dict,
    config: dict | None = None,
) -> list[dict]:
    """Apply focused grid filter to active markets. Returns qualifying NO signals.

    Each market dict needs at minimum:
        ticker, series, yes_mid, source, event_ticker

    Optional fields:
        event_title, strike_word, yes_bid, yes_ask, volume, close_time, category
    """
    cfg = config or FOCUSED_CONFIG
    signals = []

    exclude_cats = set(cfg.get("exclude_categories", []))
    blocked = set(cfg.get("blocked_series", []))
    max_yes = cfg["max_yes_price"]
    br_max = cfg["grid_br_max"]
    fee_kalshi = cfg["kalshi_fee_rt"]
    slip = cfg["slippage"]
    edge_min_lf = cfg.get("edge_min_libfrog", cfg["grid_edge_min"])
    edge_min_roll = cfg.get("edge_min_rolling", cfg["grid_edge_min"])
    min_hist_lf = cfg.get("min_history_libfrog", 10)
    min_hist_roll = cfg.get("min_history_rolling", cfg.get("min_history", 10))

    for mkt in active_markets:
        series = mkt["series"]
        yes_mid = mkt["yes_mid"]

        # --- Category exclusion ---
        category = mkt.get("category", "")
        if category in exclude_cats:
            continue

        # --- Series blocklist ---
        if series in blocked:
            continue

        # --- Price filter ---
        if yes_mid > max_yes or yes_mid < 0.05:
            continue

        # --- Rate lookup: word-level first, then series-level ---
        strike_word = mkt.get("strike_word", "")
        word_info, rate_source = _find_word_rate(
            series, strike_word, rates, min_calls=min_hist_lf)

        if word_info is not None:
            br = word_info["base_rate"]
            n = word_info.get("n_calls", 0)
        else:
            info = _find_series_rate(series, rates)
            if not info:
                continue
            br = info["base_rate"]
            n = info.get("n_markets", 0)
            rate_source = "series"

        # --- Tiered min history ---
        min_hist = min_hist_lf if rate_source == "libfrog" else min_hist_roll
        if n < min_hist:
            continue

        # --- BR cap ---
        if br > br_max:
            continue

        # --- Tiered edge threshold ---
        edge = yes_mid - br
        edge_min = edge_min_lf if rate_source == "libfrog" else edge_min_roll
        if edge < edge_min:
            continue

        # --- Expected PnL and Kelly sizing ---
        fee = fee_kalshi if mkt.get("source") == "kalshi" else 0.0
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
            "category": category,
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
# Position sizing
# ---------------------------------------------------------------------------
def size_position(
    signal: dict,
    capital: float,
    config: dict | None = None,
) -> tuple[int, float]:
    """Compute number of contracts and total cost for a signal.

    Returns (n_contracts, total_cost). Returns (0, 0) if position too small.
    """
    cfg = config or FOCUSED_CONFIG
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
    """Compute realized PnL when a market settles."""
    cfg = config or FOCUSED_CONFIG
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
# Kalshi API helpers (same as pm_mentions_strategy.py)
# ---------------------------------------------------------------------------
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


def _kalshi_get(path: str, params: dict | None = None) -> dict | None:
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
    """Fetch all active mention markets from Kalshi."""
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

    category = "earnings" if "EARNINGS" in series.upper() else \
               "sports" if any(x in series.upper() for x in ["NFL", "TNF", "MNF", "MVE",
                                                               "NBA", "MLB", "NCAA", "CFB",
                                                               "SNF", "NCAAB"]) else \
               "political_person"  # conservative default — will be filtered

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
        "category": category,
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
