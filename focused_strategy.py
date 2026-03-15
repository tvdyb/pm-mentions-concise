"""PM Mentions Focused Strategy — Targets Profitable Segments Only

Tighter version of pm_mentions_strategy.py based on honest backtest findings:
- Caps YES price at 50c (50-75c bucket has zero edge)
- Excludes political_person category (negative PnL)
- Tiered edge thresholds: lower for LibFrog (more reliable), higher for rolling series
- Stricter min history for rolling series rates

Usage:
    from focused_strategy import compute_signals, FOCUSED_CONFIG
    from shared import load_base_rates, fetch_active_kalshi, size_position

    rates = load_base_rates("base_rates.json")
    markets = fetch_active_kalshi(rates)
    signals = compute_signals(markets, rates)

    for sig in signals:
        n_contracts, cost = size_position(sig, capital=1000, config=FOCUSED_CONFIG)
        print(f"{sig['ticker']}: {n_contracts} NO @ ${cost:.2f} "
              f"(rate_source={sig['rate_source']})")
"""

from shared import (
    find_series_rate,
    find_word_rate,
    SERIES_EQUIVALENCES,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
FOCUSED_CONFIG = {
    # Core grid filter
    "grid_br_max": 0.50,

    # Tighter YES price cap — the 50-75c bucket has zero edge in honest backtest
    "max_yes_price": 0.50,

    # Category exclusions
    "exclude_categories": ["political_person"],

    # Series blocklist
    "blocked_series": [],

    # Tiered edge thresholds by rate source
    "edge_min_libfrog": 0.08,    # LibFrog rates are precise -> can trade thinner edge
    "edge_min_rolling": 0.12,    # Rolling series rates are noisier -> need more edge

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
    edge_min_lf = cfg.get("edge_min_libfrog", 0.10)
    edge_min_roll = cfg.get("edge_min_rolling", 0.10)
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
        word_info, rate_source = find_word_rate(
            series, strike_word, rates, min_calls=min_hist_lf)

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
