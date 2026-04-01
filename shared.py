"""Shared utilities for PM Mentions strategies.

Contains base rate lookup, Kalshi API helpers, position sizing, and
settlement PnL — used by both pm_mentions_strategy.py and focused_strategy.py.
"""

import json
import time

import requests

# ---------------------------------------------------------------------------
# Series equivalences
# ---------------------------------------------------------------------------
SERIES_EQUIVALENCES = {
    "KXFEDMENTION": "KXPOWELLMENTION",
    "KXJPOWMENTION": "KXPOWELLMENTION",
    "KXTRUMPMENTIONB": "KXTRUMPMENTION",
    "KXSTARMERMENTIONB": "KXSTARMERMENTION",
    "KXTRUMPMENTIONDURATION": "KXTRUMPMENTION",
}

# Political person keywords for category classification
POLITICAL_KEYWORDS = [
    "TRUMP", "POWELL", "VANCE", "PSAKI", "LEAVITT", "STARMER",
    "BIDEN", "HARRIS", "DESANTIS", "JPOW", "FED",
]

SPORTS_KEYWORDS = [
    "NFL", "TNF", "MNF", "MVE", "NBA", "MLB", "NCAA", "CFB", "SNF", "NCAAB",
]


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


def find_series_rate(series: str, rates: dict) -> dict | None:
    """Look up base rate for a series, trying equivalences."""
    if series in rates and "base_rate" in rates[series]:
        return rates[series]
    if series in SERIES_EQUIVALENCES:
        equiv = SERIES_EQUIVALENCES[series]
        if equiv in rates and "base_rate" in rates[equiv]:
            return rates[equiv]
    return None


def find_word_rate(
    series: str,
    strike_word: str,
    rates: dict,
    min_calls: int = 10,
) -> tuple[dict | None, str]:
    """Look up a word-level LibFrog rate for a (series, strike_word) pair.

    Returns (rate_dict_or_None, rate_source).
    """
    if not strike_word:
        return None, "series"

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


def equiv_series(series: str) -> str:
    """Return the canonical series ticker after applying equivalences."""
    if series in SERIES_EQUIVALENCES:
        return SERIES_EQUIVALENCES[series]
    return series


# ---------------------------------------------------------------------------
# Polymarket fee calculation
# ---------------------------------------------------------------------------

PM_FEE_SCHEDULE = {
    "mentions":    {"rate": 0.25, "exponent": 2},
    "sports":      {"rate": 0.03, "exponent": 1},
    "crypto":      {"rate": 0.072, "exponent": 1},
    "politics":    {"rate": 0.04, "exponent": 1},
    "finance":     {"rate": 0.04, "exponent": 1},
    "economics":   {"rate": 0.03, "exponent": 0.5},
    "culture":     {"rate": 0.05, "exponent": 1},
    "weather":     {"rate": 0.025, "exponent": 0.5},
    "tech":        {"rate": 0.04, "exponent": 1},
    "geopolitics": {"rate": 0.0, "exponent": 1},
    "other":       {"rate": 0.20, "exponent": 2},
}


def pm_taker_fee(price: float, category: str = "mentions") -> float:
    """Compute Polymarket taker fee per contract.

    Formula: fee = p × feeRate × (p × (1-p))^exponent
    where p = price of the token being bought.

    Returns fee in dollars per contract (≥ 0.0001 minimum, or 0 if below).
    """
    sched = PM_FEE_SCHEDULE.get(category, PM_FEE_SCHEDULE["other"])
    rate = sched["rate"]
    exp = sched["exponent"]
    if rate == 0 or price <= 0 or price >= 1:
        return 0.0
    raw = price * rate * (price * (1.0 - price)) ** exp
    return round(max(raw, 0.0001), 4) if raw > 0 else 0.0


# ---------------------------------------------------------------------------
# Expected PnL and Kelly sizing
# ---------------------------------------------------------------------------
def compute_expected_pnl(
    yes_mid: float,
    base_rate: float,
    fee: float = 0.0,
    slippage: float = 0.01,
    kelly_fraction: float = 0.25,
    fee_category: str | None = None,
) -> tuple[float, float]:
    """Compute expected PnL per NO contract and quarter-Kelly fraction.

    If fee_category is set (e.g. "mentions"), computes the Polymarket
    taker fee from the NO price instead of using the flat fee param.

    Returns (expected_pnl, kelly_quarter).
    """
    eff_yes = max(0.01, yes_mid - slippage)
    no_cost = 1.0 - eff_yes
    p_no = 1.0 - base_rate

    if fee_category:
        fee = pm_taker_fee(no_cost, category=fee_category)

    epnl = p_no * eff_yes - base_rate * no_cost - fee

    if epnl > 0:
        b = eff_yes / no_cost if no_cost > 0 else 0
        kelly_full = (p_no * b - base_rate) / b if b > 0 else 0
        kelly_q = max(0.0, kelly_full * kelly_fraction)
    else:
        kelly_q = 0.0

    return epnl, kelly_q


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------
def size_position(
    signal: dict,
    capital: float,
    config: dict,
) -> tuple[int, float]:
    """Compute number of contracts and total cost for a signal.

    Returns (n_contracts, total_cost). Returns (0, 0) if position too small.
    """
    max_size = capital * config["max_position_pct"]
    kelly_size = capital * signal["kelly_quarter"]
    position_size = min(kelly_size, max_size)

    if position_size < 1.0:
        return 0, 0.0

    slip = config["slippage"]
    eff_yes = max(0.01, signal["yes_mid"] - slip)
    no_cost = 1.0 - eff_yes
    n_contracts = int(position_size / no_cost)

    min_size = config.get("min_order_size", 5)
    if n_contracts < min_size:
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
    fee: float = 0.0,
    slippage: float = 0.01,
    fee_category: str | None = None,
) -> float:
    """Compute realized PnL when a market settles."""
    if config is not None:
        fee = config["kalshi_fee_rt"]
        slippage = config["slippage"]
    eff_yes = max(0.01, entry_price - slippage)
    no_cost = 1.0 - eff_yes
    if fee_category:
        fee = pm_taker_fee(no_cost, category=fee_category)

    if side == "NO":
        pnl_per = (eff_yes - fee) if result == "no" else (-no_cost - fee)
    else:
        pnl_per = ((1.0 - eff_yes) - fee) if result == "yes" else (-eff_yes - fee)

    return pnl_per * n_contracts


# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------
def classify_category(series: str) -> str:
    """Classify a series into a category based on keywords."""
    series_up = series.upper()
    if "EARNINGS" in series_up:
        return "earnings"
    if any(x in series_up for x in SPORTS_KEYWORDS):
        return "sports"
    if any(x in series_up for x in POLITICAL_KEYWORDS):
        return "political_person"
    return "other"


# ---------------------------------------------------------------------------
# Kalshi API helpers
# ---------------------------------------------------------------------------
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


def kalshi_get(path: str, params: dict | None = None) -> dict | None:
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


def parse_kalshi_market(m: dict, series: str, event: dict | None = None) -> dict | None:
    """Parse a raw Kalshi market dict into a standardized market dict."""
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

    category = classify_category(series)

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


def fetch_active_kalshi(rates: dict, delay: float = 0.3) -> list[dict]:
    """Fetch all active mention markets from Kalshi."""
    data = kalshi_get("/series", {"limit": 1000})
    if not data:
        return []

    mention_series = [s["ticker"] for s in data.get("series", [])
                      if "MENTION" in s.get("ticker", "").upper()]

    active = []
    for series in mention_series:
        time.sleep(delay)
        ev_data = kalshi_get("/events", {
            "series_ticker": series, "status": "open", "limit": 50,
        })

        if not ev_data or not ev_data.get("events"):
            mkt_data = kalshi_get("/markets", {
                "status": "open", "limit": 100, "series_ticker": series,
            })
            if mkt_data:
                for m in mkt_data.get("markets", []):
                    if m.get("status") in ("open", "active"):
                        parsed = parse_kalshi_market(m, series)
                        if parsed:
                            active.append(parsed)
            continue

        for event in ev_data["events"]:
            time.sleep(delay)
            mkt_data = kalshi_get("/markets", {
                "event_ticker": event["event_ticker"], "limit": 200,
            })
            if not mkt_data:
                continue
            for m in mkt_data.get("markets", []):
                if m.get("status") in ("open", "active", "trading"):
                    parsed = parse_kalshi_market(m, series, event)
                    if parsed:
                        active.append(parsed)

    return active


def check_settlement(ticker: str) -> str | None:
    """Check if a Kalshi market has settled. Returns "yes", "no", or None."""
    data = kalshi_get(f"/markets/{ticker}")
    if data and isinstance(data, dict):
        mkt = data.get("market", data)
        result = mkt.get("result")
        if result in ("yes", "no"):
            return result
    return None
