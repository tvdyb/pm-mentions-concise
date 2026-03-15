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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
