# PM Mentions Strategy — Full Operating Report

*Last updated: 2026-03-16. Backtest data: 10,021 resolved markets, 2024-06-27 to 2026-04-30.*

---

## 1. What This Strategy Does

Buy NO on Polymarket "mention markets" — binary contracts on whether a public figure will say a specific word during an event (press conference, speech, etc).

**Core thesis**: Markets systematically overprice YES on rare words. A speaker who historically says "Bitcoin" in 30% of press conferences shouldn't be priced at YES=45%. We buy NO at 55c and collect $1 when the word isn't said.

**Edge source**: We know, from 10,000+ resolved markets and 165 political speech transcripts, how often each speaker says each word. The market doesn't price this in accurately.

---

## 2. Backtest Results (Honest VWAP)

All numbers use real CLOB trade history (VWAP with 25% time buffer) as entry prices. Rolling base rates with zero look-ahead. PM taker fees included (mentions: 25% rate, exponent 2). 1c slippage.

| Metric | Value |
|---|---|
| Total trades | 2,848 |
| Win rate | 67.9% |
| Mean PnL per trade | +$0.037 |
| Total PnL | +$106.60 |
| Per-trade Sharpe | 0.086 |
| Max drawdown | $13.26 |
| 95% CI on mean PnL | [$0.022, $0.053] |
| Bootstrapped Sharpe CI | [0.048, 0.123] |

### Out-of-sample validation

| Period | N | Win Rate | Mean PnL | Sharpe | 95% CI |
|---|---|---|---|---|---|
| In-sample 60% (to 2025-11-10) | 1,708 | 68.3% | +$0.028 | 0.065 | [$0.007, $0.049] |
| **Out-of-sample 40%** (2025-11 to 2026-04) | **1,140** | **67.4%** | **+$0.051** | **0.116** | **[$0.025, $0.076]** |

OOS performance is *better* than in-sample. Edge is not decaying.

### Parameter robustness

256 parameter combinations tested. **100% have positive Sharpe**. The strategy is not fragile to parameter choices.

---

## 3. How It Works (Step by Step)

### Step 1: Discover active mention markets

The script queries the Polymarket Gamma API for all events tagged `mention-markets`:

```
GET https://gamma-api.polymarket.com/events?active=true&closed=false&tag_slug=mention-markets
```

Each event (e.g., "What will Trump say at his March press conference?") contains 20-100+ individual word markets ("Will he say 'Tariff'?", "Will he say 'Bitcoin'?", etc).

### Step 2: Parse each market

For each market, extract:
- **Speaker** (from event title, e.g., "Trump", "Powell", "Leavitt")
- **Strike word** (from market question, e.g., "Tariff", "Bitcoin", "China")
- **YES price** (current mid from CLOB order book)
- **Category** (political_person, earnings, other)
- **Token IDs** (needed for order placement)

### Step 3: Look up base rate (3-tier hierarchy)

For each market, determine the true probability the speaker says the word:

1. **Transcript word-level rate** (best): Check 165 political speech transcripts. "Has Trump said 'Bitcoin' before? In how many speeches?" → e.g., 12/68 = 17.6%. Available for 2,175 word/speaker pairs.

2. **Speaker-level rolling rate** (good): From 10,000+ resolved PM markets, what fraction of words does this speaker actually say? e.g., Trump = 44.0%, Leavitt = 35.8%, Melania = 19.5%.

3. **Category-level rate** (fallback): political_person = 42.0%, other = 37.4%.

### Step 4: Apply filters

A market passes the filter if ALL conditions are met:

| Filter | Threshold | Why |
|---|---|---|
| Edge (transcript rate) | >= 4c | Most precise rate, tighter threshold OK |
| Edge (speaker, 100+ history) | >= 4c | High-N speakers are reliable |
| Edge (speaker, 20-99 history) | >= 6c | Less data, need more edge |
| Edge (category fallback) | >= 10c | Least precise, need biggest buffer |
| Max YES price | <= 60% | Above 60% = word is too likely, risky NO |
| Min YES price | >= 5% | Below 5% = illiquid, no edge |
| Base rate cap | <= 50% | Don't trade if speaker says most words |
| Min speaker history | >= 20 markets | Need enough data to trust the rate |
| Category exclusion | No earnings | Earnings mentions lose money on PM |

**Edge = YES price - base rate.** If Trump's base rate is 44% and a word is priced at YES=50%, the edge is 6c.

### Step 5: Size positions (Quarter-Kelly)

For each qualifying signal:

```
Expected PnL = P(NO wins) × YES_price - P(YES wins) × NO_cost
Kelly fraction = ((p × b) - q) / b    where b = YES/NO odds ratio
Position = min(Kelly/4 × capital, 5% × capital)
```

| Sizing parameter | Value |
|---|---|
| Kelly fraction | 25% (quarter-Kelly) |
| Max per position | 5% of capital |
| Max per event | 20% of capital |
| Max total exposure | 80% of capital |

### Step 6: Place orders

GTC (good-til-cancelled) limit orders to BUY NO at `1 - YES_price`. Orders go through the Polymarket CLOB via `py-clob-client`.

---

## 4. Base Rate Data

### Speaker base rates (from 10,000 resolved PM markets)

| Speaker | Base Rate | Markets | Notes |
|---|---|---|---|
| trump | 44.0% | 5,261 | Primary volume driver |
| leavitt | 35.8% | 477 | Press secretary, very profitable |
| kamala | 30.2% | 291 | Lower rate = more NO wins |
| vance | 40.2% | 291 | Close to break-even |
| powell | 46.9% | 243 | Higher rate, lower edge |
| starmer | 41.5% | 207 | UK PM, slight negative PnL |
| biden | 30.6% | 134 | Low rate, profitable |
| sanders | 42.7% | 117 | |
| mrbeast | 31.5% | 108 | Non-political |
| elon | 27.9% | 61 | Very low rate, very profitable |
| melania | 19.5% | 41 | Lowest rate, highest edge |

### Transcript word-level rates (from 165 political speeches)

2,175 word/speaker combinations. Examples for Trump (68 transcripts):

| Word | Said in | Rate | Likely NO? |
|---|---|---|---|
| "American" | 68/68 | 100% | Never trade NO |
| "China" | 62/68 | 91% | Almost never trade NO |
| "Bitcoin" | 12/68 | 18% | Strong NO signal if YES > 22% |
| "Filibuster" | 2/68 | 3% | Very strong NO signal |
| "DEI" | 15/68 | 22% | Good NO signal if YES > 26% |

### Category rates

| Category | Base Rate | Markets | Strategy result |
|---|---|---|---|
| political_person | 42.0% | 7,473 | **+$75 total PnL** (core edge) |
| other | 37.4% | 1,612 | **+$32 total PnL** |
| earnings | 56.9% | 914 | **Excluded** (negative PnL) |

---

## 5. Speaker Performance (Backtest)

### Most profitable speakers

| Speaker | Trades | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| trump | 2,275 | 69% | +$0.017 | +$39.12 |
| leavitt | 97 | 74% | +$0.225 | +$21.79 |
| biden | 46 | 83% | +$0.128 | +$5.89 |
| elon | 14 | 93% | +$0.376 | +$5.26 |
| altman | 13 | 92% | +$0.292 | +$3.79 |
| mrbeast | 32 | 62% | +$0.098 | +$3.12 |

### Speakers to watch (marginal or negative)

| Speaker | Trades | Win Rate | Mean PnL | Total PnL |
|---|---|---|---|---|
| starmer | 24 | 46% | -$0.017 | -$0.40 |
| vance | 45 | 47% | -$0.023 | -$1.04 |
| powell | 20 | 50% | +$0.043 | +$0.86 |

Starmer and Vance are break-even to slightly negative. Consider adding them to exclusions if they continue underperforming.

---

## 6. Running It Live

### Prerequisites

```bash
# 1. Install dependencies
pip install py-clob-client python-dotenv requests numpy

# 2. Set up Polymarket API credentials
#    Export your private key from Polymarket account settings
echo 'POLYMARKET_PRIVATE_KEY=0x...' > .env

# 3. Build calibration data (one-time, refresh monthly)
python pm_base_rates.py        # builds data/pm_calibration.json
python pm_transcript_rates.py  # builds data/pm_transcript_rates.json (needs pm_mentions transcript data)
```

### Scan (no orders)

```bash
python polymarket_client.py
```

This will:
1. Authenticate with Polymarket CLOB
2. Load calibration data from `data/pm_calibration.json`
3. Fetch all active mention markets (tag: `mention-markets`)
4. Run `pm_focused_strategy.compute_signals()` to filter
5. Print qualifying signals with edge, expected PnL, and rate source

### Place live orders

```bash
python polymarket_client.py --trade --capital 500
```

This does everything above, plus places GTC limit orders for each qualifying signal sized by quarter-Kelly.

### Example output

```
Scanning Polymarket mention markets (tag_slug=mention-markets)...
  Found 147 active mention markets

Running PM-native strategy (speaker base rates, edge>=4%/6%, max_yes=60%)...
  12 signals pass filter

  #  Word/Phrase                          YES     BR    Edge   E[PnL]      Speaker       Src
-------------------------------------------------------------------------------------------------------------------
  1  Bitcoin                              24%    18%    +6%   +0.049        trump  transcript
  2  Filibuster                            9%     3%    +6%   +0.054        trump  transcript
  3  Iran                                 38%    31%    +7%   +0.038        trump  transcript
  4  DEI                                  28%    22%    +6%   +0.042        trump  transcript
```

### Cron / scheduled execution

To run every 4 hours during market hours:

```bash
# Add to crontab:
0 */4 * * * cd /path/to/pm-mentions-concise && python polymarket_client.py --trade --capital 500 >> logs/pm_trades.log 2>&1
```

---

## 7. File Reference

| File | Purpose |
|---|---|
| `polymarket_client.py` | **Main entry point**. Fetches markets, runs strategy, places orders |
| `pm_focused_strategy.py` | Strategy logic: `compute_signals()` and `PM_CONFIG` |
| `pm_base_rates.py` | Builds speaker/category base rates from resolved markets |
| `pm_transcript_rates.py` | Builds word-level rates from political speech transcripts |
| `shared.py` | PnL calculation, Kelly sizing, position sizing |
| `pm_trade_fetcher.py` | Fetches CLOB trade history (for backtesting, not live) |
| `pm_vwap_backtest.py` | Honest VWAP backtest using real trade prices |
| `pm_data_collector.py` | Collects resolved market data from Polymarket |
| `data/pm_calibration.json` | Speaker/category base rates (built by `pm_base_rates.py`) |
| `data/pm_transcript_rates.json` | Word-level transcript rates (built by `pm_transcript_rates.py`) |
| `data/pm_resolved_markets.json` | 10,021 resolved mention markets |
| `data/pm_markets_with_trades.json` | CLOB trade data for backtesting |
| `tests.py` | 52 tests covering all strategy components |

---

## 8. Key Configuration (`PM_CONFIG`)

```python
PM_CONFIG = {
    # Edge thresholds (tiered by rate quality)
    "edge_min_speaker_high_n": 0.04,   # 4c for speakers with 100+ markets
    "edge_min_speaker_low_n": 0.06,    # 6c for speakers with 20-99 markets
    "edge_min_category": 0.10,         # 10c for category-level fallback
    "edge_min_transcript": 0.04,       # 4c for transcript word-level rates

    # Price filters
    "max_yes_price": 0.60,             # Don't trade if YES > 60%
    "min_yes_price": 0.05,             # Don't trade if YES < 5%
    "br_max": 0.50,                    # Don't trade if base rate > 50%

    # History requirements
    "min_speaker_n": 20,               # Need 20+ resolved markets per speaker
    "min_category_n": 50,              # Category rates need 50+ markets
    "min_transcript_events": 10,       # Need 10+ transcripts for word-level

    # Categories
    "exclude_categories": ["earnings"],  # Earnings are negative EV on PM

    # Position sizing
    "kelly_fraction": 0.25,            # Quarter-Kelly
    "max_position_pct": 0.05,          # 5% of capital per position
    "max_per_event_pct": 0.20,         # 20% of capital per event
    "max_total_exposure_pct": 0.80,    # 80% max total exposure

    # Costs
    "fee": 0.0,                        # flat fee override (0 = use fee_category)
    "fee_category": "mentions",        # PM taker fee schedule (25% rate, exp 2)
    "slippage": 0.01,                  # 1c slippage assumed
}
```

---

## 9. PnL Math

For each NO trade:

```
Entry:
  YES price = market price (e.g., 0.30)
  Effective YES = YES - slippage = 0.29
  NO cost = 1 - effective_YES = 0.71
  You pay $0.71 per NO contract

Settlement:
  If word NOT said (NO wins):  PnL = +$0.29 per contract  (collect YES side)
  If word IS said (YES wins):  PnL = -$0.71 per contract  (lose NO cost)

Expected PnL:
  E[PnL] = P(NO) × eff_YES - P(YES) × NO_cost
  E[PnL] = (1 - base_rate) × eff_YES - base_rate × NO_cost

Example: Trump word at YES=30%, base_rate=20%
  E[PnL] = 0.80 × 0.29 - 0.20 × 0.71 = 0.232 - 0.142 = +$0.09
```

---

## 10. Kill Criteria

Stop trading immediately if any of these are hit:

1. **Rolling 30-trade mean PnL < -$0.05** for two consecutive windows
2. **Drawdown exceeds $27** (2x backtest max DD of $13.26)
3. **OOS Sharpe < 0** over any 60-day window with >= 20 trades
4. **Market structure change**: Polymarket changes resolution rules, fees, or stops listing mention markets
5. **Transcript data staleness**: Refresh transcript rates if > 2 years old

---

## 11. Risks and Limitations

| Risk | Mitigation |
|---|---|
| Concentrated in Trump (~80% of trades) | Monitor per-speaker PnL; diversify as more speakers are listed |
| Edge is small (~3.7c/trade) | Quarter-Kelly sizing limits ruin probability |
| Q2-Q3 2025 had near-zero Sharpe | Edge fluctuates; kill criteria catch prolonged drawdowns |
| Starmer/Vance slightly negative | Watch list; consider excluding if trend continues |
| Transcript data is static | Refresh periodically; rates from 165 speeches are stable |
| Polymarket liquidity varies | Min YES price filter (5%) and slippage assumption |
| Resolution disputes | Rare for mention markets (binary yes/no on a word) |

---

## 12. Refreshing Data

### Monthly (recommended)

```bash
# Re-collect resolved markets and rebuild calibration
python pm_data_collector.py
python pm_base_rates.py
```

### Quarterly

```bash
# Refresh transcript rates if new speeches are available
python pm_transcript_rates.py

# Re-run backtest to check for edge decay
python pm_vwap_backtest.py --save
```

### After any code change

```bash
python -m pytest tests.py -v
```
