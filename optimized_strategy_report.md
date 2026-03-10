# Optimized Strategy Report

*Generated 2026-03-10 11:46 from raw market data*

---

## Executive Summary

This report compares the **optimized** grid filter (excluding earnings markets and capping YES price at 75%) against the baseline and other variants.

### Optimized vs Baseline

| Metric | Baseline | Optimized | Delta |
|--------|--------:|----------:|------:|
| Trades | 1,443 | 1,248 | -195 |
| Mean PnL | $+0.1089 | $+0.1249 | $+0.0160 |
| Sharpe | 0.363 | 0.449 | +0.086 |
| Win Rate | 71.3% | 88.4% | +17.1pp |
| Total PnL | $+157.1 | $+155.9 | $-1.2 |
| Max Drawdown | $5.9 | $4.6 | $-1.3 |
| 95% CI | [+0.0930, +0.1243] | [+0.1093, +0.1401] | - |
| CI excl zero | Yes | Yes | - |

The optimized strategy **improves Sharpe by +0.086** while reducing trade count by 195. The exclusion of earnings markets and high-YES-price markets removes noise and concentrates on higher-quality trades.

---

## 1. Optimized Strategy Statistics

Parameters: edge >= 10c, base_rate <= 50%, min_history >= 10, max YES price <= 75%, earnings excluded.

| Metric | Value |
|--------|------:|
| Trades | 1,248 |
| Total PnL | $+155.9 |
| Mean PnL/trade | $+0.1249 |
| Std dev | $0.2786 |
| Sharpe ratio | 0.449 |
| Win rate | 88.4% |
| Max drawdown | $4.6 |
| Max consecutive losses | 7 |
| Bootstrap 95% CI | [+0.1093, +0.1401] |
| CI excludes zero | Yes |
| Series traded | 38 |

## 2. Category Breakdown

Earnings markets are excluded in the optimized strategy (should show 0).

| Category | N | Mean PnL | Sharpe | Win Rate | 95% CI |
|----------|--:|--------:|-------:|---------:|--------|
| media_word | 8 | $+0.2112 | 1.546 | 100% | - |
| other | 347 | $+0.1186 | 0.422 | 88% | [+0.088, +0.148] |
| political_person | 385 | $+0.0864 | 0.284 | 84% | [+0.055, +0.117] |
| sports_word | 508 | $+0.1571 | 0.619 | 92% | [+0.135, +0.179] |
| earnings_word | 0 | - | - | - | - |

## 3. Price Bucket Breakdown

With max YES price capped at 75%, the 75-95% bucket should show 0 trades.

| Bucket | N | Mean PnL | Sharpe | Win Rate |
|--------|--:|--------:|-------:|---------:|
| 5-25% | 735 | $+0.0984 | 0.790 | 99% |
| 25-50% | 343 | $+0.1871 | 0.524 | 85% |
| 50-75% | 170 | $+0.1144 | 0.235 | 51% |
| 75-95% | 0 | - | - | - |

## 4. Edge Decay Analysis

Does the edge compress over time?

### Halves

| Period | N | Mean PnL | Sharpe | Win Rate |
|--------|--:|--------:|-------:|---------:|
| First half | 624 | $+0.1031 | 0.347 | 86% |
| Second half | 624 | $+0.1468 | 0.571 | 91% |

### Quarters

| Period | N | Mean PnL | Sharpe | Win Rate |
|--------|--:|--------:|-------:|---------:|
| Q1 | 312 | $+0.0901 | 0.299 | 85% |
| Q2 | 312 | $+0.1161 | 0.396 | 87% |
| Q3 | 312 | $+0.1173 | 0.430 | 88% |
| Q4 | 312 | $+0.1763 | 0.744 | 93% |

**Edge appears stable or improving.** Latest quarter Sharpe (0.744) exceeds earliest (0.299).

## 5. Event Clustering Risk

Markets within the same event share correlated outcomes.

| Metric | Value |
|--------|------:|
| Unique events traded | 278 |
| Avg markets per event | 4.5 |
| Effective N (event-level) | 278 |
| Event-level Sharpe | 0.631 |

Worst single event: `KXNBAMENTION-26JAN24GSWMIN` -- $-4.36 across 12 markets

## 6. Series Concentration

| Metric | Value |
|--------|------:|
| Series traded | 38 |
| Top 5 series PnL | $+106.2 |
| Top 5 % of absolute PnL | 67% |

| Series | PnL |
|--------|----:|
| KXNCAABMENTION | $+59.2 |
| KXSECPRESSMENTION | $+14.5 |
| KXVANCEMENTION | $+11.9 |
| KXNBAMENTION | $+11.4 |
| KXSURVIVORMENTION | $+9.1 |

## 7. Strategy Variant Comparison

| Variant | Earnings | Max YES | Edge | BR Cap | N | Mean PnL | Sharpe | Win Rate | CI |
|---------|:--------:|--------:|-----:|-------:|--:|--------:|-------:|---------:|------|
| Baseline | Included | 95% | 10c | 50% | 1,443 | $+0.1089 | 0.363 | 71% | [+0.093, +0.124] |
| Optimized | Excluded | 75% | 10c | 50% | 1,248 | $+0.1249 | 0.449 | 88% | [+0.109, +0.140] |
| Aggressive | Excluded | 75% | 15c | 30% | 829 | $+0.1488 | 0.550 | 90% | [+0.130, +0.167] |
| Conservative | Excluded | 50% | 10c | 40% | 1,297 | $+0.1196 | 0.513 | 94% | [+0.107, +0.132] |

**Best Sharpe: Aggressive** (0.550 on 829 trades)

## 8. Parameter Sensitivity Grid

All combos exclude earnings markets. Shows Sharpe (N trades).

### BR cap = 30%

| Edge \ Max YES | 50% | 60% | 75% | 95% |
|----------------|-------:|-------:|-------:|-------:|
| 5c | 0.458 (1584) | 0.439 (1699) | 0.370 (1806) | 0.343 (1242) |
| 8c | 0.471 (1513) | 0.448 (1614) | 0.422 (1507) | 0.353 (1154) |
| 10c | 0.513 (1297) | 0.494 (1386) | 0.447 (1246) | 0.396 (1036) |
| 12c | 0.550 (1117) | 0.516 (1111) | 0.499 (1053) | 0.409 (865) |
| 15c | 0.670 (692) | 0.614 (810) | 0.550 (829) | 0.423 (625) |

### BR cap = 40%

| Edge \ Max YES | 50% | 60% | 75% | 95% |
|----------------|-------:|-------:|-------:|-------:|
| 5c | 0.458 (1584) | 0.440 (1700) | 0.375 (1850) | 0.277 (2049) |
| 8c | 0.471 (1513) | 0.448 (1614) | 0.424 (1520) | 0.329 (1583) |
| 10c | 0.513 (1297) | 0.494 (1386) | 0.449 (1248) | 0.365 (1393) |
| 12c | 0.550 (1117) | 0.516 (1111) | 0.501 (1055) | 0.387 (1161) |
| 15c | 0.670 (692) | 0.614 (810) | 0.550 (829) | 0.420 (880) |

### BR cap = 50%

| Edge \ Max YES | 50% | 60% | 75% | 95% |
|----------------|-------:|-------:|-------:|-------:|
| 5c | 0.458 (1584) | 0.440 (1700) | 0.375 (1850) | 0.270 (2194) |
| 8c | 0.471 (1513) | 0.448 (1614) | 0.424 (1520) | 0.334 (1626) |
| 10c | 0.513 (1297) | 0.494 (1386) | 0.449 (1248) | 0.374 (1420) |
| 12c | 0.550 (1117) | 0.516 (1111) | 0.501 (1055) | 0.397 (1177) |
| 15c | 0.670 (692) | 0.614 (810) | 0.550 (829) | 0.427 (886) |

**Best combo (N >= 20): edge=15c, BR<=30%, maxYES=50%** -- Sharpe 0.670 on 692 trades

## 9. Capacity Estimate

| Metric | Value |
|--------|------:|
| Total universe volume | $445,869,811 |
| Optimized-traded volume | $4,498,381 |
| Max capital (5% of volume) | $224,919 |
| Trades/day (historical avg) | 3.1 |
| Trades/week | 22 |
| Projected annual trades | 1142 |
| Projected annual PnL | $+143 |

## 10. Go/No-Go Recommendation

### Recommendation: CAUTIOUS GO

The optimized grid filter shows a **statistically significant edge** with Sharpe 0.449 and bootstrap CI that excludes zero. Win rate of 88% on 1,248 trades supports deployment at small scale.

**The optimized variant improves on the baseline** (Sharpe 0.449 vs 0.363). Recommend using the optimized parameters for live deployment.

**Minimum bankroll:** $500-$1,000 for paper trading; $2,000-$5,000 for real capital deployment to withstand drawdown streaks.

## 11. Kill Criteria

1. **Stop if cumulative PnL falls below -$100** on a $1,000 bankroll (10% drawdown)
2. **Stop if win rate drops below 55%** after 50+ trades
3. **Stop if Sharpe drops below 0.15** on a rolling 100-trade window
4. **Review quarterly** -- if edge decays below 5c average, reduce sizing or halt
5. **Stop if 3 consecutive events produce losses** exceeding $50 total

**Key risks:**

- **Event clustering**: A single bad event can produce correlated losses across 4 simultaneous positions
- **Series concentration**: Top 5 series account for 67% of absolute PnL
- **Edge decay**: Markets may become more efficient over time
- **Liquidity**: Some markets have thin order books; slippage may exceed 1c
- **Reduced trade count**: Optimized filters reduce N, increasing variance of estimates

---

*Report computed from 20,193 settled markets across 203 series. Date range: 2025-01-30 to 2026-03-07. Fee: $0.02/RT. Slippage: 1c.*