#!/usr/bin/env python3
"""Honest backtest for PM Mentions Grid Filter Strategy.

Fixes two bugs in the original ad-hoc backtest:
  1. Entry price: uses VWAP variants instead of opening_price
  2. Look-ahead bias: uses rolling base rates instead of static rates
     computed from the full dataset

LibFrog word-level rates (from external transcript data) are NOT
look-ahead — they come from a separate dataset and are used as-is.

Usage:
    python backtest.py
    python backtest.py --save   # also writes backtest_report.md
"""

import json
import argparse
import numpy as np
from collections import defaultdict
from datetime import datetime

from pm_mentions_strategy import CONFIG

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_markets(path="data/kalshi_all_series.json"):
    with open(path) as f:
        return json.load(f)["markets"]


def load_libfrog_rates(path="base_rates.json"):
    """Load only the LibFrog word-level entries (keys containing '|')."""
    with open(path) as f:
        rates = json.load(f)
    return {k: v for k, v in rates.items()
            if "|" in k and v.get("source") == "libfrog"}


def load_static_rates(path="base_rates.json"):
    """Load all static rates (series + word-level) for the original backtest."""
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Series equivalences (same as strategy file)
# ---------------------------------------------------------------------------

SERIES_EQUIVALENCES = {
    "KXFEDMENTION": "KXPOWELLMENTION",
    "KXJPOWMENTION": "KXPOWELLMENTION",
    "KXTRUMPMENTIONB": "KXTRUMPMENTION",
    "KXSTARMERMENTIONB": "KXSTARMERMENTION",
    "KXTRUMPMENTIONDURATION": "KXTRUMPMENTION",
}


def _equiv_series(series):
    """Return the canonical series ticker after applying equivalences."""
    if series in SERIES_EQUIVALENCES:
        return SERIES_EQUIVALENCES[series]
    # Strip trailing letter (KXSTARMERMENTIONB → KXSTARMERMENTION)
    if series[-1:].isalpha() and series[-1] != "N":
        return series[:-1]
    return series


# ---------------------------------------------------------------------------
# LibFrog word-level lookup (no look-ahead — external data)
# ---------------------------------------------------------------------------

def libfrog_lookup(libfrog_rates, series, strike_word):
    """Look up LibFrog word-level rate. Returns (base_rate, n_calls) or (None, 0)."""
    key = f"{series}|{strike_word}"
    if key in libfrog_rates:
        e = libfrog_rates[key]
        if e.get("n_calls", 0) >= 10:
            return e["base_rate"], e["n_calls"]

    if " / " in strike_word:
        for part in strike_word.split(" / "):
            alt_key = f"{series}|{part.strip()}"
            if alt_key in libfrog_rates:
                e = libfrog_rates[alt_key]
                if e.get("n_calls", 0) >= 10:
                    return e["base_rate"], e["n_calls"]

    return None, 0


# ---------------------------------------------------------------------------
# Static rate lookup (for original/biased backtest)
# ---------------------------------------------------------------------------

def static_rate_lookup(static_rates, series, strike_word, is_earnings):
    """Look up rate from the static base_rates.json (look-ahead biased)."""
    # Word-level first for earnings
    if is_earnings and strike_word:
        key = f"{series}|{strike_word}"
        if key in static_rates:
            e = static_rates[key]
            if e.get("source") == "libfrog" and e.get("n_calls", 0) >= 10:
                return e["base_rate"], e.get("n_calls", 0), "libfrog"
        if " / " in strike_word:
            for part in strike_word.split(" / "):
                alt_key = f"{series}|{part.strip()}"
                if alt_key in static_rates:
                    e = static_rates[alt_key]
                    if e.get("source") == "libfrog" and e.get("n_calls", 0) >= 10:
                        return e["base_rate"], e.get("n_calls", 0), "libfrog"

    # Series-level
    if series in static_rates and "base_rate" in static_rates[series]:
        r = static_rates[series]
        return r["base_rate"], r.get("n_markets", 0), "series_static"

    canon = _equiv_series(series)
    if canon != series and canon in static_rates and "base_rate" in static_rates[canon]:
        r = static_rates[canon]
        return r["base_rate"], r.get("n_markets", 0), "series_static"

    return None, 0, None


# ---------------------------------------------------------------------------
# PnL computation (matches compute_settlement_pnl in strategy file)
# ---------------------------------------------------------------------------

def compute_pnl(entry_price, result, fee, slippage):
    """Compute per-contract PnL for a NO trade."""
    eff_yes = max(0.01, entry_price - slippage)
    no_cost = 1.0 - eff_yes
    if result == "no":
        return eff_yes - fee
    else:
        return -no_cost - fee


# ---------------------------------------------------------------------------
# Rolling backtest (honest)
# ---------------------------------------------------------------------------

def run_rolling_backtest(markets, libfrog_rates, cfg):
    """Run backtest with rolling base rates and VWAP entry prices.

    For each market (sorted by close_time):
      - Compute rolling base rate from all prior settled markets in the series
      - Check LibFrog word-level rate for earnings (external, not look-ahead)
      - Apply grid filter
      - Record PnL at each VWAP variant
      - Update rolling state with this market's outcome
    """
    fee = cfg["kalshi_fee_rt"]
    slip = cfg["slippage"]
    edge_min = cfg["grid_edge_min"]
    br_max = cfg["grid_br_max"]
    min_hist = cfg["min_history"]
    max_yes = cfg["max_yes_price"]

    # Sort by close_time for temporal ordering
    sorted_markets = sorted(markets, key=lambda m: m.get("close_time", ""))

    # Rolling state: series -> list of outcomes (1=yes, 0=no)
    rolling = defaultdict(list)

    price_keys = ["vwap_25pct_buffer", "vwap_10pct_buffer", "vwap_no_buffer"]
    trades = []

    for m in sorted_markets:
        result = m.get("result")
        if result not in ("yes", "no"):
            continue

        series = m["series"]
        is_earnings = "EARNINGS" in series.upper()
        strike_word = m.get("strike_word", "")
        outcome = 1 if result == "yes" else 0
        canon = _equiv_series(series)

        # --- Determine base rate ---
        rate_source = None
        br = None
        n_hist = 0

        # LibFrog word-level for earnings (not look-ahead)
        if is_earnings and strike_word:
            lf_br, lf_n = libfrog_lookup(libfrog_rates, series, strike_word)
            if lf_br is not None:
                br = lf_br
                n_hist = lf_n
                rate_source = "libfrog"

        # Rolling series rate
        if br is None:
            # Use canonical series for rolling lookback
            prior = rolling.get(canon, [])
            if len(prior) >= min_hist:
                br = np.mean(prior)
                n_hist = len(prior)
                rate_source = "rolling"

        # Update rolling state AFTER evaluating (no look-ahead)
        rolling[canon].append(outcome)

        # --- Skip if no usable rate ---
        if br is None:
            continue

        # --- Evaluate at each VWAP variant ---
        trade_row = {
            "ticker": m.get("ticker", ""),
            "series": series,
            "category": m.get("category", "other"),
            "strike_word": strike_word,
            "is_earnings": is_earnings,
            "result": result,
            "rate_source": rate_source,
            "base_rate": br,
            "n_history": n_hist,
            "close_time": m.get("close_time", ""),
            "opening_price": m.get("opening_price"),
            "passed": {},  # price_key -> bool
            "pnl": {},     # price_key -> float
            "entry": {},   # price_key -> float
            "edge": {},    # price_key -> float
        }

        for pk in price_keys:
            price = m.get(pk)
            if price is None or price <= 0.05 or price > 0.95:
                trade_row["passed"][pk] = False
                continue

            if price > max_yes:
                trade_row["passed"][pk] = False
                continue

            edge = price - br
            if edge < edge_min or br > br_max:
                trade_row["passed"][pk] = False
                continue

            trade_row["passed"][pk] = True
            trade_row["entry"][pk] = price
            trade_row["edge"][pk] = edge
            trade_row["pnl"][pk] = compute_pnl(price, result, fee, slip)

        trades.append(trade_row)

    return trades


# ---------------------------------------------------------------------------
# Original (biased) backtest for comparison
# ---------------------------------------------------------------------------

def run_original_backtest(markets, static_rates, cfg):
    """Run the original backtest: opening_price + static base rates."""
    fee = cfg["kalshi_fee_rt"]
    slip = cfg["slippage"]
    edge_min = cfg["grid_edge_min"]
    br_max = cfg["grid_br_max"]
    min_hist = cfg["min_history"]
    max_yes = cfg["max_yes_price"]

    trades = []
    for m in markets:
        result = m.get("result")
        if result not in ("yes", "no"):
            continue

        series = m["series"]
        is_earnings = "EARNINGS" in series.upper()
        strike_word = m.get("strike_word", "")
        price = m.get("opening_price")

        if price is None or price <= 0.05 or price > 0.95:
            continue
        if price > max_yes:
            continue

        br, n_hist, rate_source = static_rate_lookup(
            static_rates, series, strike_word, is_earnings)
        if br is None or n_hist < min_hist:
            continue

        edge = price - br
        if edge < edge_min or br > br_max:
            continue

        pnl = compute_pnl(price, result, fee, slip)
        trades.append({
            "pnl": pnl,
            "entry": price,
            "edge": edge,
            "base_rate": br,
            "rate_source": rate_source,
            "result": result,
            "category": m.get("category", "other"),
            "is_earnings": is_earnings,
            "series": series,
            "close_time": m.get("close_time", ""),
        })

    return trades


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def compute_stats(pnls, label=""):
    """Compute standard trading stats from a list of PnLs."""
    if not pnls:
        return {"label": label, "n": 0}
    arr = np.array(pnls)
    n = len(arr)
    wins = int(np.sum(arr > 0))
    mu = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    total = float(np.sum(arr))
    cum = np.cumsum(arr)
    peak = np.maximum.accumulate(cum)
    dd = float(np.max(peak - cum)) if n > 0 else 0.0

    per_trade_sharpe = mu / std if std > 0 else 0.0

    # Bootstrap 95% CI
    rng = np.random.default_rng(42)
    boot = [float(np.mean(rng.choice(arr, size=n, replace=True)))
            for _ in range(10000)]
    ci_lo, ci_hi = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))

    return {
        "label": label,
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": wins / n,
        "mean_pnl": mu,
        "std_pnl": std,
        "total_pnl": total,
        "per_trade_sharpe": per_trade_sharpe,
        "max_drawdown": dd,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
    }


def fmt_stats_table(stats_list):
    """Format a list of stats dicts into a markdown table."""
    lines = []
    lines.append("| Variant | N | Win Rate | Mean PnL | Std | Total PnL "
                 "| Sharpe | Max DD | 95% CI |")
    lines.append("|---------|---|----------|----------|-----|-----------|"
                 "--------|--------|--------|")
    for s in stats_list:
        if s["n"] == 0:
            lines.append(f"| {s['label']} | 0 | — | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {s['label']} "
            f"| {s['n']} "
            f"| {s['win_rate']:.1%} "
            f"| ${s['mean_pnl']:+.4f} "
            f"| ${s['std_pnl']:.4f} "
            f"| ${s['total_pnl']:+.2f} "
            f"| {s['per_trade_sharpe']:.4f} "
            f"| ${s['max_drawdown']:.2f} "
            f"| [${s['ci_lo']:+.4f}, ${s['ci_hi']:+.4f}] |"
        )
    return "\n".join(lines)


def fmt_simple_table(header, rows):
    """Format a simple markdown table from header list and row tuples."""
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(rolling_trades, original_trades, markets):
    """Generate the full backtest report as a markdown string."""
    lines = []
    lines.append("# PM Mentions Backtest Report — Fixed")
    lines.append("")
    lines.append(f"*Generated {datetime.now():%Y-%m-%d %H:%M} from "
                 f"{len(markets):,} settled markets.*")
    lines.append("")
    lines.append("This backtest fixes two critical bugs in the original analysis:")
    lines.append("")
    lines.append("1. **Entry price**: Uses VWAP (time-weighted average price "
                 "with buffer) instead of `opening_price` (often 1c/99c first trades)")
    lines.append("2. **Look-ahead bias**: Uses rolling base rates computed from "
                 "prior settled markets only, instead of static rates computed "
                 "from the entire dataset")
    lines.append("")
    lines.append("LibFrog word-level rates are NOT look-ahead — they come from "
                 "external transcript data and are used as-is.")

    # ----- Primary VWAP variant -----
    pk_primary = "vwap_25pct_buffer"
    price_keys = ["vwap_25pct_buffer", "vwap_10pct_buffer", "vwap_no_buffer"]
    price_labels = {
        "vwap_25pct_buffer": "VWAP 25% buffer (primary)",
        "vwap_10pct_buffer": "VWAP 10% buffer",
        "vwap_no_buffer": "VWAP no buffer",
    }

    # ----- Section: Comparison vs Original -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Original vs Fixed: Side-by-Side")
    lines.append("")

    orig_pnls = [t["pnl"] for t in original_trades]
    orig_stats = compute_stats(orig_pnls, "Original (opening_price + static rates)")

    fixed_pnls = [t["pnl"][pk_primary] for t in rolling_trades
                  if t["passed"].get(pk_primary)]
    fixed_stats = compute_stats(fixed_pnls, "Fixed (VWAP 25% + rolling rates)")

    lines.append(fmt_stats_table([orig_stats, fixed_stats]))
    lines.append("")

    delta_n = fixed_stats["n"] - orig_stats["n"]
    delta_mu = fixed_stats["mean_pnl"] - orig_stats["mean_pnl"] if fixed_stats["n"] > 0 else 0
    delta_total = fixed_stats["total_pnl"] - orig_stats["total_pnl"] if fixed_stats["n"] > 0 else 0

    lines.append(f"**Delta**: {delta_n:+d} trades, "
                 f"${delta_mu:+.4f} mean PnL/trade, "
                 f"${delta_total:+.2f} total PnL")

    # Annualized Sharpe estimate
    close_times = sorted([m["close_time"] for m in markets if m.get("close_time")])
    if close_times:
        t0 = datetime.fromisoformat(close_times[0].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(close_times[-1].replace("Z", "+00:00"))
        days = (t1 - t0).days
        if days > 0 and fixed_stats["n"] > 0:
            trades_per_year = fixed_stats["n"] / days * 365
            ann_sharpe = fixed_stats["per_trade_sharpe"] * np.sqrt(trades_per_year)
            lines.append("")
            lines.append(f"*Annualized Sharpe estimate: {ann_sharpe:.3f} "
                         f"(assuming {trades_per_year:.0f} trades/year over "
                         f"{days} day range, sqrt({trades_per_year:.0f}) = "
                         f"{np.sqrt(trades_per_year):.1f})*")

    # ----- Section: Entry Price Sensitivity -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Entry Price Sensitivity (all use rolling base rates)")
    lines.append("")

    vwap_stats = []
    for pk in price_keys:
        pnls = [t["pnl"][pk] for t in rolling_trades if t["passed"].get(pk)]
        vwap_stats.append(compute_stats(pnls, price_labels[pk]))
    lines.append(fmt_stats_table(vwap_stats))
    lines.append("")
    lines.append("*VWAP 25% buffer strips the first and last 25% of trading "
                 "time — closest to a realistic fill for someone scanning "
                 "active markets. VWAP no buffer includes extreme early/late "
                 "prints and is the harshest test.*")

    # ----- Section: By Category -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Breakdown by Category")
    lines.append("")

    cat_groups = defaultdict(list)
    for t in rolling_trades:
        if not t["passed"].get(pk_primary):
            continue
        cat = t["category"]
        cat_groups[cat].append(t["pnl"][pk_primary])

    cat_stats = [compute_stats(pnls, cat) for cat, pnls in
                 sorted(cat_groups.items(), key=lambda x: -len(x[1]))]
    lines.append(fmt_stats_table(cat_stats))

    # ----- Section: LibFrog vs Rolling -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Rate Source: LibFrog vs Rolling Series")
    lines.append("")

    source_groups = defaultdict(list)
    for t in rolling_trades:
        if not t["passed"].get(pk_primary):
            continue
        source_groups[t["rate_source"]].append(t["pnl"][pk_primary])

    source_stats = [compute_stats(pnls, src) for src, pnls in
                    sorted(source_groups.items(), key=lambda x: -len(x[1]))]
    lines.append(fmt_stats_table(source_stats))

    traded_fixed = [t for t in rolling_trades if t["passed"].get(pk_primary)]
    n_lf = sum(1 for t in traded_fixed if t["rate_source"] == "libfrog")
    n_roll = sum(1 for t in traded_fixed if t["rate_source"] == "rolling")
    lines.append("")
    lines.append(f"LibFrog-rated trades: {n_lf} ({n_lf/len(traded_fixed)*100:.1f}%) "
                 f"| Rolling series-rated: {n_roll} ({n_roll/len(traded_fixed)*100:.1f}%)"
                 if traded_fixed else "No trades.")

    # ----- Section: YES Price Buckets -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Breakdown by YES Price Bucket")
    lines.append("")

    price_buckets = {"5-25%": [], "25-50%": [], "50-75%": []}
    for t in rolling_trades:
        if not t["passed"].get(pk_primary):
            continue
        p = t["entry"][pk_primary]
        if p < 0.25:
            price_buckets["5-25%"].append(t["pnl"][pk_primary])
        elif p < 0.50:
            price_buckets["25-50%"].append(t["pnl"][pk_primary])
        else:
            price_buckets["50-75%"].append(t["pnl"][pk_primary])

    bucket_stats = [compute_stats(pnls, bucket) for bucket, pnls in
                    sorted(price_buckets.items())]
    lines.append(fmt_stats_table(bucket_stats))

    # ----- Section: Edge Decay -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Edge Decay (Chronological Splits)")
    lines.append("")

    traded = sorted(
        [t for t in rolling_trades if t["passed"].get(pk_primary)],
        key=lambda t: t["close_time"])
    n_traded = len(traded)

    if n_traded >= 4:
        # Halves
        half = n_traded // 2
        h1_pnls = [t["pnl"][pk_primary] for t in traded[:half]]
        h2_pnls = [t["pnl"][pk_primary] for t in traded[half:]]
        h1_dates = f"{traded[0]['close_time'][:10]} – {traded[half-1]['close_time'][:10]}"
        h2_dates = f"{traded[half]['close_time'][:10]} – {traded[-1]['close_time'][:10]}"

        lines.append("### Halves")
        lines.append("")
        lines.append(fmt_stats_table([
            compute_stats(h1_pnls, f"First half ({h1_dates})"),
            compute_stats(h2_pnls, f"Second half ({h2_dates})"),
        ]))

        # Quarters
        q = n_traded // 4
        quarters = [traded[:q], traded[q:2*q], traded[2*q:3*q], traded[3*q:]]
        lines.append("")
        lines.append("### Quarters")
        lines.append("")
        q_stats = []
        for i, chunk in enumerate(quarters):
            if not chunk:
                continue
            q_pnls = [t["pnl"][pk_primary] for t in chunk]
            q_dates = f"{chunk[0]['close_time'][:10]} – {chunk[-1]['close_time'][:10]}"
            q_stats.append(compute_stats(q_pnls, f"Q{i+1} ({q_dates})"))
        lines.append(fmt_stats_table(q_stats))

    # ----- Section: Top/Bottom Series -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Top and Bottom Series")
    lines.append("")

    series_groups = defaultdict(list)
    for t in traded:
        series_groups[t["series"]].append(t["pnl"][pk_primary])

    series_ranked = sorted(
        [(s, pnls) for s, pnls in series_groups.items() if len(pnls) >= 3],
        key=lambda x: np.sum(x[1]), reverse=True)

    if series_ranked:
        lines.append("### Best (>= 3 trades, by total PnL)")
        lines.append("")
        rows = []
        for s, pnls in series_ranked[:10]:
            arr = np.array(pnls)
            rows.append((
                s, str(len(pnls)), f"{np.mean(arr > 0):.0%}",
                f"${np.mean(arr):+.3f}", f"${np.sum(arr):+.2f}"))
        lines.append(fmt_simple_table(
            ["Series", "N", "Win Rate", "Mean PnL", "Total PnL"], rows))

        lines.append("")
        lines.append("### Worst")
        lines.append("")
        rows = []
        for s, pnls in series_ranked[-10:]:
            arr = np.array(pnls)
            rows.append((
                s, str(len(pnls)), f"{np.mean(arr > 0):.0%}",
                f"${np.mean(arr):+.3f}", f"${np.sum(arr):+.2f}"))
        lines.append(fmt_simple_table(
            ["Series", "N", "Win Rate", "Mean PnL", "Total PnL"], rows))

    # ----- Section: Methodology -----
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Methodology Notes")
    lines.append("")
    lines.append(f"- **Grid filter**: edge >= {cfg_edge*100:.0f}c, "
                 f"base rate <= {cfg_br*100:.0f}%, "
                 f"min history >= {cfg_min_hist}, "
                 f"max YES price <= {cfg_max_yes*100:.0f}%")
    lines.append(f"- **Fees**: ${CONFIG['kalshi_fee_rt']:.2f} round-trip per contract")
    lines.append(f"- **Slippage**: ${CONFIG['slippage']:.2f} assumed")
    lines.append("- **Side**: Always NO")
    lines.append("- **Rolling base rate**: For each market, `mean(outcomes of all "
                 "prior settled markets in the canonical series)`. Market's own "
                 "outcome added to rolling state AFTER evaluation.")
    lines.append("- **LibFrog rates**: Used as-is for earnings word-level lookups "
                 "(external transcript data, not derived from this market dataset). "
                 "Requires n_calls >= 10.")
    lines.append("- **Series equivalences**: " +
                 ", ".join(f"{k} → {v}" for k, v in SERIES_EQUIVALENCES.items()))
    lines.append("- **Per-trade Sharpe**: mean(PnL) / std(PnL). NOT annualized "
                 "unless explicitly labeled.")
    lines.append("- **Bootstrap CI**: 10,000 resamples, seed=42")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Honest PM Mentions backtest")
    parser.add_argument("--save", action="store_true",
                        help="Save report to backtest_report.md")
    args = parser.parse_args()

    print("Loading data...")
    markets = load_markets()
    libfrog_rates = load_libfrog_rates()
    static_rates = load_static_rates()
    print(f"  {len(markets):,} markets, {len(libfrog_rates):,} LibFrog word rates")

    # Store config values for report
    global cfg_edge, cfg_br, cfg_min_hist, cfg_max_yes
    cfg_edge = CONFIG["grid_edge_min"]
    cfg_br = CONFIG["grid_br_max"]
    cfg_min_hist = CONFIG["min_history"]
    cfg_max_yes = CONFIG["max_yes_price"]

    print("\nRunning rolling backtest (honest)...")
    rolling_trades = run_rolling_backtest(markets, libfrog_rates, CONFIG)
    pk = "vwap_25pct_buffer"
    n_pass = sum(1 for t in rolling_trades if t["passed"].get(pk))
    print(f"  {n_pass} trades pass filter (VWAP 25% buffer)")

    print("Running original backtest (biased)...")
    original_trades = run_original_backtest(markets, static_rates, CONFIG)
    print(f"  {len(original_trades)} trades (opening_price + static rates)")

    print("\nGenerating report...")
    report = generate_report(rolling_trades, original_trades, markets)

    # Print summary to console
    fixed_pnls = [t["pnl"][pk] for t in rolling_trades if t["passed"].get(pk)]
    orig_pnls = [t["pnl"] for t in original_trades]

    print("\n" + "=" * 70)
    print("  ORIGINAL (opening_price + static rates)")
    print("=" * 70)
    s = compute_stats(orig_pnls, "original")
    print(f"  Trades: {s['n']}")
    print(f"  Win rate: {s['win_rate']:.1%}")
    print(f"  Mean PnL: ${s['mean_pnl']:+.4f}")
    print(f"  Per-trade Sharpe: {s['per_trade_sharpe']:.4f}")
    print(f"  Total PnL: ${s['total_pnl']:+.2f}")

    print("\n" + "=" * 70)
    print("  FIXED (VWAP 25% buffer + rolling rates)")
    print("=" * 70)
    s = compute_stats(fixed_pnls, "fixed")
    if s["n"] > 0:
        print(f"  Trades: {s['n']}")
        print(f"  Win rate: {s['win_rate']:.1%}")
        print(f"  Mean PnL: ${s['mean_pnl']:+.4f}")
        print(f"  Per-trade Sharpe: {s['per_trade_sharpe']:.4f}")
        print(f"  Total PnL: ${s['total_pnl']:+.2f}")
        print(f"  Max DD: ${s['max_drawdown']:.2f}")
        print(f"  95% CI: [${s['ci_lo']:+.4f}, ${s['ci_hi']:+.4f}]")
    else:
        print("  No trades passed filter.")

    if args.save:
        out_path = "backtest_report.md"
        with open(out_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to {out_path}")
    else:
        print("\nRun with --save to write backtest_report.md")


if __name__ == "__main__":
    main()
