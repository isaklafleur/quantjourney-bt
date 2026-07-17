# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""Tests for backtester.local_lake.read_pit against a local temp-dir lake."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq

from backtester.local_lake import (
    pit_sp500_ticker_universe,
    read_pit,
    resolve_pit_sp500,
    sctr_features_ticker_universe,
)


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


def test_resolve_pit_sp500_add_remove_readd(tmp_path):
    rows = [
        {
            "symbol": "AAA", "name": "AAA Inc", "index_name": "sp500",
            "opt_out": None,
            "event_time": datetime(2020, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2020, 1, 1, tzinfo=UTC),
        },
        {
            "symbol": "BBB", "name": "BBB Inc", "index_name": "sp500",
            "opt_out": datetime(2021, 6, 1, tzinfo=UTC),
            "event_time": datetime(2019, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2019, 1, 1, tzinfo=UTC),
        },
        {
            "symbol": "CCC", "name": "CCC Inc", "index_name": "nasdaq100",
            "opt_out": None,
            "event_time": datetime(2020, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2020, 1, 1, tzinfo=UTC),
        },
    ]
    _write_parquet(tmp_path, "index_membership", rows)

    days = [date(2020, 6, 1), date(2021, 7, 1)]
    result = resolve_pit_sp500(
        days,
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert result[date(2020, 6, 1)] == {"AAA", "BBB"}
    assert result[date(2021, 7, 1)] == {"AAA"}  # BBB opted out 2021-06-01; CCC is nasdaq100, not sp500


def test_pit_sp500_ticker_universe_union_excludes_names_that_left_before_window(tmp_path):
    rows = [
        {
            "symbol": "AAA", "name": "AAA Inc", "index_name": "sp500",
            "opt_out": None,
            "event_time": datetime(2020, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2020, 1, 1, tzinfo=UTC),
        },
        {
            "symbol": "BBB", "name": "BBB Inc", "index_name": "sp500",
            "opt_out": datetime(2019, 6, 1, tzinfo=UTC),
            "event_time": datetime(2015, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2015, 1, 1, tzinfo=UTC),
        },
    ]
    _write_parquet(tmp_path, "index_membership", rows)

    tickers = pit_sp500_ticker_universe(
        date(2020, 1, 1),
        date(2020, 12, 31),
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert tickers == ["AAA"]  # BBB opted out 2019-06-01, before the 2020 window started


def test_resolve_pit_sp500_dedupes_repeated_snapshot_rewrites(tmp_path):
    # index_membership gets rewritten wholesale on each source run; a
    # symbol appears at multiple knowledge_time values with the same
    # event_time/opt_out facts -- only the freshest copy should count.
    rows = [
        {
            "symbol": "AAA", "name": "AAA Inc", "index_name": "sp500",
            "opt_out": None,
            "event_time": datetime(2020, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2020, 1, 1, tzinfo=UTC),
        },
        {
            "symbol": "AAA", "name": "AAA Inc", "index_name": "sp500",
            "opt_out": None,
            "event_time": datetime(2020, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2020, 6, 1, tzinfo=UTC),
        },
    ]
    _write_parquet(tmp_path, "index_membership", rows)

    result = resolve_pit_sp500(
        [date(2021, 1, 1)],
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert result[date(2021, 1, 1)] == {"AAA"}


def test_resolve_pit_sp500_preserves_distinct_spans_for_same_symbol_reentry(tmp_path):
    # AAA left the index (span 1) and later re-entered (span 2). Both
    # spans share the symbol but have different event_time/opt_out facts,
    # so PIT resolution keyed on (symbol, event_time) must keep both.
    rows = [
        {
            "symbol": "AAA", "name": "AAA Inc", "index_name": "sp500",
            "opt_out": datetime(2015, 1, 1, tzinfo=UTC),
            "event_time": datetime(2010, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2010, 1, 1, tzinfo=UTC),
        },
        {
            "symbol": "AAA", "name": "AAA Inc", "index_name": "sp500",
            "opt_out": None,
            "event_time": datetime(2018, 1, 1, tzinfo=UTC),
            "knowledge_time": datetime(2018, 1, 1, tzinfo=UTC),
        },
    ]
    _write_parquet(tmp_path, "index_membership", rows)

    days = [date(2012, 1, 1), date(2016, 1, 1), date(2020, 1, 1)]
    result = resolve_pit_sp500(
        days,
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert result[date(2012, 1, 1)] == {"AAA"}  # inside span 1
    assert result[date(2016, 1, 1)] == set()  # gap between spans
    assert result[date(2020, 1, 1)] == {"AAA"}  # inside span 2 (re-entry)

    universe = pit_sp500_ticker_universe(
        date(2011, 1, 1),
        date(2013, 1, 1),
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )
    assert universe == ["AAA"]  # window overlaps span 1

    universe_span2 = pit_sp500_ticker_universe(
        date(2019, 1, 1),
        date(2021, 1, 1),
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )
    assert universe_span2 == ["AAA"]  # window overlaps span 2


def test_sctr_features_ticker_universe_includes_names_outside_current_membership(tmp_path):
    # AAA has an sctr_features row but is NOT an index member per
    # index_membership in this window (confirmed against real data: the
    # original strategy trades exactly this way, with no separate
    # membership filter) -- the universe must still include it.
    rows = [
        {
            "ticker": "AAA",
            "event_time": datetime(2016, 3, 11, tzinfo=UTC),
            "knowledge_time": datetime(2016, 3, 11, tzinfo=UTC),
            "close": 100.0,
            "pct_above_ema200": 0.0, "roc125": 0.0, "pct_above_ema50": 0.0,
            "roc20": 0.0, "ppo_slope": 0.0, "rsi14": 0.0,
            "indicator_score": 0.0, "rank": 99.0,
        },
        {
            "ticker": "BBB",
            "event_time": datetime(2016, 3, 12, tzinfo=UTC),
            "knowledge_time": datetime(2016, 3, 12, tzinfo=UTC),
            "close": 50.0,
            "pct_above_ema200": 0.0, "roc125": 0.0, "pct_above_ema50": 0.0,
            "roc20": 0.0, "ppo_slope": 0.0, "rsi14": 0.0,
            "indicator_score": 0.0, "rank": 50.0,
        },
    ]
    _write_parquet(tmp_path, "sctr_features", rows)

    universe = sctr_features_ticker_universe(
        date(2016, 1, 1),
        date(2016, 12, 31),
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert universe == ["AAA", "BBB"]


def test_sctr_features_ticker_universe_returns_empty_list_when_no_rows(tmp_path):
    _write_parquet(
        tmp_path,
        "sctr_features",
        [
            {
                "ticker": "AAA",
                "event_time": datetime(2010, 1, 1, tzinfo=UTC),
                "knowledge_time": datetime(2010, 1, 1, tzinfo=UTC),
                "close": 100.0,
                "pct_above_ema200": 0.0, "roc125": 0.0, "pct_above_ema50": 0.0,
                "roc20": 0.0, "ppo_slope": 0.0, "rsi14": 0.0,
                "indicator_score": 0.0, "rank": 99.0,
            }
        ],
    )

    universe = sctr_features_ticker_universe(
        date(2016, 1, 1),
        date(2016, 12, 31),
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        filesystem=pafs.LocalFileSystem(),
        root=str(tmp_path),
    )

    assert universe == []
