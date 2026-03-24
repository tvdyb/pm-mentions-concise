#!/usr/bin/env python3
"""PM Mentions trading bot — continuous scanner and executor.

Fetches active Polymarket mention markets, runs the PM-native strategy
to find +EV NO opportunities, walks order books level-by-level, and
places FOK orders on the CLOB.

Usage:
    python bot.py --dry-run        # scan + signals, no orders
    python bot.py --paper          # scan + signals + fake fills, no real orders
    python bot.py                  # live trading with real FOK orders

Environment variables:
    POLYMARKET_PRIVATE_KEY  — Polygon wallet private key
    TG_BOT_TOKEN            — Telegram bot token (optional)
    TG_CHAT_ID              — Telegram chat ID (optional)
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pm_base_rates import load_calibration
from pm_focused_strategy import compute_signals as pm_compute_signals, PM_CONFIG
from shared import compute_expected_pnl, compute_settlement_pnl, size_position

from polymarket_client import (
    BOT_CONFIG,
    check_daily_loss,
    create_client,
    enrich_with_order_book,
    execute_fok_no,
    fetch_mention_markets,
    load_positions,
    record_trade,
    save_positions,
    walk_order_book_ev,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("bot")
logger.setLevel(logging.DEBUG)

_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(_ch)

_fh = logging.FileHandler(LOG_DIR / "bot.log")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_fh)


# ---------------------------------------------------------------------------
# Telegram alerts
# ---------------------------------------------------------------------------

def _send_tg(message: str) -> None:
    """Send Telegram alert (best-effort, never raises)."""
    token = BOT_CONFIG.get("telegram_bot_token", "")
    chat_id = BOT_CONFIG.get("telegram_chat_id", "")
    if not token or not chat_id:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
    except Exception:
        logger.debug("Telegram send failed", exc_info=True)


def _trade_alert(sig: dict, n_contracts: int, cost: float, levels: list) -> None:
    """Send Telegram alert for a trade."""
    best_yes = levels[0]["yes_implied"] if levels else sig["yes_mid"]
    no_price = 1.0 - best_yes
    msg = (
        f"\U0001f7e2 TRADE: Sold YES @ {best_yes:.2f} (NO @ {no_price:.2f})\n"
        f"  Market: \"{sig.get('event_title', '')[:60]}\"\n"
        f"  Word: \"{sig.get('strike_word', '')}\"\n"
        f"  Edge: +{sig['edge']*100:.0f}c "
        f"(BR={sig['base_rate']*100:.0f}%, YES={sig['yes_mid']*100:.0f}%)\n"
        f"  Contracts: {n_contracts}, Cost: ${cost:.2f}\n"
        f"  Rate source: {sig.get('rate_source', 'unknown')}"
    )
    _send_tg(msg)


def _settlement_alert(
    condition_id: str, pos: dict, result: str, pnl: float, daily_pnl: float,
) -> None:
    """Send Telegram alert for settlement."""
    won = (result == "no")
    emoji = "\U0001f534"
    check = "\u2713" if won else "\u2717"
    msg = (
        f"{emoji} SETTLED: \"{pos.get('strike_word', condition_id)}\" "
        f"\u2192 {result.upper()} {check}\n"
        f"  PnL: {'+' if pnl >= 0 else ''}{pnl:.2f} "
        f"({pos.get('n_contracts', 0)} contracts)\n"
        f"  Daily PnL: ${daily_pnl:.2f}"
    )
    _send_tg(msg)


# ---------------------------------------------------------------------------
# Settlement checker
# ---------------------------------------------------------------------------

def _check_settlements(state: dict, config: dict) -> None:
    """Check all open positions for settlement and compute realized PnL."""
    import requests as _req

    settled = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for cid, pos in list(state["positions"].items()):
        try:
            resp = _req.get(
                f"https://gamma-api.polymarket.com/markets/{cid}",
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            continue

        # Determine result
        prices = data.get("outcomePrices", "")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except (json.JSONDecodeError, ValueError):
                continue
        if not prices or len(prices) < 2:
            continue

        yes_p = float(prices[0])
        no_p = float(prices[1])
        result = None
        if yes_p >= 0.99:
            result = "yes"
        elif no_p >= 0.99:
            result = "no"
        elif data.get("resolved") is True:
            result = "yes" if yes_p > no_p else "no"

        if result is None:
            continue

        # Compute realized PnL
        n = pos.get("n_contracts", 0)
        total_cost = pos.get("total_cost", 0.0)
        avg_no = total_cost / n if n > 0 else 0.0

        # compute_settlement_pnl expects the YES entry price, not NO cost.
        # record_trade stores yes_price; fall back to 1 - avg_no for old state.
        yes_entry = pos.get("yes_price", 1.0 - avg_no)

        pnl = compute_settlement_pnl(
            yes_entry, result, side="NO", n_contracts=n,
            fee=config.get("fee", 0.0), slippage=0.0,  # already accounted for
        )

        # Update daily PnL (add back cost + realized pnl)
        state["daily_pnl"][today] = state["daily_pnl"].get(today, 0.0) + total_cost + pnl
        daily_pnl_val = state["daily_pnl"].get(today, 0.0)

        logger.info("  SETTLED: %s -> %s | PnL: $%.2f (%d contracts)",
                     pos.get("strike_word", cid)[:40], result.upper(), pnl, n)

        _settlement_alert(cid, pos, result, pnl, daily_pnl_val)
        settled.append(cid)

    # Remove settled positions
    for cid in settled:
        del state["positions"][cid]


# ---------------------------------------------------------------------------
# Main scan cycle
# ---------------------------------------------------------------------------

def run_cycle(
    client,
    calibration: dict,
    config: dict,
    state: dict,
    capital: float,
    max_daily_loss: float,
    mode: str = "live",
) -> int:
    """Run one scan-and-trade cycle.

    Args:
        mode: "live" (real orders), "paper" (fake fills), "dry-run" (no fills)

    Returns number of orders placed/simulated.
    """
    # 1. Check daily loss limit
    ok, today_pnl = check_daily_loss(state, max_daily_loss)
    if not ok:
        logger.warning("Daily loss limit breached ($%.2f, limit $%.2f). Skipping.",
                        abs(today_pnl), max_daily_loss)
        return 0

    # 2. Fetch active markets
    logger.info("Scanning Polymarket mention markets...")
    raw_markets = fetch_mention_markets()
    logger.info("  %d raw markets from Gamma API", len(raw_markets))
    if not raw_markets:
        return 0

    # 3. Enrich with CLOB order books (skip in dry-run if no client)
    if client is not None:
        logger.info("Fetching CLOB order books...")
        markets = enrich_with_order_book(client, raw_markets)
        logger.info("  %d markets with order book liquidity", len(markets))
    else:
        markets = raw_markets

    if not markets:
        return 0

    # 4. Run strategy
    signals = pm_compute_signals(markets, calibration, config=config)
    logger.info("  %d signals pass strategy filter", len(signals))

    if not signals:
        return 0

    # Display signals
    logger.info("")
    logger.info("%3s  %-35s  %5s  %5s  %6s  %7s  %12s  %8s",
                 "#", "Word/Phrase", "YES", "BR", "Edge", "E[PnL]", "Speaker", "Src")
    logger.info("-" * 110)
    for i, sig in enumerate(signals):
        logger.info("%3d  %-35s  %4.0f%%  %4.0f%%  %+5.0f%%  %+6.3f  %12s  %8s",
                     i + 1, sig.get("strike_word", "")[:33],
                     sig["yes_mid"] * 100, sig["base_rate"] * 100,
                     sig["edge"] * 100, sig["expected_pnl"],
                     sig.get("speaker", "")[:12], sig["rate_source"])

    # 5. Execute trades
    max_positions = BOT_CONFIG.get("max_open_positions", 10)
    n_orders = 0
    # Subtract capital already locked in open positions
    open_cost = sum(p.get("total_cost", 0.0) for p in state["positions"].values())
    remaining_capital = capital - open_cost

    for sig in signals:
        # Respect position limit
        if len(state["positions"]) >= max_positions:
            logger.info("Max open positions (%d) reached. Stopping.", max_positions)
            break

        # Re-check daily loss
        ok, _ = check_daily_loss(state, max_daily_loss)
        if not ok:
            logger.warning("Daily loss limit reached during execution.")
            break

        cid = sig["ticker"]

        # Skip if already have position
        if cid in state["positions"] and state["positions"][cid].get("n_contracts", 0) > 0:
            logger.debug("  Skip %s — already positioned", sig["strike_word"][:30])
            continue

        # Size position
        n_contracts, cost = size_position(sig, remaining_capital, config)
        if n_contracts < 1:
            continue

        # Find market with order book
        mkt = next((m for m in markets if m.get("ticker") == cid or m.get("condition_id") == cid), None)
        if not mkt:
            continue

        # Walk order book for +EV levels
        yes_book = mkt.get("yes_book")
        if yes_book is not None:
            yes_bids = yes_book.bids or []
            max_contracts_per = BOT_CONFIG.get("max_contracts_per_level", 50)
            ev_levels = walk_order_book_ev(
                yes_bids, sig["base_rate"], config,
                max_contracts=min(n_contracts, max_contracts_per))

            if not ev_levels:
                logger.debug("  No +EV liquidity for %s", sig["strike_word"][:30])
                continue

            ev_contracts = sum(lv["size"] for lv in ev_levels)
            ev_cost = sum(lv["no_price"] * lv["size"] for lv in ev_levels)
            worst_price = ev_levels[-1]["no_price"]
        else:
            # No order book (dry-run without client) — use signal pricing
            if mode == "dry-run":
                ev_contracts = n_contracts
                ev_cost = cost
                worst_price = 1.0 - sig["yes_mid"]
                ev_levels = [{"no_price": worst_price, "size": n_contracts,
                              "yes_implied": sig["yes_mid"], "epnl": sig["expected_pnl"]}]
            else:
                logger.debug("  No order book for %s", sig["strike_word"][:30])
                continue

        min_order = config.get("min_order_size", 5)
        if ev_contracts < min_order:
            continue

        # Skip wide spreads
        max_spread = config.get("max_no_spread", 0.05)
        if mkt.get("no_spread", 0) > max_spread:
            logger.debug("  Skip %s — spread too wide", sig["strike_word"][:30])
            continue

        logger.info("")
        logger.info("  %s (speaker=%s)", sig["strike_word"][:40], sig.get("speaker", ""))
        logger.info("    YES=%.0f%%  BR=%.0f%%  edge=+%.0f%%  src=%s",
                     sig["yes_mid"] * 100, sig["base_rate"] * 100,
                     sig["edge"] * 100, sig["rate_source"])
        logger.info("    %s %d NO @ $%.3f (cost $%.2f)",
                     "FOK BUY" if mode == "live" else f"[{mode.upper()}]",
                     int(ev_contracts), worst_price, ev_cost)

        # Execute
        order_result = None
        if mode == "live":
            order_result = execute_fok_no(
                client, mkt, n_contracts=int(ev_contracts),
                no_price=worst_price, config=config)
            if not order_result:
                logger.warning("    FOK failed or rejected.")
                continue
        elif mode == "paper":
            order_result = {"paper": True, "n_contracts": int(ev_contracts)}

        # Record trade (live and paper modes)
        if mode in ("live", "paper"):
            avg_no = ev_cost / ev_contracts if ev_contracts > 0 else 0
            record_trade(state, cid, sig["strike_word"],
                         sig.get("speaker", ""), int(ev_contracts),
                         avg_no, ev_cost, order_result)
            _trade_alert(sig, int(ev_contracts), ev_cost, ev_levels)

        remaining_capital -= ev_cost
        n_orders += 1
        logger.info("    Filled. Remaining capital: $%.2f", remaining_capital)

        time.sleep(0.5)

    # 6. Check settlements
    if state["positions"]:
        logger.info("\nChecking %d open positions for settlement...",
                     len(state["positions"]))
        _check_settlements(state, config)

    # 7. Save state
    state["last_scan"] = datetime.now(timezone.utc).isoformat()
    save_positions(state)

    logger.info("Cycle complete. %d orders, %d open positions.",
                 n_orders, len(state["positions"]))
    return n_orders


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PM Mentions trading bot")
    parser.add_argument("--dry-run", action="store_true",
                        help="Scan + signals only, no orders")
    parser.add_argument("--paper", action="store_true",
                        help="Scan + signals + fake fills, no real orders")
    parser.add_argument("--capital", type=float, default=BOT_CONFIG["capital"],
                        help=f"Capital to allocate (default: ${BOT_CONFIG['capital']:.0f})")
    parser.add_argument("--interval", type=int, default=BOT_CONFIG["scan_interval"],
                        help=f"Scan interval in seconds (default: {BOT_CONFIG['scan_interval']})")
    parser.add_argument("--max-daily-loss", type=float,
                        default=BOT_CONFIG["max_daily_loss"],
                        help=f"Daily loss limit (default: ${BOT_CONFIG['max_daily_loss']:.0f})")
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle and exit")
    args = parser.parse_args()

    # Determine mode
    if args.dry_run:
        mode = "dry-run"
    elif args.paper:
        mode = "paper"
    else:
        mode = "live"

    # Load calibration
    cal_path = Path("data/pm_calibration.json")
    if not cal_path.exists():
        logger.error("No calibration data. Run: python pm_base_rates.py")
        sys.exit(1)
    calibration = load_calibration(str(cal_path))
    logger.info("Loaded calibration: %d speakers, %d resolved markets",
                 calibration["metadata"]["n_speakers"],
                 calibration["overall"]["n_markets"])

    # Create CLOB client (skip for dry-run)
    client = None
    if mode == "live":
        logger.info("Authenticating with Polymarket CLOB...")
        client = create_client()
        logger.info("  Authenticated.")
    elif mode == "paper":
        try:
            client = create_client()
            logger.info("Paper mode with real order books.")
        except Exception:
            logger.info("Paper mode without CLOB client (using Gamma prices).")

    # Load state
    state = load_positions()
    logger.info("Loaded state: %d open positions, %d historical trades",
                 len(state["positions"]), len(state["trades"]))

    # Banner
    excluded = PM_CONFIG.get("exclude_speakers", [])
    logger.info("")
    logger.info("=== PM Mentions Bot ===")
    logger.info("  Mode:           %s", mode.upper())
    logger.info("  Capital:        $%.0f", args.capital)
    logger.info("  Max daily loss: $%.0f", args.max_daily_loss)
    logger.info("  Interval:       %ds", args.interval)
    logger.info("  Edge thresholds: %dc/%dc/%dc (high-N/low-N/category)",
                 int(PM_CONFIG["edge_min_speaker_high_n"] * 100),
                 int(PM_CONFIG["edge_min_speaker_low_n"] * 100),
                 int(PM_CONFIG["edge_min_category"] * 100))
    if excluded:
        logger.info("  Excluded:       %s", ", ".join(excluded))
    logger.info("")

    # Main loop
    while True:
        try:
            run_cycle(
                client, calibration, PM_CONFIG, state,
                capital=args.capital,
                max_daily_loss=args.max_daily_loss,
                mode=mode,
            )
        except KeyboardInterrupt:
            logger.info("\nStopped by user.")
            break
        except Exception:
            logger.exception("Error in scan cycle")

        if args.once:
            break

        logger.info("\nNext scan in %ds...", args.interval)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("\nStopped by user.")
            break


if __name__ == "__main__":
    main()
