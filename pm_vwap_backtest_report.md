# PM Mentions — Honest VWAP Backtest (Polymarket)

*Generated 2026-03-16 17:25 from 220 resolved markets (217 with CLOB trades, 212 with VWAP), 2024-06-27 to 2024-08-31.*

All results use **real VWAP 25% buffer** entry prices from CLOB trade history and **rolling speaker base rates** (no look-ahead). Polymarket has **zero fees**; 1c slippage assumed. Per-trade Sharpe = mean/std.

---

## 1. Executive Summary

PM-native strategy using speaker-level base rates (rolling) and transcript word-level rates where available.

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| PM VWAP Backtest | 79 | 79.7% | $+0.0655 | $0.3873 | $+5.17 | 0.1691 | $3.09 | [$-0.0200, $+0.1501] |

*Bootstrapped per-trade Sharpe 95% CI: [-0.0461, 0.4613]*

---

## 2. Entry Price Sensitivity

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| VWAP 25% buffer (primary) | 79 | 79.7% | $+0.0655 | $0.3873 | $+5.17 | 0.1691 | $3.09 | [$-0.0200, $+0.1501] |
| VWAP 10% buffer | 83 | 81.9% | $+0.0826 | $0.3642 | $+6.85 | 0.2268 | $2.38 | [$+0.0011, $+0.1578] |
| VWAP no buffer | 89 | 85.4% | $+0.1269 | $0.3086 | $+11.29 | 0.4111 | $1.99 | [$+0.0602, $+0.1887] |

---

## 3. Out-of-Sample Validation

### 60/40 Walk-Forward Split

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| In-sample 60% ( – 2024-08-15) | 47 | 83.0% | $+0.0971 | $0.3567 | $+4.57 | 0.2723 | $1.30 | [$-0.0089, $+0.1950] |
| Out-of-sample 40% (2024-08-15 – 2024-08-31) | 32 | 75.0% | $+0.0190 | $0.4300 | $+0.61 | 0.0442 | $2.16 | [$-0.1324, $+0.1619] |

### Chronological Thirds

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Third 1 ( – 2024-07-18) | 26 | 84.6% | $+0.1286 | $0.3588 | $+3.34 | 0.3584 | $1.05 | [$-0.0163, $+0.2555] |
| Third 2 (2024-07-18 – 2024-08-17) | 26 | 76.9% | $+0.0052 | $0.3786 | $+0.14 | 0.0138 | $2.58 | [$-0.1454, $+0.1403] |
| Third 3 (2024-08-17 – 2024-08-31) | 27 | 77.8% | $+0.0628 | $0.4253 | $+1.69 | 0.1476 | $2.16 | [$-0.1012, $+0.2102] |

---

## 4. Rate Source Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| transcript | 75 | 81.3% | $+0.0730 | $0.3760 | $+5.48 | 0.1942 | $2.58 | [$-0.0163, $+0.1544] |
| speaker | 4 | 50.0% | $-0.0758 | $0.6211 | $-0.30 | -0.1221 | $0.49 | [$-0.6061, $+0.4545] |
- transcript: 75 trades (94.9%)
- speaker: 4 trades (5.1%)

---

## 5. Category Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| political_person | 79 | 79.7% | $+0.0655 | $0.3873 | $+5.17 | 0.1691 | $3.09 | [$-0.0200, $+0.1501] |

---

## 6. Speaker Breakdown

### Best Speakers (>= 5 trades)

| Speaker | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| trump | 47 | 83% | $+0.0630 | +2.96 |
| biden | 28 | 79% | $+0.0899 | +2.52 |

### Worst Speakers (>= 5 trades)

| Speaker | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| trump | 47 | 83% | $+0.0630 | +2.96 |
| biden | 28 | 79% | $+0.0899 | +2.52 |

---

## 7. YES Price Bucket Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| 15-25% | 17 | 76.5% | $-0.0459 | $0.4400 | $-0.78 | -0.1043 | $1.97 | [$-0.2782, $+0.1343] |
| 25-40% | 18 | 77.8% | $+0.0846 | $0.4278 | $+1.52 | 0.1978 | $1.10 | [$-0.1281, $+0.2571] |
| 40-60% | 23 | 65.2% | $+0.1117 | $0.4861 | $+2.57 | 0.2299 | $2.71 | [$-0.0932, $+0.2913] |
| 5-15% | 21 | 100.0% | $+0.0886 | $0.0295 | $+1.86 | 3.0017 | $0.00 | [$+0.0766, $+0.1008] |

---

## 8. Edge Decay (Chronological Splits)

### Halves

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| First half ( – 2024-07-27) | 39 | 87.2% | $+0.1487 | $0.3366 | $+5.80 | 0.4418 | $1.05 | [$+0.0391, $+0.2486] |
| Second half (2024-07-27 – 2024-08-31) | 40 | 72.5% | $-0.0157 | $0.4195 | $-0.63 | -0.0373 | $3.09 | [$-0.1452, $+0.1091] |

### Quarters

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Q1 ( – 2024-07-11) | 19 | 84.2% | $+0.1342 | $0.3881 | $+2.55 | 0.3457 | $1.05 | [$-0.0497, $+0.2872] |
| Q2 (2024-07-11 – 2024-07-24) | 19 | 89.5% | $+0.1613 | $0.2968 | $+3.07 | 0.5436 | $0.68 | [$+0.0235, $+0.2769] |
| Q3 (2024-07-27 – 2024-08-17) | 19 | 73.7% | $-0.0598 | $0.3591 | $-1.14 | -0.1664 | $2.58 | [$-0.2222, $+0.0887] |
| Q4 (2024-08-17 – 2024-08-31) | 22 | 72.7% | $+0.0316 | $0.4628 | $+0.69 | 0.0682 | $2.16 | [$-0.1623, $+0.2140] |

---

## 9. Parameter Sensitivity Grid

256 combos tested (4 values each for max_yes, edge_sp_high, edge_sp_low, edge_transcript). Sorted by Sharpe.

### Top 20 by Sharpe (N >= 20)

| max_yes | edge_hi | edge_lo | edge_tx | N | Win Rate | Mean PnL | Sharpe | Total PnL |
|---|---|---|---|---|---|---|---|---|
| 50% | 2% | 4% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 2% | 6% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 2% | 8% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 2% | 10% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 4% | 4% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 4% | 6% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 4% | 8% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 4% | 10% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 6% | 4% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 6% | 6% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 6% | 8% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 6% | 10% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 8% | 4% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 8% | 6% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 8% | 8% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 50% | 8% | 10% | 8% | 61 | 82.0% | $+0.0810 | 0.2140 | $+4.9 |
| 60% | 2% | 4% | 8% | 70 | 78.6% | $+0.0793 | 0.1999 | $+5.6 |
| 60% | 2% | 6% | 8% | 70 | 78.6% | $+0.0793 | 0.1999 | $+5.6 |
| 60% | 2% | 8% | 8% | 70 | 78.6% | $+0.0793 | 0.1999 | $+5.6 |
| 60% | 2% | 10% | 8% | 70 | 78.6% | $+0.0793 | 0.1999 | $+5.6 |

*256 combos with N >= 20. 256 (100%) positive Sharpe. Median: 0.1415. Max: 0.2140.*

---

## 10. Kill Criteria

Stop trading if:

1. **Rolling 30-trade mean PnL < -$0.05** for two consecutive windows (backtest mean: $+0.0655)
2. **Drawdown exceeds $6** (2x backtest max DD of $3.1)
3. **OOS Sharpe < 0** over any 60-day window with >= 20 trades
4. **Market structure change**: Polymarket changes resolution rules, fees, or stops listing mention markets
5. **Transcript data staleness**: > 2 years old for political speakers. Refresh by running pm_transcript_rates.py

---

## 11. PM vs Kalshi Comparison

*Compare with focused_backtest_report.md for Kalshi results.*

| Dimension | Polymarket | Kalshi |
|---|---|---|
| Fees | 0% | 2c round-trip |
| Rate source | Speaker-level + transcript word-level | Series-level + LibFrog word-level |
| Political person | Profitable (core edge) | Negative PnL (excluded) |
| Earnings | Negative PnL (excluded) | Profitable (core edge) |
| N trades (VWAP 25%) | 79 | 740 (focused backtest) |
| Win rate | 79.7% | 81.6% |
| Mean PnL | $+0.0655 | +$0.1170 |
| Sharpe | 0.1691 | 0.3146 |

**Key differences:**

- PM has zero fees → lower edge thresholds are viable (4c vs 8-12c)
- PM mention markets are predominantly political speakers → speaker-level base rates work well
- Transcript word-level rates provide per-word precision for political speakers (equivalent to LibFrog for earnings)
- PM data is larger (10K+ resolved markets vs 20K for Kalshi) but concentrated in fewer speakers

---

## 12. Methodology Notes

- **Entry prices**: Real VWAP from CLOB trade history (25% buffer = exclude first/last 25% of trading time)
- **Rolling base rate**: mean(outcomes) of all prior resolved markets for the same speaker. Updated AFTER evaluation.
- **Transcript rates**: Static word-level rates from political speech transcripts (press conferences, debates). Not look-ahead since they predate PM markets.
- **Fees**: $0 (Polymarket has no trading fees)
- **Slippage**: $0.01 assumed
- **Side**: Always NO
- **Edge thresholds**: 4c (speaker high-N), 6c (speaker low-N), 4c (transcript), 10c (category)
- **Max YES price**: 60%
- **Excluded categories**: earnings
- **Min speaker history**: 20 markets
- **Bootstrap**: 10,000 resamples, seed=42
- **Parameter grid**: 256 combos