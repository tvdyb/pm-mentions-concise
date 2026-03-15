# PM Mentions Backtest Report — Fixed

*Generated 2026-03-15 16:47 from 20,252 settled markets.*

This backtest fixes two critical bugs in the original analysis:

1. **Entry price**: Uses VWAP (time-weighted average price with buffer) instead of `opening_price` (often 1c/99c first trades)
2. **Look-ahead bias**: Uses rolling base rates computed from prior settled markets only, instead of static rates computed from the entire dataset

LibFrog word-level rates are NOT look-ahead — they come from external transcript data and are used as-is.

---

## Original vs Fixed: Side-by-Side

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Original (opening_price + static rates) | 555 | 61.8% | $+0.1052 | $0.4235 | $+58.39 | 0.2484 | $9.15 | [$+0.0695, $+0.1398] |
| Fixed (VWAP 25% + rolling rates) | 3769 | 48.6% | $+0.0288 | $0.4600 | $+108.60 | 0.0626 | $20.38 | [$+0.0143, $+0.0433] |

**Delta**: +3214 trades, $-0.0764 mean PnL/trade, $+50.21 total PnL

*Annualized Sharpe estimate: 3.673 (assuming 3439 trades/year over 400 day range, sqrt(3439) = 58.6)*

---

## Entry Price Sensitivity (all use rolling base rates)

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| VWAP 25% buffer (primary) | 3769 | 48.6% | $+0.0288 | $0.4600 | $+108.60 | 0.0626 | $20.38 | [$+0.0143, $+0.0433] |
| VWAP 10% buffer | 3105 | 46.0% | $+0.0008 | $0.4444 | $+2.36 | 0.0017 | $47.49 | [$-0.0149, $+0.0164] |
| VWAP no buffer | 2101 | 34.7% | $-0.1150 | $0.3653 | $-241.65 | -0.3148 | $257.49 | [$-0.1304, $-0.0991] |

*VWAP 25% buffer strips the first and last 25% of trading time — closest to a realistic fill for someone scanning active markets. VWAP no buffer includes extreme early/late prints and is the harshest test.*

---

## Breakdown by Category

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| political_person | 1433 | 34.9% | $-0.0470 | $0.4604 | $-67.30 | -0.1020 | $88.59 | [$-0.0708, $-0.0226] |
| other | 1306 | 52.5% | $+0.0692 | $0.4687 | $+90.34 | 0.1476 | $11.38 | [$+0.0438, $+0.0948] |
| earnings | 811 | 68.4% | $+0.0959 | $0.4162 | $+77.74 | 0.2303 | $4.32 | [$+0.0667, $+0.1241] |
| sports | 219 | 41.6% | $+0.0357 | $0.4930 | $+7.82 | 0.0724 | $4.41 | [$-0.0284, $+0.1002] |

---

## Rate Source: LibFrog vs Rolling Series

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| rolling | 2961 | 43.2% | $+0.0106 | $0.4697 | $+31.48 | 0.0226 | $27.10 | [$-0.0063, $+0.0275] |
| libfrog | 808 | 68.4% | $+0.0955 | $0.4161 | $+77.13 | 0.2294 | $4.32 | [$+0.0670, $+0.1244] |

LibFrog-rated trades: 808 (21.4%) | Rolling series-rated: 2961 (78.6%)

---

## Breakdown by YES Price Bucket

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| 25-50% | 651 | 75.1% | $+0.1172 | $0.4276 | $+76.30 | 0.2741 | $3.62 | [$+0.0846, $+0.1488] |
| 5-25% | 218 | 96.3% | $+0.1152 | $0.1921 | $+25.11 | 0.5995 | $1.51 | [$+0.0877, $+0.1385] |
| 50-75% | 2900 | 39.1% | $+0.0025 | $0.4778 | $+7.19 | 0.0052 | $42.91 | [$-0.0145, $+0.0196] |

---

## Edge Decay (Chronological Splits)

### Halves

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| First half (2025-01-31 – 2025-12-11) | 1884 | 50.4% | $+0.0297 | $0.4494 | $+55.86 | 0.0660 | $15.64 | [$+0.0093, $+0.0496] |
| Second half (2025-12-11 – 2026-03-07) | 1885 | 46.8% | $+0.0280 | $0.4705 | $+52.74 | 0.0595 | $20.38 | [$+0.0070, $+0.0488] |

### Quarters

| Variant | N | Win Rate | Mean PnL | Std | Total PnL | Sharpe | Max DD | 95% CI |
|---------|---|----------|----------|-----|-----------|--------|--------|--------|
| Q1 (2025-01-31 – 2025-10-14) | 942 | 52.4% | $+0.0296 | $0.4348 | $+27.88 | 0.0681 | $15.64 | [$+0.0022, $+0.0575] |
| Q2 (2025-10-14 – 2025-12-11) | 942 | 48.4% | $+0.0297 | $0.4638 | $+27.98 | 0.0640 | $14.37 | [$+0.0004, $+0.0591] |
| Q3 (2025-12-11 – 2026-02-04) | 942 | 45.2% | $+0.0157 | $0.4654 | $+14.76 | 0.0337 | $20.38 | [$-0.0143, $+0.0445] |
| Q4 (2026-02-04 – 2026-03-07) | 943 | 48.4% | $+0.0403 | $0.4755 | $+37.98 | 0.0847 | $11.10 | [$+0.0099, $+0.0712] |

---

## Top and Bottom Series

### Best (>= 3 trades, by total PnL)

| Series | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| KXSURVIVORMENTION | 79 | 75% | $+0.234 | $+18.48 |
| KXNFLMENTION | 195 | 44% | $+0.061 | $+11.82 |
| KXSOUTHPARKMENTION | 61 | 90% | $+0.193 | $+11.76 |
| KXNCAABMENTION | 279 | 41% | $+0.036 | $+9.91 |
| KXSECPRESSMENTION | 357 | 43% | $+0.027 | $+9.67 |
| KXSTARMERMENTION | 55 | 64% | $+0.149 | $+8.21 |
| KXEARNINGSMENTIONNVDA | 36 | 78% | $+0.199 | $+7.17 |
| KXEARNINGSMENTIONGOOGL | 34 | 76% | $+0.169 | $+5.76 |
| KXLEAVITTMENTIONDURATION | 25 | 76% | $+0.218 | $+5.44 |
| KXEARNINGSMENTIONPLTR | 32 | 88% | $+0.164 | $+5.25 |

### Worst

| Series | N | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| KXEARNINGSMENTIONRY | 9 | 22% | $-0.247 | $-2.22 |
| KXEARNINGSMENTIONDAL | 8 | 25% | $-0.290 | $-2.32 |
| KXPSAKIMENTION | 7 | 0% | $-0.359 | $-2.52 |
| KXTRUMPMENTIONDURATION | 14 | 14% | $-0.246 | $-3.45 |
| KXTBPNMENTION | 11 | 9% | $-0.325 | $-3.58 |
| KXEARNINGSMENTIONNFLX | 24 | 38% | $-0.158 | $-3.78 |
| KXSNFMENTION | 24 | 21% | $-0.166 | $-4.00 |
| KXVANCEMENTION | 109 | 34% | $-0.054 | $-5.89 |
| KXTRUMPMENTIONB | 268 | 23% | $-0.151 | $-40.57 |
| KXTRUMPMENTION | 498 | 30% | $-0.082 | $-40.78 |

---

## Methodology Notes

- **Grid filter**: edge >= 10c, base rate <= 50%, min history >= 10, max YES price <= 75%
- **Fees**: $0.02 round-trip per contract
- **Slippage**: $0.01 assumed
- **Side**: Always NO
- **Rolling base rate**: For each market, `mean(outcomes of all prior settled markets in the canonical series)`. Market's own outcome added to rolling state AFTER evaluation.
- **LibFrog rates**: Used as-is for earnings word-level lookups (external transcript data, not derived from this market dataset). Requires n_calls >= 10.
- **Series equivalences**: KXFEDMENTION → KXPOWELLMENTION, KXJPOWMENTION → KXPOWELLMENTION, KXTRUMPMENTIONB → KXTRUMPMENTION, KXSTARMERMENTIONB → KXSTARMERMENTION, KXTRUMPMENTIONDURATION → KXTRUMPMENTION
- **Per-trade Sharpe**: mean(PnL) / std(PnL). NOT annualized unless explicitly labeled.
- **Bootstrap CI**: 10,000 resamples, seed=42