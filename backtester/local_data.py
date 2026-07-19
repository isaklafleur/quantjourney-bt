"""
Builds a /bt/prepare-compatible payload (same contract as
backtester.sample_data.build_sample_bt_payload) from data read out of a
local MinIO / S3-compatible lake, for Backtester(source="minio").

Copyright (c) 2026 QuantJourney.
Licensed under the Apache License 2.0.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd

from backtester import lake_api
from backtester.bt_payload import frame_payload, series_payload
from backtester.local_lake import read_pit, resolve_pit_sp500

SPY_TICKER = "SPY"
TREND_SMA_WINDOW = 200

__all__ = ["build_local_minio_bt_payload"]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _price_panel(bars: pd.DataFrame, tickers: list[str], dates: pd.DatetimeIndex) -> pd.DataFrame:
    bars = bars[bars["ticker"].isin(tickers)]
    wide = bars.pivot_table(
        index="event_time",
        columns="ticker",
        values=["open", "high", "low", "close", "volume"],
    )
    wide = wide.reindex(dates)
    wide.columns = wide.columns.swaplevel(0, 1)
    full_cols = pd.MultiIndex.from_product([tickers, ["open", "high", "low", "close", "volume"]])
    wide = wide.reindex(columns=full_cols)
    wide.columns.names = ["instrument", "field"]
    for ticker in tickers:
        wide[(ticker, "adj_close")] = wide[(ticker, "close")]
    return wide.sort_index(axis=1)


def _sctr_rank_panel(
    sctr: pd.DataFrame, tickers: list[str], dates: pd.DatetimeIndex
) -> pd.DataFrame:
    if sctr.empty:
        return pd.DataFrame(np.nan, index=dates, columns=tickers)
    sctr = sctr[sctr["ticker"].isin(tickers)]
    wide = sctr.pivot_table(index="event_time", columns="ticker", values="rank")
    return wide.reindex(index=dates, columns=tickers)


def _spy_trend_down(spy_bars: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    spy = spy_bars[spy_bars["ticker"] == SPY_TICKER].sort_values("event_time")
    spy_close = spy.set_index("event_time")["close"]
    sma200 = spy_close.rolling(TREND_SMA_WINDOW, min_periods=TREND_SMA_WINDOW).mean()
    down = (spy_close < sma200).astype(float)
    return down.reindex(dates).fillna(0.0)


def _eligibility_panel(
    trading_days: list[date],
    tickers: list[str],
    as_of: datetime,
    *,
    filesystem: Any,
    root: str | None,
) -> pd.DataFrame:
    membership_by_day = resolve_pit_sp500(
        trading_days, as_of=as_of, filesystem=filesystem, root=root
    )
    dates = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") for d in trading_days])
    elig = pd.DataFrame(0.0, index=dates, columns=tickers)
    ticker_set = set(tickers)
    for day, ts in zip(trading_days, dates, strict=True):
        members = membership_by_day.get(day, set()) & ticker_set
        if members:
            elig.loc[ts, sorted(members)] = 1.0
    return elig


def _parameters_panel(
    tickers: list[str],
    dates: pd.DatetimeIndex,
    sctr_rank: pd.DataFrame,
    eligibility: pd.DataFrame,
    trend_down: pd.Series,
) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        frame = pd.DataFrame(
            {
                (ticker, "exchange"): 0.0,
                (ticker, "units"): 0.0,
                (ticker, "eligibility"): eligibility[ticker],
                (ticker, "active"): eligibility[ticker],
                (ticker, "forecasts"): 0.0,
                (ticker, "is_trading_day"): 1.0,
                (ticker, "day_type"): 1.0,
                (ticker, "sctr_rank"): sctr_rank[ticker],
                (ticker, "spy_trend_down"): trend_down,
            },
            index=dates,
        )
        frames.append(frame)
    parameters = pd.concat(frames, axis=1)
    parameters.columns = pd.MultiIndex.from_tuples(
        parameters.columns, names=["instrument", "field"]
    )
    return parameters


def _metrics_panel(prices: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        close = prices[(ticker, "adj_close")]
        ret = close.pct_change(fill_method=None).fillna(0.0)
        nav = (1.0 + ret).cumprod()
        drawdown = nav / nav.cummax() - 1.0
        frame = pd.DataFrame(
            {
                (ticker, "returns"): ret,
                (ticker, "volatility"): ret.rolling(20, min_periods=2).std().fillna(0.0),
                (ticker, "daily_pnl"): ret,
                (ticker, "transaction_costs"): 0.0,
                (ticker, "net_asset_value"): nav,
                (ticker, "gross_asset_value"): nav,
                (ticker, "daily_net_return"): ret,
                (ticker, "drawdown"): drawdown,
            },
            index=prices.index,
        )
        frames.append(frame)
    metrics = pd.concat(frames, axis=1)
    metrics.columns = pd.MultiIndex.from_tuples(metrics.columns, names=["instrument", "field"])
    return metrics


def build_local_minio_bt_payload(
    *,
    instruments: list[str],
    start: str,
    end: str,
    initial_nav: float = 100.0,
    as_of: datetime | None = None,
    filesystem: Any = None,
    root: str | None = None,
) -> dict[str, Any]:
    """Build a /bt/prepare-compatible payload by reading OHLCV, SCTR rank,
    PIT S&P 500 membership, and the SPY trend regime from a local MinIO
    lake -- matches sample_data.build_sample_bt_payload's return contract
    exactly so backtester.core._process_market_data() consumes it
    identically to a live API response."""
    as_of = as_of or datetime.now(UTC)
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    tickers = [str(t).strip().upper() for t in instruments if str(t).strip()]
    if not tickers:
        raise ValueError("build_local_minio_bt_payload requires at least one instrument")

    bars = lake_api.read_bars(
        "equity_bars_1d_yahoo_adj",
        tickers=tickers,
        start=start_date,
        end=end_date,
    )
    if bars.empty:
        raise ValueError(f"No equity_bars_1d_yahoo_adj rows for {tickers} in [{start}, {end}]")

    # No `start=` here (unlike the equity bars read above): the 200-day SMA
    # in _spy_trend_down needs lookback before start_date, so SPY is read
    # from full history rather than truncated to the backtest window.
    spy_bars = read_pit(
        "processed",
        "market_ref_bars_1d_yahoo_adj",
        as_of=as_of,
        tickers=[SPY_TICKER],
        end=end_date,
        filesystem=filesystem,
        root=root,
    )
    if spy_bars.empty:
        raise ValueError("No SPY rows in market_ref_bars_1d_yahoo_adj for the requested window")

    sctr = lake_api.read_features(
        "sctr_features",
        tickers=tickers,
        as_of=as_of.date(),
    )

    dates = pd.DatetimeIndex(sorted(bars["event_time"].unique()))
    prices = _price_panel(bars, tickers, dates)
    sctr_rank = _sctr_rank_panel(sctr, tickers, dates)
    trend_down = _spy_trend_down(spy_bars, dates)
    trading_days = [ts.date() for ts in dates]
    eligibility = _eligibility_panel(trading_days, tickers, as_of, filesystem=filesystem, root=root)
    parameters = _parameters_panel(tickers, dates, sctr_rank, eligibility, trend_down)
    metrics = _metrics_panel(prices, tickers)

    returns_mean = metrics.xs("returns", level="field", axis=1).mean(axis=1).fillna(0.0)
    nav = initial_nav * (1.0 + returns_mean).cumprod()
    nav.name = "nav"

    return {
        "session_id": "local-minio-session",
        "dataset_id": "local-minio-dataset",
        "instrument_names": tickers,
        "prices": frame_payload(prices),
        "metrics": frame_payload(metrics),
        "parameters": frame_payload(parameters),
        "nav": series_payload(nav),
        "summary": {
            "source": "minio",
            "instruments": len(tickers),
            "dates": len(dates),
            "start": dates[0].date().isoformat() if len(dates) else start,
            "end": dates[-1].date().isoformat() if len(dates) else end,
        },
    }
