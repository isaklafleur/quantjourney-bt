# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

from __future__ import annotations

import pandas as pd

from backtester.portfolio.instr_data import InstrumentData
from strategies.sctr_momentum_regime_gated import SCTRMomentumRegimeGated


def _instruments_data(
    dates: pd.DatetimeIndex,
    tickers: list[str],
    rank: pd.DataFrame,
    eligibility: pd.DataFrame,
    trend_down: pd.Series,
) -> InstrumentData:
    price_frames = []
    for t in tickers:
        price_frames.append(
            pd.DataFrame(
                {
                    (t, "open"): 10.0, (t, "high"): 10.0, (t, "low"): 10.0,
                    (t, "close"): 10.0, (t, "adj_close"): 10.0, (t, "volume"): 100.0,
                },
                index=dates,
            )
        )
    prices = pd.concat(price_frames, axis=1)
    prices.columns = pd.MultiIndex.from_tuples(prices.columns, names=["instrument", "field"])

    param_frames = []
    for t in tickers:
        param_frames.append(
            pd.DataFrame(
                {
                    (t, "exchange"): 0.0, (t, "units"): 0.0,
                    (t, "eligibility"): eligibility[t], (t, "active"): eligibility[t],
                    (t, "forecasts"): 0.0, (t, "is_trading_day"): 1.0, (t, "day_type"): 1.0,
                    (t, "sctr_rank"): rank[t], (t, "spy_trend_down"): trend_down,
                },
                index=dates,
            )
        )
    parameters = pd.concat(param_frames, axis=1)
    parameters.columns = pd.MultiIndex.from_tuples(parameters.columns, names=["instrument", "field"])

    metrics_frames = []
    for t in tickers:
        metrics_frames.append(
            pd.DataFrame(
                {
                    (t, "returns"): 0.0, (t, "volatility"): 0.0, (t, "daily_pnl"): 0.0,
                    (t, "transaction_costs"): 0.0, (t, "net_asset_value"): 100.0,
                    (t, "gross_asset_value"): 100.0, (t, "daily_net_return"): 0.0,
                    (t, "drawdown"): 0.0,
                },
                index=dates,
            )
        )
    metrics = pd.concat(metrics_frames, axis=1)
    metrics.columns = pd.MultiIndex.from_tuples(metrics.columns, names=["instrument", "field"])

    return InstrumentData(
        group_data=pd.Series(["equity"] * len(tickers), index=tickers, name="group"),
        group_order=["equity"],
        strategies=pd.DataFrame(),
        prices=prices,
        metrics=metrics,
        parameters=parameters,
    )


def test_strategy_wires_parameters_panel_into_regime_gated_weights():
    dates = pd.bdate_range("2024-01-01", periods=4, tz="UTC")
    tickers = ["AAA", "BBB"]
    rank = pd.DataFrame({"AAA": [96.0] * 4, "BBB": [50.0] * 4}, index=dates)
    eligibility = pd.DataFrame({"AAA": [1.0] * 4, "BBB": [1.0] * 4}, index=dates)
    trend_down = pd.Series([0.0, 1.0, 0.0, 0.0], index=dates)

    strategy = SCTRMomentumRegimeGated(
        instruments=tickers,
        backtest_period={"start": "2024-01-01", "end": "2024-01-10"},
        source="minio",
        strategy_name="test_sctr_regime_gated",
        show_text_reports=False,
        skip_analysis=True,
    )
    strategy.instruments_data = _instruments_data(dates, tickers, rank, eligibility, trend_down)

    signals = strategy._compute_signals()
    strategy.instruments_data.add_strategy_data(strategy.strategy_name, "signals", signals)
    weights = strategy._compute_weights()

    assert weights.loc[dates[0], "AAA"] == 1.0
    assert weights.loc[dates[1], "AAA"] == 0.0  # gated day: liquidated
    assert weights.loc[dates[2], "AAA"] == 1.0  # immediate re-entry
    assert weights.loc[dates[3], "AAA"] == 1.0
    assert (weights["BBB"] == 0.0).all()  # never crosses entry_threshold


def test_compute_signals_fills_nan_rank_so_engine_validation_accepts_it():
    # Real sctr_features data has NaN gaps -- e.g. a ticker before its
    # feature history starts. The engine's own signal validation
    # (Backtester._validate_strategy_output) rejects non-finite values,
    # so _compute_signals must not pass NaN through.
    dates = pd.bdate_range("2024-01-01", periods=3, tz="UTC")
    tickers = ["AAA", "BBB"]
    rank = pd.DataFrame({"AAA": [96.0, float("nan"), 96.0], "BBB": [50.0] * 3}, index=dates)
    eligibility = pd.DataFrame({"AAA": [1.0] * 3, "BBB": [1.0] * 3}, index=dates)
    trend_down = pd.Series([0.0, 0.0, 0.0], index=dates)

    strategy = SCTRMomentumRegimeGated(
        instruments=tickers,
        backtest_period={"start": "2024-01-01", "end": "2024-01-10"},
        source="minio",
        strategy_name="test_sctr_regime_gated_nan",
        show_text_reports=False,
        skip_analysis=True,
    )
    strategy.instruments_data = _instruments_data(dates, tickers, rank, eligibility, trend_down)

    signals = strategy._compute_signals()

    assert signals.to_numpy(dtype=float).size > 0
    assert (signals.to_numpy(dtype=float) == signals.to_numpy(dtype=float)).all()  # no NaN
    assert signals.loc[dates[1], "AAA"] == 0.0  # NaN filled to a value below both thresholds
