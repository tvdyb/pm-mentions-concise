#!/usr/bin/env python3
"""Fetch all resolved Polymarket mention markets and build a local dataset.

Saves to data/pm_resolved_markets.json in a format parallel to
data/kalshi_all_series.json.

Usage:
    python pm_data_collector.py              # fetch and save
    python pm_data_collector.py --stats      # print stats only (no fetch)
"""

import json
import re
import argparse
import requests
from pathlib import Path

GAMMA_API = "https://gamma-api.polymarket.com"
OUT_PATH = Path("data/pm_resolved_markets.json")


# ---------------------------------------------------------------------------
# Speaker / strike parsing (reused from polymarket_client.py patterns)
# ---------------------------------------------------------------------------

def parse_speaker(title: str) -> str:
    """Extract speaker name from event title."""
    t = title.lower()
    m = re.search(r'what will (.+?) (?:say|post|tweet)', t)
    if m:
        return m.group(1).strip()
    m = re.search(r'will (.+?) (?:say|mention|tweet)', t)
    if m:
        return m.group(1).strip()
    return ""


def extract_strike(question: str) -> str:
    """Extract quoted strike word/phrase from a question."""
    quoted = re.findall(r'"([^"]+)"', question)
    if quoted:
        return " / ".join(quoted)
    quoted = re.findall(r"'([^']+)'", question)
    if quoted:
        return " / ".join(quoted)
    quoted = re.findall(r'\u201c([^\u201d]+)\u201d', question)
    if quoted:
        return " / ".join(quoted)
    return ""


def infer_category(speaker: str, title: str) -> str:
    """Infer category from speaker + event title."""
    t = title.lower()
    if "earnings" in t or "keynote" in t or "gtc" in t:
        return "earnings"
    political = [
        "trump", "powell", "biden", "harris", "vance", "starmer",
        "leavitt", "psaki", "sanders", "kamala", "pelosi", "cuomo",
        "obama", "clinton", "mamdani", "walz", "hochul", "whitmer",
        "buttigieg", "rfk", "netanyahu", "zelenskyy", "zelensky",
        "sacks", "hegseth", "rutte",
    ]
    sp = speaker.lower()
    if any(p in sp for p in political):
        return "political_person"
    # Check title for political context
    if "press conference" in t or "pmq" in t or "truth social" in t:
        return "political_person"
    return "other"


# ---------------------------------------------------------------------------
# Gamma API fetching
# ---------------------------------------------------------------------------

def fetch_resolved_events() -> list[dict]:
    """Fetch all resolved mention-market events from Gamma API."""
    all_events = []
    offset = 0
    while True:
        resp = requests.get(f"{GAMMA_API}/events", params={
            "active": "false",
            "closed": "true",
            "limit": 100,
            "offset": offset,
            "tag_slug": "mention-markets",
        }, timeout=60)
        resp.raise_for_status()
        events = resp.json()
        if not events:
            break
        all_events.extend(events)
        offset += 100
        if len(events) < 100:
            break
    return all_events


def parse_events_to_markets(events: list[dict]) -> list[dict]:
    """Parse Gamma API events into flat market dicts."""
    markets = []
    for e in events:
        event_title = e.get("title", "")
        speaker = parse_speaker(event_title)
        category = infer_category(speaker, event_title)

        for m in e.get("markets", []):
            question = m.get("question", "")
            strike = extract_strike(question)

            prices = m.get("outcomePrices", "")
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except (json.JSONDecodeError, ValueError):
                    continue
            if not prices or len(prices) < 2:
                continue

            yes_p = float(prices[0])
            no_p = float(prices[1])
            if yes_p == 1.0:
                result = "yes"
            elif no_p == 1.0:
                result = "no"
            else:
                result = None  # still open or ambiguous

            volume = float(m.get("volume", 0) or 0)

            markets.append({
                "condition_id": m.get("conditionId", ""),
                "question": question,
                "event_id": str(e.get("id", "")),
                "event_title": event_title,
                "speaker": speaker,
                "strike_word": strike,
                "category": category,
                "result": result,
                "volume": volume,
                "start_date": m.get("startDate", m.get("createdAt", "")),
                "end_date": m.get("endDate", ""),
                "last_yes_price": yes_p,
            })

    return markets


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def print_stats(markets: list[dict]):
    """Print summary stats for the dataset."""
    resolved = [m for m in markets if m["result"] in ("yes", "no")]
    yes_n = sum(1 for m in resolved if m["result"] == "yes")
    no_n = sum(1 for m in resolved if m["result"] == "no")

    print(f"Total markets: {len(markets)}")
    print(f"  Resolved: {len(resolved)} (YES={yes_n}, NO={no_n})")
    print(f"  Unresolved: {len(markets) - len(resolved)}")
    if resolved:
        print(f"  Overall YES rate: {yes_n / len(resolved):.3f}")

    # By speaker
    speaker_stats = {}
    for m in resolved:
        sp = m["speaker"] or "(unknown)"
        if sp not in speaker_stats:
            speaker_stats[sp] = {"yes": 0, "no": 0}
        speaker_stats[sp][m["result"]] += 1

    print(f"\nTop speakers (by resolved market count):")
    for sp, c in sorted(speaker_stats.items(), key=lambda x: -(x[1]["yes"] + x[1]["no"]))[:20]:
        total = c["yes"] + c["no"]
        br = c["yes"] / total
        print(f"  {sp}: {total} markets, BR={br:.3f}")

    # By category
    cat_stats = {}
    for m in resolved:
        cat = m["category"]
        if cat not in cat_stats:
            cat_stats[cat] = {"yes": 0, "no": 0}
        cat_stats[cat][m["result"]] += 1

    print(f"\nBy category:")
    for cat, c in sorted(cat_stats.items(), key=lambda x: -(x[1]["yes"] + x[1]["no"])):
        total = c["yes"] + c["no"]
        br = c["yes"] / total
        print(f"  {cat}: {total} markets, BR={br:.3f}")

    # Date range
    dates = sorted(m["end_date"] for m in resolved if m["end_date"])
    if dates:
        print(f"\nDate range: {dates[0][:10]} to {dates[-1][:10]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch resolved Polymarket mention markets")
    parser.add_argument("--stats", action="store_true",
                        help="Print stats from existing data (no fetch)")
    args = parser.parse_args()

    if args.stats:
        if not OUT_PATH.exists():
            print(f"No data file at {OUT_PATH}. Run without --stats first.")
            return
        with open(OUT_PATH) as f:
            data = json.load(f)
        print_stats(data["markets"])
        return

    print("Fetching resolved mention events from Polymarket...")
    events = fetch_resolved_events()
    print(f"  {len(events)} events")

    print("Parsing markets...")
    markets = parse_events_to_markets(events)
    print(f"  {len(markets)} markets parsed")

    # Save
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "source": "polymarket_gamma_api",
        "tag_slug": "mention-markets",
        "n_events": len(events),
        "n_markets": len(markets),
        "markets": markets,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved to {OUT_PATH}")

    print_stats(markets)


if __name__ == "__main__":
    main()
