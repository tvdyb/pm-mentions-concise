# PM Mentions Strategy — Handoff Package

Self-contained prediction market mention strategy for integration into your paper trading infrastructure.

## What's Here

| File | Purpose |
|------|---------|
| `pm_mentions_strategy.py` | Single-file strategy module — all logic, no external deps beyond `requests` + `numpy` |
| `base_rates.json` | Historical base rates: 203 series-level + ~1,700 word-level LibFrog transcript rates |
| `strategy_report.md` | Full strategy report — explains everything from scratch, includes updated backtest with LibFrog |
| `optimized_strategy_report.pdf` | Earlier backtest report with parameter sensitivity analysis (pre-LibFrog) |
| `optimized_strategy_report.md` | Same earlier report in markdown |

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
    print(f"{sig['ticker']}: {n_contracts} NO @ ${cost:.2f} (rate_source={sig['rate_source']})")

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
- Min history: >= 10 settled markets in series (or n_calls for LibFrog)
- Max YES price: 75% (skip high-YES markets)
- Earnings markets are now tradeable via LibFrog word-level rates
- Quarter-Kelly sizing, 5% max per position, 80% max total exposure

## LibFrog Integration

Word-level earnings transcript base rates from [LibFrog](https://libfrog.com) are baked into `base_rates.json` at rest — no runtime API dependency.

### base_rates.json format

The file contains two kinds of entries:

**Series-level** (keyed by series ticker):
```json
"KXEARNINGSMENTIONAAPL": {
  "base_rate": 0.657534,
  "n_markets": 73
}
```

**Word-level** (keyed as `"SERIES|word"`, source: LibFrog):
```json
"KXEARNINGSMENTIONAAPL|iPhone": {
  "base_rate": 0.78,
  "n_calls": 74,
  "source": "libfrog"
}
```

### How word-level rates are used

In `compute_signals()`, for each market:

1. Look up `"SERIES|strike_word"` in the rates dict
2. If found and `n_calls >= 10`, use it as the base rate (`rate_source: "libfrog"`)
3. If the strike word contains `" / "` (e.g., `"AI / Artificial Intelligence"`), try each part
4. Fall back to the series-level rate (`rate_source: "series"`)

Each signal dict includes a `rate_source` field (`"libfrog"` or `"series"`) so downstream systems can see which rate was used.

### Data sources

Word-level rates are merged from two LibFrog data files (matched preferred over generic), filtered to entries where `base_rate` is not null and `n_calls >= 5`.

## Backtest Results (555 trades, 20,252 settled markets)

| Metric | Value |
|--------|-------|
| Trades | 555 (408 political/other + 145 earnings LibFrog + 2 earnings series) |
| Win rate | 61.8% |
| Mean PnL/contract | +$0.105 |
| Annualized Sharpe | 3.95 |
| Bootstrap 95% CI | [$0.070, $0.140] |
| Max drawdown | $9.15 |
| Total PnL (1 per trade) | +$58.39 |

LibFrog-rated earnings trades alone: **82.8% win rate, Sharpe 5.35, +$15.23 total**.

See `strategy_report.md` for the full breakdown including edge buckets, price buckets, company-level analysis, worked examples, and kill criteria.

## Integration Notes

- `fetch_active_kalshi()` hits the public Kalshi API (no auth needed for market data). Replace with your own data source if you already have one.
- `compute_signals()` is the core filter — feed it any list of market dicts with `{ticker, series, yes_mid, source, event_ticker}` fields. Include `strike_word` for word-level LibFrog lookups on earnings markets.
- `size_position()` returns `(n_contracts, total_cost)` — enforce your own exposure limits on top.
- `CONFIG` dict at the top of `pm_mentions_strategy.py` has all tunable parameters.
- Update `base_rates.json` periodically as new markets settle to keep base rates current. Re-run the LibFrog merge script to refresh word-level rates.
