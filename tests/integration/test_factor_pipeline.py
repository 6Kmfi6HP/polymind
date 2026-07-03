"""Integration tests: Factor pipeline + Backtesting end-to-end."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.backtesting.data import BacktestDataConfig, DataLoader, DataSource, MarketDataPoint
from polymind.backtesting.engine import BacktestConfig, BacktestEngine
from polymind.backtesting.factor_bt import FactorBacktestConfig, FactorBacktester
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.execution.fill_model import MarketSnapshot
from polymind.factors.execution import ExecutionBridgeConfig, FactorExecutionBridge
from polymind.factors.filters import FilterConfig, apply_all_filters
from polymind.factors.pipeline import (
    FactorPipeline,
    MarketFeatures,
    ScoreResult,
    UniverseSnapshot,
)
from polymind.factors.portfolio_construction import PortfolioConfig, construct_portfolio
from polymind.factors.scoring import momentum_score, rank_normalize
from polymind.storage.price_store import PriceSnapshot, PriceStore


# =========================================================================
# Scenario 1: Full factor pipeline flow
# =========================================================================


def _feature_fn(universe: UniverseSnapshot) -> UniverseSnapshot:
    """Compute features — identity passthrough for test data."""
    return universe


def _score_fn(universe: UniverseSnapshot) -> ScoreResult:
    """Score markets by 24h momentum."""
    raw = momentum_score(universe, lookback="24h")
    ranked = rank_normalize(raw)
    return ScoreResult(scores=ranked, timestamp=universe.timestamp)


def _portfolio_fn(scores: ScoreResult) -> list[PortfolioTarget]:
    """Construct portfolio from ranked scores."""
    config = PortfolioConfig(
        top_n=3,
        max_exposure_per_market=100.0,
        total_exposure=500.0,
        min_confidence=0.0,  # allow rank-normalized scores down to 0.0
    )
    return construct_portfolio(scores.scores, config)


def _filter_fn(universe: UniverseSnapshot) -> UniverseSnapshot:
    """Apply spread and volume filters."""
    config = FilterConfig(max_spread_bps=100.0, min_volume_24h=1000.0)
    return apply_all_filters(universe, config)


class TestFullFactorPipelineFlow:
    """MarketSnapshot creation -> FactorPipeline -> SpreadFilter/VolumeFilter -> FactorExecutionBridge -> OrderIntent."""

    @pytest.mark.asyncio
    async def test_full_pipeline_to_order_intents(self) -> None:
        """Complete flow: universe with filters, scoring, portfolio construction, and bridge conversion."""
        ts = datetime(2026, 6, 1, 12, 0, 0)

        # --- Build a universe with varied market features ---
        markets = {
            "0xaaa": MarketFeatures(
                market_id="0xaaa",
                mid_price=0.60,
                spread_bps=25.0,
                volume_24h=50_000.0,
                momentum_24h=0.15,
                volatility_24h=0.20,
            ),
            "0xbbb": MarketFeatures(
                market_id="0xbbb",
                mid_price=0.30,
                spread_bps=200.0,  # wide spread -> filtered out
                volume_24h=5_000.0,
                momentum_24h=0.05,
                volatility_24h=0.10,
            ),
            "0xccc": MarketFeatures(
                market_id="0xccc",
                mid_price=1.20,
                spread_bps=50.0,
                volume_24h=800.0,  # low volume -> filtered out
                momentum_24h=-0.10,
                volatility_24h=0.15,
            ),
            "0xddd": MarketFeatures(
                market_id="0xddd",
                mid_price=0.90,
                spread_bps=10.0,
                volume_24h=100_000.0,
                momentum_24h=0.25,
                volatility_24h=0.05,
            ),
        }
        universe = UniverseSnapshot(timestamp=ts, markets=markets)

        # --- Build pipeline with real filters, scoring, and portfolio construction ---
        pipeline = FactorPipeline(
            feature_fn=_feature_fn,
            filter_fn=_filter_fn,
            score_fn=_score_fn,
            portfolio_fn=_portfolio_fn,
        )

        targets = await pipeline.run(universe)

        # After filtering: 0xbbb (spread 200bps) and 0xccc (volume 800) removed
        assert len(targets) <= 2, "At most 2 markets survive filtering"
        target_mids = {t.market_id for t in targets}
        assert "0xaaa" in target_mids
        assert "0xddd" in target_mids

        # Both survivors have positive momentum -> LONG
        for t in targets:
            assert t.direction == PositionDirection.LONG
            assert t.target_size > 0
            assert t.confidence >= 0.0

        # --- Convert targets to OrderIntents via FactorExecutionBridge ---
        bridge = FactorExecutionBridge(ExecutionBridgeConfig())
        all_orders: list = []
        for t in targets:
            snapshot = MarketSnapshot(
                market_id=t.market_id,
                bid_price=0.0,
                bid_size=0.0,
                ask_price=0.0,
                ask_size=0.0,
                mid_price=markets[t.market_id].mid_price,
                timestamp=ts,
            )
            orders = await bridge.to_order_intents(t, snapshot)
            all_orders.extend(orders)

        # Verify orders
        assert len(all_orders) == len(targets)
        for o in all_orders:
            assert o.side.value == "BUY"
            assert o.size > 0
            assert o.market_id in {"0xaaa", "0xddd"}
            assert o.metadata.get("strategy") is not None

    @pytest.mark.asyncio
    async def test_filter_rejects_all_markets(self) -> None:
        """When all markets fail filters, pipeline returns empty targets."""
        ts = datetime(2026, 6, 1, 12, 0, 0)
        universe = UniverseSnapshot(
            timestamp=ts,
            markets={
                "0xeee": MarketFeatures(
                    market_id="0xeee",
                    mid_price=0.005,  # below min_mid_price
                    spread_bps=500.0,  # above max_spread_bps
                    volume_24h=10.0,  # below min_volume_24h
                    momentum_24h=0.0,
                    volatility_24h=0.99,
                ),
            },
        )
        pipeline = FactorPipeline(
            feature_fn=_feature_fn,
            filter_fn=_filter_fn,
            score_fn=_score_fn,
            portfolio_fn=_portfolio_fn,
        )
        targets = await pipeline.run(universe)
        assert targets == []

    @pytest.mark.asyncio
    async def test_empty_universe_returns_empty(self) -> None:
        """An empty universe produces no targets."""
        pipeline = FactorPipeline(
            feature_fn=_feature_fn,
            filter_fn=_filter_fn,
            score_fn=_score_fn,
            portfolio_fn=_portfolio_fn,
        )
        targets = await pipeline.run(UniverseSnapshot(timestamp=datetime.now()))
        assert targets == []


# =========================================================================
# Scenario 2: Factor pipeline + Backtesting integration
# =========================================================================


class TestFactorBacktestIntegration:
    """DataLoader -> FactorBacktester -> FactorBacktestResult."""

    @pytest.mark.asyncio
    async def test_backtest_single_step(self) -> None:
        """Run a single-step backtest and verify FactorBacktestResult fields."""
        loader = DataLoader()
        ts = datetime(2026, 6, 1, 12, 0, 0)

        data_points = [
            MarketDataPoint(
                market_id="0xaaa",
                timestamp=ts,
                bid_price=0.59,
                ask_price=0.61,
                mid_price=0.60,
                bid_size=10_000.0,
                ask_size=10_000.0,
                volume=50_000.0,
            ),
            MarketDataPoint(
                market_id="0xddd",
                timestamp=ts,
                bid_price=0.89,
                ask_price=0.91,
                mid_price=0.90,
                bid_size=15_000.0,
                ask_size=15_000.0,
                volume=100_000.0,
            ),
            MarketDataPoint(
                market_id="0xbbb",
                timestamp=ts,
                bid_price=0.29,
                ask_price=0.31,
                mid_price=0.30,
                bid_size=5_000.0,
                ask_size=5_000.0,
                volume=5_000.0,
            ),
        ]
        loader.load_in_memory(data_points)

        config = BacktestDataConfig(
            source=DataSource.IN_MEMORY,
            market_ids=["0xaaa", "0xbbb", "0xddd"],
        )
        loaded = await loader.load_snapshots_batch(config)
        assert len(loaded) == 3

        # Build scores dict and snapshots dict for FactorBacktester
        scores: dict[str, float] = {
            "0xaaa": 0.8,
            "0xddd": 0.6,
            "0xbbb": 0.2,
        }
        snapshots: dict[str, MarketSnapshot] = {
            dp.market_id: dp.to_market_snapshot() for dp in loaded
        }

        bt_config = FactorBacktestConfig(
            initial_capital=10_000.0,
            top_n=2,
            max_position_size=500.0,
        )
        bt = FactorBacktester(bt_config)
        result = bt.run(scores, snapshots)

        # top_n=2 so 0xaaa (0.8) and 0xddd (0.6) are selected
        assert "0xaaa" in result.market_id
        assert "0xddd" in result.market_id
        assert result.total_trades == 2  # two positions opened
        assert result.win_rate >= 0.0
        # First step: no PnL history yet (1 data point) -> metrics default to 0
        assert result.sharpe == 0.0
        assert result.sortino == 0.0

    @pytest.mark.asyncio
    async def test_backtest_multi_step(self) -> None:
        """Multi-step backtest accumulates PnL and computes metrics."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=2, max_position_size=500.0))
        ts = datetime(2026, 6, 1, 12, 0, 0)

        # Step 1: open positions in 0xaaa and 0xddd
        scores_1 = {"0xaaa": 0.9, "0xddd": 0.7, "0xbbb": 0.1}
        snaps_1: dict[str, MarketSnapshot] = {
            "0xaaa": MarketSnapshot("0xaaa", 0.59, 1000, 0.61, 1000, 0.60, ts),
            "0xddd": MarketSnapshot("0xddd", 0.89, 1000, 0.91, 1000, 0.90, ts),
            "0xbbb": MarketSnapshot("0xbbb", 0.29, 1000, 0.31, 1000, 0.30, ts),
        }
        r1 = bt.run(scores_1, snaps_1)
        assert r1.total_trades == 2  # opened 2

        # Step 2: 0xddd drops out, 0xbbb enters -> close 0xddd, open 0xbbb
        scores_2 = {"0xaaa": 0.85, "0xbbb": 0.75, "0xddd": 0.3}
        snaps_2: dict[str, MarketSnapshot] = {
            "0xaaa": MarketSnapshot("0xaaa", 0.62, 1000, 0.64, 1000, 0.63, ts),
            "0xbbb": MarketSnapshot("0xbbb", 0.32, 1000, 0.34, 1000, 0.33, ts),
            "0xddd": MarketSnapshot("0xddd", 0.88, 1000, 0.90, 1000, 0.89, ts),
        }
        r2 = bt.run(scores_2, snaps_2)
        assert r2.total_trades == 4  # 2 new trades (close 0xddd, open 0xbbb)
        assert len(r2.pnl_history) >= 1

        # Step 3: all positions close, no new ones
        scores_3: dict[str, float] = {}
        snaps_3: dict[str, MarketSnapshot] = {}
        r3 = bt.run(scores_3, snaps_3)
        assert r3.total_trades >= 4  # accumulated trades
        # With >=2 PnL data points, sharpe/sortino should be computed
        if len(r3.pnl_history) >= 2:
            assert r3.sharpe != 0.0 or r3.total_return == 0.0
        assert r3.max_drawdown >= 0.0
        assert r3.num_winners + r3.num_losers == r3.total_trades

    @pytest.mark.asyncio
    async def test_backtest_empty_scores(self) -> None:
        """Empty scores produce an empty result."""
        bt = FactorBacktester(FactorBacktestConfig())
        result = bt.run({}, {})
        assert result.total_trades == 0
        assert result.total_return == 0.0

    @pytest.mark.asyncio
    async def test_backtest_no_matching_snapshots(self) -> None:
        """Scores with no corresponding snapshots are skipped."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=2))
        ts = datetime(2026, 6, 1, 12, 0, 0)
        scores = {"0xaaa": 0.9, "0xddd": 0.7}
        snapshots = {
            "0xaaa": MarketSnapshot("0xaaa", 0.59, 1000, 0.61, 1000, 0.60, ts),
        }
        result = bt.run(scores, snapshots)
        # Only 0xaaa has a snapshot, so only 1 trade
        assert result.total_trades == 1
        assert "0xaaa" in result.market_id


# =========================================================================
# Scenario 3: Price storage + Backtesting integration
# =========================================================================


class TestPriceStoreBacktestIntegration:
    """PriceStore append/read -> BacktestEngine end-to-end."""

    @pytest.mark.asyncio
    async def test_price_store_to_backtest_engine(self) -> None:
        """Append PriceSnapshots, read them back, and run BacktestEngine."""
        store = PriceStore(path=None)  # in-memory
        ts = datetime(2026, 6, 1, 12, 0, 0)

        # --- Append snapshots for two markets ---
        snapshots_t0 = [
            PriceSnapshot(
                market_id="0xaaa",
                timestamp=ts,
                bid_price=0.59,
                ask_price=0.61,
                mid_price=0.60,
                bid_size=10_000.0,
                ask_size=10_000.0,
                volume=50_000.0,
            ),
            PriceSnapshot(
                market_id="0xddd",
                timestamp=ts,
                bid_price=0.89,
                ask_price=0.91,
                mid_price=0.90,
                bid_size=15_000.0,
                ask_size=15_000.0,
                volume=100_000.0,
            ),
        ]
        for s in snapshots_t0:
            await store.append_snapshot(s)

        # --- Read back and verify ---
        loaded = await store.read_snapshots_batch("0xaaa")
        assert len(loaded) == 1
        assert loaded[0].mid_price == 0.60

        all_ids = await store.get_market_ids()
        assert sorted(all_ids) == ["0xaaa", "0xddd"]

        # --- Build UniverseSnapshot from PriceStore data ---
        market_features: dict[str, MarketFeatures] = {}
        for mid in all_ids:
            snaps = await store.read_snapshots_batch(mid)
            if snaps:
                latest = snaps[-1]
                market_features[mid] = MarketFeatures(
                    market_id=mid,
                    mid_price=latest.mid_price,
                    spread_bps=(
                        (latest.ask_price - latest.bid_price) / latest.mid_price * 10_000
                        if latest.mid_price > 0
                        else 0.0
                    ),
                    volume_24h=latest.volume,
                )

        universe = UniverseSnapshot(timestamp=ts, markets=market_features)
        assert len(universe.markets) == 2

        # --- Create a minimal pipeline ---
        pipeline = FactorPipeline(
            feature_fn=_feature_fn,
            filter_fn=lambda u: u,  # no filtering for this test
            score_fn=_score_fn,
            portfolio_fn=_portfolio_fn,
        )

        # --- Run BacktestEngine ---
        engine = BacktestEngine(pipeline, BacktestConfig(initial_capital=10_000.0))
        result = await engine.run([universe])

        assert result.num_trades >= 0
        assert result.total_return_pct is not None
        assert len(result.portfolio_values) >= 1
        assert result.portfolio_values[0] == 10_000.0

    @pytest.mark.asyncio
    async def test_price_store_multi_step_backtest(self) -> None:
        """Multiple time steps of PriceSnapshots through BacktestEngine."""
        store = PriceStore(path=None)
        ts0 = datetime(2026, 6, 1, 12, 0, 0)
        ts1 = datetime(2026, 6, 1, 16, 0, 0)

        # Step 0 snapshots
        for s in [
            PriceSnapshot("0xaaa", ts0, 0.59, 0.61, 0.60, 10_000, 10_000, 50_000),
            PriceSnapshot("0xddd", ts0, 0.89, 0.91, 0.90, 15_000, 15_000, 100_000),
        ]:
            await store.append_snapshot(s)

        # Step 1 snapshots (prices move)
        for s in [
            PriceSnapshot("0xaaa", ts1, 0.64, 0.66, 0.65, 10_000, 10_000, 55_000),
            PriceSnapshot("0xddd", ts1, 0.84, 0.86, 0.85, 15_000, 15_000, 105_000),
        ]:
            await store.append_snapshot(s)

        # Build universe snapshots from store data for each unique timestamp
        all_ids = await store.get_market_ids()
        universes: list[UniverseSnapshot] = []
        for t in [ts0, ts1]:
            features: dict[str, MarketFeatures] = {}
            for mid in all_ids:
                async for s in store.read_snapshots(mid):
                    if s.timestamp == t:
                        features[mid] = MarketFeatures(
                            market_id=mid,
                            mid_price=s.mid_price,
                            spread_bps=(
                                (s.ask_price - s.bid_price) / s.mid_price * 10_000
                                if s.mid_price > 0
                                else 0.0
                            ),
                            volume_24h=s.volume,
                            momentum_24h=0.05,  # simplified for test
                        )
            if features:
                universes.append(UniverseSnapshot(timestamp=t, markets=features))

        assert len(universes) == 2

        # Pipeline that scores each market equally
        def equal_scores(u: UniverseSnapshot) -> ScoreResult:
            scores = {mid: 0.5 for mid in u.markets}
            return ScoreResult(scores=scores, timestamp=u.timestamp)

        pipeline = FactorPipeline(
            feature_fn=_feature_fn,
            filter_fn=lambda u: u,
            score_fn=equal_scores,
            portfolio_fn=_portfolio_fn,
        )

        engine = BacktestEngine(pipeline, BacktestConfig(initial_capital=10_000.0))
        result = await engine.run(universes)

        # Equal scores keep the same positions across steps, so no closes occur
        # but open/adjust actions are recorded in trades
        assert len(result.trades) > 0
        assert len(result.pnl_series) == len(universes)
        # Portfolio value should have been updated per step
        assert len(result.portfolio_values) == len(universes) + 1  # initial + per-step

    @pytest.mark.asyncio
    async def test_price_store_empty_returns_empty_backtest(self) -> None:
        """Empty PriceStore leads to empty universe and no trades."""
        store = PriceStore(path=None)
        ids = await store.get_market_ids()
        assert ids == []

        pipeline = FactorPipeline(
            feature_fn=_feature_fn,
            filter_fn=lambda u: u,
            score_fn=lambda u: ScoreResult(scores={}, timestamp=u.timestamp),
            portfolio_fn=lambda s: [],
        )
        engine = BacktestEngine(pipeline)
        result = await engine.run([])
        assert result.num_trades == 0
        assert result.total_return_pct == 0.0
        assert result.portfolio_values == [10_000.0]  # initial capital

    @pytest.mark.asyncio
    async def test_price_store_count_and_append_consistency(self) -> None:
        """Append and count verify store consistency before backtesting."""
        store = PriceStore(path=None)
        ts = datetime(2026, 6, 1, 12, 0, 0)

        await store.append_snapshot(
            PriceSnapshot("0xaaa", ts, 0.59, 0.61, 0.60, 10_000, 10_000, 50_000)
        )
        await store.append_snapshot(
            PriceSnapshot("0xaaa", ts, 0.60, 0.62, 0.61, 10_000, 10_000, 51_000)
        )
        cnt = await store.count_snapshots("0xaaa")
        assert cnt == 2

        # Read with limit
        snaps = await store.read_snapshots_batch("0xaaa", limit=1)
        assert len(snaps) == 1

        # Full read returns both
        snaps_all = await store.read_snapshots_batch("0xaaa")
        assert len(snaps_all) == 2
