# PM Mentions Bot

Polymarket mention-market trading bot. Buys NO when YES is overpriced relative to speaker-level historical base rates from 10K+ resolved markets.

## Architecture

| File | Purpose |
|------|---------|
| `bot.py` | Main loop: scan, signal, execute (FOK directional + MM mode) |
| `polymarket_client.py` | CLOB client, order execution, state persistence |
| `pm_focused_strategy.py` | Signal generation: tiered edge thresholds, category/speaker filters |
| `shared.py` | Expected PnL, Kelly sizing, PM taker fee formula, settlement |
| `pm_base_rates.py` | Build speaker/category calibration from resolved PM markets |
| `pm_data_collector.py` | Fetch and parse resolved mention markets from Gamma API |
| `pm_transcript_rates.py` | Word-level transcript rates (optional, highest precision) |
| `pm_vwap_backtest.py` | VWAP backtest with rolling rates, parameter grid (768 combos) |
| `tests.py` | 110 unit tests covering strategy, execution, fees, deployment |

## Setup

```bash
# Install (Python 3.11+)
pip install -e ".[dev]"

# Required env vars
export POLYMARKET_PRIVATE_KEY="0x..."

# Optional env vars
export POLYMARKET_SIG_TYPE=1          # 0=EOA, 1=Magic/email proxy, 2=Gnosis proxy
export POLYMARKET_FUNDER="0x..."      # required for sig_type 1 or 2
export POLYMARKET_CLOB_HOST="https://clob.polymarket.com"
export POLYMARKET_CHAIN_ID=137        # Polygon mainnet
export TG_BOT_TOKEN="..."            # Telegram alerts (optional)
export TG_CHAT_ID="..."              # Telegram chat ID (optional)
```

## Build Calibration Data

Before the bot can trade, you need calibration data:

```bash
# 1. Fetch resolved mention markets (writes data/pm_resolved_markets.json)
python pm_data_collector.py

# 2. Build speaker/category base rates (writes data/pm_calibration.json)
python pm_base_rates.py

# 3. (Optional) Build word-level transcript rates
python pm_transcript_rates.py
```

Calibration must be refreshed at least every 14 days. Live mode refuses to start with stale data.

## Running the Bot

```bash
# Dry run — scan + signals, no orders, no CLOB auth needed
python bot.py --dry-run --once

# Paper trading — scan + fake fills, uses real order books
python bot.py --paper --once

# Live trading — real FOK orders on Polymarket CLOB
python bot.py --once              # single cycle
python bot.py                     # continuous loop (180s interval)
python bot.py --capital 200 --max-daily-loss 50

# Market-making mode (two-sided GTC quotes)
python bot.py --mm --once
python bot.py --mm
```

## Live Deployment Checklist

1. **Wallet setup**: Confirm your wallet type and set `POLYMARKET_SIG_TYPE` accordingly. If using a proxy wallet (type 1 or 2), set `POLYMARKET_FUNDER`.
2. **Calibration data**: Run `pm_data_collector.py` then `pm_base_rates.py`. Verify `data/pm_calibration.json` exists and is <14 days old.
3. **Preflight**: Run `python bot.py --dry-run --once` to verify signals look reasonable.
4. **Paper test**: Run `python bot.py --paper --once` to verify CLOB auth and order book fetching work.
5. **Canary**: Run `python bot.py --once` with small `--capital` (e.g., $25) to place a single cycle of real orders.
6. **Monitor**: Check `logs/bot.log` and Telegram alerts. Verify fills match expected behavior.
7. **Continuous**: Run `python bot.py` only after canary succeeds. The bot acquires a file lock (`bot_state.lock`) to prevent duplicate instances.
8. **Refresh**: Re-run calibration pipeline weekly. Live mode will refuse to trade if data is >14 days stale.

## Safety Features

- **Daily loss limit**: Stops trading when realized PnL breaches threshold (default $25)
- **Position limits**: Max 10 open positions, max 5 per speaker
- **FOK strict fill**: Only records trades on MATCHED/FILLED status (rejects LIVE/empty)
- **Single-process lock**: `fcntl.flock` prevents concurrent instances
- **Calibration freshness**: Live mode exits if data is >14 days old
- **Atomic state saves**: Write to tmp file + rename to prevent corruption
- **Graceful shutdown**: SIGINT/SIGTERM cancels all open orders (MM mode)

## Fees

Polymarket taker fees use the formula: `fee = p * feeRate * (p * (1-p))^exponent`

For mentions: rate=25%, exponent=2. Fees peak at p=0.50 (~$0.008/contract) and drop fast at extremes. At p=0.10 (typical NO entry): ~$0.0002/contract.

## Running Tests

```bash
python -m pytest tests.py -v
```

## Backtests

```bash
python pm_vwap_backtest.py --save   # writes pm_vwap_backtest_report.md
```
