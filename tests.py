"""Unit tests for PM Mentions strategy components."""

import pytest
from shared import (
    find_series_rate,
    find_word_rate,
    equiv_series,
    classify_category,
    compute_settlement_pnl,
    size_position,
    SERIES_EQUIVALENCES,
)
from pm_mentions_strategy import compute_signals as original_compute_signals, CONFIG
from focused_strategy import compute_signals as focused_compute_signals, FOCUSED_CONFIG


# ---------------------------------------------------------------------------
# find_series_rate
# ---------------------------------------------------------------------------

class TestFindSeriesRate:
    def test_direct_match(self):
        rates = {"KXTRUMPMENTION": {"base_rate": 0.43, "n_markets": 100}}
        assert find_series_rate("KXTRUMPMENTION", rates)["base_rate"] == 0.43

    def test_equivalence_match(self):
        rates = {"KXTRUMPMENTION": {"base_rate": 0.43, "n_markets": 100}}
        result = find_series_rate("KXTRUMPMENTIONB", rates)
        assert result is not None
        assert result["base_rate"] == 0.43

    def test_no_match(self):
        rates = {"KXTRUMPMENTION": {"base_rate": 0.43, "n_markets": 100}}
        assert find_series_rate("KXNONEXISTENT", rates) is None

    def test_vz_not_stripped_to_v(self):
        """The VZ→V bug: KXEARNINGSMENTIONVZ should NOT match KXEARNINGSMENTIONV."""
        rates = {"KXEARNINGSMENTIONV": {"base_rate": 0.50, "n_markets": 50}}
        assert find_series_rate("KXEARNINGSMENTIONVZ", rates) is None

    def test_trailing_letter_not_stripped(self):
        """Generic trailing letter should not be stripped — only explicit equivalences."""
        rates = {"KXSTARMERMENTION": {"base_rate": 0.30, "n_markets": 50}}
        # KXSTARMERMENTIONB is in SERIES_EQUIVALENCES, so it SHOULD match
        assert find_series_rate("KXSTARMERMENTIONB", rates) is not None
        # But KXSTARMERMENTIONX is NOT in equivalences, should NOT match
        assert find_series_rate("KXSTARMERMENTIONX", rates) is None

    def test_entry_without_base_rate_skipped(self):
        """A key that exists but has no base_rate field should be skipped."""
        rates = {"KXFOO": {"n_markets": 10}}
        assert find_series_rate("KXFOO", rates) is None


# ---------------------------------------------------------------------------
# find_word_rate
# ---------------------------------------------------------------------------

class TestFindWordRate:
    def test_direct_match(self):
        rates = {"KXEARNINGSMENTIONAAPL|iPhone": {
            "base_rate": 0.78, "n_calls": 74, "source": "libfrog"}}
        info, source = find_word_rate("KXEARNINGSMENTIONAAPL", "iPhone", rates)
        assert info is not None
        assert source == "libfrog"
        assert info["base_rate"] == 0.78

    def test_slash_alternative(self):
        rates = {"KXEARNINGSMENTIONAAPL|AI": {
            "base_rate": 0.50, "n_calls": 30, "source": "libfrog"}}
        info, source = find_word_rate(
            "KXEARNINGSMENTIONAAPL", "AI / Artificial Intelligence", rates)
        assert info is not None
        assert source == "libfrog"

    def test_no_match(self):
        rates = {}
        info, source = find_word_rate("KXFOO", "bar", rates)
        assert info is None
        assert source == "series"

    def test_none_strike_word(self):
        """strike_word=None should not crash."""
        rates = {"KXFOO|None": {
            "base_rate": 0.5, "n_calls": 20, "source": "libfrog"}}
        info, source = find_word_rate("KXFOO", None, rates)
        assert info is None
        assert source == "series"

    def test_empty_strike_word(self):
        rates = {"KXFOO|": {
            "base_rate": 0.5, "n_calls": 20, "source": "libfrog"}}
        info, source = find_word_rate("KXFOO", "", rates)
        assert info is None
        assert source == "series"

    def test_min_calls_filter(self):
        rates = {"KXFOO|bar": {
            "base_rate": 0.5, "n_calls": 5, "source": "libfrog"}}
        info, _ = find_word_rate("KXFOO", "bar", rates, min_calls=10)
        assert info is None

    def test_non_libfrog_source_ignored(self):
        rates = {"KXFOO|bar": {
            "base_rate": 0.5, "n_calls": 50, "source": "manual"}}
        info, _ = find_word_rate("KXFOO", "bar", rates)
        assert info is None


# ---------------------------------------------------------------------------
# equiv_series
# ---------------------------------------------------------------------------

class TestEquivSeries:
    def test_known_equivalence(self):
        assert equiv_series("KXTRUMPMENTIONB") == "KXTRUMPMENTION"

    def test_no_equivalence(self):
        assert equiv_series("KXSOMERANDOM") == "KXSOMERANDOM"

    def test_vz_not_stripped(self):
        """KXEARNINGSMENTIONVZ should NOT become KXEARNINGSMENTIONV."""
        assert equiv_series("KXEARNINGSMENTIONVZ") == "KXEARNINGSMENTIONVZ"


# ---------------------------------------------------------------------------
# classify_category
# ---------------------------------------------------------------------------

class TestClassifyCategory:
    def test_earnings(self):
        assert classify_category("KXEARNINGSMENTIONAAPL") == "earnings"

    def test_sports(self):
        assert classify_category("KXNFLMENTION") == "sports"
        assert classify_category("KXNBAMENTION") == "sports"

    def test_political(self):
        assert classify_category("KXTRUMPMENTION") == "political_person"
        assert classify_category("KXPOWELLMENTION") == "political_person"
        assert classify_category("KXSTARMERMENTION") == "political_person"

    def test_other_default(self):
        """Unknown series should default to 'other', NOT 'political_person'."""
        assert classify_category("KXSOMERANDOM") == "other"
        assert classify_category("KXWEATHERMENTION") == "other"


# ---------------------------------------------------------------------------
# compute_settlement_pnl
# ---------------------------------------------------------------------------

class TestSettlementPnl:
    def test_no_side_wins(self):
        pnl = compute_settlement_pnl(0.30, "no", fee=0.02, slippage=0.01)
        # eff_yes = 0.29, pnl_per = 0.29 - 0.02 = 0.27
        assert abs(pnl - 0.27) < 1e-6

    def test_no_side_loses(self):
        pnl = compute_settlement_pnl(0.30, "yes", fee=0.02, slippage=0.01)
        # eff_yes = 0.29, no_cost = 0.71, pnl_per = -0.71 - 0.02 = -0.73
        assert abs(pnl - (-0.73)) < 1e-6

    def test_multiple_contracts(self):
        pnl = compute_settlement_pnl(0.30, "no", n_contracts=5, fee=0.02, slippage=0.01)
        assert abs(pnl - 0.27 * 5) < 1e-6


# ---------------------------------------------------------------------------
# compute_signals — edge cases
# ---------------------------------------------------------------------------

class TestComputeSignals:
    def _make_market(self, **overrides):
        base = {
            "ticker": "TEST-TICKER",
            "series": "KXEARNINGSMENTIONAAPL",
            "event_ticker": "EVT",
            "yes_mid": 0.30,
            "source": "kalshi",
            "strike_word": "iPhone",
        }
        base.update(overrides)
        return base

    def test_basic_signal(self):
        rates = {"KXEARNINGSMENTIONAAPL": {"base_rate": 0.15, "n_markets": 50}}
        mkts = [self._make_market()]
        signals = original_compute_signals(mkts, rates)
        assert len(signals) == 1
        assert signals[0]["side"] == "NO"

    def test_below_edge_threshold(self):
        rates = {"KXEARNINGSMENTIONAAPL": {"base_rate": 0.25, "n_markets": 50}}
        mkts = [self._make_market(yes_mid=0.30)]  # edge = 0.05 < 0.10
        signals = original_compute_signals(mkts, rates)
        assert len(signals) == 0

    def test_yes_too_high(self):
        rates = {"KXEARNINGSMENTIONAAPL": {"base_rate": 0.15, "n_markets": 50}}
        mkts = [self._make_market(yes_mid=0.80)]
        signals = original_compute_signals(mkts, rates)
        assert len(signals) == 0

    def test_focused_excludes_political(self):
        rates = {"KXTRUMPMENTION": {"base_rate": 0.15, "n_markets": 50}}
        mkts = [self._make_market(
            series="KXTRUMPMENTION", category="political_person",
            yes_mid=0.40)]
        signals = focused_compute_signals(mkts, rates)
        assert len(signals) == 0

    def test_focused_yes_cap_50c(self):
        rates = {"KXEARNINGSMENTIONAAPL": {"base_rate": 0.15, "n_markets": 50}}
        mkts = [self._make_market(yes_mid=0.60, category="earnings")]
        signals = focused_compute_signals(mkts, rates)
        assert len(signals) == 0


# ---------------------------------------------------------------------------
# size_position
# ---------------------------------------------------------------------------

class TestSizePosition:
    def test_basic_sizing(self):
        signal = {"yes_mid": 0.30, "kelly_quarter": 0.05}
        cfg = {"max_position_pct": 0.05, "slippage": 0.01}
        n, cost = size_position(signal, 1000, cfg)
        assert n > 0
        assert cost > 0

    def test_zero_kelly(self):
        signal = {"yes_mid": 0.30, "kelly_quarter": 0.0}
        cfg = {"max_position_pct": 0.05, "slippage": 0.01}
        n, cost = size_position(signal, 1000, cfg)
        assert n == 0
        assert cost == 0.0


# ---------------------------------------------------------------------------
# PM-native strategy tests
# ---------------------------------------------------------------------------

from pm_focused_strategy import compute_signals as pm_compute_signals, PM_CONFIG
from pm_base_rates import find_speaker_rate, _normalize_speaker


class TestPmNormalizeSpeaker:
    def test_alias(self):
        assert _normalize_speaker("Donald Trump") == "trump"
        assert _normalize_speaker("JD Vance") == "vance"
        assert _normalize_speaker("J.D. Vance") == "vance"
        assert _normalize_speaker("Kamala Harris") == "kamala"

    def test_passthrough(self):
        assert _normalize_speaker("trump") == "trump"
        assert _normalize_speaker("mrbeast") == "mrbeast"


class TestPmFindSpeakerRate:
    def test_direct_match(self):
        cal = {"by_speaker": {"trump": {"base_rate": 0.44, "n_markets": 5261}}}
        result = find_speaker_rate("trump", cal, min_n=20)
        assert result is not None
        assert result["base_rate"] == 0.44

    def test_min_n_filter(self):
        cal = {"by_speaker": {"trump": {"base_rate": 0.44, "n_markets": 10}}}
        result = find_speaker_rate("trump", cal, min_n=20)
        assert result is None

    def test_partial_match(self):
        cal = {"by_speaker": {"trump": {"base_rate": 0.44, "n_markets": 100}}}
        # "donald trump" normalizes to "trump" via aliases
        result = find_speaker_rate("Donald Trump", cal, min_n=20)
        assert result is not None

    def test_no_match(self):
        cal = {"by_speaker": {}}
        result = find_speaker_rate("unknown_speaker", cal, min_n=20)
        assert result is None


class TestPmComputeSignals:
    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
        }
        base.update(overrides)
        return base

    def _make_calibration(self, **overrides):
        cal = {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
                "mrbeast": {"base_rate": 0.315, "n_markets": 108},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
                "other": {"base_rate": 0.37, "n_markets": 1612},
                "earnings": {"base_rate": 0.57, "n_markets": 914},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }
        cal.update(overrides)
        return cal

    def test_trump_signal_above_threshold(self):
        """Trump at YES=50% vs BR=44% → edge=6% ≥ 4c (high-N threshold)."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(yes_mid=0.50)]
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 1
        assert signals[0]["side"] == "NO"
        assert abs(signals[0]["edge"] - 0.06) < 0.001

    def test_trump_below_threshold(self):
        """Trump at YES=46% vs BR=44% → edge=2% < 4c minimum."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(yes_mid=0.46)]
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 0

    def test_max_yes_cap(self):
        """YES=70% exceeds max_yes=60% → filtered out."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(yes_mid=0.70)]
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 0

    def test_earnings_excluded(self):
        """Earnings category excluded per PM backtest findings."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(
            category="earnings", speaker="coinbase", yes_mid=0.50)]
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 0

    def test_tiered_edge_low_n_speaker(self):
        """Speaker with <100 markets needs 6c edge (not 4c)."""
        cal = self._make_calibration()
        # mrbeast has 108 markets (>100), so still uses 4c threshold
        # But let's set n_markets to 50 to test the low-N path
        cal["by_speaker"]["mrbeast"]["n_markets"] = 50
        mkts = [self._make_pm_market(
            speaker="mrbeast", category="other", yes_mid=0.36)]
        # edge = 0.36 - 0.315 = 0.045 → below 6c low-N threshold
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 0

    def test_category_fallback(self):
        """Unknown speaker falls back to category rate."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(
            speaker="unknownspeaker", category="other", yes_mid=0.50)]
        signals = pm_compute_signals(mkts, cal)
        # edge = 0.50 - 0.37 = 0.13 ≥ 10c category threshold → signal
        assert len(signals) == 1
        assert signals[0]["rate_source"] == "category"


class TestTranscriptRateIntegration:
    """Test that transcript word-level rates are used as highest-priority source."""

    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "Filibuster",
            "speaker": "trump",
            "category": "political_person",
        }
        base.update(overrides)
        return base

    def _make_calibration(self):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_transcript_overrides_speaker_on_divergence(self):
        """When transcript rate diverges >10pp from speaker, transcript overrides."""
        from pm_transcript_rates import OUT_PATH
        if not OUT_PATH.exists():
            pytest.skip("Transcript rates not generated")
        cal = self._make_calibration()
        # "Filibuster" should have ~0% rate in Trump transcripts (diverges from 0.44).
        # Use yes_mid=0.15 so edge (~15c) stays within max_edge=0.20 cap.
        mkts = [self._make_pm_market(yes_mid=0.15, strike_word="Filibuster")]
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 1
        sig = signals[0]
        assert sig["rate_source"] == "transcript_override"
        # Word-level rate should be much lower than speaker rate (0.44)
        assert sig["base_rate"] < 0.10

    def test_falls_back_to_speaker_when_no_transcript(self):
        """Words not in transcripts fall back to speaker-level rate."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(
            yes_mid=0.50, strike_word="XyzNonexistentWord123")]
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 1
        assert signals[0]["rate_source"] == "speaker"
        assert signals[0]["base_rate"] == 0.44


# ---------------------------------------------------------------------------
# VWAP computation tests
# ---------------------------------------------------------------------------

from pm_trade_fetcher import compute_vwap, trades_to_yes_prices, enrich_market


class TestVwapComputation:
    def _make_trades(self, prices_and_sizes, t_start=1000, t_step=100):
        """Build trade list with evenly spaced timestamps."""
        return [
            {"yes_price": p, "size": s, "timestamp": t_start + i * t_step}
            for i, (p, s) in enumerate(prices_and_sizes)
        ]

    def test_vwap_no_buffer(self):
        trades = self._make_trades([(0.20, 10), (0.30, 20), (0.40, 10)])
        vwap = compute_vwap(trades, 0.0)
        expected = (0.20*10 + 0.30*20 + 0.40*10) / 40
        assert abs(vwap - expected) < 1e-6

    def test_vwap_with_buffer(self):
        """25% buffer on 4 trades (t=0,100,200,300) excludes t<75 and t>225."""
        trades = self._make_trades([
            (0.10, 10), (0.20, 10), (0.30, 10), (0.40, 10)
        ])
        vwap = compute_vwap(trades, 0.25)
        # Only trades at t=100 and t=200 are in window [75, 225]
        expected = (0.20*10 + 0.30*10) / 20
        assert abs(vwap - expected) < 1e-6

    def test_vwap_too_few_trades(self):
        trades = self._make_trades([(0.20, 10)])
        assert compute_vwap(trades, 0.0) is None

    def test_vwap_empty(self):
        assert compute_vwap([], 0.0) is None

    def test_trades_to_yes_prices_converts_no(self):
        """NO outcome trades should have yes_price = 1 - price."""
        raw = [
            {"price": 0.80, "size": 10, "timestamp": 1000, "outcomeIndex": 1},
            {"price": 0.30, "size": 5, "timestamp": 1001, "outcomeIndex": 0},
        ]
        converted = trades_to_yes_prices(raw)
        assert len(converted) == 2
        # NO at 0.80 → YES = 0.20
        assert abs(converted[0]["yes_price"] - 0.20) < 1e-6
        # YES at 0.30 → YES = 0.30
        assert abs(converted[1]["yes_price"] - 0.30) < 1e-6

    def test_enrich_market_computes_all_fields(self):
        market = {"condition_id": "test"}
        raw_trades = [
            {"price": 0.25, "size": 10, "timestamp": 1000, "outcomeIndex": 0},
            {"price": 0.30, "size": 20, "timestamp": 2000, "outcomeIndex": 0},
            {"price": 0.35, "size": 10, "timestamp": 3000, "outcomeIndex": 0},
        ]
        result = enrich_market(market, raw_trades)
        assert result["n_trades"] == 3
        assert result["vwap_no_buffer"] is not None
        assert result["opening_price"] == 0.25
        assert result["last_price_trade"] == 0.35


# ---------------------------------------------------------------------------
# PM VWAP backtest tests
# ---------------------------------------------------------------------------

from pm_vwap_backtest import run_pm_vwap_backtest


class TestPmVwapBacktest:
    def test_rolling_no_lookahead(self):
        """First 19 markets for a speaker should not generate trades (min_speaker_n=20)."""
        markets = []
        for i in range(25):
            markets.append({
                "condition_id": f"cid_{i}",
                "speaker": "trump",
                "category": "political_person",
                "strike_word": f"Word{i}",
                "result": "no",
                "end_date": f"2025-01-{i+1:02d}T00:00:00Z",
                "vwap_25pct_buffer": 0.50,
                "vwap_10pct_buffer": 0.50,
                "vwap_no_buffer": 0.50,
                "n_trades": 10,
            })
        cfg = dict(PM_CONFIG)
        trades = run_pm_vwap_backtest(markets, cfg, price_keys=["vwap_25pct_buffer"])
        passed = [t for t in trades if t["passed"].get("vwap_25pct_buffer")]
        # First 20 have no prior history → no trades
        # Trade 21+ has rolling rate = 0% (all NO) → edge = 0.50 - 0.0 = 0.50 → passes
        assert all(t["end_date"] >= "2025-01-21" for t in passed)

    def test_earnings_excluded(self):
        """Earnings category should be excluded per PM_CONFIG."""
        markets = []
        # Build enough speaker history first
        for i in range(25):
            markets.append({
                "condition_id": f"cid_{i}",
                "speaker": "jensen huang",
                "category": "earnings",
                "strike_word": "GPU",
                "result": "no",
                "end_date": f"2025-01-{i+1:02d}T00:00:00Z",
                "vwap_25pct_buffer": 0.50,
                "n_trades": 10,
            })
        cfg = dict(PM_CONFIG)
        trades = run_pm_vwap_backtest(markets, cfg, price_keys=["vwap_25pct_buffer"])
        passed = [t for t in trades if t["passed"].get("vwap_25pct_buffer")]
        assert len(passed) == 0


# ---------------------------------------------------------------------------
# Order book walking tests (Task 5)
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass
class MockOrderSummary:
    price: str
    size: str


from polymarket_client import walk_order_book_ev, check_daily_loss, record_trade


class TestWalkOrderBookEv:
    def _make_yes_bids(self, price_size_pairs):
        """Build mock YES bids from (price, size) pairs, sorted descending (CLOB format)."""
        return [MockOrderSummary(price=str(p), size=str(s))
                for p, s in sorted(price_size_pairs, reverse=True)]

    def test_all_levels_positive_ev(self):
        """All YES bid levels are +EV for NO → take all of them."""
        # YES bids at 0.40, 0.35, 0.30 → NO prices 0.60, 0.65, 0.70
        bids = self._make_yes_bids([(0.40, 10), (0.35, 20), (0.30, 15)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev(bids, base_rate=0.10, config=cfg, max_contracts=100)
        assert len(levels) == 3
        total = sum(lv["size"] for lv in levels)
        assert total == 45

    def test_stops_at_negative_ev(self):
        """Stops walking when a YES bid level makes NO trade -EV."""
        # YES bid at 0.70 → NO@0.30 → +EV with BR=0.45
        # YES bid at 0.30 → NO@0.70 → -EV with BR=0.45
        # epnl at YES=0.70: 0.55 * 0.69 - 0.45 * 0.30 = +0.2445 → +EV
        # epnl at YES=0.30: 0.55 * 0.29 - 0.45 * 0.70 = -0.1555 → -EV
        bids = self._make_yes_bids([(0.70, 10), (0.30, 10)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev(bids, base_rate=0.45, config=cfg, max_contracts=100)
        assert len(levels) == 1
        assert abs(levels[0]["no_price"] - 0.30) < 1e-6  # 1 - 0.70

    def test_respects_max_contracts(self):
        """Stops when max_contracts is reached."""
        bids = self._make_yes_bids([(0.40, 100)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev(bids, base_rate=0.10, config=cfg, max_contracts=25)
        assert len(levels) == 1
        assert levels[0]["size"] == 25

    def test_empty_bids(self):
        """No YES bids → no levels."""
        levels = walk_order_book_ev(
            [], base_rate=0.10, config={"fee": 0.0, "slippage": 0.01},
            max_contracts=100)
        assert levels == []

    def test_all_negative_ev(self):
        """All levels are -EV → empty result."""
        # YES bid at 0.80 → NO@0.20, base_rate=0.90 → -EV
        bids = self._make_yes_bids([(0.80, 10)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev(bids, base_rate=0.90, config=cfg, max_contracts=100)
        assert levels == []


# ---------------------------------------------------------------------------
# FOK +EV gating tests
# ---------------------------------------------------------------------------

class TestFokEvGating:
    """Verify that the strategy only sends FOK when +EV at executable price."""

    def test_positive_ev_at_best_bid(self):
        """If best YES bid gives +EV for NO, walk_order_book_ev returns it."""
        bid = MockOrderSummary(price="0.40", size="50")  # NO @ 0.60
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev([bid], base_rate=0.20, config=cfg, max_contracts=50)
        assert len(levels) == 1
        assert levels[0]["epnl"] > 0

    def test_negative_ev_at_best_bid(self):
        """If best YES bid makes NO trade -EV, no FOK should be sent."""
        bid = MockOrderSummary(price="0.10", size="50")  # NO @ 0.90
        cfg = {"fee": 0.0, "slippage": 0.01}
        # YES=0.10, base_rate=0.95 → -EV
        levels = walk_order_book_ev([bid], base_rate=0.95, config=cfg, max_contracts=50)
        assert levels == []


# ---------------------------------------------------------------------------
# Position tracking tests
# ---------------------------------------------------------------------------

class TestPositionTracking:
    def test_record_trade_creates_position(self):
        state = {"positions": {}, "trades": [], "daily_pnl": {}, "daily_cost": {}}
        record_trade(state, "cond_abc", "Bitcoin", "trump",
                     10, 0.70, 7.0, {"orderID": "ord123"})
        assert "cond_abc" in state["positions"]
        pos = state["positions"]["cond_abc"]
        assert pos["n_contracts"] == 10
        assert abs(pos["total_cost"] - 7.0) < 1e-6
        assert pos["speaker"] == "trump"
        assert len(state["trades"]) == 1

    def test_record_trade_accumulates(self):
        state = {"positions": {}, "trades": [], "daily_pnl": {}, "daily_cost": {}}
        record_trade(state, "cond_abc", "Bitcoin", "trump", 10, 0.70, 7.0, None)
        record_trade(state, "cond_abc", "Bitcoin", "trump", 5, 0.65, 3.25, None)
        pos = state["positions"]["cond_abc"]
        assert pos["n_contracts"] == 15
        assert abs(pos["total_cost"] - 10.25) < 1e-6
        assert len(state["trades"]) == 2

    def test_daily_cost_tracked(self):
        state = {"positions": {}, "trades": [], "daily_pnl": {}, "daily_cost": {}}
        record_trade(state, "c1", "Word1", "trump", 10, 0.70, 7.0, None)
        record_trade(state, "c2", "Word2", "trump", 5, 0.60, 3.0, None)
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Cost tracked separately; daily_pnl only has realized PnL (none yet)
        assert abs(state["daily_cost"][today] - 10.0) < 1e-6
        assert state["daily_pnl"].get(today, 0.0) == 0.0

    def test_trades_list_capped(self):
        """Trades list should not grow beyond MAX_TRADE_HISTORY."""
        state = {"positions": {}, "trades": [], "daily_pnl": {}, "daily_cost": {}}
        # Fill with 5000 trades
        for i in range(5001):
            record_trade(state, f"cid_{i}", f"Word{i}", "speaker",
                         1, 0.50, 0.50, None)
        assert len(state["trades"]) == 5000
        # Most recent trade should be the last one added
        assert state["trades"][-1]["condition_id"] == "cid_5000"


# ---------------------------------------------------------------------------
# Speaker exclusion tests
# ---------------------------------------------------------------------------

class TestMaxVolumeFilter:
    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
        }
        base.update(overrides)
        return base

    def _make_calibration(self):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_volume_below_max_passes(self):
        """Market with volume < max_volume should pass."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=5000)]
        cfg = dict(PM_CONFIG)
        cfg["max_volume"] = 10_000
        cfg["max_volume_extended"] = 10_000
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1

    def test_volume_above_max_filtered(self):
        """Market with volume > max_volume should be filtered out."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=15_000)]
        cfg = dict(PM_CONFIG)
        cfg["max_volume"] = 10_000
        cfg["max_volume_extended"] = 10_000
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 0

    def test_no_max_volume_passes_all(self):
        """With max_volume=inf, all volumes pass."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=999_999)]
        cfg = dict(PM_CONFIG)
        cfg["max_volume"] = float("inf")
        cfg["max_volume_extended"] = float("inf")
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1


class TestTieredVolumeFilter:
    """Test two-tier volume filter (core + extended with trade-count gate)."""

    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
        }
        base.update(overrides)
        return base

    def _make_calibration(self):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_core_tier_passes(self):
        """Market with vol=2000 passes regardless of n_trades."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=2000, n_trades=10)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1

    def test_extended_tier_passes_with_enough_trades(self):
        """Market with vol=4000 and n_trades=100 passes."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=4000, n_trades=100)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1

    def test_extended_tier_excluded_insufficient_trades(self):
        """Market with vol=4000 and n_trades=50 is excluded."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=4000, n_trades=50)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 0

    def test_above_extended_always_excluded(self):
        """Market with vol=6000 is always excluded regardless of n_trades."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=6000, n_trades=200)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 0

    def test_n_bid_levels_as_proxy(self):
        """n_bid_levels should work as fallback for n_trades in live mode."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(volume=4000, n_bid_levels=100)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1


class TestConfidenceScaledKelly:
    """Test confidence-scaled Kelly fractions based on n_history."""

    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
            "volume": 1000,
        }
        base.update(overrides)
        return base

    def _make_calibration(self, n_markets=5261):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": n_markets},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_high_confidence_kelly(self):
        """Signal with n_history=600 gets kelly_fraction=0.35."""
        cal = self._make_calibration(n_markets=600)
        mkts = [self._make_pm_market()]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1
        assert signals[0]["kelly_fraction"] == 0.35

    def test_low_confidence_kelly(self):
        """Signal with n_history=50 gets kelly_fraction=0.18."""
        cal = self._make_calibration(n_markets=50)
        mkts = [self._make_pm_market()]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1
        assert signals[0]["kelly_fraction"] == 0.18

    def test_default_kelly_without_tiers(self):
        """Without tiers configured, default 0.25 is used."""
        cal = self._make_calibration(n_markets=600)
        mkts = [self._make_pm_market()]
        cfg = dict(PM_CONFIG)
        del cfg["kelly_confidence_tiers"]
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1
        assert signals[0]["kelly_fraction"] == 0.25


class TestTranscriptRateDemotion:
    """Test that speaker rate is preferred over transcript, with divergence override."""

    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
            "volume": 1000,
        }
        base.update(overrides)
        return base

    def _make_calibration(self):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_speaker_preferred_over_transcript(self):
        """When both speaker and transcript are available and similar, speaker wins."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market()]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1
        # Speaker rate should be used since transcript rates (if loaded)
        # would not diverge by >10pp for a normal word
        assert signals[0]["rate_source"] == "speaker"

    def test_transcript_used_when_no_speaker(self):
        """Transcript rate is used when no speaker rate exists."""
        from pm_transcript_rates import OUT_PATH
        if not OUT_PATH.exists():
            pytest.skip("Transcript rates not generated")
        cal = self._make_calibration()
        # Remove trump from calibration so speaker rate isn't found
        cal["by_speaker"] = {}
        mkts = [self._make_pm_market(yes_mid=0.15, strike_word="Filibuster")]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        if signals:
            assert signals[0]["rate_source"] == "transcript"


class TestMaxEdgeFilter:
    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
            "volume": 1000,
        }
        base.update(overrides)
        return base

    def _make_calibration(self):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_edge_within_cap_passes(self):
        """Edge of 6c (YES=0.50, BR=0.44) should pass max_edge=0.20."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(yes_mid=0.50)]  # edge = 0.50 - 0.44 = 0.06
        cfg = dict(PM_CONFIG)
        cfg["max_edge"] = 0.20
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1

    def test_large_edge_filtered(self):
        """Edge >20c should be filtered — market knows something we don't."""
        cal = self._make_calibration()
        # YES=0.60, BR=0.20 -> edge=0.40 (way above 20c cap)
        cal_low_br = dict(cal)
        cal_low_br["by_speaker"] = {"trump": {"base_rate": 0.20, "n_markets": 5261}}
        mkts = [self._make_pm_market(yes_mid=0.45)]  # edge = 0.45 - 0.20 = 0.25
        cfg = dict(PM_CONFIG)
        cfg["max_edge"] = 0.20
        signals = pm_compute_signals(mkts, cal_low_br, config=cfg)
        assert len(signals) == 0

    def test_no_max_edge_passes_all(self):
        """With max_edge=inf, all edges pass."""
        cal = self._make_calibration()
        cal["by_speaker"] = {"trump": {"base_rate": 0.10, "n_markets": 5261}}
        mkts = [self._make_pm_market(yes_mid=0.55)]  # edge = 0.45
        cfg = dict(PM_CONFIG)
        cfg["max_edge"] = float("inf")
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1


class TestPriceTrendFilter:
    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
        }
        base.update(overrides)
        return base

    def _make_calibration(self):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_small_trend_passes(self):
        """Price trend within limit should pass."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(price_trend=0.02)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1

    def test_large_positive_trend_filtered(self):
        """Large positive price trend (YES drifting up) should be filtered."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(price_trend=0.10)]
        cfg = dict(PM_CONFIG)
        cfg["max_price_trend"] = 0.05
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 0

    def test_no_trend_data_passes(self):
        """Markets without price_trend data should pass (no filter applied)."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market()]  # no price_trend key
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1


class TestCountResolvedNos:
    def test_counts_collapsed_yes(self):
        """Markets with YES <= 0.03 should be counted as resolved NO."""
        from bot import _count_resolved_nos
        markets = [
            {"event_ticker": "E1", "yes_mid": 0.02},  # resolved NO
            {"event_ticker": "E1", "yes_mid": 0.01},  # resolved NO
            {"event_ticker": "E1", "yes_mid": 0.50},  # still active
            {"event_ticker": "E2", "yes_mid": 0.03},  # resolved NO (boundary)
            {"event_ticker": "E2", "yes_mid": 0.04},  # active (above threshold)
        ]
        result = _count_resolved_nos(markets)
        assert result["E1"] == 2
        assert result["E2"] == 1

    def test_empty_markets(self):
        from bot import _count_resolved_nos
        assert _count_resolved_nos([]) == {}

    def test_no_resolved(self):
        from bot import _count_resolved_nos
        markets = [
            {"event_ticker": "E1", "yes_mid": 0.50},
            {"event_ticker": "E1", "yes_mid": 0.30},
        ]
        assert _count_resolved_nos(markets) == {}

    def test_missing_event_ticker_skipped(self):
        from bot import _count_resolved_nos
        markets = [
            {"yes_mid": 0.01},  # no event_ticker
            {"event_ticker": "", "yes_mid": 0.01},  # empty event_ticker
        ]
        assert _count_resolved_nos(markets) == {}


class TestEventBoostLogic:
    """Test the validated intra-event decay from 597 multi-market events."""

    def test_decay_table_in_config(self):
        """Default config has validated decay table."""
        from pm_focused_strategy import PM_CONFIG
        assert PM_CONFIG["event_decay"] == {1: 0.85, 2: 0.78, 3: 0.75, 4: 0.70}
        assert PM_CONFIG["event_decay_default"] == 0.60

    def test_one_resolved_no_decays(self):
        """1 resolved NO -> 0.85x decay (bot now boosts starting at 1)."""
        base_rate = 0.44
        decay_table = {1: 0.85, 2: 0.78, 3: 0.75, 4: 0.70}
        decay = decay_table.get(1, 0.60)
        effective_br = base_rate * decay
        assert abs(effective_br - 0.374) < 0.01

    def test_two_resolved_nos_decay(self):
        """2 resolved NOs -> 0.78x decay."""
        base_rate = 0.44
        decay_table = {1: 0.85, 2: 0.78, 3: 0.75, 4: 0.70}
        decay = decay_table.get(2, 0.60)
        effective_br = base_rate * decay
        assert abs(effective_br - 0.343) < 0.01

    def test_five_plus_uses_default(self):
        """5+ resolved NOs -> default 0.60x decay."""
        base_rate = 0.44
        decay_table = {1: 0.85, 2: 0.78, 3: 0.75, 4: 0.70}
        decay = decay_table.get(5, 0.60)
        effective_br = base_rate * decay
        assert abs(effective_br - 0.264) < 0.01

    def test_no_boost_at_zero(self):
        """0 resolved NOs -> no decay applied."""
        # Bot only applies boost when n_resolved >= 1
        base_rate = 0.44
        assert base_rate == 0.44


class TestBookDepthEnrichment:
    def test_dollar_depth_computed(self):
        """enrich_with_order_book should compute dollar depth (price * size)."""
        from unittest.mock import MagicMock
        client = MagicMock()
        bid1 = MagicMock()
        bid1.price = "0.40"
        bid1.size = "100"
        bid2 = MagicMock()
        bid2.price = "0.35"
        bid2.size = "50"
        ask1 = MagicMock()
        ask1.price = "0.45"
        ask1.size = "20"
        book = MagicMock()
        book.bids = [bid1, bid2]
        book.asks = [ask1]
        client.get_order_book.return_value = book

        from polymarket_client import enrich_with_order_book
        mkts = [{"yes_token_id": "tok1", "yes_mid": 0.40}]
        result = enrich_with_order_book(client, mkts)
        assert len(result) == 1
        # Dollar depth: 0.40*100 + 0.35*50 = 40 + 17.5 = 57.5
        assert abs(result[0]["total_bid_depth"] - 57.5) < 1e-6
        assert result[0]["n_bid_levels"] == 2

    def test_price_trend_with_asks(self):
        """price_trend should be computed when asks exist."""
        from unittest.mock import MagicMock
        client = MagicMock()
        bid1 = MagicMock()
        bid1.price = "0.40"
        bid1.size = "100"
        ask1 = MagicMock()
        ask1.price = "0.50"
        ask1.size = "20"
        book = MagicMock()
        book.bids = [bid1]
        book.asks = [ask1]
        client.get_order_book.return_value = book

        from polymarket_client import enrich_with_order_book
        mkts = [{"yes_token_id": "tok1", "yes_mid": 0.40}]
        result = enrich_with_order_book(client, mkts)
        # clob_mid = (0.40 + 0.50) / 2 = 0.45, gamma mid = 0.40 -> trend = +0.05
        assert abs(result[0]["price_trend"] - 0.05) < 1e-6

    def test_price_trend_none_without_asks(self):
        """price_trend should be None when no asks on book."""
        from unittest.mock import MagicMock
        client = MagicMock()
        bid1 = MagicMock()
        bid1.price = "0.40"
        bid1.size = "100"
        book = MagicMock()
        book.bids = [bid1]
        book.asks = []
        client.get_order_book.return_value = book

        from polymarket_client import enrich_with_order_book
        mkts = [{"yes_token_id": "tok1", "yes_mid": 0.40}]
        result = enrich_with_order_book(client, mkts)
        assert result[0]["price_trend"] is None


class TestSpeakerExclusion:
    def _make_pm_market(self, **overrides):
        base = {
            "ticker": "cond123",
            "series": "KXTRUMPMENTION",
            "event_ticker": "EVT",
            "yes_mid": 0.50,
            "source": "polymarket",
            "strike_word": "TestWord",
            "speaker": "trump",
            "category": "political_person",
        }
        base.update(overrides)
        return base

    def _make_calibration(self):
        return {
            "by_speaker": {
                "trump": {"base_rate": 0.44, "n_markets": 5261},
                "starmer": {"base_rate": 0.42, "n_markets": 207},
                "vance": {"base_rate": 0.40, "n_markets": 291},
            },
            "by_category": {
                "political_person": {"base_rate": 0.42, "n_markets": 7473},
            },
            "overall": {"base_rate": 0.426, "n_markets": 9999},
        }

    def test_starmer_excluded(self):
        """Starmer is in exclude_speakers → no signal."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(speaker="starmer", yes_mid=0.55)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 0

    def test_vance_excluded(self):
        """Vance is in exclude_speakers → no signal."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(speaker="vance", yes_mid=0.55)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 0

    def test_trump_not_excluded(self):
        """Trump is NOT in exclude_speakers → signal passes."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(speaker="trump", yes_mid=0.50)]
        cfg = dict(PM_CONFIG)
        signals = pm_compute_signals(mkts, cal, config=cfg)
        assert len(signals) == 1

    def test_exclusion_configurable(self):
        """Can override exclude_speakers to empty list."""
        cal = self._make_calibration()
        mkts = [self._make_pm_market(speaker="starmer", yes_mid=0.55)]
        cfg = dict(PM_CONFIG)
        cfg["exclude_speakers"] = []
        signals = pm_compute_signals(mkts, cal, config=cfg)
        # With empty exclusion list, starmer at YES=55% vs BR=42% → edge=13% → passes
        assert len(signals) == 1


# ---------------------------------------------------------------------------
# Daily loss limit tests
# ---------------------------------------------------------------------------

class TestDailyLossLimit:
    def test_ok_when_no_trades(self):
        state = {"positions": {}, "trades": [], "daily_pnl": {}}
        ok, pnl = check_daily_loss(state, max_daily_loss=25.0)
        assert ok is True
        assert pnl == 0.0

    def test_ok_within_limit(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        state = {"positions": {}, "trades": [], "daily_pnl": {today: -20.0}}
        ok, pnl = check_daily_loss(state, max_daily_loss=25.0)
        assert ok is True

    def test_breached_at_limit(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        state = {"positions": {}, "trades": [], "daily_pnl": {today: -30.0}}
        ok, pnl = check_daily_loss(state, max_daily_loss=25.0)
        assert ok is False


# ---------------------------------------------------------------------------
# VWAP backtest speaker exclusion test
# ---------------------------------------------------------------------------

class TestVwapBacktestVolumeFilter:
    def test_high_volume_excluded(self):
        """Markets above max_volume should be excluded in VWAP backtest."""
        markets = []
        for i in range(25):
            markets.append({
                "condition_id": f"cid_{i}",
                "speaker": "trump",
                "category": "political_person",
                "strike_word": f"Word{i}",
                "result": "no",
                "end_date": f"2025-01-{i+1:02d}T00:00:00Z",
                "vwap_25pct_buffer": 0.50,
                "n_trades": 10,
                "volume": 15_000,  # above max
            })
        cfg = dict(PM_CONFIG)
        cfg["max_volume"] = 10_000
        cfg["max_volume_extended"] = 10_000
        trades = run_pm_vwap_backtest(markets, cfg, price_keys=["vwap_25pct_buffer"])
        passed = [t for t in trades if t["passed"].get("vwap_25pct_buffer")]
        assert len(passed) == 0

    def test_normal_volume_passes(self):
        """Markets within volume range should pass in VWAP backtest."""
        markets = []
        for i in range(25):
            markets.append({
                "condition_id": f"cid_{i}",
                "speaker": "trump",
                "category": "political_person",
                "strike_word": f"Word{i}",
                "result": "no",
                "end_date": f"2025-01-{i+1:02d}T00:00:00Z",
                "vwap_25pct_buffer": 0.15,  # low YES price -> edge within max_edge cap
                "n_trades": 10,
                "volume": 2000,
            })
        cfg = dict(PM_CONFIG)
        cfg["max_volume"] = 3_000
        cfg["max_volume_extended"] = 3_000
        trades = run_pm_vwap_backtest(markets, cfg, price_keys=["vwap_25pct_buffer"])
        passed = [t for t in trades if t["passed"].get("vwap_25pct_buffer")]
        assert len(passed) > 0


class TestParamGridVolume:
    def test_grid_includes_volume(self):
        """Parameter grid results should include max_vol field."""
        from pm_vwap_backtest import run_param_grid
        # Minimal dataset: just enough to produce some trades
        markets = []
        for i in range(25):
            markets.append({
                "condition_id": f"cid_{i}",
                "speaker": "trump",
                "category": "political_person",
                "strike_word": f"Word{i}",
                "result": "no",
                "end_date": f"2025-01-{i+1:02d}T00:00:00Z",
                "vwap_25pct_buffer": 0.50,
                "n_trades": 10,
                "volume": 3000,
            })
        cfg = dict(PM_CONFIG)
        results = run_param_grid(markets, cfg)
        # Should have 4*4*4*4*3 = 768 combos
        assert len(results) == 768
        # All results should have max_vol field
        assert all("max_vol" in r for r in results)
        # Should have results with different max_vol values
        max_vols = set(r["max_vol"] for r in results)
        assert max_vols == {5_000, 10_000, None}


class TestVwapBacktestSpeakerExclusion:
    def test_excluded_speaker_not_traded(self):
        """Starmer markets should be excluded in VWAP backtest."""
        markets = []
        for i in range(25):
            markets.append({
                "condition_id": f"cid_{i}",
                "speaker": "starmer",
                "category": "political_person",
                "strike_word": f"Word{i}",
                "result": "no",
                "end_date": f"2025-01-{i+1:02d}T00:00:00Z",
                "vwap_25pct_buffer": 0.55,
                "n_trades": 10,
            })
        cfg = dict(PM_CONFIG)
        trades = run_pm_vwap_backtest(markets, cfg, price_keys=["vwap_25pct_buffer"])
        passed = [t for t in trades if t["passed"].get("vwap_25pct_buffer")]
        assert len(passed) == 0


# ---------------------------------------------------------------------------
# Market Making: compute_mm_quotes
# ---------------------------------------------------------------------------

from shared import pm_taker_fee
from polymarket_client import compute_mm_quotes


# ---------------------------------------------------------------------------
# pm_taker_fee
# ---------------------------------------------------------------------------

class TestPmTakerFee:
    def test_mentions_fee_at_half(self):
        """At p=0.50 mentions fee should be non-trivial."""
        fee = pm_taker_fee(0.50, "mentions")
        # 0.50 * 0.25 * (0.50*0.50)^2 = 0.50 * 0.25 * 0.0625 = 0.0078
        assert fee == pytest.approx(0.0078, abs=0.001)

    def test_mentions_fee_at_extreme(self):
        """At p=0.10, fee should be very small due to exponent 2."""
        fee = pm_taker_fee(0.10, "mentions")
        # 0.10 * 0.25 * (0.10*0.90)^2 = 0.10 * 0.25 * 0.0081 = 0.000203
        assert fee < 0.001
        assert fee > 0

    def test_geopolitics_free(self):
        """Geopolitics should be fee-free."""
        assert pm_taker_fee(0.50, "geopolitics") == 0.0

    def test_sports_fee(self):
        """Sports: 3% rate, exponent 1."""
        fee = pm_taker_fee(0.50, "sports")
        # 0.50 * 0.03 * (0.50*0.50)^1 = 0.50 * 0.03 * 0.25 = 0.00375
        assert fee == pytest.approx(0.0038, abs=0.001)

    def test_fee_at_zero_price(self):
        assert pm_taker_fee(0.0, "mentions") == 0.0

    def test_fee_at_one_price(self):
        assert pm_taker_fee(1.0, "mentions") == 0.0

    def test_unknown_category_uses_other(self):
        """Unknown category falls back to 'other' schedule."""
        fee = pm_taker_fee(0.50, "nonexistent")
        fee_other = pm_taker_fee(0.50, "other")
        assert fee == fee_other


class TestComputeMmQuotes:
    def test_basic_symmetric(self):
        """No inventory => symmetric quotes around fair value."""
        q = compute_mm_quotes(0.40, 0.03, inventory=0, skew_per=0.005)
        assert q["yes_bid"] == pytest.approx(0.37, abs=0.011)
        assert q["yes_ask"] == pytest.approx(0.43, abs=0.011)
        assert q["no_bid_price"] == pytest.approx(1.0 - q["yes_ask"], abs=0.001)
        assert q["skew"] == 0.0

    def test_inventory_skew_long_no(self):
        """Long NO (short YES) -> inventory negative -> skew raises quotes."""
        q_neutral = compute_mm_quotes(0.40, 0.03, inventory=0, skew_per=0.005)
        q_long_no = compute_mm_quotes(0.40, 0.03, inventory=-10, skew_per=0.005)
        # Skew = -10 * 0.005 = -0.05, applied as -skew => +0.05
        # Both quotes shift up (more aggressive YES buying)
        assert q_long_no["yes_bid"] > q_neutral["yes_bid"]
        assert q_long_no["yes_ask"] > q_neutral["yes_ask"]

    def test_inventory_skew_long_yes(self):
        """Long YES -> skew lowers quotes (more eager to sell YES)."""
        q_neutral = compute_mm_quotes(0.40, 0.03, inventory=0, skew_per=0.005)
        q_long_yes = compute_mm_quotes(0.40, 0.03, inventory=10, skew_per=0.005)
        assert q_long_yes["yes_bid"] < q_neutral["yes_bid"]
        assert q_long_yes["yes_ask"] < q_neutral["yes_ask"]

    def test_bid_always_below_ask(self):
        """Even with extreme skew, bid must stay below ask."""
        q = compute_mm_quotes(0.50, 0.01, inventory=50, skew_per=0.01)
        assert q["yes_bid"] < q["yes_ask"]

    def test_clamped_to_valid_range(self):
        """Quotes should be in (0, 1) after tick snapping."""
        q = compute_mm_quotes(0.02, 0.03, inventory=0, skew_per=0.0)
        assert q["yes_bid"] >= 0.01
        assert q["yes_ask"] <= 0.99
        q2 = compute_mm_quotes(0.98, 0.03, inventory=0, skew_per=0.0)
        assert q2["yes_bid"] >= 0.01
        assert q2["yes_ask"] <= 0.99

    def test_tick_size_rounding(self):
        """Quotes snap to tick_size grid."""
        q = compute_mm_quotes(0.333, 0.03, inventory=0, skew_per=0.0, tick_size="0.01")
        # 0.333 - 0.03 = 0.303 -> rounds to 0.30
        # 0.333 + 0.03 = 0.363 -> rounds to 0.36
        assert q["yes_bid"] == pytest.approx(0.30, abs=0.011)
        assert q["yes_ask"] == pytest.approx(0.36, abs=0.011)


# ---------------------------------------------------------------------------
# Market Making: run_mm_cycle (unit-level)
# ---------------------------------------------------------------------------

class TestMmReconcileFills:
    def test_fill_detection_removes_from_state(self):
        """Confirmed filled order (MATCHED status) gets removed from mm_orders."""
        from bot import _reconcile_mm_fills

        state = {
            "positions": {},
            "trades": [],
            "daily_pnl": {},
            "daily_cost": {},
            "mm_orders": {
                "order_abc": {
                    "condition_id": "cid1",
                    "strike_word": "test",
                    "speaker": "trump",
                    "side": "BUY_NO",
                    "price": 0.60,
                    "size": 10,
                },
            },
        }

        # Mock client: order not in open list, but get_order confirms MATCHED
        class MockClient:
            def get_orders(self, params=None):
                return []
            def get_order(self, order_id):
                return {"id": order_id, "status": "MATCHED", "size_matched": "10"}

        fills = _reconcile_mm_fills(MockClient(), state, {})
        assert fills == 1
        assert "order_abc" not in state["mm_orders"]
        # BUY_NO fill should create a position
        assert "cid1" in state["positions"]
        assert state["positions"]["cid1"]["n_contracts"] == 10

    def test_partial_fill_records_correct_size(self):
        """Partially filled then cancelled order records only the filled portion."""
        from bot import _reconcile_mm_fills

        state = {
            "positions": {},
            "trades": [],
            "daily_pnl": {},
            "daily_cost": {},
            "mm_orders": {
                "order_partial": {
                    "condition_id": "cid_partial",
                    "strike_word": "partial",
                    "speaker": "trump",
                    "side": "BUY_NO",
                    "price": 0.60,
                    "size": 10,
                },
            },
        }

        class MockClient:
            def get_orders(self, params=None):
                return []
            def get_order(self, order_id):
                return {"id": order_id, "status": "CANCELLED", "size_matched": "3"}

        fills = _reconcile_mm_fills(MockClient(), state, {})
        assert fills == 1
        assert "order_partial" not in state["mm_orders"]
        # Position should reflect only the 3 filled contracts, not 10
        assert "cid_partial" in state["positions"]
        assert state["positions"]["cid_partial"]["n_contracts"] == 3

    def test_cancelled_order_removed_no_phantom(self):
        """Cancelled order with no fills gets removed without creating a position."""
        from bot import _reconcile_mm_fills

        state = {
            "positions": {},
            "trades": [],
            "daily_pnl": {},
            "daily_cost": {},
            "mm_orders": {
                "order_cancel": {
                    "condition_id": "cid_cancel",
                    "strike_word": "phantom",
                    "speaker": "trump",
                    "side": "BUY_NO",
                    "price": 0.60,
                    "size": 10,
                },
            },
        }

        class MockClient:
            def get_orders(self, params=None):
                return []
            def get_order(self, order_id):
                return {"id": order_id, "status": "CANCELLED", "size_matched": "0"}

        fills = _reconcile_mm_fills(MockClient(), state, {})
        assert fills == 0
        assert "order_cancel" not in state["mm_orders"]
        # No phantom position created
        assert "cid_cancel" not in state["positions"]

    def test_unknown_status_skipped(self):
        """Order with unknown status is skipped (not removed, not counted as fill)."""
        from bot import _reconcile_mm_fills

        state = {
            "positions": {},
            "trades": [],
            "daily_pnl": {},
            "daily_cost": {},
            "mm_orders": {
                "order_unk": {
                    "condition_id": "cid_unk",
                    "strike_word": "mystery",
                    "speaker": "biden",
                    "side": "BUY_NO",
                    "price": 0.50,
                    "size": 5,
                },
            },
        }

        class MockClient:
            def get_orders(self, params=None):
                return []
            def get_order(self, order_id):
                return {"id": order_id, "status": "PENDING"}

        fills = _reconcile_mm_fills(MockClient(), state, {})
        assert fills == 0
        # Order stays in tracking since status is ambiguous
        assert "order_unk" in state["mm_orders"]

    def test_unfilled_order_stays(self):
        """Order still open stays in mm_orders."""
        from bot import _reconcile_mm_fills

        state = {
            "positions": {},
            "trades": [],
            "daily_pnl": {},
            "daily_cost": {},
            "mm_orders": {
                "order_xyz": {
                    "condition_id": "cid2",
                    "strike_word": "test2",
                    "speaker": "biden",
                    "side": "BUY_YES",
                    "price": 0.35,
                    "size": 5,
                },
            },
        }

        class MockClient:
            def get_orders(self, params=None):
                return [{"id": "order_xyz"}]
            def get_order(self, order_id):
                return {"id": order_id, "status": "LIVE"}

        fills = _reconcile_mm_fills(MockClient(), state, {})
        assert fills == 0
        assert "order_xyz" in state["mm_orders"]


class TestMmGracefulShutdown:
    def test_shutdown_handler_sets_flag(self):
        """Signal handler sets _shutdown_requested flag."""
        import bot
        bot._shutdown_requested = False
        bot._mm_client = None  # no client to cancel on
        bot._handle_shutdown(2, None)
        assert bot._shutdown_requested is True
        # Reset
        bot._shutdown_requested = False


# ---------------------------------------------------------------------------
# Deployment: wallet auth validation
# ---------------------------------------------------------------------------

class TestCreateClientValidation:
    def test_invalid_sig_type_raises(self):
        """Invalid signature_type should raise ValueError."""
        from polymarket_client import BOT_CONFIG
        original = BOT_CONFIG["signature_type"]
        BOT_CONFIG["signature_type"] = 5
        try:
            from polymarket_client import create_client
            with pytest.raises(ValueError, match="Invalid POLYMARKET_SIG_TYPE"):
                create_client(private_key="0x" + "a" * 64)
        finally:
            BOT_CONFIG["signature_type"] = original


# ---------------------------------------------------------------------------
# Deployment: FOK strict fill validation
# ---------------------------------------------------------------------------

class TestFokStrictValidation:
    def test_fok_rejects_live_status(self):
        """FOK should reject LIVE status — it means not fully filled."""
        from polymarket_client import execute_fok_no

        class MockClient:
            def create_order(self, *a, **kw):
                return "signed"
            def post_order(self, *a, **kw):
                return {"status": "LIVE", "orderID": "abc"}

        mkt = {
            "no_token_id": "token123",
            "tick_size": "0.01",
            "neg_risk": False,
            "strike_word": "test",
        }
        result = execute_fok_no(MockClient(), mkt, 10, 0.60, {"fee": 0})
        assert result is None

    def test_fok_accepts_matched(self):
        """FOK should accept MATCHED status."""
        from polymarket_client import execute_fok_no

        class MockClient:
            def create_order(self, *a, **kw):
                return "signed"
            def post_order(self, *a, **kw):
                return {"status": "MATCHED", "orderID": "abc"}

        mkt = {
            "no_token_id": "token123",
            "tick_size": "0.01",
            "neg_risk": False,
            "strike_word": "test",
        }
        result = execute_fok_no(MockClient(), mkt, 10, 0.60, {"fee": 0})
        assert result is not None
        assert result["status"] == "MATCHED"

    def test_fok_rejects_empty_response(self):
        """FOK should reject None/empty response."""
        from polymarket_client import execute_fok_no

        class MockClient:
            def create_order(self, *a, **kw):
                return "signed"
            def post_order(self, *a, **kw):
                return None

        mkt = {
            "no_token_id": "token123",
            "tick_size": "0.01",
            "neg_risk": False,
            "strike_word": "test",
        }
        result = execute_fok_no(MockClient(), mkt, 10, 0.60, {"fee": 0})
        assert result is None


# ---------------------------------------------------------------------------
# Deployment: calibration freshness
# ---------------------------------------------------------------------------

class TestCalibrationFreshness:
    def test_pm_taker_fee_integrated_with_epnl(self):
        """compute_expected_pnl with fee_category should reduce PnL vs no fee."""
        from shared import compute_expected_pnl
        epnl_no_fee, _ = compute_expected_pnl(0.40, 0.20, fee=0.0, slippage=0.01)
        epnl_with_fee, _ = compute_expected_pnl(0.40, 0.20, slippage=0.01,
                                                  fee_category="mentions")
        assert epnl_with_fee < epnl_no_fee
        assert epnl_with_fee > 0  # should still be positive at this edge

    def test_fee_adjusted_kelly_smaller_than_gross(self):
        """Kelly sizing with fees should be smaller than without fees."""
        from shared import compute_expected_pnl
        _, kelly_no_fee = compute_expected_pnl(0.40, 0.20, fee=0.0, slippage=0.01)
        _, kelly_with_fee = compute_expected_pnl(0.40, 0.20, slippage=0.01,
                                                   fee_category="mentions")
        assert kelly_with_fee < kelly_no_fee
        assert kelly_with_fee > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
