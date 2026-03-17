# PM Mentions — Honest VWAP Backtest (Polymarket)

*Generated 2026-03-16 22:44 from 10,021 resolved markets (9,468 with CLOB trades, 8,627 with VWAP), 2024-06-27 to 2026-04-30.*

All results use **real VWAP 25% buffer** entry prices from CLOB trade history and **rolling speaker base rates** (no look-ahead). Polymarket has **zero fees**; 1c slippage assumed. Per-trade Sharpe = mean/std.

---

## 1. Executive Summary

PM-native strategy using speaker-level base rates (rolling) and transcript word-level rates where available.

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| PM VWAP Backtest | 2848 | 67.9% | $+0.0374 | $0.4378 | $+106.60 | 0.0855 | $13.26 | [$+0.0215, $+0.0532] |

*Bootstrapped per-trade Sharpe 95% CI: [0.0484, 0.1230]*

---

## 2. Entry Price Sensitivity

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| VWAP 25% buffer (primary) | 2848 | 67.9% | $+0.0374 | $0.4378 | $+106.60 | 0.0855 | $13.26 | [$+0.0215, $+0.0532] |
| VWAP 10% buffer | 2847 | 69.0% | $+0.0357 | $0.4261 | $+101.69 | 0.0838 | $20.19 | [$+0.0201, $+0.0513] |
| VWAP no buffer | 2151 | 82.7% | $+0.1331 | $0.3249 | $+286.40 | 0.4098 | $5.15 | [$+0.1197, $+0.1469] |

---

## 3. Out-of-Sample Validation

### 60/40 Walk-Forward Split

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| In-sample 60% ( – 2025-11-10) | 1708 | 68.3% | $+0.0283 | $0.4361 | $+48.41 | 0.0650 | $13.26 | [$+0.0074, $+0.0490] |
| Out-of-sample 40% (2025-11-10 – 2026-04-30) | 1140 | 67.4% | $+0.0510 | $0.4402 | $+58.19 | 0.1160 | $8.70 | [$+0.0248, $+0.0760] |

### Chronological Thirds

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Third 1 ( – 2025-05-12) | 949 | 72.2% | $+0.0454 | $0.4181 | $+43.12 | 0.1087 | $9.51 | [$+0.0188, $+0.0720] |
| Third 2 (2025-05-12 – 2025-12-07) | 949 | 64.0% | $+0.0092 | $0.4549 | $+8.78 | 0.0203 | $13.26 | [$-0.0198, $+0.0378] |
| Third 3 (2025-12-07 – 2026-04-30) | 950 | 67.7% | $+0.0576 | $0.4387 | $+54.70 | 0.1313 | $8.70 | [$+0.0294, $+0.0852] |

---

## 4. Rate Source Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| transcript | 2318 | 69.2% | $+0.0200 | $0.4259 | $+46.32 | 0.0469 | $31.05 | [$+0.0026, $+0.0370] |
| speaker | 317 | 61.8% | $+0.0937 | $0.4775 | $+29.70 | 0.1962 | $3.97 | [$+0.0413, $+0.1461] |
| category | 213 | 63.4% | $+0.1436 | $0.4821 | $+30.58 | 0.2978 | $4.24 | [$+0.0773, $+0.2065] |
- transcript: 2318 trades (81.4%)
- speaker: 317 trades (11.1%)
- category: 213 trades (7.5%)

---

## 5. Category Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| political_person | 2609 | 68.3% | $+0.0288 | $0.4330 | $+75.03 | 0.0664 | $26.81 | [$+0.0120, $+0.0455] |
| other | 239 | 64.4% | $+0.1321 | $0.4775 | $+31.57 | 0.2766 | $6.20 | [$+0.0724, $+0.1918] |

---

## 6. Speaker Breakdown

### Best Speakers (>= 5 trades)

| Speaker | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| trump | 2275 | 69% | $+0.0172 | +39.12 |
| leavitt | 97 | 74% | $+0.2247 | +21.79 |
|  | 127 | 57% | $+0.0755 | +9.58 |
| biden | 46 | 83% | $+0.1280 | +5.89 |
| elon | 14 | 93% | $+0.3756 | +5.26 |
| altman | 13 | 92% | $+0.2916 | +3.79 |
| mrbeast | 32 | 62% | $+0.0975 | +3.12 |
| sanders | 14 | 64% | $+0.1896 | +2.65 |
| hegseth | 7 | 100% | $+0.3271 | +2.29 |
| kamala | 54 | 61% | $+0.0387 | +2.09 |
| melania | 7 | 86% | $+0.2892 | +2.02 |
| ackman | 8 | 75% | $+0.2507 | +2.01 |
| powell | 20 | 50% | $+0.0429 | +0.86 |
| swift | 5 | 60% | $+0.0734 | +0.37 |
| tucker | 9 | 56% | $+0.0263 | +0.24 |

### Worst Speakers (>= 5 trades)

| Speaker | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| sanders | 14 | 64% | $+0.1896 | +2.65 |
| hegseth | 7 | 100% | $+0.3271 | +2.29 |
| kamala | 54 | 61% | $+0.0387 | +2.09 |
| melania | 7 | 86% | $+0.2892 | +2.02 |
| ackman | 8 | 75% | $+0.2507 | +2.01 |
| powell | 20 | 50% | $+0.0429 | +0.86 |
| swift | 5 | 60% | $+0.0734 | +0.37 |
| tucker | 9 | 56% | $+0.0263 | +0.24 |
| starmer | 24 | 46% | $-0.0167 | -0.40 |
| vance | 45 | 47% | $-0.0232 | -1.04 |

---

## 7. YES Price Bucket Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| 15-25% | 408 | 86.8% | $+0.0578 | $0.3383 | $+23.60 | 0.1710 | $3.00 | [$+0.0238, $+0.0899] |
| 25-40% | 778 | 70.8% | $+0.0258 | $0.4508 | $+20.07 | 0.0572 | $14.57 | [$-0.0062, $+0.0579] |
| 40-60% | 1347 | 54.0% | $+0.0352 | $0.4938 | $+47.37 | 0.0712 | $10.56 | [$+0.0091, $+0.0615] |
| 5-15% | 315 | 95.9% | $+0.0494 | $0.2000 | $+15.56 | 0.2470 | $1.69 | [$+0.0261, $+0.0698] |

---

## 8. Edge Decay (Chronological Splits)

### Halves

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| First half ( – 2025-09-25) | 1424 | 69.2% | $+0.0346 | $0.4323 | $+49.34 | 0.0801 | $9.51 | [$+0.0121, $+0.0567] |
| Second half (2025-09-25 – 2026-04-30) | 1424 | 66.6% | $+0.0402 | $0.4433 | $+57.26 | 0.0907 | $9.32 | [$+0.0169, $+0.0630] |

### Quarters

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Q1 ( – 2025-03-11) | 712 | 74.0% | $+0.0626 | $0.4095 | $+44.56 | 0.1528 | $4.05 | [$+0.0324, $+0.0928] |
| Q2 (2025-03-11 – 2025-09-25) | 712 | 64.5% | $+0.0067 | $0.4526 | $+4.78 | 0.0148 | $9.51 | [$-0.0264, $+0.0398] |
| Q3 (2025-09-25 – 2025-12-31) | 712 | 63.3% | $+0.0091 | $0.4559 | $+6.49 | 0.0200 | $9.32 | [$-0.0240, $+0.0438] |
| Q4 (2025-12-31 – 2026-04-30) | 712 | 69.9% | $+0.0713 | $0.4284 | $+50.77 | 0.1664 | $8.00 | [$+0.0392, $+0.1025] |

---

## 9. Parameter Sensitivity Grid

256 combos tested (4 values each for max_yes, edge_sp_high, edge_sp_low, edge_transcript). Sorted by Sharpe.

### Top 20 by Sharpe (N >= 20)

| max_yes | edge_hi | edge_lo | edge_tx | N | Win Rate | Mean PnL | Sharpe | Total PnL |
|---|---|---|---|---|---|---|---|---|
| 40% | 2% | 4% | 2% | 1577 | 80.8% | $+0.0426 | 0.1128 | $+67.2 |
| 40% | 6% | 4% | 2% | 1556 | 81.0% | $+0.0424 | 0.1125 | $+65.9 |
| 40% | 8% | 4% | 2% | 1555 | 81.0% | $+0.0422 | 0.1120 | $+65.5 |
| 40% | 2% | 8% | 2% | 1563 | 80.9% | $+0.0422 | 0.1119 | $+66.0 |
| 40% | 6% | 8% | 2% | 1542 | 81.0% | $+0.0420 | 0.1116 | $+64.7 |
| 40% | 2% | 10% | 2% | 1558 | 80.9% | $+0.0421 | 0.1116 | $+65.6 |
| 40% | 6% | 10% | 2% | 1537 | 81.0% | $+0.0418 | 0.1112 | $+64.3 |
| 50% | 8% | 4% | 2% | 2170 | 75.4% | $+0.0457 | 0.1112 | $+99.2 |
| 40% | 8% | 8% | 2% | 1541 | 81.0% | $+0.0417 | 0.1110 | $+64.3 |
| 40% | 2% | 6% | 2% | 1565 | 80.8% | $+0.0419 | 0.1110 | $+65.5 |
| 40% | 8% | 10% | 2% | 1536 | 81.0% | $+0.0416 | 0.1107 | $+63.9 |
| 40% | 6% | 6% | 2% | 1544 | 81.0% | $+0.0416 | 0.1106 | $+64.3 |
| 40% | 4% | 4% | 2% | 1559 | 80.9% | $+0.0416 | 0.1104 | $+64.9 |
| 40% | 8% | 6% | 2% | 1543 | 80.9% | $+0.0414 | 0.1101 | $+63.9 |
| 50% | 8% | 10% | 2% | 2140 | 75.4% | $+0.0452 | 0.1100 | $+96.7 |
| 50% | 8% | 8% | 2% | 2149 | 75.4% | $+0.0451 | 0.1098 | $+96.9 |
| 40% | 4% | 8% | 2% | 1545 | 80.9% | $+0.0412 | 0.1095 | $+63.7 |
| 40% | 4% | 10% | 2% | 1540 | 80.9% | $+0.0411 | 0.1091 | $+63.3 |
| 50% | 8% | 6% | 2% | 2153 | 75.3% | $+0.0447 | 0.1088 | $+96.3 |
| 40% | 4% | 6% | 2% | 1547 | 80.9% | $+0.0409 | 0.1085 | $+63.3 |

*256 combos with N >= 20. 256 (100%) positive Sharpe. Median: 0.0950. Max: 0.1128.*

---

## 10. Kill Criteria

Stop trading if:

1. **Rolling 30-trade mean PnL < -$0.05** for two consecutive windows (backtest mean: $+0.0374)
2. **Drawdown exceeds $27** (2x backtest max DD of $13.3)
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
| N trades (VWAP 25%) | 2848 | 740 (focused backtest) |
| Win rate | 67.9% | 81.6% |
| Mean PnL | $+0.0374 | +$0.1170 |
| Sharpe | 0.0855 | 0.3146 |

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