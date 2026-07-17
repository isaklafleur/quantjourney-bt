# Local MinIO data source + SCTR momentum regime-gated strategy port

- **Status:** Approved, pending implementation plan.
- **Date:** 2026-07-16.

## Goal

Today `Backtester` only fetches market data from the QuantJourney Cloud API
(`/bt/prepare`). Add a second, local data source — the user's own MinIO
instance (an S3-compatible object store already populated by a separate
project, IMQuantFund) — selectable via the existing `source` parameter, and
use it to run a faithful port of the "SCTR momentum, regime-gated (binary
trend pause)" strategy
(`docs/research/strategies/sctr-momentum-regime-gated.md` in that other
project) through quantjourney-bt's own engine.

This is a **port**, not a literal re-run: quantjourney-bt's `Backtester` is
architecturally different from the engine that produced the original result
(vectorized `_compute_signals`/`_compute_weights` panels + configurable
rebalance/cost/slippage models here, vs. a day-by-day polars loop with an
explicit bps-of-turnover cost formula there). Numbers are expected to be
close, not bit-for-bit identical — see "Known fidelity gaps" below.

Scope decided with the user:
- **Faithful port, validated against the original.** Implement the actual
  strategy rules (not a simplified stand-in), then compare the resulting
  return series against the original trial's already-materialized result.
- **Full PIT S&P 500 membership**, not a fixed/current ticker list —
  reconstructed from MinIO's `index_membership` dataset, matching what the
  original trial traded.

## Data available (confirmed present in the user's local MinIO)

Verified via a direct read-only Polars scan against
`http://localhost:9000` (credentials from IMQuantFund's `.env`,
`IMQF_STORAGE__*`) before writing this design:

| Bucket | Dataset | Rows | Purpose |
|---|---|---|---|
| `processed` | `equity_bars_1d_yahoo_adj` | ~12.0M | Adjusted OHLCV for book P&L |
| `processed` | `market_ref_bars_1d_yahoo_adj` | ~104k | SPY (and other refs) for trend regime |
| `research` | `sctr_features` | ~4.5M | Precomputed SCTR `rank` (0-100) |
| `processed` | `index_membership` | ~10k | PIT S&P 500 roster (symbol, event_time, opt_out) |
| `analytics` | `sctr_momentum_regime_gated_pnl` | — | The original trial's materialized result, used for validation |

All datasets share the same on-disk convention as `imqf_data.lake`:
`s3://{bucket}/dataset={name}/**/*.parquet`, bitemporal (`event_time` +
`knowledge_time`), append-only.

`equity_bars_1d_yahoo_adj` / `market_ref_bars_1d_yahoo_adj` schema:
`event_time, open, high, low, close, volume, ticker, knowledge_time,
source, dataset`. `close` is already Yahoo-adjusted (no separate
`adj_close` column at the source).

`sctr_features` schema: `ticker, event_time, knowledge_time, close,
pct_above_ema200, roc125, pct_above_ema50, roc20, ppo_slope, rsi14,
indicator_score, rank, dataset`. Only `rank` is needed by this strategy.

`index_membership` schema: `symbol, name, opt_out, index_name, event_time,
knowledge_time, source, dataset`. Exact `index_name` values (to isolate
S&P 500 specifically) must be inspected during implementation before the
membership filter is written — a concrete pre-implementation check, not an
open design question.

## Architecture

### 1. `backtester/local_lake.py` — MinIO reader

```python
def read_pit(
    bucket: str,
    dataset: str,
    *,
    as_of: datetime,
    tickers: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame: ...
```

Reads `s3://{bucket}/dataset={dataset}/**/*.parquet` via
`pyarrow.fs.S3FileSystem` + `pyarrow.dataset` (endpoint/credentials from new
env vars below), pushes down `ticker`/`event_time` filters at the Arrow
level, then PIT-resolves in pandas: filter `knowledge_time <= as_of`, sort
by `knowledge_time` descending, `drop_duplicates(["ticker", "event_time"],
keep="first")`. This is a direct pandas port of
`imqf_data.lake.pit_resolve`, kept independent of that private package —
quantjourney-bt is a separately published repo and must not depend on it.

`pyarrow` is added as a new optional extra
(`quantjourney-bt[minio]`), lazy-imported only inside this module, so it
adds no weight for users who never touch this feature. No `boto3` — reads
only, and `pyarrow.fs.S3FileSystem` talks S3 natively against MinIO with an
endpoint override.

New env vars (quantjourney-bt's own names, not IMQuantFund's
`IMQF_STORAGE__*`, so the feature is reusable against anyone's
similarly-laid-out S3/MinIO lake):
- `QJ_LOCAL_LAKE_ENDPOINT_URL`
- `QJ_LOCAL_LAKE_ACCESS_KEY`
- `QJ_LOCAL_LAKE_SECRET_KEY`

### 2. Universe reconstruction

`resolve_pit_sp500(trading_days: list[date]) -> dict[date, set[str]]` in
the same module. Reads `index_membership` PIT-resolved as of "now", then
for each trading day returns the set of `symbol`s where `event_time <= day`
and (`opt_out` is null or `opt_out > day`). Feeds the `eligibility` field
in step 3.

### 3. `backtester/local_data.py` — payload adapter

`build_local_minio_bt_payload(instruments, start, end, initial_nav=...) ->
dict` mirrors `sample_data.py::build_sample_bt_payload`'s return shape
exactly (`session_id, dataset_id, instrument_names, prices, metrics,
parameters, nav, summary`), so the untouched `_process_market_data()` in
`core.py` consumes it identically to a live API response or the sample-data
path. Fields:

- **`prices`**: `(ticker, field)` MultiIndex panel with
  `open, high, low, close, adj_close, volume`; `adj_close` = `close` since
  the source is already Yahoo-adjusted.
- **`parameters`**: the 7 fields `InstrumentData` requires
  (`exchange, units, eligibility, active, forecasts, is_trading_day,
  day_type`, from `backtester/portfolio/schemas.py`'s
  `REQUIRED_PARAMETER_FIELDS`) plus two extra fields the strategy reads —
  `sctr_rank` (from `sctr_features.rank`, forward-filled/0 outside a
  ticker's covered range) and `spy_trend_down` (1 on days PIT-resolved SPY
  closes below its 200-day SMA, computed here from
  `market_ref_bars_1d_yahoo_adj`, broadcast identically across every
  ticker column since it's a market-wide signal). `eligibility` carries the
  PIT S&P 500 mask from step 2 (1/0, never null — required by
  `validate_parameters_frame`).
- **`metrics`** / **`nav`**: lightweight computed placeholders, same
  trivial pandas calc `sample_data.py` already uses (returns, rolling vol,
  drawdown / a flat NAV series scaled by `initial_capital`). Confirmed by
  reading `core.py::_process_market_data` and `PortfolioData` that these
  are schema/initial-state scaffolding only — the engine recomputes actual
  NAV and returns from `weights` × forward returns during the real run, so
  placeholder values here are safe and never leak into strategy logic or
  reported performance.

### 4. Wiring into `Backtester`

One new branch in `backtester/mixins/sdk_client.py::_fetch_market_data()`,
sibling to the existing `self._source == "sample"` branch:

```python
elif self._source == "minio":
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
    return
```

No network call, no credentials required, no changes to
`_process_market_data()`, auth, or any other engine internals. Usage:
`Backtester(source="minio", instruments=[...], ...)`.

### 5. Strategy port — `strategies/sctr_momentum_regime_gated.py`

`class SCTRMomentumRegimeGated(Backtester)`, rules taken directly from the
spec doc:

- **Entry:** SCTR `rank >= 95`. **Hold:** `rank >= 85`. **Minimum hold:**
  90 trading days, overridable only by the gate. **Max positions:** 20,
  equal-weight. Incumbent-priority selection each day: incumbents passing
  the hold threshold (or still under min-hold) keep their slot; remaining
  slots go to the best new entry-eligible challengers by rank — a direct
  pandas port of `imqf_backtest.portfolio.build_daily_portfolios`'s
  algorithm (day-by-day stateful loop, not a vectorized re-rank, since
  incumbency has to persist across days).
- **Gate:** on any day `parameters[(ticker, "spy_trend_down")] == 1`,
  force-liquidate every held name and take no new entries that day,
  overriding min-hold; re-entry is immediate and automatic the first day
  the flag clears — no added hysteresis, matching the spec.
- **Eligibility:** only tickers with `parameters[(ticker, "eligibility")]
  == 1` that day are candidates for entry or continued holding.
- **Costs:** approximated via quantjourney-bt's existing commission/
  weight-cost-model configuration (`backtester/execution/`) to match the
  original's flat 10bps round-trip cost. The target behavior — 10bps of
  turnover, symmetric on entry and exit — is fixed by this design; which
  specific existing class implements it is an implementation-time lookup
  against `backtester/execution/`, not an open design decision.
- **Rebalance policy:** daily (`RebalancePolicy(frequency="daily")` or
  equivalent), matching "daily evaluation" in the spec.
- **Instruments passed to `Backtester.__init__`:** the union of every
  ticker that was PIT-eligible at any point in `[2016-01-01, today]` — the
  day-by-day loop then respects `eligibility` per day, so ineligible
  tickers are simply never selected, not physically absent from the panel.

### 6. Validation against the original

A short script/report step reads `analytics/sctr_momentum_regime_gated_pnl`
via the same `read_pit` helper and compares its `net_return` series against
quantjourney-bt's own result: Pearson correlation, and deltas on Sharpe,
CAGR, and max drawdown. Exact match is not the bar (see "Known fidelity
gaps"); high correlation and directionally similar risk metrics are.

## Testing plan

- Unit tests for `local_lake.read_pit`'s PIT-resolution logic (bitemporal
  duplicate resolution, `as_of` filtering) against small synthetic parquet
  fixtures — no live MinIO dependency for CI.
- Unit tests for `resolve_pit_sp500`'s day-by-day membership logic against
  a small synthetic `index_membership` fixture (add/remove/re-add cases).
- Unit test for `SCTRMomentumRegimeGated`'s day-by-day weight loop against
  a small synthetic panel covering: entry, hold-via-hysteresis, min-hold
  override, gate force-liquidation, gate re-entry, and the 20-slot cap —
  mirroring the scenarios already implicitly covered by
  `imqf_backtest.portfolio`'s own design notes.
- One integration run against the user's real local MinIO (manual, not
  CI — requires their running instance) producing the validation report
  from step 6.

## Known fidelity gaps (surfaced honestly, not hidden)

- Turnover-cost mechanics differ structurally between the two engines
  (quantjourney-bt's commission/slippage/weight-cost-model stack vs. the
  source project's explicit `turnover * cost_bps / 10_000` formula), so
  net-return-level parity is expected to be close, not exact.
- The two engines' rebalance/fill timing conventions may not line up
  exactly day-for-day even at "daily" frequency; the validation step's
  correlation coefficient is the intended way to detect if this drifts
  further than expected, not an a priori guarantee of a specific number.

## Out of scope for this change

- Walk-forward windows, deflated Sharpe, cost sweeps, and the other
  registry-mandatory evaluation gates from the original spec doc — this
  port targets a working, validated backtest run in quantjourney-bt, not a
  full re-certification against that project's registry process.
- Any modification to the two files the user pointed at as reference
  (`docs/research/strategies/sctr-momentum-regime-gated.md` and
  `orchestration/assets/sctr_momentum_regime_gated.py` in the IMQuantFund
  project) — read-only context, per the user's original instruction.
- Writing to MinIO — this feature is read-only.
