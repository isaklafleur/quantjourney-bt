# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""Tests for backtester.local_lake.read_pit against a local temp-dir lake."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq

from backtester.local_lake import read_pit


def _write_parquet(root, dataset: str, rows: list[dict]) -> None:
    path = root / f"dataset={dataset}"
    path.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path / "part-0.parquet")


def test_read_pit_resolves_latest_knowledge_time(tmp_path):
    _write_parquet(
        tmp_path,
        "equity_bars_1d_yahoo_adj",
        [
            {
                "ticker": "AAPL",
                "event_time": datetime(2024, 1, 2, tzinfo=UTC),
                "knowledge_time": datetime(2024, 1, 2, tzinfo=UTC),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 100.0,
                "volume": 1000.0,
            },
            {
                "ticker": "AAPL",
                "event_time": datetime(2024, 1, 2, tzinfo=UTC),
                "knowledge_time": datetime(2024, 1, 3, tzinfo=UTC),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 101.0,
                "volume": 1100.0,
            },
        ],
    )

    df = read_pit(
        "processed",
        "equity_bars_1d_yahoo_adj",
        as_of=datetime(2024, 1, 10, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert len(df) == 1
    assert df.iloc[0]["close"] == 101.0


def test_read_pit_respects_as_of_cutoff(tmp_path):
    _write_parquet(
        tmp_path,
        "equity_bars_1d_yahoo_adj",
        [
            {
                "ticker": "AAPL",
                "event_time": datetime(2024, 1, 2, tzinfo=UTC),
                "knowledge_time": datetime(2024, 1, 2, tzinfo=UTC),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 100.0,
                "volume": 1000.0,
            },
            {
                "ticker": "AAPL",
                "event_time": datetime(2024, 1, 2, tzinfo=UTC),
                "knowledge_time": datetime(2024, 1, 3, tzinfo=UTC),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 101.0,
                "volume": 1100.0,
            },
        ],
    )

    df = read_pit(
        "processed",
        "equity_bars_1d_yahoo_adj",
        as_of=datetime(2024, 1, 2, 23, 59, 59, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert len(df) == 1
    assert df.iloc[0]["close"] == 100.0


def test_read_pit_filters_tickers_and_date_range(tmp_path):
    rows = [
        {
            "ticker": t,
            "event_time": datetime(2024, 1, d, tzinfo=UTC),
            "knowledge_time": datetime(2024, 1, d, tzinfo=UTC),
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": float(d),
            "volume": 1.0,
        }
        for t in ("AAPL", "MSFT")
        for d in (1, 2, 3)
    ]
    _write_parquet(tmp_path, "equity_bars_1d_yahoo_adj", rows)

    df = read_pit(
        "processed",
        "equity_bars_1d_yahoo_adj",
        as_of=datetime(2024, 1, 10, tzinfo=UTC),
        tickers=["AAPL"],
        start=date(2024, 1, 2),
        end=date(2024, 1, 3),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert set(df["ticker"]) == {"AAPL"}
    assert sorted(df["event_time"].dt.day.tolist()) == [2, 3]


def test_read_pit_returns_empty_frame_when_nothing_matches(tmp_path):
    _write_parquet(
        tmp_path,
        "equity_bars_1d_yahoo_adj",
        [
            {
                "ticker": "AAPL",
                "event_time": datetime(2024, 1, 2, tzinfo=UTC),
                "knowledge_time": datetime(2024, 1, 2, tzinfo=UTC),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 100.0,
                "volume": 1000.0,
            },
        ],
    )

    df = read_pit(
        "processed",
        "equity_bars_1d_yahoo_adj",
        as_of=datetime(2024, 1, 10, tzinfo=UTC),
        tickers=["MSFT"],
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert df.empty
