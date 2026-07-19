# Lake API client — swap MinIO bars/features reads for IMQuantFund's HTTP lake API

- **Status:** Approved, pending implementation plan.
- **Date:** 2026-07-18.

## Goal

IMQuantFund now exposes a read-only HTTP API (`/api/v1/lake/*`, doc:
`IMQuantFund/docs/superpowers/specs/2026-07-18-external-lake-data-api-design.md`)
specifically so external, read-only consumers like `quantjourney-bt` can pull
its curated, point-in-time-correct data without importing `imqf_*` packages
or touching MinIO/S3 credentials directly. That spec explicitly deferred
wiring a client into `quantjourney-bt` as "that project's own follow-up" —
this is that follow-up.

Today, `Backtester(source="minio")` reads four datasets straight out of
MinIO via `backtester/local_lake.py`'s `pyarrow.fs.S3FileSystem` +
`pyarrow.dataset` PIT-resolution logic: `equity_bars_1d_yahoo_adj`,
`market_ref_bars_1d_yahoo_adj`, `sctr_features`, and `index_membership`.
This change moves the two highest-volume, API-covered reads
(`equity_bars_1d_yahoo_adj`, `sctr_features`) onto the new HTTP API, and
keeps the other two on direct MinIO because the API has no equivalent for
them (see "Why not all four datasets" below).

## Why not all four datasets

Investigated and decided with the user before writing this design:

- **`market_ref_bars_1d_yahoo_adj`** (used for the SPY 200-day trend
  regime filter) is not in the API's bar-dataset allow-list at all
  (`_BAR_DATASETS = ("equity_bars_1d_yahoo_adj",)` in IMQuantFund's
  `packages/api/src/imqf_api/routers/lake.py`). No client-side workaround
  changes that; it stays on MinIO.
- **`index_membership`** (the raw PIT span table — `symbol, event_time,
  opt_out, index_name` — that `local_lake.resolve_pit_sp500` reads *once*
  and uses to reconstruct day-by-day S&P 500 eligibility across an entire
  backtest range) has no HTTP equivalent. `/api/v1/lake/universe/{name}`
  only returns a resolved ticker list for one `as_of` date, not the span
  table. Reproducing `resolve_pit_sp500`'s range reconstruction over HTTP
  would mean one API call per unique trading day — thousands of
  round-trips for a multi-year daily backtest — which is a strictly worse
  trade than keeping the one cheap, same-machine MinIO read. Decided:
  keep `index_membership` on MinIO; `read_universe` (below) is still
  implemented for future single-date lookups, just not used by
  `local_data.py`'s day-by-day eligibility path today.

## Architecture

### 1. `backtester/lake_api.py` — new HTTP client module

```python
def read_bars(
    dataset: str, *, tickers: list[str], start: date, end: date,
) -> pd.DataFrame: ...

def read_features(
    dataset: str, *, tickers: list[str], as_of: date,
) -> pd.DataFrame: ...

def read_universe(name: str, *, as_of: date) -> list[str]: ...
```

- `read_bars` → `GET {QJ_LAKE_API_URL}/api/v1/lake/bars/{dataset}?tickers=...&start=...&end=...`,
  header `X-API-Key: {QJ_LAKE_API_KEY}`. Response is
  `application/vnd.apache.parquet` bytes; parsed via
  `pd.read_parquet(io.BytesIO(response.content))`.
- `read_features` → same shape against `.../features/{dataset}?tickers=...&as_of=...`.
- `read_universe` → same auth, JSON response (`list[str]`), against
  `.../universe/{name}?as_of=...`.
- Synchronous `httpx.Client`, constructed fresh per call (via a context
  manager) when no client is injected, matching `local_lake.py`'s
  per-call `pyarrow.fs.S3FileSystem` construction pattern — request volumes
  are low, and this avoids lifetime-management complexity. Tests inject a
  mock client built on `httpx.MockTransport`; production callers omit it
  and get a fresh real client. The sync-only style matches existing code:
  `_fetch_market_data` in `backtester/mixins/sdk_client.py` calls
  `build_local_minio_bt_payload` without `await`, so the data-fetch path
  stays sync end-to-end.
- `httpx` is already a core dependency (`pyproject.toml`); no new
  dependency for this module. `local_lake.py`'s `pyarrow` extra is still
  required for the two datasets that remain on MinIO.

New env vars (quantjourney-bt-side names, following `local_lake.py`'s
existing `QJ_LOCAL_LAKE_*` precedent of not reusing IMQuantFund's own
`IMQF_*` names):

- `QJ_LAKE_API_URL` — default `http://localhost:8000`.
- `QJ_LAKE_API_KEY` — required, no default. Must match the value of
  IMQuantFund's `IMQF_API__LAKE_API_KEY`.

### 2. `backtester/local_data.py` — swap two reads

`build_local_minio_bt_payload` changes two of its four `read_pit` calls:

```python
# was: read_pit("processed", "equity_bars_1d_yahoo_adj", as_of=..., tickers=..., start=..., end=..., filesystem=..., root=...)
bars = lake_api.read_bars("equity_bars_1d_yahoo_adj", tickers=tickers, start=start, end=end)

# was: read_pit("research", "sctr_features", as_of=as_of, tickers=..., start=..., end=..., filesystem=..., root=...)
sctr = lake_api.read_features("sctr_features", tickers=tickers, as_of=as_of.date())
```

`sctr`'s `as_of` must be `build_local_minio_bt_payload`'s own `as_of`
parameter (default: `datetime.now(UTC)`, i.e. "whatever knowledge exists
right now") — **not** `end`. That preserves the original `read_pit` call's
exact semantic: a single knowledge-time cutoff shared across every read in
this function, independent of the backtest's own date window. Passing
`end` instead would silently change what "point-in-time" means for this
one dataset. See "Known behavior differences" below for why `bars` doesn't
get the same treatment.

Unchanged:

```python
spy_bars = read_pit("processed", "market_ref_bars_1d_yahoo_adj", ...)   # stays MinIO
membership_by_day = resolve_pit_sp500(trading_days, as_of=..., ...)      # stays MinIO
```

`filesystem`/`root` test-injection parameters on `build_local_minio_bt_payload`
stay as-is for the two MinIO-backed reads; the two HTTP-backed reads take
no such parameter (tests mock at the `httpx` transport layer instead — see
Testing).

`Backtester(source="minio")` keeps its name. It is still reading from "your
local IMQuantFund lake" — the transport underneath two of its four reads
changed, not the concept the `source` value names. No public API rename.

### 3. Data flow

```
Backtester(source="minio")
  -> local_data.build_local_minio_bt_payload
       -> lake_api.read_bars("equity_bars_1d_yahoo_adj", ...)   -> HTTP -> IMQuantFund packages/api
       -> lake_api.read_features("sctr_features", ...)          -> HTTP -> IMQuantFund packages/api
       -> local_lake.read_pit("market_ref_bars_1d_yahoo_adj", ...) -> MinIO (unchanged)
       -> local_lake.resolve_pit_sp500(...)                        -> MinIO (unchanged)
```

### Known behavior differences

- **Bars' knowledge-time cutoff changes.** IMQuantFund's
  `GET /api/v1/lake/bars/{dataset}` router hardcodes
  `pit_resolve(..., as_of=end)` server-side — the endpoint has no `as_of`
  query param at all, only `start`/`end`. The original direct-MinIO
  `read_pit` call used the function-level `as_of` (default: now) for bars
  too. In practice this means bars are now PIT-resolved as of the
  backtest's own end date rather than "as of today," so a knowledge
  revision landing after `end` but before "now" would now be excluded
  where it previously would have been included. This is imposed by the
  API's contract, not a client-side choice, and not worth a follow-up:
  revisions to already-published adjusted daily bars this late are not
  expected in practice, and the API spec's own design intentionally ties
  bars' PIT resolution to the query window it was built for
  (`quantjourney-bt` backtests over historical ranges — see that spec's
  "Endpoints" section). `sctr_features`, by contrast, keeps the original
  now-based cutoff exactly, since `/features/{dataset}` takes `as_of` as
  a caller-supplied parameter with no hardcoded value.

### Error handling

- Non-2xx HTTP responses raise `ValueError` with the request URL, status
  code, and response body — mirroring the existing informative-error
  style already used for auth failures in
  `backtester/mixins/sdk_client.py` (e.g. the 401/403/409 branches around
  `_get_sdk_client`), rather than letting a raw `httpx.HTTPStatusError`
  surface.
- A 401 specifically gets a message pointing at `QJ_LAKE_API_KEY` (missing
  or wrong), matching the existing pattern of pointing users at the
  specific env var to check.
- A 404 (unknown dataset/universe name) passes through the API's own
  response body, which already lists the valid names — no need to
  duplicate that list client-side.
- Zero matching rows is not an error: the API returns `200` with an
  empty-but-schema-valid Parquet file, and `pd.read_parquet` on that
  correctly returns an empty, correctly-typed DataFrame — same contract
  `local_data.py` already relies on from `local_lake.read_pit`.
- Malformed dates are prevented client-side by typing `start`/`end`/`as_of`
  as `datetime.date` in the function signatures (same as `local_lake.py`
  already does) rather than relying on the API's `422`.

## Testing plan

- `tests/test_lake_api.py`: unit tests against `httpx.MockTransport` (no
  new dependency — built into `httpx`, already a core dependency):
  - `read_bars` / `read_features` happy path: mock transport returns a
    small Parquet body (built in-test via `pyarrow`/`pandas`), assert the
    parsed DataFrame matches.
  - `read_universe` happy path: mock transport returns a JSON list.
  - 401 → `ValueError` mentioning `QJ_LAKE_API_KEY`.
  - 404 → `ValueError` including the API's own body text.
  - Empty result (200, empty-but-schema-valid Parquet) → empty DataFrame,
    not an exception.
  - Request shape: assert the `X-API-Key` header and query params
    (`tickers`, `start`/`end`/`as_of`) are sent correctly.
- `tests/test_local_minio_source.py` and `tests/test_local_lake.py`:
  unchanged — they cover `market_ref_bars_1d_yahoo_adj` and
  `index_membership`, which don't move.
- `tests/test_local_minio_source.py`'s existing
  `test_backtester_source_minio_uses_local_payload_and_skips_network`
  monkeypatches `build_local_minio_bt_payload` wholesale and never
  exercises the underlying reads — confirmed unaffected by this change,
  no update needed.
- `tests/test_local_data.py` **does** need updating: its `patched_reads`
  fixture and the other two tests monkeypatch `local_data.read_pit`
  directly with a `fake_read_pit` that branches on all three dataset
  names, including the two moving to HTTP
  (`equity_bars_1d_yahoo_adj`, `sctr_features`). Once
  `build_local_minio_bt_payload` calls `lake_api.read_bars`/
  `lake_api.read_features` for those two, the existing fixture's fake
  branches for them go dead and the real (network-calling) functions
  would run instead. Fix: monkeypatch `local_data.lake_api.read_bars`
  and `local_data.lake_api.read_features` for those two datasets
  alongside the existing `local_data.read_pit` monkeypatch (which keeps
  covering only `market_ref_bars_1d_yahoo_adj`), in all three tests in
  that file.
- One manual, non-CI integration check: run `Backtester(source="minio")`
  against the user's real, running IMQuantFund API
  (`http://localhost:8000`, confirmed live during this design) and confirm
  the resulting payload matches a MinIO-only run from before this change —
  same validation spirit as the original MinIO design's step 6, but a
  before/after comparison rather than a comparison against a separate
  materialized trial result.

## Out of scope for this change

- The research loop / `docs/research/` structure — separate spec, built
  after this one lands.
- Adding `market_ref_bars_1d_yahoo_adj` or a span-table endpoint to
  IMQuantFund's API — that's a change to a different repository and not
  requested here; both stay on MinIO.
- Any change to `strategies/sctr_momentum_regime_gated.py` or
  `strategies/validate_sctr_momentum_regime_gated.py` — they call
  `local_lake.pit_sp500_ticker_universe`/`read_pit` directly for
  validation against the original trial's materialized result; that
  reference-data read is orthogonal to the payload-building path this
  spec changes and is left untouched.
- Retrying/backoff, connection pooling tuning, or async conversion of the
  data-fetch path — out of scope; match existing sync behavior exactly.
