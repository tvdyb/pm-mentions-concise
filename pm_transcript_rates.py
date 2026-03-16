#!/usr/bin/env python3
"""Build word-level base rates from political speech transcripts.

This is the political equivalent of LibFrog — instead of earnings call
transcripts, we use press conferences, debates, and SOTU addresses to
compute how often each word/phrase has historically been said by each speaker.

Reads from: pm_mentions/data/entities/events_with_entities.json
             (or pm_mentions/data/transcripts/all_events.json)
Outputs: data/pm_transcript_rates.json

Usage:
    python pm_transcript_rates.py              # build and save
    python pm_transcript_rates.py --show       # show without saving
    python pm_transcript_rates.py --words "Filibuster,Bitcoin,Iran"  # test specific words
"""

import json
import os
import re
import argparse
from collections import defaultdict
from pathlib import Path

# Try both transcript sources — configurable via env var PM_MENTIONS_DIR,
# defaults to ../pm_mentions relative to this file's directory.
_PM_MENTIONS_DIR = Path(
    os.environ.get("PM_MENTIONS_DIR", Path(__file__).resolve().parent.parent / "pm_mentions")
)
TRANSCRIPTS_PATH = _PM_MENTIONS_DIR / "data" / "transcripts" / "all_events.json"
ENTITIES_PATH = _PM_MENTIONS_DIR / "data" / "entities" / "events_with_entities.json"
OUT_PATH = Path("data/pm_transcript_rates.json")

# Speaker name normalization to match pm_base_rates.py conventions
TRANSCRIPT_SPEAKER_MAP = {
    "Donald J. Trump": "trump",
    "Joseph R. Biden, Jr.": "biden",
    "Barack Obama": "obama",
    "Presidential Candidate Debates": "debate",
}


def load_transcripts() -> list[dict]:
    """Load transcript events from the pm_mentions project."""
    # Prefer entities file (has both transcript + entity data)
    path = ENTITIES_PATH if ENTITIES_PATH.exists() else TRANSCRIPTS_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"No transcript data found. Expected at:\n"
            f"  {ENTITIES_PATH}\n  {TRANSCRIPTS_PATH}\n"
            f"Run the pm_mentions scraper first.")
    with open(path) as f:
        return json.load(f)


def normalize_speaker(speaker: str) -> str:
    """Map transcript speaker to canonical name."""
    return TRANSCRIPT_SPEAKER_MAP.get(speaker, speaker.lower())


def compute_word_rate(
    word: str,
    transcripts: list[dict],
    case_sensitive: bool = False,
) -> dict:
    """Check how many transcripts contain a word/phrase.

    Returns {rate, n_events, n_said, events_said_in}.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(r'\b' + re.escape(word) + r'\b', flags)

    n_said = 0
    events_said = []
    for t in transcripts:
        text = t.get("transcript", "")
        if pattern.search(text):
            n_said += 1
            events_said.append(t.get("date", "")[:10])

    n_total = len(transcripts)
    return {
        "base_rate": n_said / n_total if n_total > 0 else 0.0,
        "n_events": n_total,
        "n_said": n_said,
        "source": "transcript",
    }


def build_rates_for_active_markets(
    transcripts: list[dict],
    words_by_speaker: dict[str, list[str]],
) -> dict:
    """Build word-level rates for a set of (speaker, word) pairs.

    Args:
        transcripts: list of transcript event dicts
        words_by_speaker: {speaker: [word1, word2, ...]}

    Returns:
        {speaker|word: {base_rate, n_events, n_said, source}}
    """
    # Group transcripts by normalized speaker
    by_speaker = defaultdict(list)
    for t in transcripts:
        sp = normalize_speaker(t.get("speaker", ""))
        by_speaker[sp].append(t)

    # For debates, also add to individual speakers mentioned
    # (debates have multiple speakers but transcript is combined)

    rates = {}
    for speaker, words in words_by_speaker.items():
        sp_transcripts = by_speaker.get(speaker, [])
        if not sp_transcripts:
            continue

        for word in words:
            if not word:
                continue
            key = f"{speaker}|{word}"
            result = compute_word_rate(word, sp_transcripts)
            rates[key] = result

    return rates


def build_full_rates(transcripts: list[dict]) -> dict:
    """Build rates for all words that have appeared in PM mention markets.

    Scans active PM markets and resolved PM data to find words to rate.
    """
    # Collect all known strike words from PM data
    words_by_speaker = defaultdict(set)

    # From resolved markets
    pm_resolved_path = Path("data/pm_resolved_markets.json")
    if pm_resolved_path.exists():
        with open(pm_resolved_path) as f:
            pm_data = json.load(f)
        for m in pm_data.get("markets", []):
            speaker = m.get("speaker", "").strip().lower()
            # Normalize PM speaker to transcript speaker
            speaker = _pm_speaker_to_transcript(speaker)
            word = m.get("strike_word", "")
            if speaker and word:
                # Handle "X / Y" strike words
                if " / " in word:
                    for part in word.split(" / "):
                        words_by_speaker[speaker].add(part.strip())
                else:
                    words_by_speaker[speaker].add(word)

    # Build rates
    rates = {}
    by_speaker_transcripts = defaultdict(list)
    for t in transcripts:
        sp = normalize_speaker(t.get("speaker", ""))
        by_speaker_transcripts[sp].append(t)

    for speaker, words in words_by_speaker.items():
        sp_transcripts = by_speaker_transcripts.get(speaker, [])
        if not sp_transcripts:
            continue

        for word in words:
            if not word or len(word) < 2:
                continue
            key = f"{speaker}|{word}"
            result = compute_word_rate(word, sp_transcripts)
            rates[key] = result

    return rates


# Speaker mapping: PM speaker names -> transcript speaker names
PM_TO_TRANSCRIPT_SPEAKER = {
    "trump": "trump",
    "donald trump": "trump",
    "biden": "biden",
    "joe biden": "biden",
    "kamala": "biden",  # Kamala appears in Biden transcripts too
    "kamala harris": "biden",
    "obama": "obama",
    "barack obama": "obama",
}


def _pm_speaker_to_transcript(pm_speaker: str) -> str:
    """Map a PM speaker name to the transcript speaker name."""
    sp = pm_speaker.strip().lower()
    return PM_TO_TRANSCRIPT_SPEAKER.get(sp, sp)


def load_transcript_rates(path: str = str(OUT_PATH)) -> dict:
    """Load saved transcript rates."""
    with open(path) as f:
        return json.load(f)


_lower_index_cache: dict[int, dict] = {}


def _get_lower_index(word_rates: dict) -> dict:
    """Build/retrieve a case-insensitive index for word_rates."""
    key = id(word_rates)
    if key not in _lower_index_cache:
        _lower_index_cache[key] = {k.lower(): v for k, v in word_rates.items()}
    return _lower_index_cache[key]


def find_transcript_rate(
    speaker: str,
    word: str,
    rates: dict,
    min_events: int = 10,
) -> dict | None:
    """Look up a word-level transcript rate.

    Args:
        speaker: normalized speaker name (e.g., "trump")
        word: strike word/phrase
        rates: loaded transcript rates dict
        min_events: minimum transcripts needed

    Returns:
        {base_rate, n_events, n_said, source} or None
    """
    word_rates = rates.get("rates", rates)

    # Build case-insensitive index (cached per id of word_rates dict)
    lower_index = _get_lower_index(word_rates)

    def _lookup(sp: str, w: str) -> dict | None:
        # Try exact match first, then case-insensitive
        key = f"{sp}|{w}"
        entry = word_rates.get(key) or lower_index.get(key.lower())
        if entry and entry.get("n_events", 0) >= min_events:
            return entry
        return None

    result = _lookup(speaker, word)
    if result:
        return result

    # Try with individual parts for "X / Y" words
    if " / " in word:
        for part in word.split(" / "):
            result = _lookup(speaker, part.strip())
            if result:
                return result

    return None


def print_rates(rates: dict, limit: int = 50):
    """Print transcript rates summary."""
    items = rates.get("rates", rates)
    if not items:
        print("No rates computed.")
        return

    # Group by speaker
    by_speaker = defaultdict(list)
    for key, data in items.items():
        if "|" not in key:
            continue
        speaker, word = key.split("|", 1)
        by_speaker[speaker].append((word, data))

    for speaker in sorted(by_speaker, key=lambda s: -len(by_speaker[s])):
        words = by_speaker[speaker]
        print(f"\n{speaker} ({len(words)} words, "
              f"{words[0][1]['n_events'] if words else 0} transcripts):")

        # Sort by base rate descending
        for word, data in sorted(words, key=lambda x: -x[1]["base_rate"])[:limit]:
            br = data["base_rate"]
            n = data["n_said"]
            total = data["n_events"]
            bar = "#" * int(br * 20)
            print(f"  {word:<30s}  {n:>3}/{total}  {br:>5.0%}  {bar}")


def main():
    parser = argparse.ArgumentParser(
        description="Build word-level rates from political transcripts")
    parser.add_argument("--show", action="store_true",
                        help="Show without saving")
    parser.add_argument("--words", type=str, default="",
                        help="Comma-separated words to test")
    args = parser.parse_args()

    print("Loading transcripts...")
    transcripts = load_transcripts()
    print(f"  {len(transcripts)} events")

    if args.words:
        # Quick test mode
        words = [w.strip() for w in args.words.split(",")]
        by_speaker = defaultdict(list)
        for t in transcripts:
            sp = normalize_speaker(t.get("speaker", ""))
            by_speaker[sp].append(t)

        for speaker, sp_transcripts in sorted(by_speaker.items(),
                                               key=lambda x: -len(x[1])):
            if len(sp_transcripts) < 5:
                continue
            print(f"\n{speaker} ({len(sp_transcripts)} transcripts):")
            for word in words:
                result = compute_word_rate(word, sp_transcripts)
                print(f"  \"{word}\": {result['n_said']}/{result['n_events']} "
                      f"= {result['base_rate']:.0%}")
        return

    print("Building word-level rates from PM market data...")
    rates = build_full_rates(transcripts)
    print(f"  {len(rates)} word/speaker rates computed")

    output = {
        "rates": rates,
        "metadata": {
            "n_rates": len(rates),
            "n_transcripts": len(transcripts),
            "transcript_source": str(ENTITIES_PATH if ENTITIES_PATH.exists()
                                     else TRANSCRIPTS_PATH),
        },
    }

    print_rates(output, limit=30)

    if not args.show:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
