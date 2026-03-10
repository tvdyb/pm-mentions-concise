# PM Mentions Strategy — Handoff Package

Self-contained prediction market mention strategy for integration into your paper trading infrastructure.

## What's Here

| File | Purpose |
|------|---------|
| `pm_mentions_strategy.py` | Single-file strategy module — all logic, no external deps beyond `requests` + `numpy` |
| `base_rates.json` | Historical base rates for 203 mention series (from 20,193 settled markets) |
| `optimized_strategy_report.pdf` | Full backtest report with parameter sensitivity analysis |
| `optimized_strategy_report.md` | Same report in markdown |

## Quick Start

```bash
pip install requests numpy
```

```python
from pm_mentions_strategy import (
    load_base_rates,
    fetch_active_kalshi,
    compute_signals,
    size_position,
    compute_settlement_pnl,
    check_settlement,
)

rates = load_base_rates("base_rates.json")
markets = fetch_active_kalshi(rates)
signals = compute_signals(markets, rates)

for sig in signals:
    n_contracts, cost = size_position(sig, capital=1000)
    # Submit to your execution system:
    #   side=NO, ticker=sig["ticker"], n=n_contracts, cost=cost
    print(f"{sig['ticker']}: {n_contracts} NO @ ${cost:.2f}")

# Later, check settlement:
result = check_settlement("TICKER-HERE")
if result:
    pnl = compute_settlement_pnl(
        entry_price=sig["yes_mid"], result=result, n_contracts=n_contracts
    )
```

## Strategy Summary

**Grid filter: buy NO on mention markets where YES is overpriced vs historical base rates.**

- Edge threshold: >= 10c (YES mid - base rate)
- Base rate cap: <= 50%
- Min history: >= 10 settled markets in series
- Max YES price: 75% (skip high-YES markets)
- Earnings excluded (negative edge)
- Quarter-Kelly sizing, 5% max per position, 80% max total exposure

## Backtest Results (1,248 trades)

| Metric | Value |
|--------|-------|
| Mean PnL/contract | +$0.125 |
| Win rate | 88.4% |
| Sharpe | 0.449 |
| Bootstrap 95% CI | [$0.109, $0.140] |
| Max drawdown | $4.6 |

See `optimized_strategy_report.pdf` for full details including parameter sensitivity, edge decay analysis, and kill criteria.

## Integration Notes

- `fetch_active_kalshi()` hits the public Kalshi API (no auth needed for market data). Replace with your own data source if you already have one.
- `compute_signals()` is the core filter — feed it any list of market dicts with `{ticker, series, yes_mid, source, event_ticker}` fields.
- `size_position()` returns `(n_contracts, total_cost)` — enforce your own exposure limits on top.
- `CONFIG` dict at the top of `pm_mentions_strategy.py` has all tunable parameters.
- Update `base_rates.json` periodically as new markets settle to keep base rates current.
