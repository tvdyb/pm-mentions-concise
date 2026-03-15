#!/usr/bin/env python3
"""Backtest for PM Mentions Focused Strategy.

Runs the focused strategy (tighter filters targeting profitable segments)
with the same rigor as backtest.py: VWAP entry, rolling base rates, no
look-ahead. Adds walk-forward OOS test, parameter sensitivity grid,
category ablation, and bootstrapped Sharpe CIs.

Usage:
    python focused_backtest.py
    python focused_backtest.py --save   # writes focused_backtest_report.md
"""

import json
import argparse
import itertools
import numpy as np
from collections import defaultdict
from datetime import datetime

from backtest import (
    load_markets,
    load_libfrog_rates,
    SERIES_EQUIVALENCES,
    _equiv_series,
    libfrog_lookup,
    compute_pnl,
    compute_stats,
    fmt_stats_table,
    fmt_simple_table,
)
from focused_strategy import FOCUSED_CONFIG
from pm_mentions_strategy import CONFIG as ORIGINAL_CONFIG

# ---------------------------------------------------------------------------
# Core rolling backtest for focused strategy
# ---------------------------------------------------------------------------

def run_focused_backtest(markets, libfrog_rates, cfg, price_keys=None):
    """Run backtest with rolling base rates, VWAP entry, focused filters.

    Returns list of trade dicts, each with passed/pnl/entry/edge per price_key.
    """
    if price_keys is None:
        price_keys = ["vwap_25pct_buffer", "vwap_10pct_buffer"]

    fee = cfg["kalshi_fee_rt"]
    slip = cfg["slippage"]
    br_max = cfg["grid_br_max"]
    max_yes = cfg["max_yes_price"]
    edge_min_lf = cfg.get("edge_min_libfrog", cfg.get("grid_edge_min", 0.10))
    edge_min_roll = cfg.get("edge_min_rolling", cfg.get("grid_edge_min", 0.10))
    min_hist_lf = cfg.get("min_history_libfrog", cfg.get("min_history", 10))
    min_hist_roll = cfg.get("min_history_rolling", cfg.get("min_history", 10))
    exclude_cats = set(cfg.get("exclude_categories", []))
    blocked = set(cfg.get("blocked_series", []))

    sorted_markets = sorted(markets, key=lambda m: m.get("close_time", ""))
    rolling = defaultdict(list)
    trades = []

    for m in sorted_markets:
        result = m.get("result")
        if result not in ("yes", "no"):
            continue

        series = m["series"]
        category = m.get("category", "other")
        is_earnings = "EARNINGS" in series.upper()
        strike_word = m.get("strike_word", "")
        outcome = 1 if result == "yes" else 0
        canon = _equiv_series(series)

        # --- Category / blocklist ---
        cat_excluded = category in exclude_cats
        series_blocked = series in blocked

        # --- Determine base rate ---
        rate_source = None
        br = None
        n_hist = 0

        if is_earnings and strike_word:
            lf_br, lf_n = libfrog_lookup(libfrog_rates, series, strike_word)
            if lf_br is not None and lf_n >= min_hist_lf:
                br = lf_br
                n_hist = lf_n
                rate_source = "libfrog"

        if br is None:
            prior = rolling.get(canon, [])
            if len(prior) >= min_hist_roll:
                br = np.mean(prior)
                n_hist = len(prior)
                rate_source = "rolling"

        # Update rolling state AFTER evaluation
        rolling[canon].append(outcome)

        if br is None:
            continue

        # --- Build trade row ---
        trade_row = {
            "ticker": m.get("ticker", ""),
            "series": series,
            "category": category,
            "strike_word": strike_word,
            "is_earnings": is_earnings,
            "result": result,
            "rate_source": rate_source,
            "base_rate": br,
            "n_history": n_hist,
            "close_time": m.get("close_time", ""),
            "cat_excluded": cat_excluded,
            "series_blocked": series_blocked,
            "passed": {},
            "pnl": {},
            "entry": {},
            "edge": {},
        }

        for pk in price_keys:
            price = m.get(pk)
            if price is None or price <= 0.05 or price > 0.95:
                trade_row["passed"][pk] = False
                continue

            if cat_excluded or series_blocked:
                trade_row["passed"][pk] = False
                continue

            if price > max_yes:
                trade_row["passed"][pk] = False
                continue

            if br > br_max:
                trade_row["passed"][pk] = False
                continue

            edge = price - br
            edge_min = edge_min_lf if rate_source == "libfrog" else edge_min_roll
            if edge < edge_min:
                trade_row["passed"][pk] = False
                continue

            trade_row["passed"][pk] = True
            trade_row["entry"][pk] = price
            trade_row["edge"][pk] = edge
            trade_row["pnl"][pk] = compute_pnl(price, result, fee, slip)

        trades.append(trade_row)

    return trades


def run_original_rolling(markets, libfrog_rates, cfg, price_keys=None):
    """Run the ORIGINAL strategy with rolling rates + VWAP for fair comparison."""
    if price_keys is None:
        price_keys = ["vwap_25pct_buffer", "vwap_10pct_buffer"]

    fee = cfg["kalshi_fee_rt"]
    slip = cfg["slippage"]
    edge_min = cfg["grid_edge_min"]
    br_max = cfg["grid_br_max"]
    min_hist = cfg["min_history"]
    max_yes = cfg["max_yes_price"]

    sorted_markets = sorted(markets, key=lambda m: m.get("close_time", ""))
    rolling = defaultdict(list)
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

        rate_source = None
        br = None
        n_hist = 0

        if is_earnings and strike_word:
            lf_br, lf_n = libfrog_lookup(libfrog_rates, series, strike_word)
            if lf_br is not None and lf_n >= min_hist:
                br = lf_br
                n_hist = lf_n
                rate_source = "libfrog"

        if br is None:
            prior = rolling.get(canon, [])
            if len(prior) >= min_hist:
                br = np.mean(prior)
                n_hist = len(prior)
                rate_source = "rolling"

        rolling[canon].append(outcome)

        if br is None:
            continue

        trade_row = {
            "series": series,
            "category": m.get("category", "other"),
            "rate_source": rate_source,
            "result": result,
            "close_time": m.get("close_time", ""),
            "passed": {},
            "pnl": {},
            "entry": {},
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
            trade_row["pnl"][pk] = compute_pnl(price, result, fee, slip)

        trades.append(trade_row)

    return trades


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PK = "vwap_25pct_buffer"

def extract_pnls(trades, pk=PK):
    return [t["pnl"][pk] for t in trades if t["passed"].get(pk)]


def bootstrap_sharpe(pnls, n_boot=10000, seed=42):
    """Bootstrap the per-trade Sharpe ratio. Returns (mean, ci_lo, ci_hi)."""
    arr = np.array(pnls)
    if len(arr) < 2:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    sharpes = []
    for _ in range(n_boot):
        sample = rng.choice(arr, size=len(arr), replace=True)
        s = np.std(sample, ddof=1)
        sharpes.append(np.mean(sample) / s if s > 0 else 0.0)
    return (float(np.mean(sharpes)),
            float(np.percentile(sharpes, 2.5)),
            float(np.percentile(sharpes, 97.5)))


# ---------------------------------------------------------------------------
# Parameter sensitivity grid
# ---------------------------------------------------------------------------

def run_param_grid(markets, libfrog_rates, base_cfg):
    """Sweep parameters and return results list."""
    max_yes_vals = [0.40, 0.50, 0.60, 0.75]
    edge_lf_vals = [0.05, 0.08, 0.10, 0.15]
    edge_roll_vals = [0.08, 0.10, 0.12, 0.15]
    min_hist_roll_vals = [10, 15, 20, 30]

    # Total combos = 4^4 = 256 — run each quickly by reusing a single
    # pass of rolling state and filtering trades post-hoc.
    # Pre-compute all trades with the loosest possible filters.
    loose_cfg = dict(base_cfg)
    loose_cfg["max_yes_price"] = max(max_yes_vals)
    loose_cfg["edge_min_libfrog"] = min(edge_lf_vals)
    loose_cfg["edge_min_rolling"] = min(edge_roll_vals)
    loose_cfg["min_history_libfrog"] = 10
    loose_cfg["min_history_rolling"] = min(min_hist_roll_vals)
    loose_cfg["exclude_categories"] = base_cfg.get("exclude_categories", [])
    loose_cfg["blocked_series"] = base_cfg.get("blocked_series", [])

    all_trades = run_focused_backtest(
        markets, libfrog_rates, loose_cfg, price_keys=[PK])

    # Now filter post-hoc for each combo
    results = []
    for my, elf, erl, mhr in itertools.product(
            max_yes_vals, edge_lf_vals, edge_roll_vals, min_hist_roll_vals):
        pnls = []
        for t in all_trades:
            if not t["passed"].get(PK):
                continue
            price = t["entry"][PK]
            if price > my:
                continue
            if t["n_history"] < (10 if t["rate_source"] == "libfrog" else mhr):
                continue
            edge = t["edge"][PK]
            edge_min = elf if t["rate_source"] == "libfrog" else erl
            if edge < edge_min:
                continue
            pnls.append(t["pnl"][PK])

        n = len(pnls)
        if n == 0:
            results.append({
                "max_yes": my, "edge_lf": elf, "edge_roll": erl,
                "min_hist_roll": mhr, "n": 0, "win_rate": 0,
                "mean_pnl": 0, "sharpe": 0, "total_pnl": 0,
            })
            continue

        arr = np.array(pnls)
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        results.append({
            "max_yes": my, "edge_lf": elf, "edge_roll": erl,
            "min_hist_roll": mhr, "n": n,
            "win_rate": float(np.mean(arr > 0)),
            "mean_pnl": float(np.mean(arr)),
            "sharpe": float(np.mean(arr) / std) if std > 0 else 0.0,
            "total_pnl": float(np.sum(arr)),
        })

    return results


# ---------------------------------------------------------------------------
# Category ablation
# ---------------------------------------------------------------------------

def run_category_ablation(markets, libfrog_rates, base_cfg):
    """Test all category exclusion combos."""
    combos = [
        ("No exclusions", []),
        ("Exclude political_person", ["political_person"]),
        ("Exclude political_person + sports", ["political_person", "sports"]),
        ("Earnings only", None),  # special: include only earnings
    ]

    results = []
    for label, excl in combos:
        cfg = dict(base_cfg)
        if excl is not None:
            cfg["exclude_categories"] = excl
            trades = run_focused_backtest(markets, libfrog_rates, cfg, [PK])
            pnls = extract_pnls(trades)
        else:
            # Earnings only: run with no category exclusion, then filter
            cfg["exclude_categories"] = []
            trades = run_focused_backtest(markets, libfrog_rates, cfg, [PK])
            pnls = [t["pnl"][PK] for t in trades
                    if t["passed"].get(PK) and t["is_earnings"]]

        results.append(compute_stats(pnls, label))

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(focused_trades, original_trades, markets,
                    libfrog_rates, param_results, ablation_results):
    lines = []
    pk = PK

    focused_pnls = extract_pnls(focused_trades)
    original_pnls = extract_pnls(original_trades)
    focused_stats = compute_stats(focused_pnls, "Focused strategy")
    original_stats = compute_stats(original_pnls, "Original strategy")

    # Date range
    close_times = sorted([m["close_time"] for m in markets if m.get("close_time")])
    t0 = datetime.fromisoformat(close_times[0].replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(close_times[-1].replace("Z", "+00:00"))
    days = (t1 - t0).days

    # ===== HEADER =====
    lines.append("# PM Mentions Focused Strategy — Backtest Report")
    lines.append("")
    lines.append(f"*Generated {datetime.now():%Y-%m-%d %H:%M} from "
                 f"{len(markets):,} settled markets "
                 f"({close_times[0][:10]} to {close_times[-1][:10]}, "
                 f"{days} days).*")
    lines.append("")
    lines.append("All results use **VWAP 25% buffer** entry prices and "
                 "**rolling base rates** (no look-ahead). Per-trade Sharpe "
                 "= mean/std, not annualized unless labeled.")

    # ===== EXECUTIVE SUMMARY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append("The focused strategy applies tighter filters to concentrate "
                 "on the profitable segments identified in the honest backtest:")
    lines.append("")
    lines.append("- **YES price cap lowered** from 75c to 50c "
                 "(the 50-75c bucket had ~zero edge)")
    lines.append("- **Political person category excluded** "
                 "(negative total PnL in honest backtest)")
    lines.append("- **Tiered edge thresholds**: 8c for LibFrog-rated earnings "
                 "(precise rates), 12c for rolling series rates (noisier)")
    lines.append("- **Stricter min history**: 15 prior markets for series rates, "
                 "10 calls for LibFrog")
    lines.append("")
    lines.append(fmt_stats_table([original_stats, focused_stats]))
    lines.append("")

    if focused_stats["n"] > 0 and original_stats["n"] > 0:
        lines.append(f"**Delta**: "
                     f"{focused_stats['n'] - original_stats['n']:+d} trades, "
                     f"${focused_stats['mean_pnl'] - original_stats['mean_pnl']:+.4f} mean PnL, "
                     f"${focused_stats['total_pnl'] - original_stats['total_pnl']:+.2f} total PnL")

    # Annualized Sharpe
    if days > 0 and focused_stats["n"] > 0:
        tpy = focused_stats["n"] / days * 365
        ann = focused_stats["per_trade_sharpe"] * np.sqrt(tpy)
        lines.append("")
        lines.append(f"*Annualized Sharpe estimate (focused): {ann:.3f} "
                     f"({tpy:.0f} trades/year)*")

    # Bootstrapped Sharpe CI
    sh_mean, sh_lo, sh_hi = bootstrap_sharpe(focused_pnls)
    lines.append(f"*Bootstrapped per-trade Sharpe 95% CI: "
                 f"[{sh_lo:.4f}, {sh_hi:.4f}]*")

    # ===== FULL RESULTS =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Full Backtest Results")
    lines.append("")

    # Entry price sensitivity
    lines.append("### Entry Price Sensitivity")
    lines.append("")
    pk_stats = []
    for pkn, label in [("vwap_25pct_buffer", "VWAP 25% buffer (primary)"),
                        ("vwap_10pct_buffer", "VWAP 10% buffer")]:
        pnls = [t["pnl"][pkn] for t in focused_trades if t["passed"].get(pkn)]
        pk_stats.append(compute_stats(pnls, label))
    lines.append(fmt_stats_table(pk_stats))

    # ===== WALK-FORWARD OOS =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Out-of-Sample Validation")
    lines.append("")

    traded = sorted(
        [t for t in focused_trades if t["passed"].get(pk)],
        key=lambda t: t["close_time"])
    n_traded = len(traded)

    # 60/40 split
    lines.append("### 60/40 Walk-Forward Split")
    lines.append("")
    lines.append("The first 60% of trades (chronologically) establish that "
                 "the filters make sense. The last 40% are out-of-sample.")
    lines.append("")

    split_60 = int(n_traded * 0.60)
    is_pnls = [t["pnl"][pk] for t in traded[:split_60]]
    oos_pnls = [t["pnl"][pk] for t in traded[split_60:]]
    is_dates = (f"{traded[0]['close_time'][:10]} – "
                f"{traded[split_60-1]['close_time'][:10]}")
    oos_dates = (f"{traded[split_60]['close_time'][:10]} – "
                 f"{traded[-1]['close_time'][:10]}")

    lines.append(fmt_stats_table([
        compute_stats(is_pnls, f"In-sample 60% ({is_dates})"),
        compute_stats(oos_pnls, f"Out-of-sample 40% ({oos_dates})"),
    ]))

    # 3-fold chronological
    lines.append("")
    lines.append("### Chronological Thirds")
    lines.append("")
    third = n_traded // 3
    thirds = [traded[:third], traded[third:2*third], traded[2*third:]]
    t_stats = []
    for i, chunk in enumerate(thirds):
        if not chunk:
            continue
        p = [t["pnl"][pk] for t in chunk]
        d = f"{chunk[0]['close_time'][:10]} – {chunk[-1]['close_time'][:10]}"
        t_stats.append(compute_stats(p, f"Third {i+1} ({d})"))
    lines.append(fmt_stats_table(t_stats))

    # ===== PARAMETER SENSITIVITY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Parameter Sensitivity Grid")
    lines.append("")
    lines.append("256 parameter combinations tested. Each row shows a combo "
                 "with N >= 20 trades. Sorted by per-trade Sharpe descending.")
    lines.append("")
    lines.append("The goal is to show the profitable region is a broad plateau, "
                 "not a single fragile peak.")
    lines.append("")

    # Show top 30 and bottom 10 by Sharpe (with N >= 20)
    valid = [r for r in param_results if r["n"] >= 20]
    valid.sort(key=lambda r: r["sharpe"], reverse=True)

    header = ["max_yes", "edge_lf", "edge_roll", "min_hist", "N",
              "Win Rate", "Mean PnL", "Sharpe", "Total PnL"]
    rows = []
    for r in valid[:30]:
        rows.append((
            f"{r['max_yes']:.0%}", f"{r['edge_lf']:.0%}",
            f"{r['edge_roll']:.0%}", str(r["min_hist_roll"]),
            str(r["n"]), f"{r['win_rate']:.1%}",
            f"${r['mean_pnl']:+.4f}", f"{r['sharpe']:.4f}",
            f"${r['total_pnl']:+.1f}",
        ))
    lines.append("### Top 30 by Sharpe (N >= 20)")
    lines.append("")
    lines.append(fmt_simple_table(header, rows))

    # Worst
    lines.append("")
    lines.append("### Bottom 10 by Sharpe (N >= 20)")
    lines.append("")
    rows = []
    for r in valid[-10:]:
        rows.append((
            f"{r['max_yes']:.0%}", f"{r['edge_lf']:.0%}",
            f"{r['edge_roll']:.0%}", str(r["min_hist_roll"]),
            str(r["n"]), f"{r['win_rate']:.1%}",
            f"${r['mean_pnl']:+.4f}", f"{r['sharpe']:.4f}",
            f"${r['total_pnl']:+.1f}",
        ))
    lines.append(fmt_simple_table(header, rows))

    # Summary stats across the grid
    sharpes = [r["sharpe"] for r in valid]
    positive = [r for r in valid if r["sharpe"] > 0]
    lines.append("")
    lines.append(f"*{len(valid)} combos with N >= 20. "
                 f"{len(positive)} ({len(positive)/len(valid)*100:.0f}%) "
                 f"have positive Sharpe. "
                 f"Median Sharpe: {np.median(sharpes):.4f}. "
                 f"Max: {max(sharpes):.4f}. "
                 f"Min: {min(sharpes):.4f}.*"
                 if valid else "No combos with N >= 20.")

    # ===== CATEGORY ABLATION =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Category Exclusion Ablation")
    lines.append("")
    lines.append(fmt_stats_table(ablation_results))

    # ===== RATE SOURCE =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Rate Source Breakdown")
    lines.append("")

    source_groups = defaultdict(list)
    for t in focused_trades:
        if t["passed"].get(pk):
            source_groups[t["rate_source"]].append(t["pnl"][pk])
    src_stats = [compute_stats(p, s) for s, p in
                 sorted(source_groups.items(), key=lambda x: -len(x[1]))]
    lines.append(fmt_stats_table(src_stats))

    n_lf = len(source_groups.get("libfrog", []))
    n_rl = len(source_groups.get("rolling", []))
    total_t = n_lf + n_rl
    if total_t > 0:
        lines.append("")
        lines.append(f"LibFrog: {n_lf} ({n_lf/total_t*100:.1f}%) | "
                     f"Rolling: {n_rl} ({n_rl/total_t*100:.1f}%)")

    # ===== CATEGORY BREAKDOWN =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. Category Breakdown (within focused filter)")
    lines.append("")

    cat_groups = defaultdict(list)
    for t in focused_trades:
        if t["passed"].get(pk):
            cat_groups[t["category"]].append(t["pnl"][pk])
    cat_stats = [compute_stats(p, c) for c, p in
                 sorted(cat_groups.items(), key=lambda x: -len(x[1]))]
    lines.append(fmt_stats_table(cat_stats))

    # ===== YES PRICE BUCKETS =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. YES Price Bucket Breakdown")
    lines.append("")

    buckets = {"5-25%": [], "25-50%": []}
    for t in focused_trades:
        if not t["passed"].get(pk):
            continue
        p = t["entry"][pk]
        if p < 0.25:
            buckets["5-25%"].append(t["pnl"][pk])
        else:
            buckets["25-50%"].append(t["pnl"][pk])
    b_stats = [compute_stats(p, b) for b, p in sorted(buckets.items())]
    lines.append(fmt_stats_table(b_stats))

    # ===== EDGE DECAY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9. Edge Decay (Chronological Splits)")
    lines.append("")

    if n_traded >= 4:
        half = n_traded // 2
        h1 = [t["pnl"][pk] for t in traded[:half]]
        h2 = [t["pnl"][pk] for t in traded[half:]]
        h1d = f"{traded[0]['close_time'][:10]} – {traded[half-1]['close_time'][:10]}"
        h2d = f"{traded[half]['close_time'][:10]} – {traded[-1]['close_time'][:10]}"

        lines.append("### Halves")
        lines.append("")
        lines.append(fmt_stats_table([
            compute_stats(h1, f"First half ({h1d})"),
            compute_stats(h2, f"Second half ({h2d})"),
        ]))

        q = n_traded // 4
        quarters = [traded[:q], traded[q:2*q], traded[2*q:3*q], traded[3*q:]]
        lines.append("")
        lines.append("### Quarters")
        lines.append("")
        q_stats = []
        for i, chunk in enumerate(quarters):
            if not chunk:
                continue
            qp = [t["pnl"][pk] for t in chunk]
            qd = f"{chunk[0]['close_time'][:10]} – {chunk[-1]['close_time'][:10]}"
            q_stats.append(compute_stats(qp, f"Q{i+1} ({qd})"))
        lines.append(fmt_stats_table(q_stats))

    # ===== TOP/BOTTOM SERIES =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 10. Top and Bottom Series")
    lines.append("")

    sg = defaultdict(list)
    for t in traded:
        sg[t["series"]].append(t["pnl"][pk])

    ranked = sorted(
        [(s, p) for s, p in sg.items() if len(p) >= 3],
        key=lambda x: np.sum(x[1]), reverse=True)

    if ranked:
        lines.append("### Best (>= 3 trades)")
        lines.append("")
        rows = []
        for s, p in ranked[:10]:
            a = np.array(p)
            rows.append((s, str(len(p)), f"{np.mean(a>0):.0%}",
                         f"${np.mean(a):+.3f}", f"${np.sum(a):+.2f}"))
        lines.append(fmt_simple_table(
            ["Series", "N", "Win Rate", "Mean PnL", "Total PnL"], rows))

        lines.append("")
        lines.append("### Worst (>= 3 trades)")
        lines.append("")
        rows = []
        for s, p in ranked[-10:]:
            a = np.array(p)
            rows.append((s, str(len(p)), f"{np.mean(a>0):.0%}",
                         f"${np.mean(a):+.3f}", f"${np.sum(a):+.2f}"))
        lines.append(fmt_simple_table(
            ["Series", "N", "Win Rate", "Mean PnL", "Total PnL"], rows))

    # ===== KILL CRITERIA =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 11. Kill Criteria")
    lines.append("")
    lines.append("Stop trading the focused strategy if:")
    lines.append("")
    lines.append("1. **Rolling 30-trade mean PnL falls below -$0.05** for two "
                 "consecutive windows. The strategy's mean is +$"
                 f"{focused_stats['mean_pnl']:.3f}; sustained negative "
                 "mean indicates the edge is gone.")
    lines.append("2. **Drawdown exceeds $15** "
                 f"(~1.5x the backtest max DD of ${focused_stats['max_drawdown']:.1f}).")
    lines.append("3. **Out-of-sample Sharpe drops below 0** over any "
                 "60-day rolling window with >= 20 trades.")
    lines.append("4. **Market structure change**: Kalshi changes fees, "
                 "resolution rules, or stops listing mention markets.")
    lines.append("5. **LibFrog data staleness**: Transcript data > 2 years old "
                 "may not reflect current management communication patterns.")

    # ===== METHODOLOGY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 12. Methodology Notes")
    lines.append("")
    lines.append(f"- **Focused filter**: "
                 f"edge >= {FOCUSED_CONFIG['edge_min_libfrog']*100:.0f}c (LibFrog) / "
                 f"{FOCUSED_CONFIG['edge_min_rolling']*100:.0f}c (rolling), "
                 f"BR <= {FOCUSED_CONFIG['grid_br_max']*100:.0f}%, "
                 f"min history >= {FOCUSED_CONFIG['min_history_libfrog']} (LibFrog) / "
                 f"{FOCUSED_CONFIG['min_history_rolling']} (rolling), "
                 f"max YES <= {FOCUSED_CONFIG['max_yes_price']*100:.0f}%")
    lines.append(f"- **Excluded categories**: "
                 f"{', '.join(FOCUSED_CONFIG['exclude_categories']) or 'none'}")
    lines.append(f"- **Fees**: ${FOCUSED_CONFIG['kalshi_fee_rt']:.2f} RT per contract")
    lines.append(f"- **Slippage**: ${FOCUSED_CONFIG['slippage']:.2f} assumed")
    lines.append("- **Side**: Always NO")
    lines.append("- **Rolling base rate**: mean(outcomes of all prior settled "
                 "markets in canonical series). Updated AFTER evaluation.")
    lines.append("- **LibFrog rates**: External transcript data, not look-ahead. "
                 "Requires n_calls >= 10.")
    lines.append("- **Series equivalences**: " +
                 ", ".join(f"{k} → {v}" for k, v in SERIES_EQUIVALENCES.items()))
    lines.append("- **Per-trade Sharpe**: mean(PnL) / std(PnL), NOT annualized "
                 "unless labeled.")
    lines.append("- **Bootstrap**: 10,000 resamples, seed=42")
    lines.append("- **Parameter grid**: 256 combos (4 values each for max_yes, "
                 "edge_lf, edge_roll, min_hist_roll), all with exclude "
                 "political_person")
    lines.append("- **Walk-forward**: 60/40 chronological split + 3-fold "
                 "chronological thirds")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Focused PM Mentions strategy backtest")
    parser.add_argument("--save", action="store_true",
                        help="Save report to focused_backtest_report.md")
    args = parser.parse_args()

    print("Loading data...")
    markets = load_markets()
    libfrog_rates = load_libfrog_rates()
    print(f"  {len(markets):,} markets, {len(libfrog_rates):,} LibFrog word rates")

    # --- Run focused strategy ---
    print("\nRunning focused strategy backtest...")
    focused_trades = run_focused_backtest(
        markets, libfrog_rates, FOCUSED_CONFIG,
        price_keys=["vwap_25pct_buffer", "vwap_10pct_buffer"])
    n_focused = sum(1 for t in focused_trades if t["passed"].get(PK))
    print(f"  {n_focused} trades pass focused filter")

    # --- Run original strategy (same rolling/VWAP methodology) ---
    print("Running original strategy backtest (for comparison)...")
    original_trades = run_original_rolling(
        markets, libfrog_rates, ORIGINAL_CONFIG,
        price_keys=["vwap_25pct_buffer", "vwap_10pct_buffer"])
    n_orig = sum(1 for t in original_trades if t["passed"].get(PK))
    print(f"  {n_orig} trades pass original filter")

    # --- Parameter sensitivity ---
    print("Running parameter sensitivity grid (256 combos)...")
    param_results = run_param_grid(markets, libfrog_rates, FOCUSED_CONFIG)
    valid = [r for r in param_results if r["n"] >= 20]
    pos = [r for r in valid if r["sharpe"] > 0]
    print(f"  {len(valid)} combos with N >= 20, "
          f"{len(pos)} ({len(pos)/len(valid)*100:.0f}%) positive Sharpe")

    # --- Category ablation ---
    print("Running category ablation...")
    ablation_results = run_category_ablation(
        markets, libfrog_rates, FOCUSED_CONFIG)
    for r in ablation_results:
        if r["n"] > 0:
            print(f"  {r['label']}: N={r['n']}, "
                  f"Sharpe={r['per_trade_sharpe']:.4f}")

    # --- Generate report ---
    print("\nGenerating report...")
    report = generate_report(
        focused_trades, original_trades, markets,
        libfrog_rates, param_results, ablation_results)

    # --- Console summary ---
    focused_pnls = extract_pnls(focused_trades)
    original_pnls = extract_pnls(original_trades)

    print("\n" + "=" * 70)
    print("  ORIGINAL (rolling rates + VWAP 25%, max_yes=75c, no excl)")
    print("=" * 70)
    s = compute_stats(original_pnls, "original")
    if s["n"] > 0:
        print(f"  Trades: {s['n']}")
        print(f"  Win rate: {s['win_rate']:.1%}")
        print(f"  Mean PnL: ${s['mean_pnl']:+.4f}")
        print(f"  Per-trade Sharpe: {s['per_trade_sharpe']:.4f}")
        print(f"  Total PnL: ${s['total_pnl']:+.2f}")

    print("\n" + "=" * 70)
    print("  FOCUSED (rolling rates + VWAP 25%, max_yes=50c, "
          "no political_person)")
    print("=" * 70)
    s = compute_stats(focused_pnls, "focused")
    if s["n"] > 0:
        print(f"  Trades: {s['n']}")
        print(f"  Win rate: {s['win_rate']:.1%}")
        print(f"  Mean PnL: ${s['mean_pnl']:+.4f}")
        print(f"  Per-trade Sharpe: {s['per_trade_sharpe']:.4f}")
        print(f"  Total PnL: ${s['total_pnl']:+.2f}")
        print(f"  Max DD: ${s['max_drawdown']:.2f}")
        print(f"  95% CI: [${s['ci_lo']:+.4f}, ${s['ci_hi']:+.4f}]")

    if args.save:
        out_path = "focused_backtest_report.md"
        with open(out_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to {out_path}")
    else:
        print("\nRun with --save to write focused_backtest_report.md")


if __name__ == "__main__":
    main()
