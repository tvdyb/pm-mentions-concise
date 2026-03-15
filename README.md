# PM Mentions Strategy

Prediction market mention strategy for Kalshi — buy NO when YES is overpriced relative to historical base rates.

## Files

| File | Purpose |
|------|---------|
| `shared.py` | Shared utilities: base rate lookup, Kalshi API, position sizing, settlement PnL, category classification |
| `pm_mentions_strategy.py` | Original strategy — single edge threshold, max YES 75c |
| `focused_strategy.py` | Focused strategy — tiered thresholds, max YES 50c, excludes political_person |
| `base_rates.json` | 203 series-level + ~1,700 word-level LibFrog transcript rates |
| `backtest.py` | Honest backtest: VWAP entry + rolling base rates (no look-ahead) |
| `focused_backtest.py` | Focused strategy backtest with OOS validation, parameter grid, category ablation |
| `tests.py` | Unit tests for edge cases (VZ bug, category defaults, None strike words, etc.) |
| `strategy_writeup.md` | Comprehensive writeup covering both strategies |
| `data/kalshi_all_series.json` | 20,252 settled markets with VWAP prices |

## Quick Start

```bash
pip install requests numpy
```

```python
from shared import load_base_rates, fetch_active_kalshi, size_position
from focused_strategy import compute_signals, FOCUSED_CONFIG

rates = load_base_rates("base_rates.json")
markets = fetch_active_kalshi(rates)
signals = compute_signals(markets, rates)

for sig in signals:
    n_contracts, cost = size_position(sig, capital=1000, config=FOCUSED_CONFIG)
    print(f"{sig['ticker']}: {n_contracts} NO @ ${cost:.2f} "
          f"(rate_source={sig['rate_source']})")
```

## Two Strategies

### Original (`pm_mentions_strategy.py`)
- Edge >= 10c, BR <= 50%, max YES 75c, min 10 history
- Honest backtest: Sharpe 0.063, 52.6% win rate

### Focused (`focused_strategy.py`)
- Tiered edge: 8c (LibFrog) / 12c (rolling series)
- Max YES 50c, excludes political_person category
- Min history: 10 (LibFrog) / 15 (rolling)
- Honest backtest: Sharpe 0.315, 55.2% win rate, positive OOS

See `strategy_writeup.md` for the full analysis.

## Running Backtests

```bash
python backtest.py --save          # writes backtest_report.md
python focused_backtest.py --save  # writes focused_backtest_report.md
```

## Running Tests

```bash
python -m pytest tests.py -v
```

## Legacy Files

- `optimized_strategy_report.pdf` — earlier backtest with inflated numbers (pre-VWAP fix). Superseded by `strategy_writeup.md`.
