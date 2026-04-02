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

import os
import time

from pm_base_rates import find_speaker_rate, find_category_rate, _normalize_speaker
from pm_transcript_rates import find_transcript_rate, load_transcript_rates, OUT_PATH
from shared import compute_expected_pnl

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
    "exclude_categories": ["earnings", "monthly", "weekly"],

    # Speaker exclusions — backtest shows these are break-even to negative
    "exclude_speakers": ["starmer", "vance"],

    # Min history for rate to be trusted
    "min_speaker_n": 20,            # need 20+ resolved markets per speaker
    "min_category_n": 50,           # category rates need more data

    # Position sizing
    "kelly_fraction": 0.25,
    "max_position_pct": 0.02,
    "max_total_exposure_pct": 0.80,
    "max_per_event_pct": 0.20,

    # Costs — Polymarket taker fees (mentions: 25% rate, exponent 2)
    "fee": 0.0,              # flat fee override (0 = use fee_category)
    "fee_category": "mentions",  # Polymarket fee schedule category
    "slippage": 0.01,

    # Execution filters
    "max_no_spread": 0.05,          # skip markets with NO spread > 5c

    # Volume filter — NOTE: live volume is in-progress (lower than final),
    # so this filter is less strict live than in backtest (which uses final volume).
    "min_volume": 0.0,              # minimum volume to consider
    "max_volume": 10_000,           # skip hyper-liquid markets (arb-dominated)

    # Price trend filter — skip markets where YES is drifting up (bad for NO)
    # Positive trend means CLOB midpoint > Gamma mid → price rising
    "max_price_trend": 0.05,        # skip if YES drifted up > 5c

    # Transcript word-level rates (political LibFrog)
    # When available, these give per-word precision instead of speaker average.
    # Minimum transcripts needed for word-level rate to be trusted.
    "min_transcript_events": 10,
    # Edge threshold for transcript-backed signals — most precise rate source,
    # so we can use a tighter threshold than speaker-level.
    "edge_min_transcript": 0.04,

    # Transcript data staleness — skip transcript rates if data is older than this
    "max_transcript_age_days": 180,

    # Intra-event decay factors (applied in bot.py when sibling markets resolve NO)
    # WARNING: these are live-only adjustments, not validated in backtest
    "event_decay_2_nos": 0.75,     # base rate multiplier when 2 sibling NOs
    "event_decay_3plus_nos": 0.65, # base rate multiplier when 3+ sibling NOs
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
    fee_category = cfg.get("fee_category")
    slip = cfg["slippage"]
    min_vol = cfg.get("min_volume", 0.0)
    max_vol = cfg.get("max_volume", float("inf"))
    max_trend = cfg.get("max_price_trend", 0.05)
    exclude_cats = set(cfg.get("exclude_categories", []))
    exclude_speakers = set(s.lower() for s in cfg.get("exclude_speakers", []))

    # Load transcript word-level rates if available
    transcript_rates = {}
    transcript_stale = False
    if OUT_PATH.exists():
        try:
            transcript_rates = load_transcript_rates()
        except (ValueError, OSError) as e:
            import warnings
            warnings.warn(f"Failed to load transcript rates: {e}")

    # Check transcript data age
    if transcript_rates and OUT_PATH.exists():
        age_days = (time.time() - os.path.getmtime(OUT_PATH)) / 86400
        max_age = cfg.get("max_transcript_age_days", 180)
        if age_days > max_age:
            import warnings
            warnings.warn(f"Transcript data is {age_days:.0f} days old (max {max_age}). "
                          f"Falling back to speaker rates. Run pm_transcript_rates.py to refresh.")
            transcript_stale = True

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
        vol = mkt.get("volume", 0)
        if vol < min_vol or vol > max_vol:
            continue

        # --- Price trend filter ---
        price_trend = mkt.get("price_trend")
        if price_trend is not None and price_trend > max_trend:
            continue

        # --- Rate lookup: speaker first, then category, then overall ---
        speaker = mkt.get("speaker", "")
        # If no speaker field, try to extract from series mapping
        if not speaker:
            series = mkt.get("series", "")
            speaker = _series_to_speaker(series)

        # --- Speaker exclusion ---
        if speaker.lower() in exclude_speakers:
            continue

        category = mkt.get("category", "other")
        br = None
        n_hist = 0
        rate_source = None

        # Transcript word-level rate (highest precision — political LibFrog)
        strike_word = mkt.get("strike_word", "")
        if transcript_rates and not transcript_stale and speaker and strike_word:
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
        epnl, kelly_q = compute_expected_pnl(
            yes_mid, br, fee=fee, slippage=slip,
            kelly_fraction=cfg["kelly_fraction"],
            fee_category=fee_category)

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
            "price_trend": mkt.get("price_trend"),
            "total_bid_depth": mkt.get("total_bid_depth"),
            "n_bid_levels": mkt.get("n_bid_levels"),
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
