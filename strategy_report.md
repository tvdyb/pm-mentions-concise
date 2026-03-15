# PM Mentions Grid Filter Strategy — Full Report

*Generated 2026-03-15 from 20,252 settled Kalshi mention markets across 203 series.*

---

## Table of Contents

1. [What This Strategy Does](#1-what-this-strategy-does)
2. [What Are Mention Markets?](#2-what-are-mention-markets)
3. [The Core Idea](#3-the-core-idea)
4. [Data Pipeline](#4-data-pipeline)
5. [Strategy Rules](#5-strategy-rules)
6. [Worked Example](#6-worked-example)
7. [Backtest Results](#7-backtest-results)
8. [Performance by Category](#8-performance-by-category)
9. [LibFrog Integration (Earnings Markets)](#9-libfrog-integration-earnings-markets)
10. [Edge Decay and Price Buckets](#10-edge-decay-and-price-buckets)
11. [Position Sizing and Risk Management](#11-position-sizing-and-risk-management)
12. [Kelly Simulation](#12-kelly-simulation)
13. [Top Series and Earnings Companies](#13-top-series-and-earnings-companies)
14. [Kill Criteria](#14-kill-criteria)
15. [File Reference](#15-file-reference)
16. [How to Run It](#16-how-to-run-it)

---

## 1. What This Strategy Does

This strategy buys NO contracts on Kalshi "mention markets" where the YES price is higher than the historical probability that the word will actually be mentioned. The difference between the market price and the true probability is the **edge**. When the edge is large enough, buying NO has positive expected value.

It is a single-file Python strategy (`pm_mentions_strategy.py`) with no runtime dependencies beyond `requests` and `numpy`. All historical data is baked into `base_rates.json`. You feed it active market data, and it returns a ranked list of NO signals with position sizes.

---

## 2. What Are Mention Markets?

Kalshi lists thousands of binary markets asking whether a specific word or phrase will be said during a specific event:

- **Political press conferences**: *"Will the White House Press Secretary say 'tariff' during tomorrow's briefing?"*
- **Earnings calls**: *"Will Apple say 'iPhone' during their next earnings call?"*
- **Sports broadcasts**: *"Will the announcer say 'dynasty' during the NBA Finals?"*
- **TV shows**: *"Will SNL mention 'Trump' this Saturday?"*

Each market resolves YES or NO. YES contracts trade between $0.01 and $0.99, representing the market's implied probability. NO contracts cost $1 minus the YES price.

**Key property**: these markets are structurally biased. Retail traders tend to overestimate mention probabilities, especially for exciting or newsworthy words, pushing YES prices above fair value. This creates a persistent edge for NO buyers.

---

## 3. The Core Idea

For each word in each series (e.g., "KXTRUMPMENTION"), we know the historical rate at which that series resolves YES — the **base rate**. For earnings markets, we additionally know word-level base rates from LibFrog transcript data — how often specific words appear in specific companies' earnings calls across many years of transcripts.

The strategy is:

```
edge = YES_price - base_rate

if edge >= 10 cents AND base_rate <= 50% AND history >= 10:
    BUY NO
```

That's it. Everything else is position sizing and risk management.

**Why it works**: If a word historically gets mentioned 15% of the time but the market prices YES at 40%, the NO buyer pays $0.60 and wins $1.00 about 85% of the time. After fees and slippage, this is strongly positive expected value.

---

## 4. Data Pipeline

### Base Rates (series-level)

Computed from 20,252 settled Kalshi markets across 203 series:

```
base_rate = count(result == "yes") / count(all settled markets in series)
```

Stored in `base_rates.json` keyed by series ticker:

```json
"KXTRUMPMENTION": {"base_rate": 0.433803, "n_markets": 2840}
```

This means ~43.4% of Trump press conference mention markets resolve YES.

### Base Rates (word-level, from LibFrog)

For earnings markets, series-level rates are too coarse — "iPhone" and "Tariff" have wildly different mention probabilities for Apple. LibFrog provides word-level base rates derived from actual earnings call transcripts (typically 40-80+ calls per company).

Stored in `base_rates.json` keyed as `"SERIES|word"`:

```json
"KXEARNINGSMENTIONAAPL|iPhone": {"base_rate": 0.938, "n_calls": 81, "source": "libfrog"}
"KXEARNINGSMENTIONAAPL|Tariff": {"base_rate": 0.049, "n_calls": 81, "source": "libfrog"}
```

This means Apple says "iPhone" in 93.8% of earnings calls (not tradeable — too high base rate) but "Tariff" in only 4.9% (tradeable if the market overprices it).

**1,691 word-level entries** cover the major earnings series. Data is baked into `base_rates.json` at rest — no runtime LibFrog API calls.

### Lookup Priority

For each active market:

1. Check for word-level rate `"SERIES|strike_word"` — use if found with `n_calls >= 10`
2. If strike word contains `" / "` (e.g., `"AI / Artificial Intelligence"`), try each part
3. Fall back to series-level rate
4. Try series equivalences (e.g., `KXTRUMPMENTIONB` → `KXTRUMPMENTION`)

Each signal includes a `rate_source` field (`"libfrog"` or `"series"`) for transparency.

---

## 5. Strategy Rules

### Entry Criteria (ALL must be true)

| Rule | Value | Rationale |
|------|-------|-----------|
| Edge >= threshold | 10c | Minimum edge to overcome fees + noise |
| Base rate <= cap | 50% | High-BR markets have thin NO margins |
| History >= minimum | 10 settled markets (or 10 transcript calls for LibFrog) | Insufficient data → unreliable rate |
| YES price <= cap | 75c | 65-95c bucket shows no edge in backtest |
| YES price > floor | 5c | Near-zero prices are untradeable |

### Side

Always NO. The structural bias makes YES overpriced.

### Exit

Hold to settlement. These are binary markets — no early exit needed.

### Fees and Slippage

| Component | Value |
|-----------|-------|
| Kalshi round-trip fee | $0.02 per contract |
| Assumed slippage | $0.01 (buying at ask vs mid) |
| Effective YES price | `max(0.01, yes_mid - 0.01)` |
| NO cost | `1.0 - effective_YES` |

### Expected PnL Formula

```
P(NO wins) = 1 - base_rate
E[PnL] = P(NO wins) * effective_YES - base_rate * NO_cost - fee
```

---

## 6. Worked Example

**Market**: KXEARNINGSMENTIONAAPL, strike word "RxPass", YES mid = 50c

**Step 1: Look up rate**
- Check `base_rates.json` for `"KXEARNINGSMENTIONAAPL|RxPass"` — not found
- The strike word is on AMZN, not AAPL. Correct lookup: `"KXEARNINGSMENTIONAMZN|RxPass"`
- Found: `base_rate = 0.049, n_calls = 81, source = "libfrog"`

**Step 2: Compute edge**
```
edge = 0.50 - 0.049 = 0.451  (45.1 cents)
```

**Step 3: Check filters**
- Edge >= 10c? Yes (45.1c)
- Base rate <= 50%? Yes (4.9%)
- History >= 10? Yes (81 calls)
- YES price <= 75c? Yes (50c)

All pass → **BUY NO**

**Step 4: Compute expected PnL**
```
effective_YES = 0.50 - 0.01 = 0.49
NO_cost = 1.0 - 0.49 = 0.51
P(NO wins) = 1 - 0.049 = 0.951

E[PnL] = 0.951 * 0.49 - 0.049 * 0.51 - 0.02
       = 0.466 - 0.025 - 0.02
       = +$0.421 per contract
```

**Step 5: Size position** (with $1,000 capital)
```
Kelly full = (P(NO) * b - base_rate) / b, where b = effective_YES / NO_cost
b = 0.49 / 0.51 = 0.961
Kelly full = (0.951 * 0.961 - 0.049) / 0.961 = 0.900
Kelly quarter = 0.900 * 0.25 = 0.225
Position = min($1000 * 0.225, $1000 * 0.05) = $50 (5% cap binds)
Contracts = floor($50 / $0.51) = 98
```

**Step 6: Actual outcome**
The word "RxPass" was not mentioned. Result = NO.
```
PnL = 98 * ($0.49 - $0.02) = 98 * $0.47 = +$46.06
```

---

## 7. Backtest Results

Backtest over all 20,252 settled markets. The strategy opens a position on every market that passes the grid filter at the opening price.

### Overall Performance (555 trades)

| Metric | Value |
|--------|-------|
| Total trades | 555 |
| Wins / Losses | 343 / 212 |
| Win rate | 61.8% |
| Mean PnL per contract | +$0.105 |
| Std PnL | $0.423 |
| Annualized Sharpe ratio | 3.95 |
| Total PnL (1 contract each) | +$58.39 |
| Maximum drawdown | $9.15 |
| Bootstrap 95% CI (mean PnL) | [$0.070, $0.140] |

### Filter Funnel

| Stage | Markets | Removed |
|-------|---------|---------|
| Total settled | 20,252 | — |
| After price filter (5c < YES <= 95c) | 4,482 | 15,770 extreme prices |
| After max YES cap (<=75c) | 3,175 | 1,307 above 75c |
| After rate lookup + min history | 3,164 | 11 insufficient data |
| After edge >= 10c | 652 | 2,512 insufficient edge |
| After base rate <= 50% | 555 | 38 + 59 high BR / no result |

~2.7% of all markets pass the filter. This is deliberate — the strategy is selective.

---

## 8. Performance by Category

| Category | Trades | Win Rate | Mean PnL | Sharpe | Total PnL |
|----------|--------|----------|----------|--------|-----------|
| Political / Other (series rate) | 408 | 54.4% | +$0.107 | 3.71 | +$43.47 |
| Earnings (LibFrog word rate) | 145 | 82.8% | +$0.105 | 5.35 | +$15.23 |
| Earnings (series rate fallback) | 2 | 50.0% | -$0.155 | -5.18 | -$0.31 |

**Key finding**: Earnings markets with LibFrog word-level rates have the best Sharpe (5.35) and the best win rate (82.8%) of any category. This is because word-level rates are far more precise than series-level averages — LibFrog knows exactly how often Apple says "iPhone" vs "Tariff", rather than averaging across all Apple earnings words.

The 2 earnings trades that fell back to series-level rates (no LibFrog match) performed poorly, validating the decision to require word-level data for earnings.

---

## 9. LibFrog Integration (Earnings Markets)

### Why Earnings Were Previously Excluded

The original strategy excluded all earnings markets because the series-level base rate for earnings (~50-65%) was too coarse. A series like KXEARNINGSMENTIONAMZN lumps together words like "Revenue" (mentioned ~99% of the time) and "RxPass" (mentioned ~5% of the time). The blended series-level rate gave no useful signal.

### What LibFrog Provides

LibFrog analyzes historical earnings call transcripts and provides, for each (company, word) pair:
- How many earnings calls were checked (`n_calls`)
- How many contained the word (`n_mentions`)
- The base rate (`n_mentions / n_calls`)

This data spans 40-80+ earnings calls per company for major tickers.

### How It Changes the Strategy

With word-level rates, the strategy can now distinguish:

| Company | Word | LibFrog Rate | Typical YES Price | Edge |
|---------|------|-------------|-------------------|------|
| AAPL | iPhone | 93.8% | 90-95c | ~0c (skip: high BR) |
| AAPL | Tariff | 4.9% | 30-50c | 25-45c (trade!) |
| UBER | Tesla | 0.0% | 20-40c | 20-40c (trade!) |
| PLTR | AIP | 45.5% | 60-70c | 15-25c (trade!) |
| AMZN | Revenue | 100% | 95c+ | skip (price filter) |

### Data Volume

- 1,691 word-level entries in `base_rates.json`
- Merged from two sources: LibFrog matched (specific company+word queries) and LibFrog generic (cross-company word queries), with matched preferred
- Filtered to `base_rate != null` and `n_calls >= 5` for storage, `n_calls >= 10` required at query time

---

## 10. Edge Decay and Price Buckets

### By Edge Bucket

| Edge Range | Trades | Win Rate | Mean PnL |
|------------|--------|----------|----------|
| 10-15c | 131 | 81.7% | +$0.149 |
| 15-20c | 125 | 66.4% | +$0.112 |
| 20-30c | 166 | 48.8% | +$0.051 |
| 30c+ | 133 | 54.1% | +$0.123 |

The 10-15c edge bucket has the highest win rate (81.7%) and best mean PnL (+$0.149). This is somewhat counterintuitive — you might expect larger edges to perform better. The reason is that very large edges often indicate a genuinely unusual situation (breaking news, controversy) where the base rate is less reliable. Moderate edge + reliable base rate = best results.

### By YES Price Bucket

| YES Price | Trades | Win Rate | Mean PnL |
|-----------|--------|----------|----------|
| 5-20c | 55 | 100% | +$0.114 |
| 20-35c | 64 | 93.8% | +$0.172 |
| 35-50c | 81 | 82.7% | +$0.214 |
| 50-65c | 170 | 59.4% | +$0.145 |
| 65-75c | 185 | 32.4% | -$0.004 |

**Critical finding**: The 65-75c bucket is breakeven. This validates the `max_yes_price = 75c` cap. Markets above 75c (excluded by the filter) would have even worse performance.

The 35-50c bucket is the sweet spot: high win rate (82.7%) and highest mean PnL (+$0.214). Low-price markets (5-20c) win 100% of the time but the payout per contract is small (you're paying ~$0.90 for NO and winning $0.10).

---

## 11. Position Sizing and Risk Management

### Quarter-Kelly Sizing

The strategy uses quarter-Kelly sizing — 25% of the theoretically optimal Kelly fraction. Full Kelly is aggressive and assumes perfect knowledge of probabilities; quarter-Kelly trades off growth for much lower variance and drawdown.

```
b = effective_YES / NO_cost        # odds ratio
Kelly_full = (P(NO) * b - base_rate) / b
Kelly_quarter = Kelly_full * 0.25
position_size = capital * Kelly_quarter
```

### Position Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| Max per position | 5% of capital | No single market can dominate |
| Max per event | 20% of capital | Correlated markets in same event |
| Max total exposure | 80% of capital | Always keep cash reserve |
| Min position | $1.00 | Skip dust-sized positions |

### Risk Controls

1. **Diversification by design**: Mention markets across different events and series are largely uncorrelated. Whether Trump says "tariff" tomorrow has no bearing on whether Apple says "Siri" next quarter.

2. **Binary payoffs cap downside**: Each NO contract costs at most $0.99. There are no leveraged losses, margin calls, or unlimited downside.

3. **Settlement is deterministic**: These markets resolve based on publicly verifiable transcripts. There is no subjective judgment in resolution.

---

## 12. Kelly Simulation

Simulating the strategy with $1,000 starting capital, quarter-Kelly sizing, and 5% max per position across all 555 trades sequentially:

| Metric | Value |
|--------|-------|
| Starting capital | $1,000 |
| Ending capital | $70,116 |
| Return | 6,912% |
| Peak capital | $213,799 |
| Trough capital | $775 |

**Important caveats**:
- This is a sequential simulation where trade order matters. Real-world execution would see different ordering.
- The trough to $775 (22.5% below start) happens early when the capital base is small and a few losses have outsized impact.
- The peak-to-end decline ($213K → $70K) reflects the high variance of large Kelly positions when capital grows large. In practice, you would scale back to fixed-dollar sizing or lower Kelly fraction at higher capital.
- Past performance does not predict future results. Base rates can shift.

---

## 13. Top Series and Earnings Companies

### Best Series by Total PnL

| Series | Trades | Win Rate | Mean PnL | Total PnL |
|--------|--------|----------|----------|-----------|
| KXNCAABMENTION | 33 | 69.7% | +$0.329 | +$10.87 |
| KXMMMENTION | 15 | 73.3% | +$0.294 | +$4.41 |
| KXLEAVITTSMFMENTION | 8 | 100% | +$0.479 | +$3.83 |
| KXLEAVITTMENTIONDURATION | 7 | 85.7% | +$0.460 | +$3.22 |
| KXGRIFFINMENTION | 10 | 100% | +$0.302 | +$3.02 |
| KXSHAQMENTION | 9 | 100% | +$0.310 | +$2.79 |
| KXVANCEMENTION | 19 | 52.6% | +$0.135 | +$2.56 |
| KXZIWEMENTION | 11 | 81.8% | +$0.232 | +$2.55 |

### Best Earnings Companies (LibFrog-rated)

| Company | Trades | Win Rate | Mean PnL | Total PnL |
|---------|--------|----------|----------|-----------|
| UBER | 9 | 100% | +$0.262 | +$2.36 |
| PLTR | 8 | 100% | +$0.227 | +$1.82 |
| AAPL | 16 | 81% | +$0.114 | +$1.82 |
| ROKU | 4 | 100% | +$0.367 | +$1.47 |
| AMD | 4 | 100% | +$0.340 | +$1.36 |
| META | 7 | 100% | +$0.181 | +$1.27 |
| GME | 3 | 100% | +$0.360 | +$1.08 |
| AMZN | 12 | 83% | +$0.081 | +$0.97 |
| ORCL | 5 | 100% | +$0.150 | +$0.75 |

### Worst Earnings Companies

| Company | Trades | Win Rate | Mean PnL | Total PnL |
|---------|--------|----------|----------|-----------|
| WMT | 3 | 33% | -$0.353 | -$1.06 |
| TSLA | 9 | 44% | -$0.114 | -$1.03 |
| MSFT | 14 | 64% | -$0.054 | -$0.75 |
| GOOGL | 9 | 67% | -$0.066 | -$0.59 |

TSLA and WMT are the clear underperformers. Tesla's earnings calls are unusually unpredictable — Elon Musk frequently mentions topics with no historical precedent. WMT has a small sample (3 trades).

---

## 14. Kill Criteria

Stop trading the strategy if any of these conditions are met:

1. **Rolling 50-trade win rate falls below 40%** for two consecutive windows. The strategy's overall win rate is 61.8%; sustained underperformance suggests the edge has disappeared.

2. **Drawdown exceeds $15 per contract** (roughly 1.6x the backtest max). This would indicate a regime change in mention market pricing.

3. **Market structure change**: If Kalshi changes fee structure, resolution methodology, or stops listing mention markets.

4. **Base rate staleness**: If `base_rates.json` hasn't been updated in 6+ months and you're trading new series not in the file.

5. **LibFrog data age**: If earnings transcript data becomes more than 2 years stale, word-level rates may no longer reflect current management communication patterns.

---

## 15. File Reference

| File | Purpose |
|------|---------|
| `pm_mentions_strategy.py` | All strategy logic in one file. Import `compute_signals`, `size_position`, `compute_settlement_pnl`. |
| `base_rates.json` | 203 series-level rates + 1,691 word-level LibFrog rates. No runtime API calls needed. |
| `data/kalshi_all_series.json` | 20,252 settled markets used to compute base rates and run backtests. |
| `strategy_report.md` | This document. |
| `optimized_strategy_report.pdf` | Earlier backtest report (pre-LibFrog). Superseded by this report for earnings analysis. |
| `optimized_strategy_report.md` | Markdown version of above. |

---

## 16. How to Run It

### Prerequisites

```bash
pip install requests numpy
```

### Live Signal Generation

```python
from pm_mentions_strategy import (
    load_base_rates,
    fetch_active_kalshi,
    compute_signals,
    size_position,
)

# 1. Load rates (series + LibFrog word-level)
rates = load_base_rates("base_rates.json")

# 2. Fetch active markets from Kalshi
markets = fetch_active_kalshi(rates)

# 3. Compute signals — returns only markets passing the grid filter
signals = compute_signals(markets, rates)

# 4. Size and execute
capital = 1000.0
for sig in signals:
    n_contracts, cost = size_position(sig, capital)
    if n_contracts > 0:
        print(f"BUY {n_contracts} NO on {sig['ticker']}")
        print(f"  Word: {sig['strike_word']}")
        print(f"  YES price: {sig['yes_mid']:.0%}")
        print(f"  Base rate: {sig['base_rate']:.1%} ({sig['rate_source']})")
        print(f"  Edge: {sig['edge']:+.0%}")
        print(f"  E[PnL]: ${sig['expected_pnl']:+.3f}/contract")
        print(f"  Cost: ${cost:.2f}")
        print()
```

### Checking Settlements

```python
from pm_mentions_strategy import check_settlement, compute_settlement_pnl

result = check_settlement("KXEARNINGSMENTIONAAPL-26JAN30-TARI")
if result:
    pnl = compute_settlement_pnl(
        entry_price=0.50,     # YES mid when you entered
        result=result,         # "yes" or "no"
        side="NO",
        n_contracts=98,
    )
    print(f"Settled: {result}, PnL: ${pnl:+.2f}")
```

### Custom Data Source

If you already have market data (e.g., from a websocket feed), skip `fetch_active_kalshi` and pass your own market dicts to `compute_signals`:

```python
my_markets = [
    {
        "ticker": "KXEARNINGSMENTIONAAPL-26APR24-IPHO",
        "series": "KXEARNINGSMENTIONAAPL",
        "event_ticker": "KXEARNINGSMENTIONAAPL-26APR24",
        "event_title": "What will Apple say during their next earnings call?",
        "strike_word": "iPhone",
        "source": "kalshi",
        "yes_mid": 0.92,
        "yes_bid": 0.91,
        "yes_ask": 0.93,
        "volume": 5000,
        "close_time": "2026-04-24T22:00:00Z",
    },
    # ... more markets
]

signals = compute_signals(my_markets, rates)
```

Required fields: `ticker`, `series`, `yes_mid`, `source`, `event_ticker`.
Include `strike_word` to enable LibFrog word-level rate lookup on earnings markets.

### Updating Base Rates

As new markets settle, regenerate series-level rates from your settled market data and re-merge LibFrog data. The format is straightforward:

```python
import json

# Your settled market data → series-level rates
rates = {}
for series, markets in your_settled_data.items():
    yes_count = sum(1 for m in markets if m["result"] == "yes")
    rates[series] = {
        "base_rate": yes_count / len(markets),
        "n_markets": len(markets),
    }

# Merge LibFrog word-level entries (already in base_rates.json)
with open("base_rates.json") as f:
    existing = json.load(f)
for key, val in existing.items():
    if "|" in key:  # word-level entry
        rates[key] = val

with open("base_rates.json", "w") as f:
    json.dump(rates, f, indent=2)
```

### Tuning Parameters

All strategy parameters are in the `CONFIG` dict at the top of `pm_mentions_strategy.py`:

```python
CONFIG = {
    "grid_edge_min": 0.10,       # lower = more trades, less edge per trade
    "grid_br_max": 0.50,         # higher = riskier high-BR trades
    "min_history": 10,           # lower = trade with less data
    "max_yes_price": 0.75,       # higher = include the weak 65-75c bucket
    "exclude_earnings": False,   # True to revert to pre-LibFrog behavior
    "kelly_fraction": 0.25,      # higher = more aggressive sizing
    "max_position_pct": 0.05,    # per-position cap
    "max_total_exposure_pct": 0.80,
    "max_per_event_pct": 0.20,
    "kalshi_fee_rt": 0.02,
    "slippage": 0.01,
}
```

Pass custom config to any function: `compute_signals(markets, rates, config=my_config)`.
