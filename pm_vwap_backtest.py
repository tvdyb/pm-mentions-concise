#!/usr/bin/env python3
"""Honest VWAP backtest for PM Mentions strategy on Polymarket.

Uses real CLOB trade history (fetched by pm_trade_fetcher.py) to compute
VWAP entry prices, then applies rolling speaker base rates with the same
PM_CONFIG filters as pm_focused_strategy.py. No look-ahead bias.

This is the Polymarket equivalent of focused_backtest.py for Kalshi.

Usage:
    python pm_vwap_backtest.py              # run and print
    python pm_vwap_backtest.py --save       # writes pm_vwap_backtest_report.md
"""

import json
import argparse
import itertools
import numpy as np
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from backtest import compute_stats, fmt_stats_table, fmt_simple_table
from shared import compute_expected_pnl, compute_settlement_pnl
from pm_base_rates import _normalize_speaker
from pm_focused_strategy import PM_CONFIG
from pm_transcript_rates import (
    find_transcript_rate, load_transcript_rates, OUT_PATH as TRANSCRIPT_RATES_PATH,
)

DATA_PATH = Path("data/pm_markets_with_trades.json")
PK_PRIMARY = "vwap_25pct_buffer"
PRICE_KEYS = ["vwap_25pct_buffer", "vwap_10pct_buffer", "vwap_no_buffer"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_pm_trade_data(path=DATA_PATH) -> list[dict]:
    with open(path) as f:
        return json.load(f)["markets"]


# ---------------------------------------------------------------------------
# Core rolling backtest
# ---------------------------------------------------------------------------

def run_pm_vwap_backtest(
    markets: list[dict],
    cfg: dict,
    transcript_rates: dict | None = None,
    price_keys: list[str] | None = None,
) -> list[dict]:
    """Run honest VWAP backtest with rolling speaker base rates.

    For each resolved market (chronologically):
    1. Look up rolling speaker base rate from all prior markets (no look-ahead).
    2. Optionally look up transcript word-level rate (highest precision).
    3. Apply PM_CONFIG filters (edge threshold, max_yes, category exclusion).
    4. Compute PnL using real VWAP entry price.

    Returns list of trade dicts with passed/pnl/entry/edge per price_key.
    """
    if price_keys is None:
        price_keys = PRICE_KEYS

    edge_min_sp_high = cfg.get("edge_min_speaker_high_n", 0.04)
    edge_min_sp_low = cfg.get("edge_min_speaker_low_n", 0.06)
    edge_min_cat = cfg.get("edge_min_category", 0.10)
    edge_min_tx = cfg.get("edge_min_transcript", 0.04)
    sp_high_n = cfg.get("speaker_high_n_threshold", 100)
    br_max = cfg["br_max"]
    max_yes = cfg["max_yes_price"]
    min_yes = cfg.get("min_yes_price", 0.05)
    min_sp_n = cfg.get("min_speaker_n", 20)
    min_cat_n = cfg.get("min_category_n", 50)
    min_tx_events = cfg.get("min_transcript_events", 10)
    slip = cfg["slippage"]
    fee = cfg.get("fee", 0.0)
    exclude_cats = set(cfg.get("exclude_categories", []))

    # Sort by end_date (chronological order for rolling rates)
    sorted_markets = sorted(markets, key=lambda m: m.get("end_date", ""))

    # Rolling state: speaker -> list of outcomes (0 or 1)
    rolling_speaker = defaultdict(list)
    # Rolling state: category -> list of outcomes
    rolling_category = defaultdict(list)

    trades = []

    for m in sorted_markets:
        result = m.get("result")
        if result not in ("yes", "no"):
            continue

        speaker = _normalize_speaker(m.get("speaker", ""))
        category = m.get("category", "other")
        strike_word = m.get("strike_word", "")
        outcome = 1 if result == "yes" else 0

        # --- Category exclusion ---
        cat_excluded = category in exclude_cats

        # --- Determine base rate (no look-ahead) ---
        br = None
        n_hist = 0
        rate_source = None

        # Priority 1: Transcript word-level rate (static, not rolling)
        if transcript_rates and speaker and strike_word:
            tx_rate = find_transcript_rate(
                speaker, strike_word, transcript_rates,
                min_events=min_tx_events)
            if tx_rate is not None:
                br = tx_rate["base_rate"]
                n_hist = tx_rate["n_events"]
                rate_source = "transcript"

        # Priority 2: Rolling speaker rate
        if br is None:
            prior = rolling_speaker.get(speaker, [])
            if len(prior) >= min_sp_n:
                br = np.mean(prior)
                n_hist = len(prior)
                rate_source = "speaker"

        # Priority 3: Rolling category rate
        if br is None:
            cat_prior = rolling_category.get(category, [])
            if len(cat_prior) >= min_cat_n:
                br = np.mean(cat_prior)
                n_hist = len(cat_prior)
                rate_source = "category"

        # Update rolling state AFTER evaluation (no look-ahead)
        if speaker:
            rolling_speaker[speaker].append(outcome)
        rolling_category[category].append(outcome)

        if br is None:
            continue

        # --- Build trade row ---
        trade_row = {
            "condition_id": m.get("condition_id", ""),
            "speaker": speaker,
            "category": category,
            "strike_word": strike_word,
            "result": result,
            "rate_source": rate_source,
            "base_rate": br,
            "n_history": n_hist,
            "end_date": m.get("end_date", ""),
            "n_trades": m.get("n_trades", 0),
            "cat_excluded": cat_excluded,
            "passed": {},
            "pnl": {},
            "entry": {},
            "edge": {},
        }

        for pk in price_keys:
            price = m.get(pk)
            if price is None:
                trade_row["passed"][pk] = False
                continue

            if price < min_yes or price > 0.95:
                trade_row["passed"][pk] = False
                continue

            if cat_excluded:
                trade_row["passed"][pk] = False
                continue

            if price > max_yes:
                trade_row["passed"][pk] = False
                continue

            if br > br_max:
                trade_row["passed"][pk] = False
                continue

            edge = price - br
            if rate_source == "transcript":
                edge_min = edge_min_tx
            elif rate_source == "speaker":
                edge_min = edge_min_sp_high if n_hist >= sp_high_n else edge_min_sp_low
            else:
                edge_min = edge_min_cat
            if edge < edge_min:
                trade_row["passed"][pk] = False
                continue

            trade_row["passed"][pk] = True
            trade_row["entry"][pk] = price
            trade_row["edge"][pk] = edge
            trade_row["pnl"][pk] = compute_settlement_pnl(
                price, result, fee=fee, slippage=slip)

        trades.append(trade_row)

    return trades


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_pnls(trades, pk=PK_PRIMARY):
    return [t["pnl"][pk] for t in trades if t["passed"].get(pk)]


def bootstrap_sharpe(pnls, n_boot=10_000, seed=42):
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

def run_param_grid(markets, cfg, transcript_rates=None):
    """Sweep key parameters and return results."""
    max_yes_vals = [0.40, 0.50, 0.60, 0.75]
    edge_sp_high_vals = [0.02, 0.04, 0.06, 0.08]
    edge_sp_low_vals = [0.04, 0.06, 0.08, 0.10]
    edge_tx_vals = [0.02, 0.04, 0.06, 0.08]

    # Run with loosest params to get all possible trades
    loose = dict(cfg)
    loose["max_yes_price"] = max(max_yes_vals)
    loose["edge_min_speaker_high_n"] = min(edge_sp_high_vals)
    loose["edge_min_speaker_low_n"] = min(edge_sp_low_vals)
    loose["edge_min_transcript"] = min(edge_tx_vals)
    loose["edge_min_category"] = 0.04

    all_trades = run_pm_vwap_backtest(
        markets, loose, transcript_rates, price_keys=[PK_PRIMARY])

    results = []
    for my, esh, esl, etx in itertools.product(
            max_yes_vals, edge_sp_high_vals, edge_sp_low_vals, edge_tx_vals):
        pnls = []
        for t in all_trades:
            if not t["passed"].get(PK_PRIMARY):
                continue
            price = t["entry"][PK_PRIMARY]
            if price > my:
                continue
            edge = t["edge"][PK_PRIMARY]
            rs = t["rate_source"]
            if rs == "transcript":
                if edge < etx:
                    continue
            elif rs == "speaker":
                threshold = esh if t["n_history"] >= cfg.get("speaker_high_n_threshold", 100) else esl
                if edge < threshold:
                    continue
            else:
                if edge < 0.10:
                    continue
            pnls.append(t["pnl"][PK_PRIMARY])

        n = len(pnls)
        if n == 0:
            results.append({
                "max_yes": my, "edge_sp_high": esh, "edge_sp_low": esl,
                "edge_tx": etx, "n": 0, "win_rate": 0,
                "mean_pnl": 0, "sharpe": 0, "total_pnl": 0,
            })
            continue

        arr = np.array(pnls)
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        results.append({
            "max_yes": my, "edge_sp_high": esh, "edge_sp_low": esl,
            "edge_tx": etx, "n": n,
            "win_rate": float(np.mean(arr > 0)),
            "mean_pnl": float(np.mean(arr)),
            "sharpe": float(np.mean(arr) / std) if std > 0 else 0.0,
            "total_pnl": float(np.sum(arr)),
        })

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(trades, markets, param_results, cfg):
    lines = []
    pk = PK_PRIMARY

    pnls = extract_pnls(trades)
    stats = compute_stats(pnls, "PM VWAP Backtest")

    # Date range
    end_dates = sorted([m["end_date"] for m in markets if m.get("end_date")])
    n_with_trades = sum(1 for m in markets if m.get("n_trades", 0) > 0)
    n_with_vwap = sum(1 for m in markets if m.get("vwap_25pct_buffer") is not None)

    # ===== HEADER =====
    lines.append("# PM Mentions — Honest VWAP Backtest (Polymarket)")
    lines.append("")
    lines.append(f"*Generated {datetime.now():%Y-%m-%d %H:%M} from "
                 f"{len(markets):,} resolved markets "
                 f"({n_with_trades:,} with CLOB trades, "
                 f"{n_with_vwap:,} with VWAP), "
                 f"{end_dates[0][:10]} to {end_dates[-1][:10]}.*")
    lines.append("")
    lines.append("All results use **real VWAP 25% buffer** entry prices from "
                 "CLOB trade history and **rolling speaker base rates** "
                 "(no look-ahead). Polymarket has **zero fees**; "
                 "1c slippage assumed. Per-trade Sharpe = mean/std.")

    # ===== EXECUTIVE SUMMARY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append("PM-native strategy using speaker-level base rates (rolling) "
                 "and transcript word-level rates where available.")
    lines.append("")
    lines.append(fmt_stats_table([stats]))

    if stats["n"] > 0:
        sh_mean, sh_lo, sh_hi = bootstrap_sharpe(pnls)
        lines.append("")
        lines.append(f"*Bootstrapped per-trade Sharpe 95% CI: "
                     f"[{sh_lo:.4f}, {sh_hi:.4f}]*")

    # ===== ENTRY PRICE SENSITIVITY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Entry Price Sensitivity")
    lines.append("")

    pk_stats = []
    for pkn, label in [
        ("vwap_25pct_buffer", "VWAP 25% buffer (primary)"),
        ("vwap_10pct_buffer", "VWAP 10% buffer"),
        ("vwap_no_buffer", "VWAP no buffer"),
    ]:
        p = [t["pnl"][pkn] for t in trades if t["passed"].get(pkn)]
        pk_stats.append(compute_stats(p, label))
    lines.append(fmt_stats_table(pk_stats))

    # ===== WALK-FORWARD OOS =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Out-of-Sample Validation")
    lines.append("")

    traded = sorted(
        [t for t in trades if t["passed"].get(pk)],
        key=lambda t: t["end_date"])
    n_traded = len(traded)

    if n_traded >= 10:
        # 60/40 split
        lines.append("### 60/40 Walk-Forward Split")
        lines.append("")
        split_60 = int(n_traded * 0.60)
        is_pnls = [t["pnl"][pk] for t in traded[:split_60]]
        oos_pnls = [t["pnl"][pk] for t in traded[split_60:]]
        is_d = f"{traded[0]['end_date'][:10]} – {traded[split_60-1]['end_date'][:10]}"
        oos_d = f"{traded[split_60]['end_date'][:10]} – {traded[-1]['end_date'][:10]}"
        lines.append(fmt_stats_table([
            compute_stats(is_pnls, f"In-sample 60% ({is_d})"),
            compute_stats(oos_pnls, f"Out-of-sample 40% ({oos_d})"),
        ]))

        # Chronological thirds
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
            d = f"{chunk[0]['end_date'][:10]} – {chunk[-1]['end_date'][:10]}"
            t_stats.append(compute_stats(p, f"Third {i+1} ({d})"))
        lines.append(fmt_stats_table(t_stats))

    # ===== RATE SOURCE BREAKDOWN =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Rate Source Breakdown")
    lines.append("")

    source_groups = defaultdict(list)
    for t in trades:
        if t["passed"].get(pk):
            source_groups[t["rate_source"]].append(t["pnl"][pk])
    src_stats = [compute_stats(p, s) for s, p in
                 sorted(source_groups.items(), key=lambda x: -len(x[1]))]
    lines.append(fmt_stats_table(src_stats))

    for s, p in sorted(source_groups.items(), key=lambda x: -len(x[1])):
        pct = len(p) / n_traded * 100 if n_traded > 0 else 0
        lines.append(f"- {s}: {len(p)} trades ({pct:.1f}%)")

    # ===== CATEGORY BREAKDOWN =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Category Breakdown")
    lines.append("")

    cat_groups = defaultdict(list)
    for t in trades:
        if t["passed"].get(pk):
            cat_groups[t["category"]].append(t["pnl"][pk])
    cat_stats = [compute_stats(p, c) for c, p in
                 sorted(cat_groups.items(), key=lambda x: -len(x[1]))]
    lines.append(fmt_stats_table(cat_stats))

    # ===== SPEAKER BREAKDOWN =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Speaker Breakdown")
    lines.append("")

    sp_groups = defaultdict(list)
    for t in trades:
        if t["passed"].get(pk):
            sp_groups[t["speaker"]].append(t["pnl"][pk])

    sp_ranked = sorted(
        [(s, p) for s, p in sp_groups.items() if len(p) >= 5],
        key=lambda x: np.sum(x[1]), reverse=True)

    if sp_ranked:
        lines.append("### Best Speakers (>= 5 trades)")
        lines.append("")
        rows = []
        for s, p in sp_ranked[:15]:
            a = np.array(p)
            rows.append((s, str(len(p)), f"{np.mean(a>0):.0%}",
                         f"${np.mean(a):+.4f}", f"{np.sum(a):+.2f}"))
        lines.append(fmt_simple_table(
            ["Speaker", "N", "Win Rate", "Mean PnL", "Total PnL"], rows))

        lines.append("")
        lines.append("### Worst Speakers (>= 5 trades)")
        lines.append("")
        rows = []
        for s, p in sp_ranked[-10:]:
            a = np.array(p)
            rows.append((s, str(len(p)), f"{np.mean(a>0):.0%}",
                         f"${np.mean(a):+.4f}", f"{np.sum(a):+.2f}"))
        lines.append(fmt_simple_table(
            ["Speaker", "N", "Win Rate", "Mean PnL", "Total PnL"], rows))

    # ===== YES PRICE BUCKETS =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. YES Price Bucket Breakdown")
    lines.append("")

    buckets = {"5-15%": [], "15-25%": [], "25-40%": [], "40-60%": []}
    for t in trades:
        if not t["passed"].get(pk):
            continue
        p = t["entry"][pk]
        if p < 0.15:
            buckets["5-15%"].append(t["pnl"][pk])
        elif p < 0.25:
            buckets["15-25%"].append(t["pnl"][pk])
        elif p < 0.40:
            buckets["25-40%"].append(t["pnl"][pk])
        else:
            buckets["40-60%"].append(t["pnl"][pk])
    b_stats = [compute_stats(p, b) for b, p in sorted(buckets.items())]
    lines.append(fmt_stats_table(b_stats))

    # ===== EDGE DECAY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. Edge Decay (Chronological Splits)")
    lines.append("")

    if n_traded >= 8:
        half = n_traded // 2
        h1 = [t["pnl"][pk] for t in traded[:half]]
        h2 = [t["pnl"][pk] for t in traded[half:]]
        h1d = f"{traded[0]['end_date'][:10]} – {traded[half-1]['end_date'][:10]}"
        h2d = f"{traded[half]['end_date'][:10]} – {traded[-1]['end_date'][:10]}"

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
            qd = f"{chunk[0]['end_date'][:10]} – {chunk[-1]['end_date'][:10]}"
            q_stats.append(compute_stats(qp, f"Q{i+1} ({qd})"))
        lines.append(fmt_stats_table(q_stats))

    # ===== PARAM GRID =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9. Parameter Sensitivity Grid")
    lines.append("")
    lines.append("256 combos tested (4 values each for max_yes, edge_sp_high, "
                 "edge_sp_low, edge_transcript). Sorted by Sharpe.")
    lines.append("")

    valid = [r for r in param_results if r["n"] >= 20]
    valid.sort(key=lambda r: r["sharpe"], reverse=True)

    if valid:
        header = ["max_yes", "edge_hi", "edge_lo", "edge_tx", "N",
                  "Win Rate", "Mean PnL", "Sharpe", "Total PnL"]

        lines.append("### Top 20 by Sharpe (N >= 20)")
        lines.append("")
        rows = []
        for r in valid[:20]:
            rows.append((
                f"{r['max_yes']:.0%}", f"{r['edge_sp_high']:.0%}",
                f"{r['edge_sp_low']:.0%}", f"{r['edge_tx']:.0%}",
                str(r["n"]), f"{r['win_rate']:.1%}",
                f"${r['mean_pnl']:+.4f}", f"{r['sharpe']:.4f}",
                f"${r['total_pnl']:+.1f}",
            ))
        lines.append(fmt_simple_table(header, rows))

        sharpes = [r["sharpe"] for r in valid]
        positive = [r for r in valid if r["sharpe"] > 0]
        lines.append("")
        lines.append(f"*{len(valid)} combos with N >= 20. "
                     f"{len(positive)} ({len(positive)/len(valid)*100:.0f}%) "
                     f"positive Sharpe. "
                     f"Median: {np.median(sharpes):.4f}. "
                     f"Max: {max(sharpes):.4f}.*")

    # ===== KILL CRITERIA =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 10. Kill Criteria")
    lines.append("")
    lines.append("Stop trading if:")
    lines.append("")
    if stats["n"] > 0:
        lines.append(f"1. **Rolling 30-trade mean PnL < -$0.05** for two consecutive "
                     f"windows (backtest mean: ${stats['mean_pnl']:+.4f})")
        lines.append(f"2. **Drawdown exceeds ${stats['max_drawdown']*2:.0f}** "
                     f"(2x backtest max DD of ${stats['max_drawdown']:.1f})")
    else:
        lines.append("1. **Rolling 30-trade mean PnL < -$0.05** for two windows")
        lines.append("2. **Drawdown exceeds $30**")
    lines.append("3. **OOS Sharpe < 0** over any 60-day window with >= 20 trades")
    lines.append("4. **Market structure change**: Polymarket changes resolution "
                 "rules, fees, or stops listing mention markets")
    lines.append("5. **Transcript data staleness**: > 2 years old for political "
                 "speakers. Refresh by running pm_transcript_rates.py")

    # ===== PM vs KALSHI COMPARISON =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 11. PM vs Kalshi Comparison")
    lines.append("")
    lines.append("*Compare with focused_backtest_report.md for Kalshi results.*")
    lines.append("")
    lines.append("| Dimension | Polymarket | Kalshi |")
    lines.append("|---|---|---|")
    lines.append("| Fees | 0% | 2c round-trip |")
    lines.append("| Rate source | Speaker-level + transcript word-level | "
                 "Series-level + LibFrog word-level |")
    lines.append("| Political person | Profitable (core edge) | "
                 "Negative PnL (excluded) |")
    lines.append("| Earnings | Negative PnL (excluded) | "
                 "Profitable (core edge) |")
    if stats["n"] > 0:
        lines.append(f"| N trades (VWAP 25%) | {stats['n']} | "
                     f"740 (focused backtest) |")
        lines.append(f"| Win rate | {stats['win_rate']:.1%} | 81.6% |")
        lines.append(f"| Mean PnL | ${stats['mean_pnl']:+.4f} | +$0.1170 |")
        lines.append(f"| Sharpe | {stats['per_trade_sharpe']:.4f} | 0.3146 |")
    lines.append("")
    lines.append("**Key differences:**")
    lines.append("")
    lines.append("- PM has zero fees → lower edge thresholds are viable (4c vs 8-12c)")
    lines.append("- PM mention markets are predominantly political speakers → "
                 "speaker-level base rates work well")
    lines.append("- Transcript word-level rates provide per-word precision for "
                 "political speakers (equivalent to LibFrog for earnings)")
    lines.append("- PM data is larger (10K+ resolved markets vs 20K for Kalshi) "
                 "but concentrated in fewer speakers")

    # ===== METHODOLOGY =====
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 12. Methodology Notes")
    lines.append("")
    lines.append(f"- **Entry prices**: Real VWAP from CLOB trade history "
                 f"(25% buffer = exclude first/last 25% of trading time)")
    lines.append(f"- **Rolling base rate**: mean(outcomes) of all prior resolved "
                 f"markets for the same speaker. Updated AFTER evaluation.")
    lines.append(f"- **Transcript rates**: Static word-level rates from "
                 f"political speech transcripts (press conferences, debates). "
                 f"Not look-ahead since they predate PM markets.")
    lines.append(f"- **Fees**: $0 (Polymarket has no trading fees)")
    lines.append(f"- **Slippage**: ${cfg['slippage']:.2f} assumed")
    lines.append(f"- **Side**: Always NO")
    lines.append(f"- **Edge thresholds**: "
                 f"{cfg['edge_min_speaker_high_n']*100:.0f}c (speaker high-N), "
                 f"{cfg['edge_min_speaker_low_n']*100:.0f}c (speaker low-N), "
                 f"{cfg.get('edge_min_transcript', 0.04)*100:.0f}c (transcript), "
                 f"{cfg['edge_min_category']*100:.0f}c (category)")
    lines.append(f"- **Max YES price**: {cfg['max_yes_price']*100:.0f}%")
    lines.append(f"- **Excluded categories**: "
                 f"{', '.join(cfg['exclude_categories']) or 'none'}")
    lines.append(f"- **Min speaker history**: {cfg['min_speaker_n']} markets")
    lines.append(f"- **Bootstrap**: 10,000 resamples, seed=42")
    lines.append(f"- **Parameter grid**: 256 combos")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Honest VWAP backtest for PM Mentions strategy")
    parser.add_argument("--save", action="store_true",
                        help="Save report to pm_vwap_backtest_report.md")
    args = parser.parse_args()

    if not DATA_PATH.exists():
        print(f"No trade data at {DATA_PATH}")
        print("Run: python pm_trade_fetcher.py")
        return

    print("Loading PM trade data...")
    markets = load_pm_trade_data()
    has_trades = [m for m in markets if m.get("n_trades", 0) > 0]
    has_vwap = [m for m in markets if m.get("vwap_25pct_buffer") is not None]
    print(f"  {len(markets)} markets, {len(has_trades)} with trades, "
          f"{len(has_vwap)} with VWAP 25%")

    # Load transcript rates
    transcript_rates = None
    if TRANSCRIPT_RATES_PATH.exists():
        try:
            transcript_rates = load_transcript_rates()
            n_tx = len(transcript_rates.get("rates", {}))
            print(f"  {n_tx} transcript word-level rates loaded")
        except Exception as e:
            print(f"  Warning: failed to load transcript rates: {e}")

    cfg = dict(PM_CONFIG)

    # --- Run backtest ---
    print("\nRunning honest VWAP backtest...")
    trades = run_pm_vwap_backtest(markets, cfg, transcript_rates)
    n_passed = sum(1 for t in trades if t["passed"].get(PK_PRIMARY))
    print(f"  {n_passed} trades pass filter (VWAP 25%)")

    # Quick console summary
    pnls = extract_pnls(trades)
    stats = compute_stats(pnls, "PM VWAP")

    if stats["n"] > 0:
        print(f"\n  Trades: {stats['n']}")
        print(f"  Win rate: {stats['win_rate']:.1%}")
        print(f"  Mean PnL: ${stats['mean_pnl']:+.4f}")
        print(f"  Per-trade Sharpe: {stats['per_trade_sharpe']:.4f}")
        print(f"  Total PnL: ${stats['total_pnl']:+.2f}")
        print(f"  Max DD: ${stats['max_drawdown']:.2f}")
        print(f"  95% CI: [${stats['ci_lo']:+.4f}, ${stats['ci_hi']:+.4f}]")

        # Rate source breakdown
        by_src = defaultdict(list)
        for t in trades:
            if t["passed"].get(PK_PRIMARY):
                by_src[t["rate_source"]].append(t["pnl"][PK_PRIMARY])
        print("\n  By rate source:")
        for src, sp in sorted(by_src.items(), key=lambda x: -len(x[1])):
            a = np.array(sp)
            print(f"    {src}: N={len(sp)}, WR={np.mean(a>0):.0%}, "
                  f"Mean=${np.mean(a):+.4f}, Total=${np.sum(a):+.2f}")
    else:
        print("\n  No trades passed the filter.")

    # --- Parameter grid ---
    print("\nRunning parameter sensitivity grid (256 combos)...")
    param_results = run_param_grid(markets, cfg, transcript_rates)
    valid = [r for r in param_results if r["n"] >= 20]
    pos = [r for r in valid if r["sharpe"] > 0]
    print(f"  {len(valid)} combos with N >= 20, "
          f"{len(pos)} positive Sharpe" if valid else "  No valid combos")

    # --- Report ---
    print("\nGenerating report...")
    report = generate_report(trades, markets, param_results, cfg)

    if args.save:
        out_path = "pm_vwap_backtest_report.md"
        with open(out_path, "w") as f:
            f.write(report)
        print(f"Report saved to {out_path}")
    else:
        print("Run with --save to write pm_vwap_backtest_report.md")


if __name__ == "__main__":
    main()
