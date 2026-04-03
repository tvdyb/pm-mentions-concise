# PM Mentions — Honest VWAP Backtest (Polymarket)

*Generated 2026-04-02 19:42 from 10,021 resolved markets (9,468 with CLOB trades, 8,627 with VWAP), 2024-06-27 to 2026-04-30.*

All results use **real VWAP 25% buffer** entry prices from CLOB trade history and **rolling speaker base rates** (no look-ahead). PM taker fees included (mentions: 25% rate, exponent 2); 1c slippage assumed. Volume: core <$3,000, extended <$5,000 (with trade-count gate). Per-trade Sharpe = mean/std.

---

## 1. Executive Summary

PM-native strategy using speaker-level base rates (rolling) and transcript word-level rates where available.

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| PM VWAP Backtest | 409 | 84.8% | $+0.1324 | $0.3443 | $+54.13 | 0.3845 | $2.73 | [$+0.0990, $+0.1655] |

*Bootstrapped per-trade Sharpe 95% CI: [0.2718, 0.5185]*

---

## 2. Entry Price Sensitivity

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| VWAP 25% buffer (primary) | 409 | 84.8% | $+0.1324 | $0.3443 | $+54.13 | 0.3845 | $2.73 | [$+0.0990, $+0.1655] |
| VWAP 10% buffer | 448 | 85.9% | $+0.1229 | $0.3273 | $+55.05 | 0.3754 | $2.10 | [$+0.0916, $+0.1531] |
| VWAP no buffer | 403 | 95.0% | $+0.1609 | $0.2041 | $+64.83 | 0.7881 | $1.30 | [$+0.1414, $+0.1806] |

---

## 3. Out-of-Sample Validation

### 60/40 Walk-Forward Split

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| In-sample 60% ( – 2025-12-31) | 245 | 83.3% | $+0.1132 | $0.3515 | $+27.74 | 0.3222 | $2.73 | [$+0.0684, $+0.1570] |
| Out-of-sample 40% (2025-12-31 – 2026-04-03) | 164 | 87.2% | $+0.1609 | $0.3322 | $+26.39 | 0.4844 | $1.69 | [$+0.1097, $+0.2098] |

### Chronological Thirds

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Third 1 ( – 2025-09-22) | 136 | 85.3% | $+0.1157 | $0.3187 | $+15.74 | 0.3632 | $2.00 | [$+0.0615, $+0.1678] |
| Third 2 (2025-09-23 – 2025-12-31) | 136 | 81.6% | $+0.1445 | $0.3882 | $+19.65 | 0.3722 | $2.73 | [$+0.0777, $+0.2087] |
| Third 3 (2025-12-31 – 2026-04-03) | 137 | 87.6% | $+0.1368 | $0.3236 | $+18.75 | 0.4228 | $1.69 | [$+0.0811, $+0.1887] |

---

## 4. Rate Source Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| transcript_override | 259 | 91.5% | $+0.0940 | $0.2676 | $+24.35 | 0.3513 | $1.87 | [$+0.0606, $+0.1253] |
| category | 75 | 72.0% | $+0.2039 | $0.4568 | $+15.29 | 0.4463 | $3.55 | [$+0.0975, $+0.3029] |
| speaker | 73 | 75.3% | $+0.2058 | $0.4178 | $+15.02 | 0.4926 | $2.08 | [$+0.1057, $+0.2978] |
| transcript | 2 | 50.0% | $-0.2657 | $0.6260 | $-0.53 | -0.4244 | $0.00 | [$-0.7084, $+0.1770] |
- transcript_override: 259 trades (63.3%)
- category: 75 trades (18.3%)
- speaker: 73 trades (17.8%)
- transcript: 2 trades (0.5%)

---

## 5. Category Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| political_person | 333 | 88.0% | $+0.1225 | $0.3126 | $+40.80 | 0.3919 | $3.20 | [$+0.0889, $+0.1549] |
| other | 76 | 71.1% | $+0.1755 | $0.4580 | $+13.33 | 0.3831 | $2.33 | [$+0.0706, $+0.2760] |

---

## 6. Speaker Breakdown

### Best Speakers (>= 5 trades)

| Speaker | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| trump | 262 | 90% | $+0.0904 | +23.69 |
| leavitt | 40 | 88% | $+0.3286 | +13.15 |
|  | 46 | 70% | $+0.1680 | +7.73 |
| elon | 6 | 100% | $+0.4552 | +2.73 |
| biden | 8 | 100% | $+0.2121 | +1.70 |
| powell | 5 | 60% | $+0.1375 | +0.69 |
| sanders | 5 | 40% | $-0.0649 | -0.32 |

### Worst Speakers (>= 5 trades)

| Speaker | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| trump | 262 | 90% | $+0.0904 | +23.69 |
| leavitt | 40 | 88% | $+0.3286 | +13.15 |
|  | 46 | 70% | $+0.1680 | +7.73 |
| elon | 6 | 100% | $+0.4552 | +2.73 |
| biden | 8 | 100% | $+0.2121 | +1.70 |
| powell | 5 | 60% | $+0.1375 | +0.69 |
| sanders | 5 | 40% | $-0.0649 | -0.32 |

---

## 7. YES Price Bucket Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| 15-25% | 108 | 93.5% | $+0.1117 | $0.2490 | $+12.07 | 0.4487 | $1.64 | [$+0.0626, $+0.1539] |
| 25-40% | 50 | 90.0% | $+0.2029 | $0.3005 | $+10.15 | 0.6753 | $0.86 | [$+0.1131, $+0.2776] |
| 40-60% | 155 | 70.3% | $+0.1768 | $0.4566 | $+27.41 | 0.3872 | $4.30 | [$+0.1051, $+0.2473] |
| 5-15% | 96 | 95.8% | $+0.0470 | $0.2023 | $+4.52 | 0.2325 | $1.52 | [$+0.0036, $+0.0814] |

---

## 8. Volume Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| $0-1K | 148 | 85.8% | $+0.1291 | $0.3395 | $+19.10 | 0.3802 | $1.69 | [$+0.0741, $+0.1828] |
| $10K+ | 0 | — | — | — | — | — | — | — |
| $1K-5K | 261 | 84.3% | $+0.1342 | $0.3476 | $+35.03 | 0.3862 | $2.65 | [$+0.0916, $+0.1750] |
| $5K-10K | 0 | — | — | — | — | — | — | — |

---

## 9. Edge Decay (Chronological Splits)

### Halves

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| First half ( – 2025-11-25) | 204 | 83.8% | $+0.1185 | $0.3381 | $+24.18 | 0.3506 | $2.73 | [$+0.0711, $+0.1637] |
| Second half (2025-11-27 – 2026-04-03) | 205 | 85.9% | $+0.1461 | $0.3506 | $+29.95 | 0.4168 | $1.69 | [$+0.0965, $+0.1929] |

### Quarters

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Q1 ( – 2025-07-22) | 102 | 88.2% | $+0.1367 | $0.2963 | $+13.95 | 0.4616 | $2.00 | [$+0.0765, $+0.1921] |
| Q2 (2025-08-06 – 2025-11-25) | 102 | 79.4% | $+0.1003 | $0.3758 | $+10.23 | 0.2669 | $2.73 | [$+0.0272, $+0.1709] |
| Q3 (2025-11-27 – 2026-02-01) | 102 | 85.3% | $+0.1731 | $0.3620 | $+17.66 | 0.4782 | $1.18 | [$+0.0998, $+0.2415] |
| Q4 (2026-02-08 – 2026-04-03) | 103 | 86.4% | $+0.1194 | $0.3386 | $+12.30 | 0.3526 | $1.69 | [$+0.0527, $+0.1827] |

---

## 10. Parameter Sensitivity Grid (with Volume)

768 combos tested (4 values each for max_yes, edge_sp_high, edge_sp_low, edge_transcript; 3 values for max_volume). Sorted by Sharpe.

### Top 20 by Sharpe (N >= 20)

| max_yes | edge_hi | edge_lo | edge_tx | max_vol | N | Win Rate | Mean PnL | Sharpe | Total PnL |
|---|---|---|---|---|---|---|---|---|---|
| 40% | 2% | 4% | 2% | $5K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 2% | $10K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 2% | none | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 4% | $5K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 4% | $10K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 4% | none | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 6% | $5K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 6% | $10K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 6% | none | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 8% | $5K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 8% | $10K | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 2% | 4% | 8% | none | 225 | 90.7% | $+0.1142 | 0.3960 | $+25.7 |
| 40% | 4% | 4% | 2% | $5K | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |
| 40% | 4% | 4% | 2% | $10K | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |
| 40% | 4% | 4% | 2% | none | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |
| 40% | 4% | 4% | 4% | $5K | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |
| 40% | 4% | 4% | 4% | $10K | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |
| 40% | 4% | 4% | 4% | none | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |
| 40% | 4% | 4% | 6% | $5K | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |
| 40% | 4% | 4% | 6% | $10K | 214 | 91.1% | $+0.1113 | 0.3945 | $+23.8 |

*768 combos with N >= 20. 768 (100%) positive Sharpe. Median: 0.3600. Max: 0.3960.*

---

## 11. Kill Criteria

Stop trading if:

1. **Rolling 30-trade mean PnL < -$0.05** for two consecutive windows (backtest mean: $+0.1324)
2. **Drawdown exceeds $5** (2x backtest max DD of $2.7)
3. **OOS Sharpe < 0** over any 60-day window with >= 20 trades
4. **Market structure change**: Polymarket changes resolution rules, fees, or stops listing mention markets
5. **Transcript data staleness**: > 2 years old for political speakers. Refresh by running pm_transcript_rates.py

---

## 12. PM vs Kalshi Comparison

*Compare with focused_backtest_report.md for Kalshi results.*

| Dimension | Polymarket | Kalshi |
|---|---|---|
| Fees | 0% | 2c round-trip |
| Rate source | Speaker-level + transcript word-level | Series-level + LibFrog word-level |
| Political person | Profitable (core edge) | Negative PnL (excluded) |
| Earnings | Negative PnL (excluded) | Profitable (core edge) |
| N trades (VWAP 25%) | 409 | 740 (focused backtest) |
| Win rate | 84.8% | 81.6% |
| Mean PnL | $+0.1324 | +$0.1170 |
| Sharpe | 0.3845 | 0.3146 |

**Key differences:**

- PM fees are small (~$0.008/contract) → lower edge thresholds viable (4c vs 8-12c)
- PM mention markets are predominantly political speakers → speaker-level base rates work well
- Transcript word-level rates provide per-word precision for political speakers (equivalent to LibFrog for earnings)
- PM data is larger (10K+ resolved markets vs 20K for Kalshi) but concentrated in fewer speakers

---

## 13. Methodology Notes

- **Entry prices**: Real VWAP from CLOB trade history (25% buffer = exclude first/last 25% of trading time)
- **Rolling base rate**: mean(outcomes) of all prior resolved markets for the same speaker. Updated AFTER evaluation.
- **Transcript rates**: Static word-level rates from political speech transcripts (press conferences, debates). Not look-ahead since they predate PM markets.
- **Fees**: $0 (Polymarket has no trading fees)
- **Slippage**: $0.01 assumed
- **Side**: Always NO
- **Edge thresholds**: 4c (speaker high-N), 6c (speaker low-N), 4c (transcript), 10c (category)
- **Max YES price**: 60%
- **Excluded categories**: earnings, monthly, weekly
- **Min speaker history**: 20 markets
- **Bootstrap**: 10,000 resamples, seed=42
- **Parameter grid**: 768 combos (incl. volume)