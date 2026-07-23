# Quality-screened value composite — research spec

- **Status:** WIP (promoted 2026-07-23)
- **Family:** Fundamental value × quality combination
- **Promoted from backlog:** 2026-07-23, rank 1

## Hypothesis

Value composite (Improve, REVIEW 2026-07-22) showed a near-flat
full-period IR (-0.059, closest to zero of any trial in this loop) but a
decisive COVID-window failure (-10.17pts vs SPY, the largest crisis-
window gap of any trial in either direction) that matches value's
classic "value trap" failure mode: a stock can be cheap on trailing
earnings/book value not because the market is mispricing it, but because
the market is correctly pricing in real distress risk — a fast,
liquidity-driven panic like COVID is exactly the regime where trailing
fundamentals lag the market's forward-looking distress assessment the
most. The hypothesized fix is structural, not a re-tuned value
construction: screen out likely-distressed names with an independent
quality/profitability signal (`quality_features.gross_profitability` or
`roic_features.roic`) *before* ranking survivors on the same earnings-
yield/book-to-market composite Value composite already used, rather than
building a new blended score. If the mechanism is right, this should
close some of the COVID-window gap without giving up Value composite's
already-near-zero full-period IR or its mild cost-sweep decay (~2.3%,
the lowest of any trial) — the same "isolate one leg via a screen rather
than a blend" pattern that moved the ROIC + momentum family from
IR -0.2205 (v1, blended) through -0.0287 (v2, median screen) to +0.2216
(v3, top-third screen), though here the screen is a risk filter, not a
selection-quality filter, so the analogy to that family's own IR-only
motivation shouldn't be over-read (`knowledge.md`'s own v2 REVIEW lesson
is that IR improvement and regime protection can decouple — this spec
explicitly tracks both, not just IR, as success criteria per the
Verdict-worthy question this idea exists to answer).

## Data & universe

- `backtester.lake_api.read_features("value_features", ...)` — already
  live-probed at Value composite's IMPLEMENT (2026-07-22, PIT S&P 500,
  709 tickers): `eps` (0% null) and `book_value_per_share` (~16.9% null,
  fallback to earnings-yield-only when null, same as Value composite).
  `knowledge_time` genuinely spread across history (2009-2026), not
  bulk-clustered near "now".
- Quality/profitability screen signal — **open design choice, decide at
  IMPLEMENT, do not assume here**:
  - `quality_features.gross_profitability` — already live-probed
    (Quality composite IMPLEMENT 2026-07-20): null on ~50-58% of rows.
  - `roic_features.roic` — already live-probed (ROIC + momentum blend
    IMPLEMENT 2026-07-22): null on ~53.75% of rows, chained through
    `nopat`/`pretax_income`/`effective_tax_rate` nulling together.
  - Both have comparably high (~50-58%) null rates — neither is a
    clearly cleaner choice on coverage alone. Pick based on which
    column's null pattern overlaps least with `value_features`' own
    null pattern on a fresh joint probe at IMPLEMENT (a name null on
    both the value inputs and the screen input can't be evaluated
    either way and should just drop, but a screen signal that's
    disproportionately null exactly where value data is present would
    silently gut the eligible pool) — re-probe jointly, don't assume
    independence from either factor's marginal null rate alone.
- Universe: PIT S&P 500 (`backtester.local_lake.pit_sp500_ticker_universe`)
  — same choice as every prior trial in this loop.
- Date range: 2016-01-01 to present, matching Value composite's own
  range exactly, since this is evaluated as a direct variant of that
  trial, not a fresh design.

## Implementation notes

- Weight mode: portfolio rank-and-hold, same as `value_composite.py`.
  Nearest existing pattern is `strategies/value_composite.py` itself
  (`worktree-value-composite`, commit `4faac4d`) — reuse its
  `_fetch_market_data` override/graft pattern (still no generic
  research-tier-feature hook in `build_local_minio_bt_payload`,
  confirmed unchanged by every prior trial that needed one) and its
  cross-sectional z-score/nanmean value-factor combination unchanged.
- New step: before ranking on the value composite score, drop names
  below a quality/profitability threshold on the chosen screen signal
  (e.g. below-median, mirroring the ROIC + momentum family's
  screen-then-rank sequential-screen shape rather than a blended
  three-factor z-score, to keep the value-vs-quality mechanisms
  separable and the result interpretable) — exact cutoff is an
  IMPLEMENT-time decision; log the reasoning in this spec's
  Implementation notes once chosen, per this loop's standing discipline
  for every prior open threshold decision.
  Reconciling the screen fraction with `value_features`' own ~17% null
  rate on `book_value_per_share` matters here: a below-median quality
  cutoff before value-ranking will materially shrink the eligible pool
  each rebalance (both null-rate haircuts compound), so IMPLEMENT should
  check the resulting median pool size and eligibility count survives
  `min_universe`-style sanity checks Value composite already used —
  don't let a screen this aggressive collapse to a near-empty portfolio
  on some rebalance dates without noticing.
- Rebalance policy (`qj-config-helper`): quarterly (`BQE`), matching
  Value composite, unless IMPLEMENT's cadence probe argues otherwise.
- Position cap: equal-weight within the top quartile of the
  quality-screened survivors, capped at `max_position_size=0.10`, same
  as every prior fundamental composite in this loop.

## Evaluation plan

Written before the BACKTEST stage runs.

- Benchmark: `benchmark_symbol="SPY"`, same as every prior trial.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=36, test_months=12)`),
  matching Value composite's own choice for filing-cadence fundamental
  data. **Known blocker to check first**: re-bisect the standing lake
  API `read_bars`'s `end`/`read_features`'s `as_of` recency defect
  (`knowledge.md`) before committing to a full `WalkForwardEngine` run —
  9 consecutive trials have hit it; if unresolved, prefer
  `slice_diagnostics` mode (no `backtester_factory`, in-process fold
  slicing of the already-fetched full-period data) the way ROIC +
  momentum blend v3 did to unblock the gate for the first time in this
  loop's history, since this is also a fixed-rule strategy with no
  fitted/tuned parameters to refit per fold.
- `purge_days`/`embargo_pct` left at `WalkForwardConfig` defaults unless
  IMPLEMENT surfaces a reason to widen them.
- Deflated Sharpe / PBO: `n_trials=1` for this new "Fundamental value ×
  quality combination" family (first trial; distinct from both
  "Fundamental value" and "Fundamental quality" alone, and distinct from
  the "Fundamental × technical combination" family the ROIC + momentum
  trials belong to).
- Cost sweep: run per the mandatory gate; quarterly rebalance with a
  narrower eligible pool suggests low sensitivity (Value composite's own
  ~2.3% decay is the mildest of any trial so far), not assumed without
  running it — a materially smaller eligible pool each rebalance could
  in principle raise per-name turnover impact even at the same
  portfolio-level turnover rate, worth watching rather than assuming
  away.
- Regime evidence: **pre-registered directional prediction** (unlike
  Value composite's own no-prediction stance) — the specific hypothesis
  this trial exists to test is that the COVID-window gap narrows
  relative to Value composite's -10.17pts, since the quality screen is
  designed to exclude the distressed names driving that underperformance.
  A 2022-bear result close to Value composite's own +6.13pts would be
  consistent with the screen targeting crisis-specific distress risk
  rather than changing the strategy's general market exposure; a large
  move in the 2022 window either direction is itself informative and
  should be reported, not just the COVID comparison.

## Results

Not yet run — filled in at BACKTEST.

## Regime evidence

Not yet gathered — filled in at REVIEW.

## Verdict & lessons

Not yet decided — filled in at REVIEW.
