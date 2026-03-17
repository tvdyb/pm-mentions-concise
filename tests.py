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

    def test_transcript_rate_preferred_over_speaker(self):
        """When transcript word-level rate exists, it should be used over speaker rate."""
        from pm_transcript_rates import OUT_PATH
        if not OUT_PATH.exists():
            pytest.skip("Transcript rates not generated")
        cal = self._make_calibration()
        # "Filibuster" should have 0% rate in Trump transcripts
        mkts = [self._make_pm_market(yes_mid=0.50, strike_word="Filibuster")]
        signals = pm_compute_signals(mkts, cal)
        assert len(signals) == 1
        sig = signals[0]
        assert sig["rate_source"] == "transcript"
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
    def _make_asks(self, price_size_pairs):
        """Build mock asks from (price, size) pairs, sorted ascending."""
        return [MockOrderSummary(price=str(p), size=str(s))
                for p, s in sorted(price_size_pairs)]

    def test_all_levels_positive_ev(self):
        """All ask levels are +EV → take all of them."""
        asks = self._make_asks([(0.60, 10), (0.65, 20), (0.70, 15)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        # base_rate = 0.10 → YES implied at 0.40 has epnl > 0
        levels = walk_order_book_ev(asks, base_rate=0.10, config=cfg, max_contracts=100)
        assert len(levels) == 3
        total = sum(lv["size"] for lv in levels)
        assert total == 45

    def test_stops_at_negative_ev(self):
        """Stops walking when a level is not +EV."""
        # base_rate=0.45 → YES implied must be > ~0.45 for +EV
        # NO price 0.50 → YES=0.50 → marginal
        # NO price 0.40 → YES=0.60 → not +EV if BR=0.45 (epnl depends on exact calc)
        asks = self._make_asks([(0.70, 10), (0.30, 10)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        # base_rate=0.45: NO@0.70 → YES=0.30 → edge=0.30-0.45=-0.15 → NOT +EV
        # Actually wait, for NO buying: we want YES to be HIGH (overpriced)
        # epnl = P(NO)*eff_yes - P(YES)*no_cost
        # at NO@0.70: eff_yes = 1-0.70-0.01=0.29, no_cost=0.70
        # epnl = 0.55 * 0.29 - 0.45 * 0.70 = 0.1595 - 0.315 = -0.1555 → not +EV
        # at NO@0.30: eff_yes = 1-0.30-0.01=0.69, no_cost=0.30
        # epnl = 0.55 * 0.69 - 0.45 * 0.30 = 0.3795 - 0.135 = +0.2445 → +EV
        levels = walk_order_book_ev(asks, base_rate=0.45, config=cfg, max_contracts=100)
        # Only the NO@0.30 level is +EV
        assert len(levels) == 1
        assert levels[0]["no_price"] == 0.30

    def test_respects_max_contracts(self):
        """Stops when max_contracts is reached."""
        asks = self._make_asks([(0.60, 100)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev(asks, base_rate=0.10, config=cfg, max_contracts=25)
        assert len(levels) == 1
        assert levels[0]["size"] == 25

    def test_empty_asks(self):
        """No asks → no levels."""
        levels = walk_order_book_ev(
            [], base_rate=0.10, config={"fee": 0.0, "slippage": 0.01},
            max_contracts=100)
        assert levels == []

    def test_all_negative_ev(self):
        """All levels are -EV → empty result."""
        # base_rate=0.90 → almost always YES wins → NO is -EV
        asks = self._make_asks([(0.20, 10)])
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev(asks, base_rate=0.90, config=cfg, max_contracts=100)
        assert levels == []


# ---------------------------------------------------------------------------
# FOK +EV gating tests
# ---------------------------------------------------------------------------

class TestFokEvGating:
    """Verify that the strategy only sends FOK when +EV at executable price."""

    def test_positive_ev_at_best_ask(self):
        """If best NO ask gives +EV, walk_order_book_ev returns it."""
        ask = MockOrderSummary(price="0.60", size="50")
        cfg = {"fee": 0.0, "slippage": 0.01}
        levels = walk_order_book_ev([ask], base_rate=0.20, config=cfg, max_contracts=50)
        assert len(levels) == 1
        assert levels[0]["epnl"] > 0

    def test_negative_ev_at_best_ask(self):
        """If best NO ask is -EV, no FOK should be sent."""
        ask = MockOrderSummary(price="0.10", size="50")
        cfg = {"fee": 0.0, "slippage": 0.01}
        # NO@0.10 → YES=0.90 → base_rate=0.85 → high BR, small edge
        # epnl = 0.15 * (0.90-0.01) - 0.85 * 0.10 = 0.1335 - 0.085 = +0.048 → actually +EV
        # Let's use base_rate=0.95 instead
        levels = walk_order_book_ev([ask], base_rate=0.95, config=cfg, max_contracts=50)
        assert levels == []


# ---------------------------------------------------------------------------
# Position tracking tests
# ---------------------------------------------------------------------------

class TestPositionTracking:
    def test_record_trade_creates_position(self):
        state = {"positions": {}, "trades": [], "daily_pnl": {}}
        record_trade(state, "cond_abc", "Bitcoin", "trump",
                     10, 0.70, 7.0, {"orderID": "ord123"})
        assert "cond_abc" in state["positions"]
        pos = state["positions"]["cond_abc"]
        assert pos["n_contracts"] == 10
        assert abs(pos["total_cost"] - 7.0) < 1e-6
        assert pos["speaker"] == "trump"
        assert len(state["trades"]) == 1

    def test_record_trade_accumulates(self):
        state = {"positions": {}, "trades": [], "daily_pnl": {}}
        record_trade(state, "cond_abc", "Bitcoin", "trump", 10, 0.70, 7.0, None)
        record_trade(state, "cond_abc", "Bitcoin", "trump", 5, 0.65, 3.25, None)
        pos = state["positions"]["cond_abc"]
        assert pos["n_contracts"] == 15
        assert abs(pos["total_cost"] - 10.25) < 1e-6
        assert len(state["trades"]) == 2

    def test_daily_pnl_tracked(self):
        state = {"positions": {}, "trades": [], "daily_pnl": {}}
        record_trade(state, "c1", "Word1", "trump", 10, 0.70, 7.0, None)
        record_trade(state, "c2", "Word2", "trump", 5, 0.60, 3.0, None)
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert abs(state["daily_pnl"][today] - (-10.0)) < 1e-6


# ---------------------------------------------------------------------------
# Speaker exclusion tests
# ---------------------------------------------------------------------------

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
