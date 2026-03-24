"""Polymarket CLOB client for PM Mentions trading bot.

Fetches active mention markets from Gamma API, walks order books for +EV
levels, places FOK orders, and tracks positions/PnL.

Imported by bot.py — all public functions are listed in __all__.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from pm_data_collector import parse_speaker, extract_strike, infer_category
from shared import compute_expected_pnl

logger = logging.getLogger("bot.polymarket_client")

__all__ = [
    "BOT_CONFIG",
    "check_daily_loss",
    "create_client",
    "enrich_with_order_book",
    "execute_fok_no",
    "fetch_mention_markets",
    "load_positions",
    "record_trade",
    "save_positions",
    "walk_order_book_ev",
]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon

BOT_CONFIG = {
    "capital": 100.0,
    "max_daily_loss": 25.0,
    "scan_interval": 180,
    "max_contracts_per_level": 50,
    "max_open_positions": 10,
    "min_order_size": 5,
    "telegram_bot_token": os.environ.get("TG_BOT_TOKEN", ""),
    "telegram_chat_id": os.environ.get("TG_CHAT_ID", ""),
    "private_key": os.environ.get("POLYMARKET_PRIVATE_KEY", ""),
    "state_file": "bot_state.json",
}


# ---------------------------------------------------------------------------
# Gamma API helpers
# ---------------------------------------------------------------------------

def _gamma_get(
    path: str,
    params: dict | None = None,
    retries: int = 3,
) -> list | dict | None:
    """GET from Gamma API with retry and backoff."""
    url = f"{GAMMA_API}{path}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                logger.warning("Gamma rate-limited, waiting %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("Gamma request failed (attempt %d): %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return None


# ---------------------------------------------------------------------------
# create_client
# ---------------------------------------------------------------------------

def create_client(private_key: str | None = None, max_retries: int = 3):
    """Create and authenticate a Polymarket CLOB client.

    Lazily imports py_clob_client so tests that don't need the CLOB
    can still import this module without the dependency installed.
    """
    from py_clob_client.client import ClobClient

    key = private_key or BOT_CONFIG["private_key"]
    if not key:
        raise ValueError(
            "No private key. Set POLYMARKET_PRIVATE_KEY env var.")

    client = ClobClient(CLOB_HOST, key=key, chain_id=CHAIN_ID)

    for attempt in range(max_retries):
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            return client
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning("CLOB auth attempt %d failed: %s", attempt + 1, e)
                time.sleep(3)
            else:
                raise


# ---------------------------------------------------------------------------
# fetch_mention_markets
# ---------------------------------------------------------------------------

def fetch_mention_markets() -> list[dict]:
    """Fetch active Polymarket mention markets from the Gamma API.

    Reuses parse_speaker(), extract_strike(), infer_category() from
    pm_data_collector for consistent parsing with the calibration data.

    Returns list of market dicts matching what compute_signals() expects.
    """
    all_markets: list[dict] = []
    offset = 0

    while True:
        events = _gamma_get("/events", {
            "active": "true",
            "tag_slug": "mention-markets",
            "limit": 100,
            "offset": offset,
        })
        if not events:
            break

        for event in events:
            event_title = event.get("title", "")
            speaker = parse_speaker(event_title)
            category = infer_category(speaker, event_title)

            for m in event.get("markets", []):
                # Parse outcome prices
                prices_raw = m.get("outcomePrices", "")
                if isinstance(prices_raw, str):
                    try:
                        prices_raw = json.loads(prices_raw)
                    except (json.JSONDecodeError, ValueError):
                        continue
                if not prices_raw or len(prices_raw) < 2:
                    continue
                yes_mid = float(prices_raw[0])
                if yes_mid <= 0.01 or yes_mid >= 0.99:
                    continue

                # Parse CLOB token IDs
                clob_raw = m.get("clobTokenIds", [])
                if isinstance(clob_raw, str):
                    try:
                        clob_raw = json.loads(clob_raw)
                    except (json.JSONDecodeError, ValueError):
                        clob_raw = []
                if not clob_raw or len(clob_raw) < 2:
                    continue

                question = m.get("question", "")
                strike = extract_strike(question)
                condition_id = m.get("conditionId", "")

                # Synthesize series from speaker (PM doesn't have Kalshi-style tickers)
                sp_key = speaker.replace(" ", "_").upper() if speaker else "UNKNOWN"
                series = f"PM_{sp_key}_MENTION"

                all_markets.append({
                    "ticker": condition_id,
                    "condition_id": condition_id,
                    "series": series,
                    "event_ticker": str(event.get("id", "")),
                    "event_title": event_title,
                    "speaker": speaker,
                    "strike_word": strike,
                    "category": category,
                    "yes_mid": yes_mid,
                    "volume": float(m.get("volume", 0) or 0),
                    "close_time": m.get("endDate", ""),
                    "source": "polymarket",
                    "question": question,
                    "yes_token_id": clob_raw[0],
                    "no_token_id": clob_raw[1],
                    "neg_risk": m.get("negRisk", False),
                    "tick_size": str(m.get("minimumTickSize", "0.01")),
                })

        if len(events) < 100:
            break
        offset += 100

    logger.info("Fetched %d active mention markets", len(all_markets))
    return all_markets


# ---------------------------------------------------------------------------
# enrich_with_order_book
# ---------------------------------------------------------------------------

def enrich_with_order_book(client, markets: list[dict]) -> list[dict]:
    """Fetch YES-side order books and attach to market dicts.

    Real NO liquidity comes from YES bids — buying NO at (1 - yes_bid)
    matches against YES bidders on the CLOB.
    """
    enriched: list[dict] = []

    for mkt in markets:
        yes_token_id = mkt.get("yes_token_id")
        if not yes_token_id:
            continue

        try:
            yes_book = client.get_order_book(yes_token_id)
        except Exception as e:
            logger.debug("Order book fetch failed for %s: %s",
                         mkt.get("strike_word", "")[:30], e)
            continue

        yes_bids = yes_book.bids or []
        yes_asks = yes_book.asks or []
        if not yes_bids:
            continue

        # CLOB returns bids descending (best first), asks ascending (best first)
        best_bid = float(yes_bids[0].price)
        best_ask = float(yes_asks[0].price) if yes_asks else 1.0
        spread = best_ask - best_bid

        mkt = dict(mkt)  # shallow copy
        mkt["yes_book"] = yes_book
        mkt["yes_best_bid"] = best_bid
        mkt["yes_best_ask"] = best_ask
        mkt["yes_spread"] = spread
        mkt["no_best_ask"] = 1.0 - best_bid
        mkt["no_spread"] = spread
        enriched.append(mkt)

        time.sleep(0.15)  # rate-limit

    return enriched


# ---------------------------------------------------------------------------
# walk_order_book_ev
# ---------------------------------------------------------------------------

def walk_order_book_ev(
    yes_bids: list,
    base_rate: float,
    config: dict,
    max_contracts: int,
) -> list[dict]:
    """Walk YES bids from highest to lowest, taking only +EV levels for NO.

    Args:
        yes_bids: Bid objects with .price and .size (strings), sorted
                  ascending (CLOB format).
        base_rate: Historical probability of YES outcome.
        config: Dict with 'fee' and 'slippage' keys.
        max_contracts: Maximum total contracts to take across all levels.

    Returns:
        List of +EV level dicts, each with:
            price      — the YES bid price
            no_price   — 1 - price (what we pay for NO)
            size       — contracts to take at this level
            epnl       — expected PnL per contract
            yes_implied — same as price (for bot.py compatibility)
    """
    if not yes_bids:
        return []

    fee = config.get("fee", 0.0)
    slippage = config.get("slippage", 0.01)

    levels: list[dict] = []
    remaining = max_contracts

    # CLOB returns bids descending (highest first) — walk top-down
    for bid in yes_bids:
        if remaining <= 0:
            break

        yes_price = float(bid.price)
        available = float(bid.size)
        no_price = 1.0 - yes_price

        epnl, _ = compute_expected_pnl(
            yes_price, base_rate, fee=fee, slippage=slippage)

        if epnl <= 0:
            break  # all subsequent levels are worse

        take = min(available, remaining)
        levels.append({
            "price": yes_price,
            "no_price": no_price,
            "size": take,
            "epnl": epnl,
            "yes_implied": yes_price,
        })
        remaining -= take

    return levels


# ---------------------------------------------------------------------------
# execute_fok_no
# ---------------------------------------------------------------------------

def execute_fok_no(
    client,
    market: dict,
    n_contracts: int,
    no_price: float,
    config: dict,
) -> dict | None:
    """Place a FOK sell-YES order (equivalent to buying NO).

    Returns order response dict on success, None on failure.
    """
    from py_clob_client.clob_types import OrderArgs, OrderType, PartialCreateOrderOptions

    no_token_id = market.get("no_token_id")
    if not no_token_id:
        logger.warning("No NO token ID for %s", market.get("strike_word", "")[:40])
        return None

    tick_size = market.get("tick_size", "0.01")
    neg_risk = market.get("neg_risk", False)

    # Round to tick
    tick = float(tick_size)
    no_price = round(round(no_price / tick) * tick, 4)

    logger.info("FOK BUY %d NO @ $%.4f — %s",
                n_contracts, no_price, market.get("strike_word", "")[:40])

    try:
        signed_order = client.create_order(
            OrderArgs(
                token_id=no_token_id,
                price=no_price,
                size=n_contracts,
                side="BUY",
            ),
            PartialCreateOrderOptions(
                tick_size=tick_size,
                neg_risk=neg_risk,
            ),
        )
        result = client.post_order(signed_order, orderType=OrderType.FOK)
        logger.info("  Order response: %s", result)
        return result
    except Exception as e:
        logger.error("FOK order failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# record_trade
# ---------------------------------------------------------------------------

def record_trade(
    state: dict,
    condition_id: str,
    strike_word: str,
    speaker: str,
    n_contracts: int,
    no_cost: float,
    total_cost: float,
    order_response: dict | None,
) -> None:
    """Record a trade in bot state.

    Updates positions, appends trade log, and tracks daily PnL.

    Also stores yes_price on the position (= 1.0 - no_cost) so that
    compute_settlement_pnl() receives the correct entry_price at
    settlement time. On accumulation, computes a weighted-average
    yes_price.
    """
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yes_price = 1.0 - no_cost

    # Update or create position
    positions = state["positions"]
    if condition_id in positions:
        pos = positions[condition_id]
        old_n = pos["n_contracts"]
        old_yes = pos.get("yes_price", 1.0 - (pos["total_cost"] / old_n if old_n else 0))
        pos["n_contracts"] += n_contracts
        pos["total_cost"] += total_cost
        # Weighted-average YES entry price
        pos["yes_price"] = (old_yes * old_n + yes_price * n_contracts) / pos["n_contracts"]
    else:
        positions[condition_id] = {
            "condition_id": condition_id,
            "strike_word": strike_word,
            "speaker": speaker,
            "side": "NO",
            "n_contracts": n_contracts,
            "total_cost": total_cost,
            "yes_price": yes_price,
            "opened_at": now,
        }

    # Append trade record
    state["trades"].append({
        "timestamp": now,
        "condition_id": condition_id,
        "strike_word": strike_word,
        "speaker": speaker,
        "action": "BUY_NO",
        "n_contracts": n_contracts,
        "no_cost": no_cost,
        "total_cost": total_cost,
        "yes_price": yes_price,
        "order_id": (order_response or {}).get("orderID", ""),
    })

    # Update daily PnL (cost is cash outflow)
    state["daily_pnl"][today] = state["daily_pnl"].get(today, 0.0) - total_cost


# ---------------------------------------------------------------------------
# check_daily_loss
# ---------------------------------------------------------------------------

def check_daily_loss(
    state: dict,
    max_daily_loss: float,
) -> tuple[bool, float]:
    """Check if daily loss limit has been breached.

    Returns (ok, daily_pnl):
        ok=True  if today's PnL > -max_daily_loss (safe to trade)
        ok=False if today's PnL <= -max_daily_loss (breached)
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_pnl = state.get("daily_pnl", {}).get(today, 0.0)
    return daily_pnl > -max_daily_loss, daily_pnl


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_positions(path: str | None = None) -> dict:
    """Load bot state from disk, or return fresh state."""
    state_path = Path(path or BOT_CONFIG["state_file"])
    if state_path.exists():
        try:
            with open(state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load state from %s: %s", state_path, e)
    return {"positions": {}, "trades": [], "daily_pnl": {}}


def save_positions(state: dict, path: str | None = None) -> None:
    """Save bot state to disk atomically (write tmp + rename)."""
    state_path = Path(path or BOT_CONFIG["state_file"])
    tmp_path = state_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
        tmp_path.replace(state_path)
    except OSError as e:
        logger.error("Failed to save state: %s", e)
