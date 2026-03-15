# PM Mentions Focused Strategy — Backtest Report

*Generated 2026-03-15 17:17 from 20,252 settled markets (2025-01-30 to 2026-03-07, 400 days).*

All results use **VWAP 25% buffer** entry prices and **rolling base rates** (no look-ahead). Per-trade Sharpe = mean/std, not annualized unless labeled.

---

## 1. Executive Summary

The focused strategy applies tighter filters to concentrate on the profitable segments identified in the honest backtest:

- **YES price cap lowered** from 75c to 50c (the 50-75c bucket had ~zero edge)
- **Political person category excluded** (negative total PnL in honest backtest)
- **Tiered edge thresholds**: 8c for LibFrog-rated earnings (precise rates), 12c for rolling series rates (noisier)
- **Stricter min history**: 15 prior markets for series rates, 10 calls for LibFrog

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Original strategy | 3769 | 48.6% | $+0.0288 | $0.4600 | $+108.60 | 0.0626 | $20.38 | [$+0.0143, $+0.0433] |
| Focused strategy | 740 | 81.6% | $+0.1170 | $0.3720 | $+86.61 | 0.3146 | $4.58 | [$+0.0903, $+0.1440] |

**Delta**: -3029 trades, $+0.0882 mean PnL, $-22.00 total PnL

*Annualized Sharpe estimate (focused): 8.175 (675 trades/year)*
*Bootstrapped per-trade Sharpe 95% CI: [0.2321, 0.4095]*

---

## 2. Full Backtest Results

### Entry Price Sensitivity

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| VWAP 25% buffer (primary) | 740 | 81.6% | $+0.1170 | $0.3720 | $+86.61 | 0.3146 | $4.58 | [$+0.0903, $+0.1440] |
| VWAP 10% buffer | 661 | 84.7% | $+0.1384 | $0.3512 | $+91.47 | 0.3941 | $3.38 | [$+0.1108, $+0.1646] |

---

## 3. Out-of-Sample Validation

### 60/40 Walk-Forward Split

The first 60% of trades (chronologically) establish that the filters make sense. The last 40% are out-of-sample.

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| In-sample 60% (2025-02-10 – 2025-12-13) | 444 | 83.8% | $+0.1258 | $0.3554 | $+55.85 | 0.3539 | $4.58 | [$+0.0931, $+0.1577] |
| Out-of-sample 40% (2025-12-14 – 2026-03-05) | 296 | 78.4% | $+0.1039 | $0.3959 | $+30.76 | 0.2625 | $3.41 | [$+0.0576, $+0.1484] |

### Chronological Thirds

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Third 1 (2025-02-10 – 2025-10-15) | 246 | 89.4% | $+0.1475 | $0.3106 | $+36.30 | 0.4750 | $2.13 | [$+0.1079, $+0.1844] |
| Third 2 (2025-10-15 – 2026-01-16) | 246 | 76.8% | $+0.1018 | $0.4023 | $+25.05 | 0.2531 | $4.58 | [$+0.0484, $+0.1514] |
| Third 3 (2026-01-21 – 2026-03-05) | 248 | 78.6% | $+0.1019 | $0.3955 | $+25.26 | 0.2576 | $3.41 | [$+0.0514, $+0.1511] |

---

## 4. Parameter Sensitivity Grid

256 parameter combinations tested. Each row shows a combo with N >= 20 trades. Sorted by per-trade Sharpe descending.

The goal is to show the profitable region is a broad plateau, not a single fragile peak.

### Top 30 by Sharpe (N >= 20)

| max_yes | edge_lf | edge_roll | min_hist | N | Win Rate | Mean PnL | Sharpe | Total PnL |
|---|---|---|---|---|---|---|---|---|
| 40% | 15% | 15% | 10 | 331 | 89.4% | $+0.1524 | 0.4990 | $+50.5 |
| 40% | 15% | 15% | 15 | 315 | 89.2% | $+0.1511 | 0.4906 | $+47.6 |
| 40% | 15% | 15% | 20 | 301 | 88.7% | $+0.1460 | 0.4654 | $+44.0 |
| 40% | 15% | 8% | 10 | 447 | 88.6% | $+0.1442 | 0.4611 | $+64.5 |
| 40% | 15% | 15% | 30 | 291 | 88.7% | $+0.1442 | 0.4587 | $+42.0 |
| 40% | 15% | 12% | 10 | 368 | 88.3% | $+0.1418 | 0.4481 | $+52.2 |
| 40% | 8% | 15% | 10 | 452 | 90.3% | $+0.1316 | 0.4478 | $+59.5 |
| 40% | 15% | 8% | 15 | 421 | 88.1% | $+0.1422 | 0.4470 | $+59.9 |
| 40% | 10% | 15% | 10 | 426 | 89.9% | $+0.1331 | 0.4446 | $+56.7 |
| 40% | 8% | 15% | 15 | 436 | 90.1% | $+0.1299 | 0.4399 | $+56.6 |
| 40% | 10% | 15% | 15 | 410 | 89.8% | $+0.1313 | 0.4363 | $+53.8 |
| 40% | 15% | 12% | 15 | 349 | 88.0% | $+0.1395 | 0.4358 | $+48.7 |
| 40% | 8% | 8% | 10 | 568 | 89.4% | $+0.1294 | 0.4285 | $+73.5 |
| 40% | 15% | 8% | 20 | 395 | 87.6% | $+0.1387 | 0.4274 | $+54.8 |
| 40% | 10% | 8% | 10 | 542 | 89.1% | $+0.1305 | 0.4256 | $+70.7 |
| 40% | 15% | 10% | 10 | 410 | 87.8% | $+0.1355 | 0.4222 | $+55.5 |
| 40% | 15% | 12% | 20 | 331 | 87.6% | $+0.1369 | 0.4220 | $+45.3 |
| 40% | 5% | 15% | 10 | 482 | 90.2% | $+0.1245 | 0.4207 | $+60.0 |
| 40% | 8% | 15% | 20 | 422 | 89.8% | $+0.1256 | 0.4201 | $+53.0 |
| 40% | 8% | 8% | 15 | 542 | 89.1% | $+0.1272 | 0.4158 | $+68.9 |
| 40% | 10% | 15% | 20 | 396 | 89.4% | $+0.1268 | 0.4157 | $+50.2 |
| 40% | 8% | 15% | 30 | 412 | 89.8% | $+0.1238 | 0.4142 | $+51.0 |
| 40% | 8% | 12% | 10 | 489 | 89.4% | $+0.1252 | 0.4132 | $+61.2 |
| 40% | 5% | 15% | 15 | 466 | 90.1% | $+0.1226 | 0.4126 | $+57.1 |
| 40% | 10% | 8% | 15 | 516 | 88.8% | $+0.1282 | 0.4124 | $+66.1 |
| 40% | 10% | 15% | 30 | 386 | 89.4% | $+0.1249 | 0.4094 | $+48.2 |
| 40% | 10% | 12% | 10 | 463 | 89.0% | $+0.1262 | 0.4093 | $+58.4 |
| 40% | 5% | 8% | 10 | 598 | 89.5% | $+0.1238 | 0.4083 | $+74.0 |
| 40% | 15% | 10% | 15 | 387 | 87.3% | $+0.1331 | 0.4082 | $+51.5 |
| 40% | 8% | 12% | 15 | 470 | 89.1% | $+0.1229 | 0.4025 | $+57.7 |

### Bottom 10 by Sharpe (N >= 20)

| max_yes | edge_lf | edge_roll | min_hist | N | Win Rate | Mean PnL | Sharpe | Total PnL |
|---|---|---|---|---|---|---|---|---|
| 75% | 5% | 10% | 20 | 2238 | 56.7% | $+0.0663 | 0.1467 | $+148.5 |
| 75% | 8% | 10% | 20 | 2202 | 56.2% | $+0.0665 | 0.1465 | $+146.4 |
| 75% | 10% | 10% | 30 | 2056 | 55.7% | $+0.0666 | 0.1458 | $+137.0 |
| 75% | 10% | 8% | 30 | 2167 | 55.9% | $+0.0666 | 0.1457 | $+144.3 |
| 75% | 10% | 8% | 20 | 2288 | 56.0% | $+0.0662 | 0.1452 | $+151.4 |
| 75% | 15% | 10% | 30 | 1941 | 54.0% | $+0.0670 | 0.1443 | $+130.0 |
| 75% | 15% | 8% | 30 | 2052 | 54.3% | $+0.0669 | 0.1443 | $+137.3 |
| 75% | 15% | 8% | 20 | 2173 | 54.4% | $+0.0665 | 0.1438 | $+144.4 |
| 75% | 10% | 10% | 20 | 2169 | 55.6% | $+0.0652 | 0.1430 | $+141.5 |
| 75% | 15% | 10% | 20 | 2054 | 54.0% | $+0.0655 | 0.1415 | $+134.5 |

*256 combos with N >= 20. 256 (100%) have positive Sharpe. Median Sharpe: 0.2911. Max: 0.4990. Min: 0.1415.*

---

## 5. Category Exclusion Ablation

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| No exclusions | 788 | 81.6% | $+0.1232 | $0.3739 | $+97.10 | 0.3296 | $3.50 | [$+0.0962, $+0.1495] |
| Exclude political_person | 740 | 81.6% | $+0.1170 | $0.3720 | $+86.61 | 0.3146 | $4.58 | [$+0.0903, $+0.1440] |
| Exclude political_person + sports | 739 | 81.6% | $+0.1166 | $0.3720 | $+86.14 | 0.3133 | $4.58 | [$+0.0895, $+0.1433] |
| Earnings only | 496 | 84.9% | $+0.1172 | $0.3445 | $+58.14 | 0.3403 | $2.71 | [$+0.0873, $+0.1469] |

---

## 6. Rate Source Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| libfrog | 496 | 84.9% | $+0.1172 | $0.3445 | $+58.14 | 0.3403 | $2.71 | [$+0.0873, $+0.1469] |
| rolling | 244 | 75.0% | $+0.1167 | $0.4232 | $+28.47 | 0.2757 | $4.76 | [$+0.0622, $+0.1691] |

LibFrog: 496 (67.0%) | Rolling: 244 (33.0%)

---

## 7. Category Breakdown (within focused filter)

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| earnings | 496 | 84.9% | $+0.1172 | $0.3445 | $+58.14 | 0.3403 | $2.71 | [$+0.0873, $+0.1469] |
| other | 243 | 74.9% | $+0.1152 | $0.4235 | $+28.00 | 0.2721 | $4.76 | [$+0.0612, $+0.1681] |
| sports | 1 | 100.0% | $+0.4695 | $0.0000 | $+0.47 | 0.0000 | $0.00 | [$+0.4695, $+0.4695] |

---

## 8. YES Price Bucket Breakdown

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| 25-50% | 531 | 75.9% | $+0.1202 | $0.4217 | $+63.80 | 0.2849 | $4.88 | [$+0.0844, $+0.1555] |
| 5-25% | 209 | 96.2% | $+0.1091 | $0.1960 | $+22.81 | 0.5569 | $1.51 | [$+0.0811, $+0.1337] |

---

## 9. Edge Decay (Chronological Splits)

### Halves

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| First half (2025-02-10 – 2025-11-20) | 370 | 86.8% | $+0.1404 | $0.3288 | $+51.93 | 0.4269 | $2.67 | [$+0.1069, $+0.1733] |
| Second half (2025-11-20 – 2026-03-05) | 370 | 76.5% | $+0.0937 | $0.4098 | $+34.68 | 0.2287 | $4.58 | [$+0.0519, $+0.1345] |

### Quarters

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Q1 (2025-02-10 – 2025-09-12) | 185 | 89.2% | $+0.1319 | $0.3073 | $+24.40 | 0.4293 | $2.13 | [$+0.0865, $+0.1746] |
| Q2 (2025-09-12 – 2025-11-20) | 185 | 84.3% | $+0.1488 | $0.3497 | $+27.53 | 0.4256 | $2.67 | [$+0.0965, $+0.1992] |
| Q3 (2025-11-20 – 2026-02-01) | 185 | 76.2% | $+0.1068 | $0.4157 | $+19.75 | 0.2568 | $4.58 | [$+0.0448, $+0.1641] |
| Q4 (2026-02-01 – 2026-03-05) | 185 | 76.8% | $+0.0807 | $0.4045 | $+14.92 | 0.1994 | $3.41 | [$+0.0198, $+0.1370] |

---

## 10. Top and Bottom Series

### Best (>= 3 trades)

| Series | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| KXSOUTHPARKMENTION | 40 | 95% | $+0.222 | $+8.86 |
| KXEARNINGSMENTIONPLTR | 30 | 97% | $+0.180 | $+5.40 |
| KXEARNINGSMENTIONNVDA | 20 | 90% | $+0.184 | $+3.69 |
| KXSNLMENTION | 22 | 77% | $+0.167 | $+3.68 |
| KXEARNINGSMENTIONAXP | 13 | 100% | $+0.281 | $+3.65 |
| KXKAMALAMENTION | 13 | 92% | $+0.273 | $+3.54 |
| KXEARNINGSMENTIONDELL | 10 | 100% | $+0.309 | $+3.09 |
| KXSURVIVORMENTION | 29 | 69% | $+0.104 | $+3.02 |
| KXEARNINGSMENTIONGOOGL | 19 | 89% | $+0.156 | $+2.97 |
| KXLEAVITTMENTIONDURATION | 12 | 83% | $+0.217 | $+2.61 |

### Worst (>= 3 trades)

| Series | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| KXEARNINGSMENTIONNFLX | 9 | 67% | $-0.083 | $-0.75 |
| KXEARNINGSMENTIONDAL | 4 | 50% | $-0.202 | $-0.81 |
| KXEARNINGSMENTIONULTA | 5 | 40% | $-0.164 | $-0.82 |
| KXSWIFTMENTION | 5 | 40% | $-0.182 | $-0.91 |
| KXMELANIAMENTION | 16 | 56% | $-0.057 | $-0.91 |
| KXCOLBERTMENTION | 12 | 50% | $-0.086 | $-1.03 |
| KXEARNINGSMENTIONRKLB | 6 | 50% | $-0.177 | $-1.06 |
| KXEARNINGSMENTIONLLY | 3 | 33% | $-0.375 | $-1.13 |
| KXEARNINGSMENTIONHD | 9 | 56% | $-0.129 | $-1.16 |
| KXEARNINGSMENTIONRY | 5 | 20% | $-0.383 | $-1.91 |

---

## 11. Kill Criteria

Stop trading the focused strategy if:

1. **Rolling 30-trade mean PnL falls below -$0.05** for two consecutive windows. The strategy's mean is +$0.117; sustained negative mean indicates the edge is gone.
2. **Drawdown exceeds $15** (~1.5x the backtest max DD of $4.6).
3. **Out-of-sample Sharpe drops below 0** over any 60-day rolling window with >= 20 trades.
4. **Market structure change**: Kalshi changes fees, resolution rules, or stops listing mention markets.
5. **LibFrog data staleness**: Transcript data > 2 years old may not reflect current management communication patterns.

---

## 12. Methodology Notes

- **Focused filter**: edge >= 8c (LibFrog) / 12c (rolling), BR <= 50%, min history >= 10 (LibFrog) / 15 (rolling), max YES <= 50%
- **Excluded categories**: political_person
- **Fees**: $0.02 RT per contract
- **Slippage**: $0.01 assumed
- **Side**: Always NO
- **Rolling base rate**: mean(outcomes of all prior settled markets in canonical series). Updated AFTER evaluation.
- **LibFrog rates**: External transcript data, not look-ahead. Requires n_calls >= 10.
- **Series equivalences**: KXFEDMENTION → KXPOWELLMENTION, KXJPOWMENTION → KXPOWELLMENTION, KXTRUMPMENTIONB → KXTRUMPMENTION, KXSTARMERMENTIONB → KXSTARMERMENTION, KXTRUMPMENTIONDURATION → KXTRUMPMENTION
- **Per-trade Sharpe**: mean(PnL) / std(PnL), NOT annualized unless labeled.
- **Bootstrap**: 10,000 resamples, seed=42
- **Parameter grid**: 256 combos (4 values each for max_yes, edge_lf, edge_roll, min_hist_roll), all with exclude political_person
- **Walk-forward**: 60/40 chronological split + 3-fold chronological thirds