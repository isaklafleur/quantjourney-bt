# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""Tests for backtester.local_data."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from backtester import local_data
from backtester.core import _payload_to_multiindex_df, _payload_to_series
from backtester.portfolio.schemas import (
    REQUIRED_METRIC_FIELDS,
    REQUIRED_PARAMETER_FIELDS,
    REQUIRED_PRICE_FIELDS,
)


def _bars(
    tickers: list[str], dates: list[datetime], closes: dict[str, list[float]]
) -> pd.DataFrame:
    rows = []
    for t in tickers:
        for d, c in zip(dates, closes[t], strict=True):
            rows.append(
                {
                    "ticker": t,
                    "event_time": d,
                    "close": c,
                    "open": c,
                    "high": c,
                    "low": c,
                    "volume": 100.0,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def patched_reads(monkeypatch):
    dates = [datetime(2024, 1, d, tzinfo=UTC) for d in range(1, 6)]
    tickers = ["AAA", "BBB"]
    closes = {"AAA": [10.0, 11.0, 12.0, 13.0, 14.0], "BBB": [20.0, 19.0, 18.0, 17.0, 16.0]}
    bars = _bars(tickers, dates, closes)
    spy_bars = _bars(["SPY"], dates, {"SPY": [100.0, 101.0, 102.0, 103.0, 104.0]})
    sctr = pd.DataFrame(
        [{"ticker": t, "event_time": d, "rank": 90.0} for t in tickers for d in dates]
    )

    def fake_read_pit(bucket, dataset, **kwargs):
        if dataset == "equity_bars_1d_yahoo_adj":
            return bars
        if dataset == "market_ref_bars_1d_yahoo_adj":
            return spy_bars
        if dataset == "sctr_features":
            return sctr
        raise AssertionError(f"unexpected dataset requested: {dataset}")

    def fake_resolve_pit_sp500(trading_days, **kwargs):
        return {day: {"AAA", "BBB"} for day in trading_days}

    monkeypatch.setattr(local_data, "read_pit", fake_read_pit)
    monkeypatch.setattr(local_data, "resolve_pit_sp500", fake_resolve_pit_sp500)
    return tickers, dates


def test_build_local_minio_bt_payload_shape(patched_reads):
    tickers, _dates = patched_reads

    payload = local_data.build_local_minio_bt_payload(
        instruments=tickers,
        start="2024-01-01",
        end="2024-01-05",
    )

    assert payload["instrument_names"] == tickers
    assert payload["summary"]["source"] == "minio"
    assert payload["summary"]["instruments"] == 2

    prices = _payload_to_multiindex_df(payload["prices"])
    price_fields = set(prices.columns.get_level_values(1))
    assert REQUIRED_PRICE_FIELDS <= price_fields
    assert prices[("AAA", "adj_close")].tolist() == prices[("AAA", "close")].tolist()

    metrics = _payload_to_multiindex_df(payload["metrics"])
    assert REQUIRED_METRIC_FIELDS <= set(metrics.columns.get_level_values(1))

    parameters = _payload_to_multiindex_df(payload["parameters"])
    param_fields = set(parameters.columns.get_level_values(1))
    assert REQUIRED_PARAMETER_FIELDS <= param_fields
    assert "sctr_rank" in param_fields
    assert "spy_trend_down" in param_fields
    assert (parameters[("AAA", "eligibility")] == 1.0).all()
    assert (parameters[("AAA", "sctr_rank")] == 90.0).all()

    nav = _payload_to_series(payload["nav"], name="nav")
    assert len(nav) == 5


def test_build_local_minio_bt_payload_marks_ineligible_names(monkeypatch):
    dates = [datetime(2024, 1, d, tzinfo=UTC) for d in range(1, 4)]
    tickers = ["AAA", "BBB"]
    bars = _bars(tickers, dates, {"AAA": [10.0, 11.0, 12.0], "BBB": [20.0, 21.0, 22.0]})
    spy_bars = _bars(["SPY"], dates, {"SPY": [100.0, 101.0, 102.0]})
    sctr = pd.DataFrame(
        [{"ticker": t, "event_time": d, "rank": 96.0} for t in tickers for d in dates]
    )

    monkeypatch.setattr(
        local_data,
        "read_pit",
        lambda bucket, dataset, **kwargs: {
            "equity_bars_1d_yahoo_adj": bars,
            "market_ref_bars_1d_yahoo_adj": spy_bars,
            "sctr_features": sctr,
        }[dataset],
    )
    # BBB was never a PIT member -- only AAA should show eligibility=1
    monkeypatch.setattr(
        local_data,
        "resolve_pit_sp500",
        lambda trading_days, **kwargs: {d: {"AAA"} for d in trading_days},
    )

    payload = local_data.build_local_minio_bt_payload(
        instruments=tickers,
        start="2024-01-01",
        end="2024-01-03",
    )
    parameters = _payload_to_multiindex_df(payload["parameters"])

    assert (parameters[("AAA", "eligibility")] == 1.0).all()
    assert (parameters[("BBB", "eligibility")] == 0.0).all()


def test_build_local_minio_bt_payload_requires_at_least_one_instrument():
    with pytest.raises(ValueError, match="at least one instrument"):
        local_data.build_local_minio_bt_payload(
            instruments=[], start="2024-01-01", end="2024-01-05"
        )
