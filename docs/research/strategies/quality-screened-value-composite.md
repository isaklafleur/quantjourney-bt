# Quality-screened value composite — research spec

- **Status:** WIP (promoted 2026-07-23) — IMPLEMENT complete, next stage BACKTEST
- **Family:** Fundamental value × quality combination
- **Promoted from backlog:** 2026-07-23, rank 1
- **Code:** `strategies/quality_screened_value_composite.py` +
  `strategies/_smoke_quality_screened_value_composite.py` (scratch smoke
  test), branch/worktree `worktree-quality-screened-value-composite`
  (`.claude/worktrees/quality-screened-value-composite`), commit `1509fe8`.

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
- Quality/profitability screen signal — **resolved at IMPLEMENT
  (2026-07-23) via a fresh joint-null probe against `value_features`,
  PIT S&P 500, 709-ticker universe**: `roic_features.roic` (null
  ~49.5% marginal) chosen over `quality_features.gross_profitability`
  (null ~55.0% marginal) — comparable marginal null rates as the spec
  anticipated, but their overlap with `value_features.book_value_per_share`-
  populated names differs materially: 369 tickers have both `roic` and
  `book_value_per_share` data vs. only 256 for `gross_profitability`, and
  only 168 bvps-populated tickers lack `roic` entirely vs. 281 that lack
  `gross_profitability`. `roic` preserves materially more of the
  value-eligible pool, confirming the spec's concern that marginal null
  rate alone doesn't predict joint coverage.
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
- New step (resolved at IMPLEMENT): before ranking on the value
  composite score, drop names below a **median (top-half) ROIC**
  threshold — matches the ROIC + momentum family's own v2 (median-split)
  starting point rather than v3's tightened top-third, since this is a
  new family's first trial, not an iteration on an already-passing gate.
  `MIN_ELIGIBLE_FOR_SCREEN=16` (so the median split leaves >= 8
  survivors) and `MIN_SURVIVORS_FOR_QUARTILE=8` (so the value-score top
  quartile of survivors has >= 2 names) — same shape as
  `roic_momentum_v3_tighter_roic_screen.py`'s thresholds. Verified via
  the committed smoke test (150-ticker PIT S&P 500 subset, 2025-01-01 to
  present): 386/386 trading days produced a nonempty selection (up to 12
  names/day), so the screen-then-rank sequence does not collapse to an
  empty portfolio in practice — the full 709-ticker BACKTEST run will
  confirm this holds across the full 2016-2026 sample.
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
