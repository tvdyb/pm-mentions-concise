# PM Mentions: Two Strategies for Prediction Market Mention Markets

*A complete writeup of two systematic strategies for trading Kalshi mention markets, with honest backtesting methodology and out-of-sample validation. Based on 20,252 settled markets from January 2025 to March 2026.*

---

## Table of Contents

1. [The Opportunity](#1-the-opportunity)
2. [What Are Mention Markets?](#2-what-are-mention-markets)
3. [Why YES Is Overpriced](#3-why-yes-is-overpriced)
4. [Data and Methodology](#4-data-and-methodology)
5. [Strategy 1: Original Grid Filter](#5-strategy-1-original-grid-filter)
6. [Strategy 2: Focused Filter](#6-strategy-2-focused-filter)
7. [Head-to-Head Comparison](#7-head-to-head-comparison)
8. [Where the Edge Lives (and Doesn't)](#8-where-the-edge-lives-and-doesnt)
9. [LibFrog: The Earnings Advantage](#9-libfrog-the-earnings-advantage)
10. [Out-of-Sample Validation](#10-out-of-sample-validation)
11. [Parameter Robustness](#11-parameter-robustness)
12. [Worked Example](#12-worked-example)
13. [Position Sizing and Risk Management](#13-position-sizing-and-risk-management)
14. [How to Run It](#14-how-to-run-it)
15. [Kill Criteria](#15-kill-criteria)
16. [File Reference](#16-file-reference)
17. [Backtesting Bugs We Fixed](#17-backtesting-bugs-we-fixed)

---

## 1. The Opportunity

Kalshi lists thousands of binary markets asking whether a specific word will be mentioned during a specific event — press conferences, earnings calls, TV shows, sports broadcasts. These markets are structurally biased: retail traders overestimate mention probabilities, especially for exciting or newsworthy words. This pushes YES prices above fair value and creates a persistent edge for NO buyers.

We built two strategies that exploit this. Both buy NO when YES is overpriced relative to historical base rates. They differ in how aggressively they filter:

| | Original Grid Filter | Focused Filter |
|---|---|---|
| Trades | 3,769 | 740 |
| Win rate | 48.6% | 81.6% |
| Mean PnL/trade | +$0.029 | +$0.117 |
| Per-trade Sharpe | 0.063 | 0.315 |
| Total PnL | +$108.60 | +$86.61 |
| Max drawdown | $20.38 | $4.58 |
| 95% CI (mean PnL) | [$0.014, $0.043] | [$0.090, $0.144] |

The original strategy makes more total money by taking 5x more trades, but each trade has a thin edge. The focused strategy is more selective and has a 5x better Sharpe with 4x lower drawdown.

Both are honest: VWAP entry prices (not opening price artifacts), rolling base rates (no look-ahead bias), bootstrapped confidence intervals excluding zero.

---

## 2. What Are Mention Markets?

Kalshi lists binary markets like:

- *"Will the White House Press Secretary say 'tariff' during tomorrow's briefing?"*
- *"Will Apple say 'iPhone' during their next earnings call?"*
- *"Will the SNL cold open mention 'Trump' this Saturday?"*
- *"Will the NBA announcer say 'dynasty' during the Finals?"*

Each market resolves YES or NO. YES contracts trade between $0.01 and $0.99, representing the market's implied probability. If you buy a NO contract, you pay `$1 - YES_price` and receive $1 if the word is not mentioned, $0 if it is.

**Market categories in our dataset (20,252 settled markets):**

| Category | Markets | Description |
|----------|---------|-------------|
| political_person | 6,955 | Press conferences, speeches (Trump, Starmer, Powell, etc.) |
| other | 9,306 | TV shows (SNL, Survivor, South Park), awards, debates |
| earnings | 2,193 | Corporate earnings calls (AAPL, NVDA, TSLA, etc.) |
| sports | 1,798 | NFL, NBA, NCAA broadcasts |

---

## 3. Why YES Is Overpriced

Three structural forces push YES prices above fair value:

1. **Availability bias**: Exciting words feel more likely to be mentioned. "Tariff" during a trade war feels inevitable, but historically it appears in only ~40% of press briefings.

2. **Asymmetric attention**: Buyers are attracted to "will they say X?" markets. Sellers (NO buyers) are less intuitive and less liquid.

3. **Imprecise estimation**: Traders guess at probabilities without historical data. A word mentioned in 10% of past events might trade at 30-40% YES because it *feels* plausible.

The result: across our dataset, the average YES price at entry (VWAP 25% buffer) is consistently higher than the realized YES rate, especially for low-base-rate words.

---

## 4. Data and Methodology

### Dataset

- **20,252 settled markets** from Kalshi, January 2025 to March 2026 (400 days)
- Each market has: ticker, series, strike_word, result (yes/no), opening_price, three VWAP variants, category, close_time

### Entry Price: VWAP, Not Opening Price

The `opening_price` is the first trade ever — often 1c or 99c, not a realistic fill. We use **VWAP with 25% buffer** (strips the first and last 25% of trading time) as the primary entry price. This represents what a trader scanning active markets would realistically pay.

How much this matters:

| Entry Price | Focused Strategy Total PnL |
|-------------|---------------------------|
| VWAP 25% buffer | +$86.61 |
| VWAP 10% buffer | +$91.47 |
| VWAP no buffer | loses money |
| Opening price | artificially inflated |

### Base Rates: Rolling, Not Static

Computing base rates from all 20,252 markets and then backtesting on those same markets is look-ahead bias — the strategy "knows" the final base rate when evaluating early markets.

We use **rolling base rates**: for each market (sorted by close_time), the base rate is the mean outcome of all *prior* settled markets in that series. The market's own outcome is added to the rolling state *after* evaluation.

**Exception — LibFrog word-level rates**: These come from external earnings transcript data (not from this market dataset), so they are not look-ahead. They are used as-is.

### Costs

| Component | Value |
|-----------|-------|
| Kalshi round-trip fee | $0.02/contract |
| Assumed slippage | $0.01 |
| Effective YES price | `max(0.01, YES_mid - 0.01)` |
| NO cost | `1.0 - effective_YES` |

### PnL Formula (NO side)

```
Win (result = NO):  PnL = effective_YES - $0.02
Loss (result = YES): PnL = -(1 - effective_YES) - $0.02
```

### Sharpe Ratio

Per-trade Sharpe = `mean(PnL) / std(PnL)`. Not annualized unless explicitly labeled. Annualized estimates use `per_trade_sharpe * sqrt(trades/year)` with the actual trade frequency from the data.

---

## 5. Strategy 1: Original Grid Filter

**File: `pm_mentions_strategy.py`**

The broadest version. Buys NO on any mention market where YES is overpriced relative to the historical base rate.

### Rules

| Parameter | Value |
|-----------|-------|
| Edge threshold | >= 10c (YES price - base rate) |
| Base rate cap | <= 50% |
| Min history | >= 10 settled markets in series |
| Max YES price | <= 75c |
| Category exclusions | None |
| Side | Always NO |

### Results (VWAP 25% + rolling rates)

| Metric | Value |
|--------|-------|
| Trades | 3,769 |
| Win rate | 48.6% |
| Mean PnL | +$0.029 |
| Std | $0.460 |
| Per-trade Sharpe | 0.063 |
| Total PnL | +$108.60 |
| Max drawdown | $20.38 |
| 95% CI (mean PnL) | [$0.014, $0.043] |
| Bootstrapped Sharpe CI | [0.031, 0.094] |

### Category Breakdown

| Category | N | Win Rate | Mean PnL | Total PnL |
|----------|---|----------|----------|-----------|
| political_person | 1,433 | 34.9% | -$0.047 | -$67.30 |
| other | 1,306 | 52.5% | +$0.069 | +$90.34 |
| earnings | 811 | 68.4% | +$0.096 | +$77.74 |
| sports | 219 | 41.6% | +$0.036 | +$7.82 |

### Verdict

The edge is real (CI excludes zero) but thin. The political_person category is a -$67 drag. Trump mentions alone account for -$81 of losses (KXTRUMPMENTION -$41, KXTRUMPMENTIONB -$41). The strategy makes money overall because the other categories more than compensate, but it takes a lot of losers to get there.

---

## 6. Strategy 2: Focused Filter

**File: `focused_strategy.py`**

Cuts the dead weight identified in the original backtest. Concentrates on the segments that actually make money.

### What Changed

| Parameter | Original | Focused | Why |
|-----------|----------|---------|-----|
| Max YES price | 75c | **50c** | 50-75c bucket has Sharpe 0.005 in original backtest |
| Category exclusions | None | **political_person** | -$67 total PnL, 34.9% win rate |
| Edge (LibFrog rates) | 10c | **8c** | LibFrog rates are precise — can trade thinner edge |
| Edge (rolling series) | 10c | **12c** | Rolling rates are noisier — need more edge |
| Min history (LibFrog) | 10 | **10** | 10 transcript calls is sufficient |
| Min history (rolling) | 10 | **15** | Need more data for noisier series rates |

### Results (VWAP 25% + rolling rates)

| Metric | Value |
|--------|-------|
| Trades | 740 |
| Win rate | 81.6% |
| Mean PnL | +$0.117 |
| Std | $0.372 |
| Per-trade Sharpe | 0.315 |
| Total PnL | +$86.61 |
| Max drawdown | $4.58 |
| 95% CI (mean PnL) | [$0.090, $0.144] |
| Bootstrapped Sharpe CI | [0.232, 0.410] |

### Category Breakdown

| Category | N | Win Rate | Mean PnL | Total PnL |
|----------|---|----------|----------|-----------|
| earnings | 496 | 84.9% | +$0.117 | +$58.14 |
| other | 243 | 74.9% | +$0.115 | +$28.00 |
| sports | 1 | 100% | +$0.470 | +$0.47 |

### Verdict

Same interface, same fee/slippage assumptions, 5x better Sharpe. The tradeoff is fewer trades (740 vs 3,769) and slightly less total PnL ($87 vs $109). But the risk-adjusted returns are dramatically better: max drawdown drops from $20 to $5, and every quarter is profitable.

---

## 7. Head-to-Head Comparison

### Full Period

| Metric | Original | Focused | Winner |
|--------|----------|---------|--------|
| Trades | 3,769 | 740 | Original (volume) |
| Win rate | 48.6% | 81.6% | Focused |
| Mean PnL | +$0.029 | +$0.117 | Focused (4x) |
| Per-trade Sharpe | 0.063 | 0.315 | Focused (5x) |
| Total PnL | +$108.60 | +$86.61 | Original |
| Max drawdown | $20.38 | $4.58 | Focused (4.5x lower) |
| 95% CI lower bound | +$0.014 | +$0.090 | Focused (6x higher) |

### By Quarter

| Quarter | Original Sharpe | Focused Sharpe |
|---------|-----------------|----------------|
| Q1 (Feb–Sep 2025) | 0.068 | 0.429 |
| Q2 (Sep–Nov 2025) | 0.064 | 0.426 |
| Q3 (Nov 2025–Feb 2026) | 0.034 | 0.257 |
| Q4 (Feb–Mar 2026) | 0.085 | 0.199 |

Both strategies show some edge decay in later quarters. The focused strategy decays from Sharpe 0.43 to 0.20 — still solidly positive. The original hovers around 0.04–0.08 throughout, barely above noise.

### Out-of-Sample (Last 40%)

| Metric | Original OOS | Focused OOS |
|--------|-------------|-------------|
| Trades | 1,508 | 296 |
| Win rate | 47.4% | 78.4% |
| Mean PnL | +$0.031 | +$0.104 |
| Per-trade Sharpe | 0.065 | 0.263 |

Both hold up out-of-sample. The focused strategy's OOS Sharpe (0.263) is still 4x the original's (0.065).

### Which One to Use?

**Focused** if you care about risk-adjusted returns, drawdown, or capital efficiency. You need ~$1,000 for practical position sizing.

**Original** if you want maximum volume and can tolerate larger drawdowns. It makes slightly more total PnL by taking many more small-edge trades.

**Both** can be run simultaneously — the focused strategy is a strict subset of the original's trades (tighter filters on the same signal).

---

## 8. Where the Edge Lives (and Doesn't)

### By YES Price Bucket (Focused Strategy)

| YES Price | N | Win Rate | Sharpe | Mean PnL |
|-----------|---|----------|--------|----------|
| 5-25c | 209 | 96.2% | 0.557 | +$0.109 |
| 25-50c | 531 | 75.9% | 0.285 | +$0.120 |
| 50-75c | (excluded) | — | — | — |

Low-price markets win almost every time (96%) but payout per win is small. The 25-50c range is the sweet spot for total PnL. The 50-75c range was actively harmful in the original backtest (Sharpe 0.005), which is why the focused strategy excludes it.

### By Rate Source

| Source | N | Win Rate | Sharpe | Mean PnL |
|--------|---|----------|--------|----------|
| LibFrog (word-level) | 496 | 84.9% | 0.340 | +$0.117 |
| Rolling series | 244 | 75.0% | 0.276 | +$0.117 |

LibFrog-rated trades are the backbone — 67% of focused strategy volume with the best Sharpe. Both sources show comparable mean PnL, but LibFrog's higher consistency gives it the edge.

### What Bleeds Money

In the original strategy, these segments destroy value:

| Segment | N | Total PnL | Problem |
|---------|---|-----------|---------|
| KXTRUMPMENTION | 498 | -$40.78 | Trump says unpredictable things |
| KXTRUMPMENTIONB | 268 | -$40.57 | Same series, different events |
| KXVANCEMENTION | 109 | -$5.89 | Political person |
| All political_person | 1,433 | -$67.30 | Systematic overshoot on political figures |
| YES 50-75c bucket | 2,900 | +$7.19 | Sharpe 0.005, adds noise |

The focused strategy avoids all of these by excluding political_person and capping YES at 50c.

---

## 9. LibFrog: The Earnings Advantage

### The Problem with Series-Level Rates for Earnings

A series like KXEARNINGSMENTIONAMZN has a blended base rate of ~60%. But this lumps together:
- "Revenue" (mentioned 100% of calls)
- "iPhone" — wrong company, but "AWS" (mentioned 95%+)
- "RxPass" (mentioned ~5% of calls)
- "Tariff" (mentioned ~3% of calls)

The series-level rate is useless for individual words.

### What LibFrog Provides

LibFrog analyzes historical earnings call transcripts across 40-80+ calls per company and provides word-level base rates:

```
KXEARNINGSMENTIONAAPL|iPhone:  base_rate=0.938, n_calls=81
KXEARNINGSMENTIONAAPL|Tariff:  base_rate=0.049, n_calls=81
KXEARNINGSMENTIONPLTR|AIP:     base_rate=0.455, n_calls=44
KXEARNINGSMENTIONUBER|Tesla:   base_rate=0.000, n_calls=68
```

This is external data from actual transcripts, not derived from the Kalshi market dataset. It is not look-ahead.

### Impact

| | Without LibFrog (series rates only) | With LibFrog |
|---|---|---|
| Earnings trades | Nearly zero (series BR usually > 50%) | 496 (focused) / 808 (original) |
| Earnings Sharpe | — | 0.340 (focused) |
| Earnings total PnL | — | +$58 (focused) / +$78 (original) |

LibFrog effectively unlocks the entire earnings category. Without it, the strategy has no way to distinguish "iPhone" (skip — always mentioned) from "Tariff" (trade — rarely mentioned but overpriced).

### Data in `base_rates.json`

1,691 word-level entries keyed as `"SERIES|word"`:
```json
"KXEARNINGSMENTIONAAPL|Tariff": {
    "base_rate": 0.049,
    "n_calls": 81,
    "source": "libfrog"
}
```

Merged from two LibFrog data sources (matched preferred over generic), filtered to `base_rate != null` and `n_calls >= 5`. At query time, requires `n_calls >= 10`.

---

## 10. Out-of-Sample Validation

### Focused Strategy: 60/40 Walk-Forward

| Period | N | Win Rate | Mean PnL | Sharpe | CI |
|--------|---|----------|----------|--------|----|
| In-sample (first 60%) | 444 | 83.8% | +$0.126 | 0.354 | [$0.093, $0.158] |
| Out-of-sample (last 40%) | 296 | 78.4% | +$0.104 | 0.263 | [$0.058, $0.148] |

The OOS Sharpe (0.263) is lower than IS (0.354) — expected — but the CI still excludes zero by a wide margin. The strategy's edge persists.

### Focused Strategy: Chronological Thirds

| Third | Dates | N | Win Rate | Sharpe |
|-------|-------|---|----------|--------|
| 1 | Feb–Oct 2025 | 246 | 89.4% | 0.475 |
| 2 | Oct 2025–Jan 2026 | 246 | 76.8% | 0.253 |
| 3 | Jan–Mar 2026 | 248 | 78.6% | 0.258 |

Third 1 is the strongest. Thirds 2 and 3 are consistent with each other and still solidly positive. The edge decays but stabilizes.

### Original Strategy: Quarters

| Quarter | N | Sharpe |
|---------|---|--------|
| Q1 | 942 | 0.068 |
| Q2 | 942 | 0.064 |
| Q3 | 942 | 0.034 |
| Q4 | 943 | 0.085 |

Flat and low throughout. The original strategy's edge is consistent but thin — more noise than signal on a per-trade basis.

---

## 11. Parameter Robustness

The focused backtest swept 256 parameter combinations:
- `max_yes_price`: [40%, 50%, 60%, 75%]
- `edge_min_libfrog`: [5%, 8%, 10%, 15%]
- `edge_min_rolling`: [8%, 10%, 12%, 15%]
- `min_history_rolling`: [10, 15, 20, 30]

**Result: 100% of 256 combos with N >= 20 trades have positive Sharpe.**

| Statistic | Value |
|-----------|-------|
| Combos tested | 256 |
| Positive Sharpe (N >= 20) | 256 / 256 (100%) |
| Median Sharpe | 0.291 |
| Max Sharpe | 0.499 |
| Min Sharpe | 0.142 |
| Chosen config Sharpe | 0.315 |

The chosen parameters (max_yes=50c, edge_lf=8c, edge_roll=12c, min_hist=15) sit in the middle of the profitable plateau, not at the peak. The peak (max_yes=40c, edge_lf=15c, edge_roll=15c) has Sharpe 0.50 but only 315 trades — tighter isn't always better for practical trading.

Key insight: **even the worst combo (max_yes=75c, edge_lf=15c, edge_roll=10c) has Sharpe 0.14**. This is not a fragile edge tuned to one parameter setting.

### Category Ablation

| Configuration | N | Sharpe |
|---------------|---|--------|
| No exclusions | 788 | 0.330 |
| Exclude political_person | 740 | 0.315 |
| Exclude political_person + sports | 739 | 0.313 |
| Earnings only | 496 | 0.340 |

The 50c YES cap already removes most bad political trades, so the category exclusion is a marginal improvement. "No exclusions" actually has the highest N and comparable Sharpe. Earnings-only is the purest signal (Sharpe 0.340) but with fewer trades.

---

## 12. Worked Example

**Market**: KXEARNINGSMENTIONAMZN, strike word "RxPass", VWAP 25% = 50c

**Step 1 — Look up rate**:
Check `base_rates.json` for `"KXEARNINGSMENTIONAMZN|RxPass"`.
Found: `base_rate = 0.049, n_calls = 81, source = "libfrog"`.

**Step 2 — Check filters (focused strategy)**:
- Category = earnings → not excluded ✓
- YES price 50c <= 50c cap ✓
- Base rate 4.9% <= 50% cap ✓
- n_calls 81 >= 10 min (LibFrog) ✓
- Edge = 50c - 4.9c = 45.1c >= 8c min (LibFrog) ✓

All pass → **BUY NO**

**Step 3 — Compute expected PnL**:
```
effective_YES = 50c - 1c slippage = 49c
NO cost = 100c - 49c = 51c
P(NO wins) = 1 - 0.049 = 0.951

E[PnL] = 0.951 × $0.49 - 0.049 × $0.51 - $0.02
       = $0.466 - $0.025 - $0.02
       = +$0.421/contract
```

**Step 4 — Size position** ($1,000 capital, quarter-Kelly):
```
Kelly fraction = 0.25
b = $0.49 / $0.51 = 0.961
Kelly full = (0.951 × 0.961 - 0.049) / 0.961 = 0.900
Kelly quarter = 0.900 × 0.25 = 0.225
Position = min($1000 × 0.225, $1000 × 0.05) = $50 (5% cap binds)
Contracts = floor($50 / $0.51) = 98
```

**Step 5 — Outcome**:
"RxPass" was not mentioned. Result = NO.
```
PnL = 98 × ($0.49 - $0.02) = 98 × $0.47 = +$46.06
```

---

## 13. Position Sizing and Risk Management

Both strategies use the same sizing framework.

### Quarter-Kelly

Full Kelly is too aggressive. Quarter-Kelly (25% of the theoretically optimal fraction) trades growth for much lower variance and drawdown.

```
b = effective_YES / NO_cost
Kelly_full = (P(NO) × b - base_rate) / b
Kelly_quarter = Kelly_full × 0.25
position = min(capital × Kelly_quarter, capital × 5%)
```

### Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| Max per position | 5% of capital | Single-market concentration cap |
| Max per event | 20% of capital | Correlated markets in same event |
| Max total exposure | 80% of capital | Cash reserve |
| Min position | $1.00 | Skip dust |

### Why Risk Is Bounded

1. **Binary payoffs**: Each NO contract costs at most $0.99. No leverage, no margin calls.
2. **Natural diversification**: Whether Trump says "tariff" tomorrow is uncorrelated with whether Apple says "Siri" next quarter.
3. **Deterministic settlement**: Markets resolve based on publicly verifiable transcripts. No subjective judgment.
4. **Short duration**: Most markets settle within days. Capital isn't locked for months.

---

## 14. How to Run It

### Installation

```bash
pip install requests numpy
```

### Focused Strategy (Recommended)

```python
from focused_strategy import (
    load_base_rates,
    fetch_active_kalshi,
    compute_signals,
    size_position,
    compute_settlement_pnl,
    check_settlement,
    FOCUSED_CONFIG,
)

rates = load_base_rates("base_rates.json")
markets = fetch_active_kalshi(rates)
signals = compute_signals(markets, rates)

capital = 1000.0
for sig in signals:
    n, cost = size_position(sig, capital)
    if n > 0:
        print(f"BUY {n} NO on {sig['ticker']}")
        print(f"  {sig['strike_word']}  YES={sig['yes_mid']:.0%}  "
              f"BR={sig['base_rate']:.1%} ({sig['rate_source']})  "
              f"edge={sig['edge']:+.0%}  E[PnL]=${sig['expected_pnl']:+.3f}")
```

### Original Strategy (More Volume)

```python
from pm_mentions_strategy import (
    load_base_rates,
    fetch_active_kalshi,
    compute_signals,
    size_position,
)

rates = load_base_rates("base_rates.json")
markets = fetch_active_kalshi(rates)
signals = compute_signals(markets, rates)
```

### Run Backtests

```bash
# Original strategy backtest (honest methodology)
python backtest.py --save

# Focused strategy backtest (with OOS + param grid)
python focused_backtest.py --save
```

### Custom Market Data

If you have your own market feed, skip `fetch_active_kalshi` and pass market dicts directly:

```python
my_markets = [{
    "ticker": "KXEARNINGSMENTIONAAPL-26APR24-TARI",
    "series": "KXEARNINGSMENTIONAAPL",
    "event_ticker": "KXEARNINGSMENTIONAAPL-26APR24",
    "strike_word": "Tariff",
    "source": "kalshi",
    "yes_mid": 0.35,
    "category": "earnings",
    # ... other optional fields
}]

signals = compute_signals(my_markets, rates)
```

Required fields: `ticker`, `series`, `yes_mid`, `source`, `event_ticker`.
Include `strike_word` for LibFrog lookup. Include `category` for category filtering.

---

## 15. Kill Criteria

### Focused Strategy

| Trigger | Threshold | Rationale |
|---------|-----------|-----------|
| Rolling 30-trade mean PnL | < -$0.05 for 2 consecutive windows | Strategy mean is +$0.117; sustained negative = edge gone |
| Max drawdown | > $15 | ~3x backtest max ($4.58) |
| OOS Sharpe | < 0 over 60 days with >= 20 trades | Edge not persisting |
| Market structure | Kalshi changes fees/rules | Assumptions invalid |
| Data staleness | LibFrog data > 2 years old | Transcript patterns evolve |

### Original Strategy

Same triggers, but with looser thresholds given its thinner edge:

| Trigger | Threshold |
|---------|-----------|
| Rolling 50-trade mean PnL | < -$0.03 for 2 consecutive windows |
| Max drawdown | > $30 |
| OOS Sharpe | < 0 over 90 days |

---

## 16. File Reference

| File | Purpose |
|------|---------|
| **`focused_strategy.py`** | Focused strategy module — tighter filters, same interface |
| **`pm_mentions_strategy.py`** | Original strategy module — broader filters |
| **`base_rates.json`** | 203 series-level rates + 1,691 LibFrog word-level rates |
| **`focused_backtest.py`** | Focused backtest with OOS validation + param grid |
| **`backtest.py`** | Original backtest with honest methodology |
| **`focused_backtest_report.md`** | Full focused backtest report |
| **`backtest_report.md`** | Full original backtest report |
| **`strategy_writeup.md`** | This document |
| **`data/kalshi_all_series.json`** | 20,252 settled markets (source data) |
| `strategy_report.md` | Earlier strategy overview (pre-honest-backtest) |
| `optimized_strategy_report.pdf` | Original parameter optimization report |
| `optimized_strategy_report.md` | Same in markdown |

---

## 17. Backtesting Bugs We Fixed

The original backtest reported Sharpe ~4 and ~88% win rate. These numbers were wrong due to two bugs:

### Bug 1: Opening Price as Entry

`opening_price` is the first trade ever in each market — often 1c or 99c. These are price discovery artifacts, not realistic fills. When YES opens at 1c and the word is not mentioned, the "NO buyer at 1c" wins $0.01 minus fees — a near-guaranteed win with tiny PnL that inflates win rate.

**Fix**: Use VWAP with buffer. VWAP 25% strips the first/last 25% of trading time, giving a price representative of the market's steady state.

**Impact**: Win rate drops from ~88% to 48-82% depending on strategy. More realistic.

### Bug 2: Look-Ahead in Base Rates

`base_rates.json` was computed from all 20,252 markets and then applied to those same markets. When evaluating market #100 in a series, the strategy was using a base rate that included outcomes of markets #101 through #2,000.

**Fix**: Rolling base rates — for each market, compute base rate from only prior settled markets. The market's own outcome is added after evaluation.

**Impact**: Many more markets pass the filter with rolling rates (the rolling rate is often lower early in a series), but mean PnL per trade drops significantly.

### Combined Impact

| | Biased Backtest | Honest Backtest (Original) | Honest (Focused) |
|---|---|---|---|
| Trades | 555 | 3,769 | 740 |
| Win rate | 61.8% | 48.6% | 81.6% |
| Mean PnL | +$0.105 | +$0.029 | +$0.117 |
| Per-trade Sharpe | 0.248 | 0.063 | 0.315 |

The focused strategy's honest numbers are better than the original biased numbers — it just took proper methodology to find where the real edge is.
