"""PM Mentions Strategy — Polymarket-native version.

Uses speaker-level base rates derived from 10K resolved PM mention markets
instead of Kalshi series-level rates. Edge = yes_price - speaker_base_rate.

Key differences from focused_strategy.py:
- Base rates from PM historical data (per-speaker), not Kalshi series
- No political_person exclusion (most PM mentions are political)
- No fees on Polymarket
- Speaker-level rates with category fallback

Usage:
    from pm_focused_strategy import compute_signals, PM_CONFIG
    from pm_base_rates import load_calibration
    from polymarket_client import fetch_mention_markets

    cal = load_calibration()
    markets = fetch_mention_markets()
    signals = compute_signals(markets, cal)
"""

from pm_base_rates import find_speaker_rate, find_category_rate, _normalize_speaker
from pm_transcript_rates import find_transcript_rate, load_transcript_rates, OUT_PATH

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
PM_CONFIG = {
    # Edge thresholds — PM has zero fees so lower edge is viable.
    # PM backtest: 4c edge is most profitable by total PnL (N=5612,
    # Sharpe=0.055, CI excludes zero). Tiered by rate quality:
    # - High-N speakers (100+): tighter edge OK (4c), rate is reliable
    # - Medium-N speakers (20-99): moderate edge (6c)
    # - Category/overall fallback: need more edge (10c)
    "edge_min_speaker_high_n": 0.04,  # speakers with 100+ markets
    "edge_min_speaker_low_n": 0.06,   # speakers with 20-99 markets
    "edge_min_category": 0.10,        # category-level fallback
    "speaker_high_n_threshold": 100,  # markets needed for "high N"

    # Base rate cap — don't trade if base rate is too high
    "br_max": 0.50,

    # Price filters — PM backtest shows max_yes=60% is the sweet spot:
    # going from 50->60% adds 6200 trades, Sharpe jumps from 0.055 to 0.123
    # Above 60% adds very few markets (diminishing returns)
    "max_yes_price": 0.60,
    "min_yes_price": 0.05,          # skip near-zero (illiquid)

    # Category exclusions — on PM, political_person is the profitable segment
    # and earnings is strongly negative (opposite of Kalshi!)
    "exclude_categories": ["earnings"],

    # Min history for rate to be trusted
    "min_speaker_n": 20,            # need 20+ resolved markets per speaker
    "min_category_n": 50,           # category rates need more data

    # Position sizing
    "kelly_fraction": 0.25,
    "max_position_pct": 0.05,
    "max_total_exposure_pct": 0.80,
    "max_per_event_pct": 0.20,

    # Costs — Polymarket has no fees
    "fee": 0.0,
    "slippage": 0.01,

    # Volume filter
    "min_volume": 0.0,              # minimum volume to consider

    # Transcript word-level rates (political LibFrog)
    # When available, these give per-word precision instead of speaker average.
    # Minimum transcripts needed for word-level rate to be trusted.
    "min_transcript_events": 10,
    # Edge threshold for transcript-backed signals — most precise rate source,
    # so we can use a tighter threshold than speaker-level.
    "edge_min_transcript": 0.04,
}


# ---------------------------------------------------------------------------
# Signal computation
# ---------------------------------------------------------------------------
def compute_signals(
    active_markets: list[dict],
    calibration: dict,
    config: dict | None = None,
) -> list[dict]:
    """Apply PM-native filter to active Polymarket mention markets.

    Returns qualifying NO signals sorted by expected PnL.

    Each market dict needs:
        ticker (condition_id), yes_mid, event_ticker, speaker or series

    Calibration dict needs:
        by_speaker: {speaker: {base_rate, n_markets}}
        by_category: {category: {base_rate, n_markets}}
        overall: {base_rate, n_markets}
    """
    cfg = config or PM_CONFIG
    signals = []

    edge_min_sp_high = cfg.get("edge_min_speaker_high_n", 0.04)
    edge_min_sp_low = cfg.get("edge_min_speaker_low_n", 0.06)
    edge_min_cat = cfg.get("edge_min_category", 0.10)
    edge_min_transcript = cfg.get("edge_min_transcript", 0.04)
    sp_high_n = cfg.get("speaker_high_n_threshold", 100)
    br_max = cfg["br_max"]
    max_yes = cfg["max_yes_price"]
    min_yes = cfg.get("min_yes_price", 0.05)
    min_sp_n = cfg.get("min_speaker_n", 20)
    min_cat_n = cfg.get("min_category_n", 50)
    min_tx_events = cfg.get("min_transcript_events", 10)
    fee = cfg.get("fee", 0.0)
    slip = cfg["slippage"]
    min_vol = cfg.get("min_volume", 0.0)
    exclude_cats = set(cfg.get("exclude_categories", []))

    # Load transcript word-level rates if available
    transcript_rates = {}
    if OUT_PATH.exists():
        try:
            transcript_rates = load_transcript_rates()
        except Exception:
            pass

    for mkt in active_markets:
        yes_mid = mkt["yes_mid"]
        category = mkt.get("category", "other")

        # --- Category exclusion ---
        if category in exclude_cats:
            continue

        # --- Price filter ---
        if yes_mid > max_yes or yes_mid < min_yes:
            continue

        # --- Volume filter ---
        if mkt.get("volume", 0) < min_vol:
            continue

        # --- Rate lookup: speaker first, then category, then overall ---
        speaker = mkt.get("speaker", "")
        # If no speaker field, try to extract from series mapping
        if not speaker:
            series = mkt.get("series", "")
            speaker = _series_to_speaker(series)

        category = mkt.get("category", "other")
        br = None
        n_hist = 0
        rate_source = None

        # Transcript word-level rate (highest precision — political LibFrog)
        strike_word = mkt.get("strike_word", "")
        if transcript_rates and speaker and strike_word:
            tx_rate = find_transcript_rate(
                speaker, strike_word, transcript_rates,
                min_events=min_tx_events)
            if tx_rate is not None:
                br = tx_rate["base_rate"]
                n_hist = tx_rate["n_events"]
                rate_source = "transcript"

        # Speaker-level rate (only if no transcript rate)
        if br is None:
            sp_rate = find_speaker_rate(speaker, calibration, min_n=min_sp_n)
            if sp_rate is not None:
                br = sp_rate["base_rate"]
                n_hist = sp_rate["n_markets"]
                rate_source = "speaker"

        # Category fallback
        if br is None:
            cat_rate = find_category_rate(category, calibration)
            if cat_rate is not None and cat_rate["n_markets"] >= min_cat_n:
                br = cat_rate["base_rate"]
                n_hist = cat_rate["n_markets"]
                rate_source = "category"

        # Overall fallback
        if br is None:
            overall = calibration.get("overall", {})
            if overall.get("n_markets", 0) >= 100:
                br = overall["base_rate"]
                n_hist = overall["n_markets"]
                rate_source = "overall"

        if br is None:
            continue

        # --- BR cap ---
        if br > br_max:
            continue

        # --- Edge calculation ---
        edge = yes_mid - br
        if rate_source == "transcript":
            edge_min = edge_min_transcript
        elif rate_source == "speaker":
            edge_min = edge_min_sp_high if n_hist >= sp_high_n else edge_min_sp_low
        else:
            edge_min = edge_min_cat
        if edge < edge_min:
            continue

        # --- Expected PnL and Kelly sizing ---
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
            "ticker": mkt.get("ticker", mkt.get("condition_id", "")),
            "series": mkt.get("series", ""),
            "event_ticker": mkt.get("event_ticker", ""),
            "event_title": mkt.get("event_title", ""),
            "strike_word": mkt.get("strike_word", ""),
            "source": "polymarket",
            "category": category,
            "speaker": speaker,
            "side": "NO",
            "yes_mid": yes_mid,
            "base_rate": br,
            "edge": edge,
            "expected_pnl": epnl,
            "kelly_quarter": kelly_q,
            "n_history": n_hist,
            "rate_source": rate_source,
            "volume": mkt.get("volume", 0),
            "close_time": mkt.get("close_time", ""),
        })

    signals.sort(key=lambda s: s["expected_pnl"], reverse=True)
    return signals


def _series_to_speaker(series: str) -> str:
    """Reverse-map a series ticker to a speaker name."""
    mapping = {
        "KXTRUMPMENTION": "trump",
        "KXPOWELLMENTION": "powell",
        "KXSTARMERMENTION": "starmer",
        "KXBIDENMENTION": "biden",
        "KXVANCEMENTION": "vance",
        "KXLEAVITTMENTION": "leavitt",
        "KXPSAKIMENTION": "psaki",
        "POLYMARKET_MRBEAST": "mrbeast",
        "KXEARNINGSMENTIONNVDA": "jensen huang",
    }
    return mapping.get(series, "")
