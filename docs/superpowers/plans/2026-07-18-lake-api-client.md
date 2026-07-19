# Lake API Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an HTTP client (`backtester/lake_api.py`) for IMQuantFund's new `/api/v1/lake/*` API, and wire `local_data.build_local_minio_bt_payload` to use it for the two highest-volume MinIO reads (`equity_bars_1d_yahoo_adj`, `sctr_features`), while `market_ref_bars_1d_yahoo_adj` and `index_membership` stay on direct MinIO.

**Architecture:** A new, dependency-free-of-pyarrow module wraps three HTTP endpoints (`read_bars`, `read_features`, `read_universe`) behind a synchronous `httpx.Client`, mirroring `local_lake.py`'s style (module-level functions, optional test-injection parameter, PIT semantics preserved exactly for `sctr_features`). `local_data.py` swaps two of its four `read_pit` calls for the new client calls; the other two, plus `local_lake.py` itself, are untouched.

**Tech Stack:** Python, `httpx` (already a core dependency), `pandas`, `pytest` with `httpx.MockTransport` for HTTP mocking (no new test dependency).

## Global Constraints

- New env vars: `QJ_LAKE_API_URL` (default `http://localhost:8000`), `QJ_LAKE_API_KEY` (required, no default, sent as `X-API-Key` header).
- No new dependency: `httpx` is already in `pyproject.toml`'s core deps.
- `Backtester(source="minio")`'s public name/value does not change.
- Non-2xx HTTP response → `ValueError` with the request URL, status code, and response body. A 401 specifically must mention `QJ_LAKE_API_KEY` in the message.
- A 200 response with zero matching rows (empty-but-schema-valid Parquet) is not an error — return an empty DataFrame with correct dtypes, never raise.
- `read_bars(dataset, *, tickers, start, end, client=None)` has **no** `as_of` parameter — the bars endpoint has none; the server hardcodes PIT resolution to `as_of=end`.
- `read_features(dataset, *, tickers, as_of, client=None)` — `as_of` is required and caller-supplied, no default inside `lake_api.py` itself.
- `read_universe(name, *, as_of, client=None)` returns `list[str]` (JSON), not a DataFrame.
- `market_ref_bars_1d_yahoo_adj` and `index_membership` (via `resolve_pit_sp500`) keep using `backtester.local_lake.read_pit`/`resolve_pit_sp500` unchanged — never touch those two call sites.
- `sctr` read in `local_data.py` must pass `as_of=as_of.date()` (the function's own `as_of` param, default `datetime.now(UTC)`) — not `end_date`. This preserves the original `read_pit` call's knowledge-time semantics exactly.

Spec: `docs/superpowers/specs/2026-07-18-lake-api-client-design.md`

---

### Task 1: `lake_api.py` core + `read_bars`

**Files:**
- Create: `backtester/lake_api.py`
- Create: `tests/test_lake_api.py`

**Interfaces:**
- Produces: `lake_api.read_bars(dataset: str, *, tickers: list[str], start: date, end: date, client: httpx.Client | None = None) -> pd.DataFrame`
- Produces (internal, reused by Tasks 2–3): `lake_api._headers() -> dict[str, str]`, `lake_api._get(path: str, params: dict[str, str], client: httpx.Client | None) -> httpx.Response`, `lake_api._raise_for_status(response: httpx.Response) -> None`, `lake_api.DEFAULT_LAKE_API_URL: str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lake_api.py`:

```python
# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""Tests for backtester.lake_api."""

from __future__ import annotations

import io
from datetime import date

import httpx
import pandas as pd
import pytest

from backtester import lake_api


def _parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf)
    return buf.getvalue()


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver")


def test_read_bars_parses_parquet_and_sends_expected_request(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")
    expected = pd.DataFrame({"ticker": ["AAPL"], "close": [123.45]})
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers["x-api-key"]
        return httpx.Response(200, content=_parquet_bytes(expected))

    result = lake_api.read_bars(
        "equity_bars_1d_yahoo_adj",
        tickers=["AAPL"],
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        client=_mock_client(handler),
    )

    pd.testing.assert_frame_equal(result, expected)
    assert "/api/v1/lake/bars/equity_bars_1d_yahoo_adj" in captured["url"]
    assert "tickers=AAPL" in captured["url"]
    assert "start=2024-01-01" in captured["url"]
    assert "end=2024-01-31" in captured["url"]
    assert captured["api_key"] == "test-key"


def test_read_bars_401_raises_value_error_mentioning_api_key(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "wrong-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(ValueError, match="QJ_LAKE_API_KEY"):
        lake_api.read_bars(
            "equity_bars_1d_yahoo_adj",
            tickers=["AAPL"],
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            client=_mock_client(handler),
        )


def test_read_bars_404_includes_response_body(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            text="unknown bars dataset 'foo' -- valid datasets: ['equity_bars_1d_yahoo_adj']",
        )

    with pytest.raises(ValueError, match="unknown bars dataset"):
        lake_api.read_bars(
            "foo",
            tickers=["AAPL"],
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            client=_mock_client(handler),
        )


def test_read_bars_empty_result_returns_empty_dataframe(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")
    empty = pd.DataFrame(
        {"ticker": pd.Series(dtype="object"), "close": pd.Series(dtype="float64")}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_parquet_bytes(empty))

    result = lake_api.read_bars(
        "equity_bars_1d_yahoo_adj",
        tickers=["AAPL"],
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        client=_mock_client(handler),
    )
    assert result.empty
    assert list(result.columns) == ["ticker", "close"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_lake_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtester.lake_api'`

- [ ] **Step 3: Write the implementation**

Create `backtester/lake_api.py`:

```python
# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
HTTP client for IMQuantFund's external, read-only lake API
(/api/v1/lake/*), used by backtester.local_data.build_local_minio_bt_payload
for Backtester(source="minio").

Two of local_data's four MinIO-era reads move onto this HTTP transport --
equity_bars_1d_yahoo_adj (via read_bars) and sctr_features (via
read_features) -- the highest-volume reads, and the only two the API
exposes. market_ref_bars_1d_yahoo_adj and index_membership stay on
backtester.local_lake's direct MinIO reads; see
docs/superpowers/specs/2026-07-18-lake-api-client-design.md for why.

Configured via QJ_LAKE_API_URL (default http://localhost:8000) and
QJ_LAKE_API_KEY (required, sent as the X-API-Key header).
"""

from __future__ import annotations

import io
import os
from datetime import date

import httpx
import pandas as pd

DEFAULT_LAKE_API_URL = "http://localhost:8000"

__all__ = ["read_bars"]


def _headers() -> dict[str, str]:
    return {"X-API-Key": os.environ["QJ_LAKE_API_KEY"]}


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise ValueError(
            f"Lake API rejected the request (401 Unauthorized) at {response.request.url}\n"
            "  Check the QJ_LAKE_API_KEY environment variable."
        )
    if response.status_code >= 400:
        raise ValueError(
            f"Lake API request to {response.request.url} failed "
            f"({response.status_code}): {response.text}"
        )


def _get(path: str, params: dict[str, str], client: httpx.Client | None) -> httpx.Response:
    headers = _headers()
    if client is not None:
        response = client.get(path, params=params, headers=headers)
    else:
        base_url = os.environ.get("QJ_LAKE_API_URL", DEFAULT_LAKE_API_URL)
        with httpx.Client(base_url=base_url, timeout=60.0) as owned_client:
            response = owned_client.get(path, params=params, headers=headers)
    _raise_for_status(response)
    return response


def read_bars(
    dataset: str,
    *,
    tickers: list[str],
    start: date,
    end: date,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Read Yahoo-adjusted daily bars for `tickers` in [start, end] via
    GET /api/v1/lake/bars/{dataset}. PIT-resolved server-side as of `end`
    (the endpoint has no separate as_of param).

    `client` lets tests inject an httpx.Client built on an
    httpx.MockTransport instead of hitting a real server; production
    callers omit it and get a fresh client built from QJ_LAKE_API_URL.
    """
    response = _get(
        f"/api/v1/lake/bars/{dataset}",
        {"tickers": ",".join(tickers), "start": start.isoformat(), "end": end.isoformat()},
        client,
    )
    return pd.read_parquet(io.BytesIO(response.content))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_lake_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backtester/lake_api.py tests/test_lake_api.py
git commit -m "feat: add lake_api.read_bars HTTP client for IMQuantFund's lake API"
```

---

### Task 2: `read_features`

**Files:**
- Modify: `backtester/lake_api.py`
- Modify: `tests/test_lake_api.py`

**Interfaces:**
- Consumes: `lake_api._get`, `lake_api._raise_for_status` (from Task 1, unchanged)
- Produces: `lake_api.read_features(dataset: str, *, tickers: list[str], as_of: date, client: httpx.Client | None = None) -> pd.DataFrame`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lake_api.py`:

```python
def test_read_features_parses_parquet_and_sends_expected_request(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")
    expected = pd.DataFrame({"ticker": ["AAPL"], "rank": [92.0]})
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, content=_parquet_bytes(expected))

    result = lake_api.read_features(
        "sctr_features",
        tickers=["AAPL"],
        as_of=date(2024, 1, 31),
        client=_mock_client(handler),
    )

    pd.testing.assert_frame_equal(result, expected)
    assert "/api/v1/lake/features/sctr_features" in captured["url"]
    assert "as_of=2024-01-31" in captured["url"]
    assert "tickers=AAPL" in captured["url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest tests/test_lake_api.py::test_read_features_parses_parquet_and_sends_expected_request -v`
Expected: FAIL with `AttributeError: module 'backtester.lake_api' has no attribute 'read_features'`

- [ ] **Step 3: Implement `read_features`**

In `backtester/lake_api.py`, update `__all__` and add the function:

```python
__all__ = ["read_bars", "read_features"]
```

```python
def read_features(
    dataset: str,
    *,
    tickers: list[str],
    as_of: date,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Read research-tier features for `tickers`, PIT-resolved as of
    `as_of`, via GET /api/v1/lake/features/{dataset}. Unlike read_bars,
    `as_of` is required and caller-controlled -- the endpoint has no
    start/end params, so callers get every event_time on record for
    `tickers`, resolved as of `as_of`."""
    response = _get(
        f"/api/v1/lake/features/{dataset}",
        {"tickers": ",".join(tickers), "as_of": as_of.isoformat()},
        client,
    )
    return pd.read_parquet(io.BytesIO(response.content))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_lake_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backtester/lake_api.py tests/test_lake_api.py
git commit -m "feat: add lake_api.read_features HTTP client"
```

---

### Task 3: `read_universe`

**Files:**
- Modify: `backtester/lake_api.py`
- Modify: `tests/test_lake_api.py`

**Interfaces:**
- Consumes: `lake_api._get`, `lake_api._raise_for_status` (unchanged)
- Produces: `lake_api.read_universe(name: str, *, as_of: date, client: httpx.Client | None = None) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lake_api.py`:

```python
def test_read_universe_parses_json_list(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["AAPL", "MSFT"])

    result = lake_api.read_universe(
        "sp500", as_of=date(2024, 1, 31), client=_mock_client(handler)
    )
    assert result == ["AAPL", "MSFT"]


def test_read_universe_404_raises_value_error(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="unknown universe 'foo'")

    with pytest.raises(ValueError, match="unknown universe"):
        lake_api.read_universe("foo", as_of=date(2024, 1, 31), client=_mock_client(handler))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_lake_api.py -k read_universe -v`
Expected: FAIL with `AttributeError: module 'backtester.lake_api' has no attribute 'read_universe'`

- [ ] **Step 3: Implement `read_universe`**

In `backtester/lake_api.py`, update `__all__` and add the function:

```python
__all__ = ["read_bars", "read_features", "read_universe"]
```

```python
def read_universe(
    name: str,
    *,
    as_of: date,
    client: httpx.Client | None = None,
) -> list[str]:
    """Read a resolved, single-date universe membership list via
    GET /api/v1/lake/universe/{name}. Not wired into
    local_data.build_local_minio_bt_payload today -- resolve_pit_sp500
    still owns day-by-day eligibility, reading the raw span table
    directly from MinIO (see module docstring) -- but exposed for later
    use (e.g. the research loop's IDEATE stage)."""
    response = _get(f"/api/v1/lake/universe/{name}", {"as_of": as_of.isoformat()}, client)
    return response.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_lake_api.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backtester/lake_api.py tests/test_lake_api.py
git commit -m "feat: add lake_api.read_universe HTTP client"
```

---

### Task 4: Wire `local_data.py` to `lake_api`

**Files:**
- Modify: `backtester/local_data.py`
- Modify: `tests/test_local_data.py`

**Interfaces:**
- Consumes: `lake_api.read_bars(dataset, *, tickers, start, end, client=None)`, `lake_api.read_features(dataset, *, tickers, as_of, client=None)` (from Tasks 1–2)

- [ ] **Step 1: Write the failing test**

This test asserts `build_local_minio_bt_payload` calls `lake_api.read_bars`/`read_features` with the right arguments, and still calls `read_pit`/`resolve_pit_sp500` only for the two MinIO-only datasets. Add to `tests/test_local_data.py` (after the existing imports, before `_bars`):

```python
def test_build_local_minio_bt_payload_routes_bars_and_sctr_through_lake_api(monkeypatch):
    dates = [datetime(2024, 1, d, tzinfo=UTC) for d in range(1, 4)]
    tickers = ["AAA", "BBB"]
    bars = _bars(tickers, dates, {"AAA": [10.0, 11.0, 12.0], "BBB": [20.0, 21.0, 22.0]})
    spy_bars = _bars(["SPY"], dates, {"SPY": [100.0, 101.0, 102.0]})
    sctr = pd.DataFrame(
        [{"ticker": t, "event_time": d, "rank": 90.0} for t in tickers for d in dates]
    )
    calls = {}

    def fake_read_bars(dataset, *, tickers, start, end, client=None):
        calls["read_bars"] = {"dataset": dataset, "tickers": tickers, "start": start, "end": end}
        return bars

    def fake_read_features(dataset, *, tickers, as_of, client=None):
        calls["read_features"] = {"dataset": dataset, "tickers": tickers, "as_of": as_of}
        return sctr

    def fake_read_pit(bucket, dataset, **kwargs):
        assert dataset == "market_ref_bars_1d_yahoo_adj", (
            f"read_pit should only be called for market_ref_bars_1d_yahoo_adj, got {dataset}"
        )
        return spy_bars

    def fake_resolve_pit_sp500(trading_days, **kwargs):
        return {day: {"AAA", "BBB"} for day in trading_days}

    monkeypatch.setattr(local_data.lake_api, "read_bars", fake_read_bars)
    monkeypatch.setattr(local_data.lake_api, "read_features", fake_read_features)
    monkeypatch.setattr(local_data, "read_pit", fake_read_pit)
    monkeypatch.setattr(local_data, "resolve_pit_sp500", fake_resolve_pit_sp500)

    fixed_as_of = datetime(2024, 6, 1, tzinfo=UTC)
    local_data.build_local_minio_bt_payload(
        instruments=tickers,
        start="2024-01-01",
        end="2024-01-03",
        as_of=fixed_as_of,
    )

    assert calls["read_bars"]["dataset"] == "equity_bars_1d_yahoo_adj"
    assert calls["read_bars"]["tickers"] == tickers
    assert calls["read_bars"]["start"].isoformat() == "2024-01-01"
    assert calls["read_bars"]["end"].isoformat() == "2024-01-03"

    assert calls["read_features"]["dataset"] == "sctr_features"
    assert calls["read_features"]["tickers"] == tickers
    assert calls["read_features"]["as_of"] == fixed_as_of.date()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest tests/test_local_data.py::test_build_local_minio_bt_payload_routes_bars_and_sctr_through_lake_api -v`
Expected: FAIL — `local_data` has no attribute `lake_api` (module not imported yet), or the assertion inside `fake_read_pit` fails because `read_pit` is still called for `equity_bars_1d_yahoo_adj`/`sctr_features` too.

- [ ] **Step 3: Update `backtester/local_data.py`**

Change the import block (was `from backtester.local_lake import read_pit, resolve_pit_sp500`):

```python
from backtester import lake_api
from backtester.local_lake import read_pit, resolve_pit_sp500
```

Replace the `equity_bars_1d_yahoo_adj` read:

```python
    bars = lake_api.read_bars(
        "equity_bars_1d_yahoo_adj",
        tickers=tickers,
        start=start_date,
        end=end_date,
    )
    if bars.empty:
        raise ValueError(f"No equity_bars_1d_yahoo_adj rows for {tickers} in [{start}, {end}]")
```

Replace the `sctr_features` read (note: `as_of=as_of.date()`, **not** `end_date` — see Global Constraints):

```python
    sctr = lake_api.read_features(
        "sctr_features",
        tickers=tickers,
        as_of=as_of.date(),
    )
```

Leave the `spy_bars = read_pit("processed", "market_ref_bars_1d_yahoo_adj", ...)` call and the `_eligibility_panel`/`resolve_pit_sp500` call completely unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_local_data.py -v`
Expected: PASS — all 4 tests in the file, including the 3 pre-existing ones (updated in Step 5 below) and the new one.

Note: this will still fail on the 3 pre-existing tests until Step 5 updates their fixtures — run the new test alone first to confirm it passes in isolation:
`uv run --no-sync pytest tests/test_local_data.py::test_build_local_minio_bt_payload_routes_bars_and_sctr_through_lake_api -v`

- [ ] **Step 5: Update the 3 pre-existing tests' fixtures**

`patched_reads` and the two tests that don't use it currently monkeypatch `local_data.read_pit` for all three of `equity_bars_1d_yahoo_adj`, `market_ref_bars_1d_yahoo_adj`, and `sctr_features`. Since the first and third now go through `lake_api`, update all three tests to monkeypatch `local_data.lake_api.read_bars`/`local_data.lake_api.read_features` for those two, keeping `local_data.read_pit` mocked only for `market_ref_bars_1d_yahoo_adj`.

Replace the `patched_reads` fixture:

```python
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

    def fake_read_bars(dataset, *, tickers, start, end, client=None):
        assert dataset == "equity_bars_1d_yahoo_adj"
        return bars

    def fake_read_features(dataset, *, tickers, as_of, client=None):
        assert dataset == "sctr_features"
        return sctr

    def fake_read_pit(bucket, dataset, **kwargs):
        if dataset == "market_ref_bars_1d_yahoo_adj":
            return spy_bars
        raise AssertionError(f"unexpected read_pit dataset requested: {dataset}")

    def fake_resolve_pit_sp500(trading_days, **kwargs):
        return {day: {"AAA", "BBB"} for day in trading_days}

    monkeypatch.setattr(local_data.lake_api, "read_bars", fake_read_bars)
    monkeypatch.setattr(local_data.lake_api, "read_features", fake_read_features)
    monkeypatch.setattr(local_data, "read_pit", fake_read_pit)
    monkeypatch.setattr(local_data, "resolve_pit_sp500", fake_resolve_pit_sp500)
    return tickers, dates
```

Replace `test_build_local_minio_bt_payload_marks_ineligible_names`'s monkeypatch block:

```python
def test_build_local_minio_bt_payload_marks_ineligible_names(monkeypatch):
    dates = [datetime(2024, 1, d, tzinfo=UTC) for d in range(1, 4)]
    tickers = ["AAA", "BBB"]
    bars = _bars(tickers, dates, {"AAA": [10.0, 11.0, 12.0], "BBB": [20.0, 21.0, 22.0]})
    spy_bars = _bars(["SPY"], dates, {"SPY": [100.0, 101.0, 102.0]})
    sctr = pd.DataFrame(
        [{"ticker": t, "event_time": d, "rank": 96.0} for t in tickers for d in dates]
    )

    monkeypatch.setattr(
        local_data.lake_api, "read_bars", lambda dataset, **kwargs: bars
    )
    monkeypatch.setattr(
        local_data.lake_api, "read_features", lambda dataset, **kwargs: sctr
    )
    monkeypatch.setattr(
        local_data,
        "read_pit",
        lambda bucket, dataset, **kwargs: spy_bars,
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
```

- [ ] **Step 6: Run all local_data tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_local_data.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Run the full test suite**

Run: `uv run --no-sync pytest -q`
Expected: PASS, no regressions. `test_local_lake.py` and `test_local_minio_source.py` are untouched by this task and should still pass unmodified.

- [ ] **Step 8: Commit**

```bash
git add backtester/local_data.py tests/test_local_data.py
git commit -m "feat: route equity bars and sctr features reads through lake_api"
```

---

## Manual verification (not part of CI)

After Task 4, with the real IMQuantFund API running at `http://localhost:8000` (confirmed live during design) and `QJ_LAKE_API_KEY` set to match IMQuantFund's `IMQF_API__LAKE_API_KEY`:

```bash
export QJ_LAKE_API_KEY=<value from IMQuantFund's .env IMQF_API__LAKE_API_KEY>
python -c "
from backtester.local_data import build_local_minio_bt_payload
payload = build_local_minio_bt_payload(instruments=['AAPL', 'MSFT'], start='2024-01-01', end='2024-03-01')
print(payload['summary'])
"
```

Confirm the summary's `instruments`/`dates` counts look sane and no exception is raised. Compare against a payload built before this change (same instruments/date range, prior commit) to confirm bars/sctr values match.
