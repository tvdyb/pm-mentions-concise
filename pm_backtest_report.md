# PM Mentions Polymarket Backtest Report

*Generated 2026-03-16 15:58 from 9,999 resolved markets in 622 events.*

## Methodology

Since CLOB price history is unavailable for old resolved markets, this backtest uses two approaches:

1. **Event-level portfolio**: Buy NO on all words in each event at the rolling speaker base rate. Profitable when fewer words resolve YES than the base rate predicts.
2. **Market-level simulation**: For each resolved market, simulate entry at hypothetical YES prices (base_rate + edge). Tests whether the strategy would have been profitable at various edge thresholds.

Both use rolling speaker base rates computed from all prior resolved events (no look-ahead). Minimum 20 prior resolved markets per speaker before trading.

## Event-Level Results

- Events tested: 458
- Profitable: 212/458 (46.3%)
- Mean PnL: $+0.0046
- Sharpe: 0.023
- 95% CI: [$-0.0149, $+0.0233]

## Market-Level Simulation

| Edge Threshold | N | Win Rate | Mean PnL | Sharpe | 95% CI |
|---|---|---|---|---|---|
| 4% | 7902 | 57.2% | $+0.0405 | 0.082 | [$+0.0292, $+0.0513] |
| 6% | 7824 | 57.3% | $+0.0610 | 0.123 | [$+0.0499, $+0.0718] |
| 8% | 7681 | 57.5% | $+0.0806 | 0.163 | [$+0.0694, $+0.0916] |
| 10% | 7374 | 57.6% | $+0.0984 | 0.199 | [$+0.0875, $+0.1097] |
| 15% | 3945 | 57.9% | $+0.1234 | 0.250 | [$+0.1081, $+0.1388] |
| 20% | 1125 | 63.1% | $+0.1297 | 0.266 | [$+0.1009, $+0.1577] |
