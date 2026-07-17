# Local MinIO Data Source + SCTR Momentum Regime-Gated Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `source="minio"` data path to `Backtester` that reads OHLCV, SCTR rank, and PIT S&P 500 membership from a local MinIO/S3-compatible lake instead of the QuantJourney API, and use it to run a faithful port of the "SCTR momentum, regime-gated" strategy, validated against that strategy's already-materialized result in the same lake.

**Architecture:** A new `backtester/local_lake.py` reads bitemporal Parquet datasets from MinIO via `pyarrow` and PIT-resolves them in pandas. A new `backtester/local_data.py` assembles those reads into the same JSON-table payload shape `backtester/sample_data.py` already produces (extracted into a shared `backtester/bt_payload.py` so both data sources use one serialization implementation), which a new branch in `backtester/mixins/sdk_client.py::_fetch_market_data()` feeds into the existing, unmodified `_process_market_data()`. SCTR rank, the PIT eligibility mask, and the SPY trend-gate flag ride into `Backtester` through the `parameters` panel, the same place computed indicators already live. A new `strategies/sctr_momentum_regime_gated.py` implements the strategy's day-by-day incumbent-priority selection as a pure, independently-testable function, wired into the standard `_compute_signals`/`_compute_weights` hook pair. A small `backtester/local_validation.py` plus `strategies/validate_sctr_momentum_regime_gated.py` compare the result against the reference PnL series already sitting in MinIO.

**Tech Stack:** Python 3.11+, pandas, pyarrow (new optional dependency, lazy-imported), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-16-minio-local-data-sctr-backtest-design.md`.
- New env vars: `QJ_LOCAL_LAKE_ENDPOINT_URL`, `QJ_LOCAL_LAKE_ACCESS_KEY`, `QJ_LOCAL_LAKE_SECRET_KEY` — never hardcode real values anywhere in committed code, tests, or docs; tests use synthetic local-filesystem fixtures, never live credentials.
- `pyarrow` is a new optional extra (`quantjourney-bt[minio]`) and is **lazy-imported** inside `backtester/local_lake.py` functions only — no top-level import anywhere, so users who don't touch this feature need nothing extra installed.
- Read-only: nothing in this plan writes to MinIO.
- Do not modify `docs/research/strategies/sctr-momentum-regime-gated.md` or `orchestration/assets/sctr_momentum_regime_gated.py` in the separate IMQuantFund project — read-only reference only.
- `backtester/portfolio/schemas.py`'s `REQUIRED_PRICE_FIELDS = {"open", "high", "low", "close", "adj_close", "volume"}`, `REQUIRED_METRIC_FIELDS = {"returns", "volatility", "daily_pnl", "transaction_costs", "net_asset_value", "gross_asset_value", "daily_net_return", "drawdown"}`, and `REQUIRED_PARAMETER_FIELDS = {"exchange", "units", "eligibility", "active", "forecasts", "is_trading_day", "day_type"}` are exact and must be present in every payload this plan produces.
- The engine applies `target_weights.shift(1)` itself (`backtester/core.py:2072`) — no code in this plan may pre-shift weights or signals; `_compute_weights()` returns the target decided using information available through that day's close, unshifted.
- S&P 500 membership rows in `processed/index_membership` use `index_name == "sp500"` (lowercase, confirmed against the live dataset) and are keyed by `symbol`, not `ticker`.
- `analytics/sctr_momentum_regime_gated_pnl` has no `ticker` column — PIT-resolve it keyed on `event_time` alone.

---

### Task 1: Extract shared frame/series payload helpers

**Files:**
- Create: `backtester/bt_payload.py`
- Modify: `backtester/sample_data.py`
- Test: `tests/test_bt_payload.py`

**Interfaces:**
- Produces: `backtester.bt_payload.frame_payload(df: pd.DataFrame) -> dict[str, Any]`, `backtester.bt_payload.series_payload(series: pd.Series) -> dict[str, Any]` — used by `sample_data.py` (this task) and `local_data.py` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bt_payload.py
from __future__ import annotations

import pandas as pd

from backtester.bt_payload import frame_payload, series_payload


def test_frame_payload_round_trips_columns_index_and_data():
    dates = pd.bdate_range("2024-01-01", periods=3, tz="UTC")
    df = pd.DataFrame(
        {("AAA", "close"): [1.0, 2.0, None], ("AAA", "volume"): [10.0, 20.0, 30.0]},
        index=dates,
    )
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["instrument", "field"])

    payload = frame_payload(df)

    assert payload["columns"] == [
        {"instrument": "AAA", "field": "close"},
        {"instrument": "AAA", "field": "volume"},
    ]
    assert payload["index"] == [d.isoformat() for d in dates]
    assert payload["data"][0] == [1.0, 10.0]
    assert payload["data"][2] == [None, 30.0]


def test_series_payload_round_trips_index_and_data():
    dates = pd.bdate_range("2024-01-01", periods=2, tz="UTC")
    series = pd.Series([100.0, None], index=dates)

    payload = series_payload(series)

    assert payload["index"] == [d.isoformat() for d in dates]
    assert payload["data"] == [100.0, None]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bt_payload.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtester.bt_payload'`

- [ ] **Step 3: Write the implementation**

```python
# backtester/bt_payload.py
"""
Shared JSON-table serialization for /bt/prepare-compatible payloads.

Used by every Backtester data source that builds its own `_api_response`
locally instead of fetching one from the API -- today `sample_data.py`
(deterministic demo data) and `local_data.py` (local MinIO lake reads).
Kept in one place so both stay byte-for-byte consistent with what
`backtester.core._payload_to_multiindex_df` / `_payload_to_series` expect.

Copyright (c) 2026 QuantJourney.
Licensed under the Apache License 2.0.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def frame_payload(df: pd.DataFrame) -> dict[str, Any]:
    columns = [
        {"instrument": str(instrument), "field": str(field)}
        for instrument, field in df.columns.to_list()
    ]
    safe = df.astype(object).where(pd.notna(df), None)
    return {
        "columns": columns,
        "index": [idx.isoformat() for idx in df.index],
        "data": safe.values.tolist(),
    }


def series_payload(series: pd.Series) -> dict[str, Any]:
    safe = series.astype(object).where(pd.notna(series), None)
    return {
        "index": [idx.isoformat() for idx in series.index],
        "data": safe.tolist(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bt_payload.py -v`
Expected: PASS

- [ ] **Step 5: Update `sample_data.py` to use the shared helpers**

In `backtester/sample_data.py`, delete the module-local `_frame_payload` and `_series_payload` functions (lines 15-33) and replace every call site (`_frame_payload(...)` / `_series_payload(...)`) with `frame_payload(...)` / `series_payload(...)`. Add the import:

```python
from backtester.bt_payload import frame_payload, series_payload
```

Then find-and-replace within the file: `_frame_payload(` → `frame_payload(`, `_series_payload(` → `series_payload(`.

- [ ] **Step 6: Run the existing sample_data-dependent tests to confirm no regression**

Run: `pytest tests/test_p0_regressions.py tests/test_public_repo.py tests/test_contract_spec_hardening.py tests/test_multi_asset_data_contract.py -v`
Expected: PASS (identical behavior, only the implementation moved)

- [ ] **Step 7: Commit**

```bash
git add backtester/bt_payload.py backtester/sample_data.py tests/test_bt_payload.py
git commit -m "$(cat <<'EOF'
refactor: extract frame/series payload serialization into bt_payload.py

Shared by sample_data.py and the upcoming local MinIO data source
(local_data.py) so both stay consistent with core.py's payload
contract instead of duplicating the same two functions.
EOF
)"
```

---

### Task 2: `minio` extra + `backtester/local_lake.read_pit`

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Create: `backtester/local_lake.py`
- Test: `tests/test_local_lake.py`

**Interfaces:**
- Produces: `backtester.local_lake.read_pit(bucket: str, dataset: str, *, as_of: datetime, tickers: list[str] | None = None, start: date | None = None, end: date | None = None, pit_keys: tuple[str, ...] = ("ticker", "event_time"), filesystem: Any = None, root: str | None = None) -> pd.DataFrame` — used by Task 3, Task 4, and the validation script (Task 8).

- [ ] **Step 1: Add the `minio` extra to `pyproject.toml`**

In `pyproject.toml`, in the `[project.optional-dependencies]` table (after `wf = ["optuna>=3.0"]`), add:

```toml
minio = ["pyarrow>=14"]
```

- [ ] **Step 2: Add `pyarrow` to CI so the new tests run**

In `.github/workflows/ci.yml`, change:

```yaml
          python -m pip install -e ".[dev,data,wf]"
```

to:

```yaml
          python -m pip install -e ".[dev,data,wf,minio]"
```

- [ ] **Step 3: Install the extra locally**

Run: `pip install -e ".[dev,minio]"`
Expected: `pyarrow` installs successfully alongside the existing dev dependencies.

- [ ] **Step 4: Write the failing tests**

```python
# tests/test_local_lake.py
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
                "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0,
            },
            {
                "ticker": "AAPL",
                "event_time": datetime(2024, 1, 2, tzinfo=UTC),
                "knowledge_time": datetime(2024, 1, 3, tzinfo=UTC),
                "open": 1.0, "high": 1.0, "low": 1.0, "close": 101.0, "volume": 1100.0,
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
                "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0,
            },
            {
                "ticker": "AAPL",
                "event_time": datetime(2024, 1, 2, tzinfo=UTC),
                "knowledge_time": datetime(2024, 1, 3, tzinfo=UTC),
                "open": 1.0, "high": 1.0, "low": 1.0, "close": 101.0, "volume": 1100.0,
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
            "open": 1.0, "high": 1.0, "low": 1.0, "close": float(d), "volume": 1.0,
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
                "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0,
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
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/test_local_lake.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtester.local_lake'`

- [ ] **Step 6: Write the implementation**

```python
# backtester/local_lake.py
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

Copyright (c) 2026 QuantJourney.
Licensed under the Apache License 2.0.
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_local_lake.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml backtester/local_lake.py tests/test_local_lake.py
git commit -m "$(cat <<'EOF'
feat: add local_lake.read_pit for MinIO/S3 lake access

New optional `minio` extra (pyarrow, lazy-imported). read_pit() PIT-
resolves a bitemporal Parquet dataset the same way the private
IMQuantFund project's imqf_data.lake.pit_resolve does, independently
reimplemented so quantjourney-bt has no dependency on that project.
EOF
)"
```

---

### Task 3: PIT S&P 500 membership resolution

**Files:**
- Modify: `backtester/local_lake.py`
- Modify: `tests/test_local_lake.py`

**Interfaces:**
- Consumes: `read_pit(...)` from Task 2.
- Produces: `backtester.local_lake.resolve_pit_sp500(trading_days: list[date], *, as_of: datetime, index_name: str = "sp500", filesystem: Any = None, root: str | None = None) -> dict[date, set[str]]` — used by Task 4. `backtester.local_lake.pit_sp500_ticker_universe(start: date, end: date, *, as_of: datetime, index_name: str = "sp500", filesystem: Any = None, root: str | None = None) -> list[str]` — used by Task 7 (`main()`) and Task 8 (validation script).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_local_lake.py`:

```python
from backtester.local_lake import pit_sp500_ticker_universe, resolve_pit_sp500  # noqa: E402


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_local_lake.py -v -k pit_sp500`
Expected: FAIL with `ImportError: cannot import name 'resolve_pit_sp500'`

- [ ] **Step 3: Write the implementation**

Append to `backtester/local_lake.py`:

```python
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
    Keyed by `symbol` alone for PIT resolution (not `symbol, event_time`)
    -- a symbol's own event_time/opt_out facts are fixed regardless of
    how many times the source dataset gets rewritten wholesale.
    """
    membership = read_pit(
        "processed",
        "index_membership",
        as_of=as_of,
        pit_keys=("symbol",),
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
    in [start, end], PIT-resolved as of `as_of`. Used to build the
    instrument list passed to Backtester.__init__ -- day-by-day
    eligibility is enforced separately, via resolve_pit_sp500."""
    membership = read_pit(
        "processed",
        "index_membership",
        as_of=as_of,
        pit_keys=("symbol",),
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_local_lake.py -v`
Expected: PASS (7 tests total)

- [ ] **Step 5: Commit**

```bash
git add backtester/local_lake.py tests/test_local_lake.py
git commit -m "$(cat <<'EOF'
feat: add PIT S&P 500 membership resolution to local_lake

resolve_pit_sp500() gives day-by-day membership for eligibility
masking; pit_sp500_ticker_universe() gives the union over a window for
building Backtester's instruments list. Both PIT-resolve keyed on
symbol alone, since index_membership gets rewritten as a full
snapshot on each source run rather than appended incrementally.
EOF
)"
```

---

### Task 4: `backtester/local_data.build_local_minio_bt_payload`

**Files:**
- Create: `backtester/local_data.py`
- Test: `tests/test_local_data.py`

**Interfaces:**
- Consumes: `backtester.local_lake.read_pit`, `backtester.local_lake.resolve_pit_sp500` (Tasks 2-3), `backtester.bt_payload.frame_payload`, `backtester.bt_payload.series_payload` (Task 1), `backtester.core._payload_to_multiindex_df` (existing, for test assertions only).
- Produces: `backtester.local_data.build_local_minio_bt_payload(*, instruments: list[str], start: str, end: str, initial_nav: float = 100.0, as_of: datetime | None = None, filesystem: Any = None, root: str | None = None) -> dict[str, Any]` — used by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_local_data.py
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


def _bars(tickers: list[str], dates: list[datetime], closes: dict[str, list[float]]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        for d, c in zip(dates, closes[t], strict=True):
            rows.append(
                {
                    "ticker": t, "event_time": d, "close": c,
                    "open": c, "high": c, "low": c, "volume": 100.0,
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
        instruments=tickers, start="2024-01-01", end="2024-01-05",
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
        local_data, "resolve_pit_sp500", lambda trading_days, **kwargs: {d: {"AAA"} for d in trading_days}
    )

    payload = local_data.build_local_minio_bt_payload(
        instruments=tickers, start="2024-01-01", end="2024-01-03",
    )
    parameters = _payload_to_multiindex_df(payload["parameters"])

    assert (parameters[("AAA", "eligibility")] == 1.0).all()
    assert (parameters[("BBB", "eligibility")] == 0.0).all()


def test_build_local_minio_bt_payload_requires_at_least_one_instrument():
    with pytest.raises(ValueError, match="at least one instrument"):
        local_data.build_local_minio_bt_payload(instruments=[], start="2024-01-01", end="2024-01-05")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_local_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtester.local_data'`

- [ ] **Step 3: Write the implementation**

```python
# backtester/local_data.py
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

from backtester.bt_payload import frame_payload, series_payload
from backtester.local_lake import pit_sp500_ticker_universe, read_pit, resolve_pit_sp500

SPY_TICKER = "SPY"
TREND_SMA_WINDOW = 200

__all__ = ["build_local_minio_bt_payload"]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _price_panel(bars: pd.DataFrame, tickers: list[str], dates: pd.DatetimeIndex) -> pd.DataFrame:
    bars = bars[bars["ticker"].isin(tickers)]
    wide = bars.pivot_table(index="event_time", columns="ticker", values=["open", "high", "low", "close", "volume"])
    wide = wide.reindex(dates)
    wide.columns = wide.columns.swaplevel(0, 1)
    full_cols = pd.MultiIndex.from_product([tickers, ["open", "high", "low", "close", "volume"]])
    wide = wide.reindex(columns=full_cols)
    wide.columns.names = ["instrument", "field"]
    for ticker in tickers:
        wide[(ticker, "adj_close")] = wide[(ticker, "close")]
    return wide.sort_index(axis=1)


def _sctr_rank_panel(sctr: pd.DataFrame, tickers: list[str], dates: pd.DatetimeIndex) -> pd.DataFrame:
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
    membership_by_day = resolve_pit_sp500(trading_days, as_of=as_of, filesystem=filesystem, root=root)
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
    parameters.columns = pd.MultiIndex.from_tuples(parameters.columns, names=["instrument", "field"])
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

    bars = read_pit(
        "processed", "equity_bars_1d_yahoo_adj", as_of=as_of,
        tickers=tickers, start=start_date, end=end_date,
        filesystem=filesystem, root=root,
    )
    if bars.empty:
        raise ValueError(f"No equity_bars_1d_yahoo_adj rows for {tickers} in [{start}, {end}]")

    spy_bars = read_pit(
        "processed", "market_ref_bars_1d_yahoo_adj", as_of=as_of,
        tickers=[SPY_TICKER], start=start_date, end=end_date,
        filesystem=filesystem, root=root,
    )
    if spy_bars.empty:
        raise ValueError("No SPY rows in market_ref_bars_1d_yahoo_adj for the requested window")

    sctr = read_pit(
        "research", "sctr_features", as_of=as_of,
        tickers=tickers, start=start_date, end=end_date,
        filesystem=filesystem, root=root,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_local_data.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backtester/local_data.py tests/test_local_data.py
git commit -m "$(cat <<'EOF'
feat: add build_local_minio_bt_payload data-source adapter

Reads equity_bars_1d_yahoo_adj, market_ref_bars_1d_yahoo_adj, and
sctr_features via local_lake.read_pit, plus PIT S&P 500 eligibility
via resolve_pit_sp500, and assembles them into the same payload shape
sample_data.build_sample_bt_payload produces. SCTR rank, PIT
eligibility, and the SPY 200-day trend gate ride in through the
parameters panel.
EOF
)"
```

---

### Task 5: Wire `source="minio"` into `Backtester`

**Files:**
- Modify: `backtester/mixins/sdk_client.py:180-208` (insert before the existing `source == "sample"` block)
- Test: `tests/test_local_minio_source.py`

**Interfaces:**
- Consumes: `backtester.local_data.build_local_minio_bt_payload` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_local_minio_source.py
from __future__ import annotations

import asyncio

from backtester import Backtester, local_data
from backtester.sample_data import build_sample_bt_payload


def test_backtester_source_minio_uses_local_payload_and_skips_network(monkeypatch):
    payload = build_sample_bt_payload(instruments=["AAA", "BBB"], start="2024-01-01", end="2024-03-01")
    payload["summary"]["source"] = "minio"

    calls: dict[str, object] = {}

    def fake_build(*, instruments, start, end, initial_nav):
        calls["instruments"] = instruments
        calls["start"] = start
        calls["end"] = end
        calls["initial_nav"] = initial_nav
        return payload

    monkeypatch.setattr(local_data, "build_local_minio_bt_payload", fake_build)

    bt = Backtester(
        instruments=["AAA", "BBB"],
        backtest_period={"start": "2024-01-01", "end": "2024-03-01"},
        source="minio",
        strategy_name="minio_source_smoke_test",
        show_text_reports=False,
        skip_analysis=True,
    )

    async def _get_sdk_client_should_not_be_called():
        raise AssertionError("source='minio' must not touch the SDK client / network")

    bt._get_sdk_client = _get_sdk_client_should_not_be_called  # type: ignore[method-assign]

    asyncio.run(bt._fetch_market_data())

    assert calls["instruments"] == ["AAA", "BBB"]
    assert calls["initial_nav"] == bt.initial_capital
    assert bt.session_id == "sample-session"
    assert bt.dataset_id == "sample-dataset"
    assert bt._api_response["summary"]["source"] == "minio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_local_minio_source.py -v`
Expected: FAIL — `fake_build` is never called (falls through to the API/auth path and raises `ValueError: Backtester requires either (email + password) or api_key`)

- [ ] **Step 3: Write the implementation**

In `backtester/mixins/sdk_client.py`, insert a new block immediately before the existing `if self._source == "sample" or os.getenv("QJ_SAMPLE_DATA", ...)` block inside `_fetch_market_data` (i.e. right after the docstring at line 184):

```python
        if self._source == "minio":
            from backtester.local_data import build_local_minio_bt_payload

            self._api_response = build_local_minio_bt_payload(
                instruments=self.instruments,
                start=self.backtest_period.start,
                end=self.backtest_period.end,
                initial_nav=self.initial_capital,
            )
            self.session_id = self._api_response["session_id"]
            self.dataset_id = self._api_response["dataset_id"]
            self._validate_data_completeness_response()
            summary = self._api_response["summary"]
            logger.info(
                f"[Backtester] Local MinIO data loaded: "
                f"session={self.session_id}, dataset={self.dataset_id}, "
                f"instruments={summary.get('instruments')}, dates={summary.get('dates')}"
            )
            return

```

The existing `if self._source == "sample" or ...:` block is left completely unchanged, immediately below this new block.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_local_minio_source.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to confirm no regression**

Run: `pytest tests/ -v`
Expected: PASS (all prior tests plus the new ones)

- [ ] **Step 6: Commit**

```bash
git add backtester/mixins/sdk_client.py tests/test_local_minio_source.py
git commit -m "$(cat <<'EOF'
feat: wire source=\"minio\" into Backtester._fetch_market_data

Sibling branch to the existing source=\"sample\" escape hatch: builds
_api_response from build_local_minio_bt_payload with no network call
and no credentials required, leaving _process_market_data() and auth
completely untouched.
EOF
)"
```

---

### Task 6: SCTR regime-gated portfolio construction (pure function)

**Files:**
- Create: `strategies/sctr_momentum_regime_gated.py`
- Test: `tests/test_sctr_momentum_regime_gated.py`

**Interfaces:**
- Produces: `strategies.sctr_momentum_regime_gated._build_regime_gated_weights(rank: pd.DataFrame, eligibility: pd.DataFrame, trend_down: pd.Series, *, entry_threshold: float = 95.0, hold_threshold: float = 85.0, min_holding_days: int = 90, max_holding_days: int = 120, max_positions: int = 20) -> pd.DataFrame` — used by Task 7's `SCTRMomentumRegimeGated._compute_weights`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sctr_momentum_regime_gated.py
from __future__ import annotations

import pandas as pd

from strategies.sctr_momentum_regime_gated import _build_regime_gated_weights


def _panel(dates: pd.DatetimeIndex, columns: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame(columns, index=dates)


def test_hold_hysteresis_and_min_holding_days_override():
    dates = pd.bdate_range("2024-01-01", periods=4)
    rank = _panel(dates, {"AAA": [96.0, 40.0, 40.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [1.0, 1.0, 1.0, 1.0]})
    trend_down = pd.Series([0.0, 0.0, 0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=2, max_positions=20,
    )

    assert weights.loc[dates[0], "AAA"] == 1.0  # entry: rank 96 >= 95
    assert weights.loc[dates[1], "AAA"] == 1.0  # rank 40 fails hold(85), but held < 2 days -> min-hold protects
    assert weights.loc[dates[2], "AAA"] == 0.0  # held 2 days now -> min-hold no longer protects -> evicted
    assert weights.loc[dates[3], "AAA"] == 1.0  # rank back to 96 -> fresh re-entry


def test_gate_liquidates_and_allows_immediate_reentry():
    dates = pd.bdate_range("2024-01-01", periods=4)
    rank = _panel(dates, {"AAA": [96.0, 96.0, 96.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [1.0, 1.0, 1.0, 1.0]})
    trend_down = pd.Series([0.0, 1.0, 0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=90, max_positions=20,
    )

    assert weights.loc[dates[0], "AAA"] == 1.0
    assert weights.loc[dates[1], "AAA"] == 0.0  # gated day: force-liquidated, no new entries evaluated
    assert weights.loc[dates[2], "AAA"] == 1.0  # trend flips back up -> immediate re-entry, no hysteresis buffer
    assert weights.loc[dates[3], "AAA"] == 1.0


def test_max_positions_cap_prioritizes_by_rank():
    dates = pd.bdate_range("2024-01-01", periods=2)
    rank = _panel(dates, {"AAA": [99.0, 99.0], "BBB": [97.0, 97.0], "CCC": [96.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [1.0, 1.0], "BBB": [1.0, 1.0], "CCC": [1.0, 1.0]})
    trend_down = pd.Series([0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=90, max_positions=2,
    )

    assert weights.loc[dates[0], "AAA"] == 0.5
    assert weights.loc[dates[0], "BBB"] == 0.5
    assert weights.loc[dates[0], "CCC"] == 0.0
    # incumbents keep their slots on day 2 even though CCC's rank alone would also qualify
    assert weights.loc[dates[1], "AAA"] == 0.5
    assert weights.loc[dates[1], "BBB"] == 0.5
    assert weights.loc[dates[1], "CCC"] == 0.0


def test_ineligible_name_never_enters_even_with_qualifying_rank():
    dates = pd.bdate_range("2024-01-01", periods=2)
    rank = _panel(dates, {"AAA": [96.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [0.0, 1.0]})
    trend_down = pd.Series([0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=90, max_positions=20,
    )

    assert weights.loc[dates[0], "AAA"] == 0.0  # ineligible on day 1 despite qualifying rank
    assert weights.loc[dates[1], "AAA"] == 1.0  # eligible from day 2 -> enters
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sctr_momentum_regime_gated.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'strategies.sctr_momentum_regime_gated'`

- [ ] **Step 3: Write the implementation**

```python
# strategies/sctr_momentum_regime_gated.py
# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
SCTR Momentum, Regime-Gated (Binary Trend Pause)
=================================================

Mode: weights.

Port of docs/research/strategies/sctr-momentum-regime-gated.md (a
separate private research project) run here against local MinIO data
(source="minio") instead of that project's own engine -- see
docs/superpowers/specs/2026-07-16-minio-local-data-sctr-backtest-design.md
for the full design and known fidelity gaps versus the original.

Rules: entry at SCTR rank >= 95, hold while rank >= 85 (hysteresis),
minimum 90-trading-day hold overridable only by the trend gate, max 20
equal-weight positions with incumbent-priority slot selection. On any day
PIT-resolved SPY closes below its 200-day SMA, every held name is
force-liquidated and no new entries are taken; re-entry is immediate and
automatic the first day the trend flips back up, with no added
hysteresis on the gate itself. Universe is the PIT S&P 500 roster --
`eligibility` masks out names on days they weren't index members.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import pandas as pd

from backtester import Backtester
from backtester.local_lake import pit_sp500_ticker_universe
from backtester.portfolio.weight_cost import FixedBpsWeightCostModel

ENTRY_THRESHOLD = 95.0
HOLD_THRESHOLD = 85.0
MIN_HOLDING_DAYS = 90
MAX_HOLDING_DAYS = 120
MAX_POSITIONS = 20


def _build_regime_gated_weights(
    rank: pd.DataFrame,
    eligibility: pd.DataFrame,
    trend_down: pd.Series,
    *,
    entry_threshold: float = ENTRY_THRESHOLD,
    hold_threshold: float = HOLD_THRESHOLD,
    min_holding_days: int = MIN_HOLDING_DAYS,
    max_holding_days: int = MAX_HOLDING_DAYS,
    max_positions: int = MAX_POSITIONS,
) -> pd.DataFrame:
    """Day-by-day incumbent-priority portfolio construction.

    `rank`/`eligibility`: dates x tickers panels. `trend_down`: a dates
    Series, 1.0 on days the market-trend gate is active. Returns a dates
    x tickers equal-weight panel -- NOT pre-shifted; the engine applies
    its own shift(1) before this is ever compared against returns.
    """
    dates = rank.index
    tickers = list(rank.columns)
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)

    held: dict[str, int] = {}  # ticker -> day_idx it entered
    for day_idx, day in enumerate(dates):
        if trend_down.loc[day] >= 1.0:
            held = {}
            continue

        day_rank = rank.loc[day]
        day_elig = eligibility.loc[day].fillna(0.0)
        entry_ok = (day_rank >= entry_threshold) & (day_elig >= 1.0)
        hold_ok = (day_rank >= hold_threshold) & (day_elig >= 1.0)

        held = {
            t: entry_idx
            for t, entry_idx in held.items()
            if (bool(hold_ok.get(t, False)) or (day_idx - entry_idx) < min_holding_days)
            and (day_idx - entry_idx) < max_holding_days
        }

        slots_remaining = max_positions - len(held)
        if slots_remaining > 0:
            candidates = day_rank[entry_ok]
            candidates = candidates[~candidates.index.isin(held.keys())].dropna()
            candidates = candidates.sort_values(ascending=False)
            for ticker in candidates.index[:slots_remaining]:
                held[ticker] = day_idx

        if held:
            w = 1.0 / len(held)
            for t in held:
                weights.loc[day, t] = w

    return weights


class SCTRMomentumRegimeGated(Backtester):
    """SCTR momentum with a binary SPY-trend regime gate (weight mode)."""

    entry_threshold = ENTRY_THRESHOLD
    hold_threshold = HOLD_THRESHOLD
    min_holding_days = MIN_HOLDING_DAYS
    max_holding_days = MAX_HOLDING_DAYS
    max_positions = MAX_POSITIONS

    def _compute_signals(self) -> pd.DataFrame:
        return self.instruments_data.get_feature("parameters", level="sctr_rank")

    def _compute_weights(self) -> pd.DataFrame:
        rank = self.signals
        eligibility = self.instruments_data.get_feature("parameters", level="eligibility")
        trend_down_panel = self.instruments_data.get_feature("parameters", level="spy_trend_down")
        trend_down = trend_down_panel.iloc[:, 0]  # broadcast market-wide flag -> single Series
        return _build_regime_gated_weights(
            rank,
            eligibility,
            trend_down,
            entry_threshold=self.entry_threshold,
            hold_threshold=self.hold_threshold,
            min_holding_days=self.min_holding_days,
            max_holding_days=self.max_holding_days,
            max_positions=self.max_positions,
        )


async def main() -> None:
    as_of = datetime.now(UTC)
    start_date, end_date = date(2016, 1, 1), as_of.date()
    instruments = pit_sp500_ticker_universe(start_date, end_date, as_of=as_of)

    strategy = SCTRMomentumRegimeGated(
        strategy_name="SCTRMomentumRegimeGated",
        strategy_type="Long / Cash",
        initial_capital=100_000,
        instruments=instruments,
        backtest_period={"start": start_date.isoformat(), "end": end_date.isoformat()},
        benchmark_symbol="SPY",
        benchmark_name="SPDR S&P 500 ETF Trust",
        source="minio",
        execution_mode="weights",
        weight_cost_model=FixedBpsWeightCostModel(total_bps=10.0),
        indicators_config=[],
        show_text_reports=True,
        save_text_reports=True,
        save_portfolio_plots=True,
        show_portfolio_plots=False,
    )
    await strategy.run_strategy()
    strategy.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sctr_momentum_regime_gated.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add strategies/sctr_momentum_regime_gated.py tests/test_sctr_momentum_regime_gated.py
git commit -m "$(cat <<'EOF'
feat: port SCTR momentum regime-gated strategy to quantjourney-bt

_build_regime_gated_weights is a pure, independently-tested port of
the day-by-day incumbent-priority selection algorithm (entry/hold
hysteresis, min-holding-days, trend-gate force-liquidation with
immediate re-entry, max-positions cap) from the original private
project's build_daily_portfolios. Wired into the standard
_compute_signals/_compute_weights hook pair via SCTRMomentumRegimeGated.
EOF
)"
```

---

### Task 7: End-to-end strategy wiring test

**Files:**
- Test: `tests/test_sctr_momentum_regime_gated_strategy.py`

**Interfaces:**
- Consumes: `strategies.sctr_momentum_regime_gated.SCTRMomentumRegimeGated` (Task 6), `backtester.portfolio.instr_data.InstrumentData` (existing).

This task verifies the class actually reads `sctr_rank`/`eligibility`/`spy_trend_down` from the `parameters` panel correctly end-to-end (Task 6 only tested the pure function in isolation) — by constructing `InstrumentData` directly (no network, no live Backtester run) and calling the two hooks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sctr_momentum_regime_gated_strategy.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sctr_momentum_regime_gated_strategy.py -v`
Expected: FAIL if the hook wiring is wrong (e.g. `KeyError` on `get_feature`); given Task 6's implementation this should actually PASS already — run it to confirm, and if it fails, fix `_compute_signals`/`_compute_weights` in `strategies/sctr_momentum_regime_gated.py` until it does.

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_sctr_momentum_regime_gated_strategy.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_sctr_momentum_regime_gated_strategy.py
git commit -m "$(cat <<'EOF'
test: cover SCTRMomentumRegimeGated's parameters-panel wiring end to end

Constructs InstrumentData directly (no network, no live Backtester
run) to verify _compute_signals/_compute_weights correctly read
sctr_rank, eligibility, and spy_trend_down off the parameters panel.
EOF
)"
```

---

### Task 8: Validation against the original trial's result

**Files:**
- Create: `backtester/local_validation.py`
- Create: `strategies/validate_sctr_momentum_regime_gated.py`
- Test: `tests/test_local_validation.py`

**Interfaces:**
- Consumes: `backtester.local_lake.read_pit` (Task 2), `strategies.sctr_momentum_regime_gated.SCTRMomentumRegimeGated` (Task 6).
- Produces: `backtester.local_validation.compare_return_series(a: pd.Series, b: pd.Series) -> ReturnSeriesComparison`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_local_validation.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtester.local_validation import compare_return_series


def test_compare_return_series_identical_series_gives_correlation_one():
    dates = pd.bdate_range("2024-01-01", periods=100)
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0.0005, 0.01, size=100), index=dates)

    result = compare_return_series(returns, returns.copy())

    assert result.correlation == pytest.approx(1.0)
    assert result.sharpe_a == pytest.approx(result.sharpe_b)
    assert result.n_common_days == 100


def test_compare_return_series_aligns_on_common_dates_only():
    dates_a = pd.bdate_range("2024-01-01", periods=10)
    dates_b = pd.bdate_range("2024-01-05", periods=10)
    a = pd.Series(0.001, index=dates_a)
    b = pd.Series(0.001, index=dates_b)

    result = compare_return_series(a, b)

    assert result.n_common_days == len(set(dates_a) & set(dates_b))


def test_compare_return_series_raises_on_no_overlap():
    a = pd.Series(0.001, index=pd.bdate_range("2024-01-01", periods=5))
    b = pd.Series(0.001, index=pd.bdate_range("2025-01-01", periods=5))

    with pytest.raises(ValueError, match="no overlapping dates"):
        compare_return_series(a, b)


def test_compare_return_series_max_drawdown_is_negative_for_a_losing_series():
    dates = pd.bdate_range("2024-01-01", periods=5)
    losing = pd.Series([-0.01, -0.01, -0.01, -0.01, -0.01], index=dates)
    flat = pd.Series([0.0, 0.0, 0.0, 0.0, 0.0], index=dates)

    result = compare_return_series(losing, flat)

    assert result.max_drawdown_a < 0.0
    assert result.max_drawdown_b == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_local_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtester.local_validation'`

- [ ] **Step 3: Write the implementation**

```python
# backtester/local_validation.py
"""
Compare a locally-produced daily net-return series against a reference
return series (e.g. an already-materialized backtest result read from
the lake) -- used to sanity-check the SCTR momentum regime-gated port
against the original trial's result.

Copyright (c) 2026 QuantJourney.
Licensed under the Apache License 2.0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252

__all__ = ["ReturnSeriesComparison", "compare_return_series"]


@dataclass(frozen=True)
class ReturnSeriesComparison:
    correlation: float
    n_common_days: int
    sharpe_a: float
    sharpe_b: float
    cagr_a: float
    cagr_b: float
    max_drawdown_a: float
    max_drawdown_b: float


def _sharpe(returns: pd.Series) -> float:
    if returns.empty or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _cagr(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    nav = (1.0 + returns).cumprod()
    years = len(returns) / TRADING_DAYS_PER_YEAR
    if years <= 0 or nav.iloc[-1] <= 0:
        return 0.0
    return float(nav.iloc[-1] ** (1.0 / years) - 1.0)


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    nav = (1.0 + returns).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return float(drawdown.min())


def compare_return_series(a: pd.Series, b: pd.Series) -> ReturnSeriesComparison:
    """`a`/`b`: daily net-return series indexed by date. Aligns on their
    common index before computing correlation and per-series risk
    metrics -- days present in only one series are dropped, not
    zero-filled (a missing observation is not a zero return)."""
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if joined.empty:
        raise ValueError("compare_return_series: no overlapping dates between the two series")

    correlation = float(joined["a"].corr(joined["b"])) if len(joined) > 1 else 0.0
    return ReturnSeriesComparison(
        correlation=correlation,
        n_common_days=len(joined),
        sharpe_a=_sharpe(joined["a"]),
        sharpe_b=_sharpe(joined["b"]),
        cagr_a=_cagr(joined["a"]),
        cagr_b=_cagr(joined["b"]),
        max_drawdown_a=_max_drawdown(joined["a"]),
        max_drawdown_b=_max_drawdown(joined["b"]),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_local_validation.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write the validation script (not unit tested — manual/integration use only, requires a running local MinIO)**

```python
# strategies/validate_sctr_momentum_regime_gated.py
# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
Compare SCTRMomentumRegimeGated's result (run against local MinIO data)
to the original trial's already-materialized result at
analytics/sctr_momentum_regime_gated_pnl.

Manual/integration use only -- requires QJ_LOCAL_LAKE_* pointed at a
running local MinIO with the datasets described in
docs/superpowers/specs/2026-07-16-minio-local-data-sctr-backtest-design.md.
Not run in CI.

Usage:
    ./strategy.sh validate_sctr_momentum_regime_gated
"""

import asyncio
from datetime import UTC, date, datetime

from backtester.local_lake import pit_sp500_ticker_universe, read_pit
from backtester.local_validation import compare_return_series
from backtester.portfolio.weight_cost import FixedBpsWeightCostModel
from strategies.sctr_momentum_regime_gated import SCTRMomentumRegimeGated


async def main() -> None:
    as_of = datetime.now(UTC)
    start_date, end_date = date(2016, 1, 1), as_of.date()
    instruments = pit_sp500_ticker_universe(start_date, end_date, as_of=as_of)

    strategy = SCTRMomentumRegimeGated(
        strategy_name="SCTRMomentumRegimeGated_validation",
        initial_capital=100_000,
        instruments=instruments,
        backtest_period={"start": start_date.isoformat(), "end": end_date.isoformat()},
        benchmark_symbol="SPY",
        source="minio",
        execution_mode="weights",
        weight_cost_model=FixedBpsWeightCostModel(total_bps=10.0),
        show_text_reports=False,
        skip_analysis=True,
    )
    await strategy.run_strategy()

    local_returns = strategy.portfolio_data.net_asset_value.pct_change().dropna()
    local_returns.index = local_returns.index.tz_localize(None)

    reference = read_pit(
        "analytics",
        "sctr_momentum_regime_gated_pnl",
        as_of=as_of,
        pit_keys=("event_time",),
    )
    reference_returns = reference.set_index("event_time")["net_return"]
    reference_returns.index = reference_returns.index.tz_localize(None)

    result = compare_return_series(local_returns, reference_returns)
    print("SCTRMomentumRegimeGated vs. original trial (analytics/sctr_momentum_regime_gated_pnl)")
    print(f"  common trading days : {result.n_common_days}")
    print(f"  return correlation  : {result.correlation:.3f}")
    print(f"  Sharpe   (qj-bt)    : {result.sharpe_a:.3f}")
    print(f"  Sharpe   (original) : {result.sharpe_b:.3f}")
    print(f"  CAGR     (qj-bt)    : {result.cagr_a:.2%}")
    print(f"  CAGR     (original) : {result.cagr_b:.2%}")
    print(f"  Max DD   (qj-bt)    : {result.max_drawdown_a:.2%}")
    print(f"  Max DD   (original) : {result.max_drawdown_b:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Commit**

```bash
git add backtester/local_validation.py strategies/validate_sctr_momentum_regime_gated.py tests/test_local_validation.py
git commit -m "$(cat <<'EOF'
feat: add return-series comparison + SCTR regime-gated validation script

compare_return_series() aligns two daily net-return series on their
common dates and reports correlation plus Sharpe/CAGR/max-drawdown
deltas. validate_sctr_momentum_regime_gated.py runs the ported
strategy against local MinIO data and compares it to the original
trial's materialized result at analytics/sctr_momentum_regime_gated_pnl
-- manual/integration use, requires a running local MinIO, not run in CI.
EOF
)"
```

---

## Manual verification (requires the user's running local MinIO — not part of any task's automated tests)

After all 8 tasks are committed:

1. Set the three env vars to the same values as IMQuantFund's `.env` (`IMQF_STORAGE__ENDPOINT_URL` → `QJ_LOCAL_LAKE_ENDPOINT_URL`, etc. — get the actual values from that file, never copy them into this repo).
2. Run `./strategy.sh sctr_momentum_regime_gated` and confirm it completes and produces a report.
3. Run `./strategy.sh validate_sctr_momentum_regime_gated` and read the printed correlation/Sharpe/CAGR/maxDD comparison against the original trial.
