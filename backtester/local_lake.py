# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
Local MinIO / S3-compatible lake reader for Backtester(source="minio").

Reads bitemporal Parquet datasets laid out as
s3://{bucket}/dataset={name}/**/*.parquet (event_time + knowledge_time
columns on every row) -- a common convention for point-in-time-correct
research data lakes. This module implements just the PIT-resolution
logic needed here, independent of any specific lake-writer implementation.

pyarrow is imported lazily inside these functions, not at module load
time, so it stays an opt-in dependency (`pip install quantjourney-bt[minio]`)
for the one feature that needs it.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd


def _filesystem_and_root(bucket: str) -> tuple[Any, str]:
    """Build a pyarrow S3FileSystem from QJ_LOCAL_LAKE_* env vars.

    Kept separate from read_pit so tests can construct their own
    (filesystem, root) pair against a local temp directory instead of
    hitting real S3/MinIO.
    """
    import pyarrow.fs as pafs

    endpoint = os.environ["QJ_LOCAL_LAKE_ENDPOINT_URL"]
    access_key = os.environ["QJ_LOCAL_LAKE_ACCESS_KEY"]
    secret_key = os.environ["QJ_LOCAL_LAKE_SECRET_KEY"]

    scheme = "https"
    host = endpoint
    if endpoint.startswith("http://"):
        scheme, host = "http", endpoint[len("http://") :]
    elif endpoint.startswith("https://"):
        scheme, host = "https", endpoint[len("https://") :]

    filesystem = pafs.S3FileSystem(
        endpoint_override=host,
        access_key=access_key,
        secret_key=secret_key,
        scheme=scheme,
    )
    return filesystem, bucket


def read_pit(
    bucket: str,
    dataset: str,
    *,
    as_of: datetime,
    tickers: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    pit_keys: tuple[str, ...] = ("ticker", "event_time"),
    filesystem: Any = None,
    root: str | None = None,
) -> pd.DataFrame:
    """Read one PIT-resolved snapshot of a bitemporal lake dataset.

    Filters to `knowledge_time <= as_of`, then keeps exactly one row per
    `pit_keys` combination -- the row with the latest `knowledge_time`.
    Most datasets are keyed by (ticker, event_time); index_membership
    is keyed by (symbol, event_time) instead, since a symbol can have
    multiple distinct membership spans (e.g. it left and later re-entered
    the index) that must each survive PIT resolution, while repeated
    snapshot rewrites of the *same* span (identical symbol and event_time,
    different knowledge_time) still collapse to one row.

    `filesystem`/`root` let callers (tests) point this at a local
    directory instead of real S3 -- production callers omit both and get
    a pyarrow S3FileSystem built from QJ_LOCAL_LAKE_* env vars, rooted at
    `bucket`.
    """
    import pyarrow.dataset as pads

    if filesystem is None:
        filesystem, root = _filesystem_and_root(bucket)
    if root is None:
        root = bucket

    path = f"{root}/dataset={dataset}"
    ds = pads.dataset(path, filesystem=filesystem, format="parquet")

    filter_expr = None

    def _and(expr: Any) -> None:
        nonlocal filter_expr
        filter_expr = expr if filter_expr is None else filter_expr & expr

    if tickers is not None:
        _and(pads.field("ticker").isin(list(tickers)))
    if start is not None:
        _and(pads.field("event_time") >= datetime(start.year, start.month, start.day, tzinfo=UTC))
    if end is not None:
        _and(
            pads.field("event_time")
            <= datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC)
        )

    table = ds.to_table(filter=filter_expr)
    df = table.to_pandas()
    if df.empty:
        return df

    as_of_ts = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    df = df[df["knowledge_time"] <= as_of_ts]
    df = df.sort_values("knowledge_time", ascending=False)
    df = df.drop_duplicates(subset=list(pit_keys), keep="first")

    sort_cols = [c for c in ("ticker", "symbol", "event_time") if c in df.columns]
    return df.sort_values(sort_cols).reset_index(drop=True)


def resolve_pit_sp500(
    trading_days: list[date],
    *,
    as_of: datetime,
    index_name: str = "sp500",
    filesystem: Any = None,
    root: str | None = None,
) -> dict[date, set[str]]:
    """Map each trading day to the set of tickers that were S&P 500
    members on that day, PIT-resolved as of `as_of`.

    A symbol is a member on `day` if some membership row has
    `event_time <= day` and (`opt_out` is null or `opt_out > day`).
    Keyed by `(symbol, event_time)` for PIT resolution -- a symbol may
    have multiple distinct membership spans (left and later re-entered
    the index), each with its own event_time/opt_out, and all of them
    must survive PIT resolution; only repeated snapshot rewrites of the
    same span collapse to one row.
    """
    membership = read_pit(
        "processed",
        "index_membership",
        as_of=as_of,
        pit_keys=("symbol", "event_time"),
        filesystem=filesystem,
        root=root,
    )
    if membership.empty:
        return {day: set() for day in trading_days}
    membership = membership[membership["index_name"] == index_name]

    result: dict[date, set[str]] = {}
    for day in trading_days:
        day_ts = pd.Timestamp(day, tz="UTC")
        active = membership[
            (membership["event_time"] <= day_ts)
            & (membership["opt_out"].isna() | (membership["opt_out"] > day_ts))
        ]
        result[day] = set(active["symbol"].tolist())
    return result


def pit_sp500_ticker_universe(
    start: date,
    end: date,
    *,
    as_of: datetime,
    index_name: str = "sp500",
    filesystem: Any = None,
    root: str | None = None,
) -> list[str]:
    """The union of every ticker that was an S&P 500 member at any point
    in [start, end], PIT-resolved as of `as_of`. Day-by-day eligibility
    is enforced separately, via resolve_pit_sp500. NOTE: not used for
    the SCTR momentum regime-gated strategy's instrument universe --
    see sctr_features_ticker_universe and that strategy's module
    docstring for why."""
    membership = read_pit(
        "processed",
        "index_membership",
        as_of=as_of,
        pit_keys=("symbol", "event_time"),
        filesystem=filesystem,
        root=root,
    )
    if membership.empty:
        return []
    membership = membership[membership["index_name"] == index_name]

    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    active = membership[
        (membership["event_time"] <= end_ts)
        & (membership["opt_out"].isna() | (membership["opt_out"] >= start_ts))
    ]
    return sorted(active["symbol"].unique().tolist())


def sctr_features_ticker_universe(
    start: date,
    end: date,
    *,
    as_of: datetime,
    filesystem: Any = None,
    root: str | None = None,
) -> list[str]:
    """The full set of tickers with any research/sctr_features row in
    [start, end], PIT-resolved as of `as_of`.

    Confirmed against real data and the original strategy's own asset
    code that it never applies a separate PIT S&P 500 membership filter
    at runtime -- it trades whatever sctr_features covers directly (that
    dataset's own universe is not identical to processed/index_membership:
    e.g. it includes names that had already left, or had not yet
    (re-)joined, the index as of a given trade date). Use this, not
    pit_sp500_ticker_universe, to match that behavior.
    """
    sctr = read_pit(
        "research",
        "sctr_features",
        as_of=as_of,
        start=start,
        end=end,
        filesystem=filesystem,
        root=root,
    )
    if sctr.empty:
        return []
    return sorted(sctr["ticker"].unique().tolist())
