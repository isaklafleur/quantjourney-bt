# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
Local MinIO / S3-compatible lake reader for Backtester(source="minio").

Reads bitemporal Parquet datasets laid out as
s3://{bucket}/dataset={name}/**/*.parquet (event_time + knowledge_time
columns on every row), the same convention a separate private research
project (IMQuantFund) uses for its own lake -- this module is an
independent, from-scratch reimplementation of just the PIT-resolution
logic needed here, kept dependency-free of that project since
quantjourney-bt is published separately.

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
    (Task 3) is keyed by (symbol,) instead, since a symbol's own
    event_time/opt_out facts don't change across repeated snapshot
    rewrites of that dataset.

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
