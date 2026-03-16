#!/usr/bin/env python3
"""Backtest for PM Mentions strategy using Polymarket historical data.

Since CLOB price history is unavailable for old resolved markets, this
backtest uses an event-level simulation approach:

1. For each resolved event, compute rolling speaker base rates from
   all prior events (no look-ahead).
2. Simulate the strategy: for each market in the event, if the speaker
   base rate would have generated a NO signal (YES price unknown, so we
   test at multiple assumed-price thresholds), compute PnL.
3. Also runs a "per-event portfolio" analysis: if we bought NO on every
   word in an event, what was the hit rate vs the speaker base rate?

This validates that speaker-level base rates are predictive on PM data,
even without exact entry prices.

Usage:
    python pm_backtest.py
    python pm_backtest.py --save   # writes pm_backtest_report.md
"""

import json
import argparse
import numpy as np
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from pm_base_rates import _normalize_speaker

DATA_PATH = Path("data/pm_resolved_markets.json")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_pm_markets(path=DATA_PATH):
    with open(path) as f:
        return json.load(f)["markets"]


# ---------------------------------------------------------------------------
# Event-level analysis
# ---------------------------------------------------------------------------

def build_event_groups(markets):
    """Group resolved markets by event, sorted by end_date."""
    events = {}
    for m in markets:
        if m.get("result") not in ("yes", "no"):
            continue
        eid = m["event_id"]
        if eid not in events:
            events[eid] = {
                "event_id": eid,
                "title": m["event_title"],
                "speaker": _normalize_speaker(m.get("speaker", "")),
                "category": m.get("category", "other"),
                "end_date": m.get("end_date", ""),
                "markets": [],
            }
        events[eid]["markets"].append(m)

    # Sort events by end_date
    return sorted(events.values(), key=lambda e: e["end_date"])


# ---------------------------------------------------------------------------
# Rolling speaker base rate backtest
# ---------------------------------------------------------------------------

def run_rolling_backtest(events):
    """Test whether rolling speaker base rates predict per-event YES rates.

    For each event (chronologically):
    1. Look up rolling speaker base rate from all prior events
    2. Compare to actual YES rate in this event
    3. If actual_rate < speaker_rate, buying NO on the event would have
       been profitable (the speaker said fewer words than expected)

    Returns list of event-level results.
    """
    # Rolling state: speaker -> list of per-event YES rates
    rolling_rates = defaultdict(list)
    # Also track per-market outcomes for more granular rolling
    rolling_outcomes = defaultdict(list)

    results = []
    for ev in events:
        speaker = ev["speaker"]
        mkts = ev["markets"]
        n_markets = len(mkts)

        if n_markets < 3:
            # Update rolling state even for small events
            for m in mkts:
                rolling_outcomes[speaker].append(1 if m["result"] == "yes" else 0)
            continue

        n_yes = sum(1 for m in mkts if m["result"] == "yes")
        actual_rate = n_yes / n_markets

        # Rolling speaker rate from prior data
        prior = rolling_outcomes.get(speaker, [])
        if len(prior) < 20:
            # Not enough history — still update and skip
            for m in mkts:
                rolling_outcomes[speaker].append(1 if m["result"] == "yes" else 0)
            continue

        predicted_rate = np.mean(prior)

        # Simulate PnL at different assumed entry prices
        # If we bought NO on markets priced at YES=predicted_rate+edge_threshold:
        # The "event portfolio" buys NO on ALL words, so we're effectively
        # betting the speaker says fewer words than the market expects.

        # Simple PnL model: if we bought NO on all N markets at the
        # speaker base rate, our per-contract cost is (1 - predicted_rate),
        # and we win on (1 - actual_rate) fraction of them.
        no_cost = 1.0 - predicted_rate
        win_frac = 1.0 - actual_rate  # fraction of NOs that win
        lose_frac = actual_rate

        # Per-contract expected PnL (average across the event)
        # Win: gain predicted_rate, Lose: lose no_cost
        avg_pnl = win_frac * predicted_rate - lose_frac * no_cost

        results.append({
            "event_id": ev["event_id"],
            "title": ev["title"],
            "speaker": speaker,
            "category": ev["category"],
            "end_date": ev["end_date"],
            "n_markets": n_markets,
            "n_yes": n_yes,
            "actual_rate": actual_rate,
            "predicted_rate": predicted_rate,
            "n_prior": len(prior),
            "prediction_error": actual_rate - predicted_rate,
            "avg_pnl": avg_pnl,
            "profitable": avg_pnl > 0,
        })

        # Update rolling state AFTER evaluation
        for m in mkts:
            rolling_outcomes[speaker].append(1 if m["result"] == "yes" else 0)

    return results


# ---------------------------------------------------------------------------
# Per-market simulation with price thresholds
# ---------------------------------------------------------------------------

def run_market_level_backtest(events):
    """Simulate per-market NO trades using rolling speaker base rates.

    For each resolved market, if the speaker base rate is known:
    - Simulate entry at various hypothetical YES prices above the base rate
    - Record PnL at each threshold

    This tests: "if a market was priced at YES=BR+edge, and we bought NO,
    how would we have done?"
    """
    rolling_outcomes = defaultdict(list)
    slippage = 0.01

    # Test at these hypothetical edge levels above the speaker base rate
    # Note: max_yes cap is applied — matches PM_CONFIG["max_yes_price"]
    max_yes = 0.60
    edge_thresholds = [0.04, 0.06, 0.08, 0.10, 0.15, 0.20]

    results_by_threshold = {et: [] for et in edge_thresholds}

    for ev in events:
        speaker = ev["speaker"]
        mkts = ev["markets"]

        prior = rolling_outcomes.get(speaker, [])
        if len(prior) < 20:
            for m in mkts:
                rolling_outcomes[speaker].append(1 if m["result"] == "yes" else 0)
            continue

        speaker_br = np.mean(prior)

        for m in mkts:
            result = m["result"]

            for et in edge_thresholds:
                # Hypothetical YES price
                hyp_yes = speaker_br + et
                if hyp_yes > max_yes or hyp_yes < 0.05:
                    continue

                eff_yes = max(0.01, hyp_yes - slippage)
                no_cost = 1.0 - eff_yes

                if result == "no":
                    pnl = eff_yes  # win: collect YES price
                else:
                    pnl = -no_cost  # lose: lose NO cost

                results_by_threshold[et].append({
                    "pnl": pnl,
                    "speaker": speaker,
                    "category": ev["category"],
                    "result": result,
                    "speaker_br": speaker_br,
                    "hyp_yes": hyp_yes,
                })

        # Update rolling
        for m in mkts:
            rolling_outcomes[speaker].append(1 if m["result"] == "yes" else 0)

    return results_by_threshold


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def compute_stats(values, label=""):
    if not values:
        return {"label": label, "n": 0}
    arr = np.array(values)
    n = len(arr)
    wins = int(np.sum(arr > 0))
    mu = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    total = float(np.sum(arr))
    sharpe = mu / std if std > 0 else 0.0

    # Bootstrap CI
    rng = np.random.default_rng(42)
    boot = [float(np.mean(rng.choice(arr, size=n, replace=True)))
            for _ in range(5000)]
    ci_lo = float(np.percentile(boot, 2.5))
    ci_hi = float(np.percentile(boot, 97.5))

    return {
        "label": label, "n": n, "wins": wins, "losses": n - wins,
        "win_rate": wins / n, "mean_pnl": mu, "std_pnl": std,
        "total_pnl": total, "sharpe": sharpe,
        "ci_lo": ci_lo, "ci_hi": ci_hi,
    }


def fmt_stats(s):
    if s["n"] == 0:
        return f"{s['label']}: no trades"
    return (f"{s['label']}: N={s['n']}, WR={s['win_rate']:.1%}, "
            f"Mean=${s['mean_pnl']:+.4f}, Sharpe={s['sharpe']:.3f}, "
            f"Total=${s['total_pnl']:+.2f}, "
            f"CI=[${s['ci_lo']:+.4f}, ${s['ci_hi']:+.4f}]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PM Mentions Polymarket backtest")
    parser.add_argument("--save", action="store_true",
                        help="Save report to pm_backtest_report.md")
    args = parser.parse_args()

    print("Loading PM resolved markets...")
    markets = load_pm_markets()
    resolved = [m for m in markets if m["result"] in ("yes", "no")]
    print(f"  {len(resolved)} resolved markets")

    print("\nBuilding event groups...")
    events = build_event_groups(resolved)
    print(f"  {len(events)} events")

    # === Event-level backtest ===
    print("\nRunning rolling event-level backtest...")
    event_results = run_rolling_backtest(events)
    print(f"  {len(event_results)} events with sufficient history")

    pnls = [r["avg_pnl"] for r in event_results]
    profitable = sum(1 for r in event_results if r["profitable"])
    print(f"  Profitable events: {profitable}/{len(event_results)} "
          f"({profitable/len(event_results):.1%})")

    s = compute_stats(pnls, "Event-level NO portfolio")
    print(f"  {fmt_stats(s)}")

    # By speaker
    print("\n  By speaker:")
    speaker_pnls = defaultdict(list)
    for r in event_results:
        speaker_pnls[r["speaker"]].append(r["avg_pnl"])

    for sp, sp_pnls in sorted(speaker_pnls.items(),
                               key=lambda x: -len(x[1])):
        if len(sp_pnls) >= 5:
            ss = compute_stats(sp_pnls, sp)
            print(f"    {fmt_stats(ss)}")

    # By category
    print("\n  By category:")
    cat_pnls = defaultdict(list)
    for r in event_results:
        cat_pnls[r["category"]].append(r["avg_pnl"])
    for cat, cp in sorted(cat_pnls.items(), key=lambda x: -len(x[1])):
        cs = compute_stats(cp, cat)
        print(f"    {fmt_stats(cs)}")

    # Prediction accuracy
    errors = [r["prediction_error"] for r in event_results]
    print(f"\n  Prediction error (actual - predicted):")
    print(f"    Mean: {np.mean(errors):+.3f}")
    print(f"    Std: {np.std(errors):.3f}")
    print(f"    RMSE: {np.sqrt(np.mean(np.array(errors)**2)):.3f}")

    # === Market-level simulation ===
    print("\n" + "=" * 70)
    print("  Market-level simulation (hypothetical entry prices)")
    print("=" * 70)

    results_by_thresh = run_market_level_backtest(events)
    for et, trades in sorted(results_by_thresh.items()):
        if not trades:
            continue
        trade_pnls = [t["pnl"] for t in trades]
        ts = compute_stats(trade_pnls, f"Edge >= {et:.0%}")
        print(f"\n  {fmt_stats(ts)}")

    # Chronological stability for the 6c edge threshold
    print("\n" + "=" * 70)
    print("  Edge decay check (6c threshold, chronological halves)")
    print("=" * 70)

    trades_6c = results_by_thresh.get(0.06, [])
    if trades_6c:
        half = len(trades_6c) // 2
        h1 = compute_stats([t["pnl"] for t in trades_6c[:half]], "First half")
        h2 = compute_stats([t["pnl"] for t in trades_6c[half:]], "Second half")
        print(f"  {fmt_stats(h1)}")
        print(f"  {fmt_stats(h2)}")

    if args.save:
        # Generate a report file
        lines = ["# PM Mentions Polymarket Backtest Report", ""]
        lines.append(f"*Generated {datetime.now():%Y-%m-%d %H:%M} from "
                     f"{len(resolved):,} resolved markets in "
                     f"{len(events)} events.*")
        lines.append("")
        lines.append("## Methodology")
        lines.append("")
        lines.append("Since CLOB price history is unavailable for old resolved "
                     "markets, this backtest uses two approaches:")
        lines.append("")
        lines.append("1. **Event-level portfolio**: Buy NO on all words in each "
                     "event at the rolling speaker base rate. Profitable when "
                     "fewer words resolve YES than the base rate predicts.")
        lines.append("2. **Market-level simulation**: For each resolved market, "
                     "simulate entry at hypothetical YES prices (base_rate + edge). "
                     "Tests whether the strategy would have been profitable at "
                     "various edge thresholds.")
        lines.append("")
        lines.append("Both use rolling speaker base rates computed from all "
                     "prior resolved events (no look-ahead). Minimum 20 prior "
                     "resolved markets per speaker before trading.")
        lines.append("")

        lines.append("## Event-Level Results")
        lines.append("")
        lines.append(f"- Events tested: {len(event_results)}")
        lines.append(f"- Profitable: {profitable}/{len(event_results)} "
                     f"({profitable/len(event_results):.1%})")
        lines.append(f"- Mean PnL: ${s['mean_pnl']:+.4f}")
        lines.append(f"- Sharpe: {s['sharpe']:.3f}")
        lines.append(f"- 95% CI: [${s['ci_lo']:+.4f}, ${s['ci_hi']:+.4f}]")
        lines.append("")

        lines.append("## Market-Level Simulation")
        lines.append("")
        lines.append("| Edge Threshold | N | Win Rate | Mean PnL | Sharpe | "
                     "95% CI |")
        lines.append("|---|---|---|---|---|---|")
        for et, trades in sorted(results_by_thresh.items()):
            if not trades:
                continue
            ts = compute_stats([t["pnl"] for t in trades], f">={et:.0%}")
            if ts["n"] > 0:
                lines.append(
                    f"| {et:.0%} | {ts['n']} | {ts['win_rate']:.1%} | "
                    f"${ts['mean_pnl']:+.4f} | {ts['sharpe']:.3f} | "
                    f"[${ts['ci_lo']:+.4f}, ${ts['ci_hi']:+.4f}] |")
        lines.append("")

        out_path = "pm_backtest_report.md"
        with open(out_path, "w") as f:
            f.write("\n".join(lines))
        print(f"\nReport saved to {out_path}")
    else:
        print("\nRun with --save to write pm_backtest_report.md")


if __name__ == "__main__":
    main()
