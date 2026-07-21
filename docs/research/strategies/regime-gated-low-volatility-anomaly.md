# Regime-gated low-volatility anomaly — research spec

- **Status:** WIP (SPEC written; branch created, no code yet)
- **Family:** Technical / risk-based, regime-conditional
- **Promoted from backlog:** 2026-07-21, rank 1
- **Code:** none yet. Research branch/worktree
  `worktree-regime-gated-low-vol` created via the native worktree tool
  (same reason as `worktree-low-vol-anomaly`/`worktree-quality-composite`:
  this session's Bash tool cannot be relied on to approve ref-mutating git
  commands unattended). Branched from `worktree-low-vol-anomaly`'s base
  (`main`), not from `worktree-low-vol-anomaly` itself — the two branches
  are independent; IMPLEMENT should copy/adapt
  `strategies/low_volatility_anomaly.py`'s vol-ranking code by hand rather
  than merging branches. Next stage: SPEC → IMPLEMENT.

## Hypothesis

Direct follow-up to Low-volatility anomaly (Improve verdict, REVIEW
2026-07-21; see `low-volatility-anomaly.md` and `knowledge.md`'s regime
evidence entry) — not a new hypothesis, a mechanism refinement motivated
by that trial's own results. The ungated version's full-period IR gate
failed decisively (-0.41 vs SPY) while showing genuine downside
protection in both available crisis windows (COVID +3.09pts, 2022 bear
+11.74pts): a long bull stretch between crises drags on absolute return
even though the risk-based mechanism (leverage-constrained investors
bidding up high-beta names; lottery-preference demand for volatile
names) works exactly as predicted during drawdowns.

The proposed fix is structural, not a curve-fit parameter tweak: only
hold the low-vol quintile when a regime signal indicates elevated
market risk; default to full-market (or cash) exposure otherwise, so
the strategy stops paying the low-vol tilt's opportunity cost during
calm bull stretches and only takes the defensive tilt when the crisis
protection is actually likely to matter. Same structural pattern as the
already-shipped `strategies/sctr_momentum_regime_gated.py` (binary
SPY-vs-200d-SMA trend gate), applied to a different underlying signal.

## Data & universe

- `backtester.lake_api.read_features("technical_features", tickers=...,
  as_of=datetime.now(UTC).date())` — `vol_60d` column, reused as-is from
  `strategies/low_volatility_anomaly.py` (confirmed live, pivoted on
  `event_time` not knowledge_time — see that file's module docstring).
- Regime signal: PIT-resolved SPY daily bars via
  `backtester.local_lake.read_pit("processed", "market_ref_bars_1d_yahoo_adj",
  tickers=["SPY"])` (same source `sctr_momentum_regime_gated.py` uses for
  its 200-day SMA trend gate) or, as an alternative construction to
  evaluate at IMPLEMENT, a realized-vol-level regime signal derived from
  `technical_features` itself (e.g. cross-sectional median/average
  `vol_60d`, or SPY's own trailing vol) — the backlog note flags the
  choice of regime signal and threshold as the real researcher-degrees-
  of-freedom risk here, so prefer the already-shipped SPY-trend
  construction unless a clear reason favors the vol-level alternative.
- Universe: PIT S&P 500 membership via
  `backtester.local_lake.pit_sp500_ticker_universe` — same choice as
  both prior trials.
- Price/eligibility: `backtester.lake_api.read_bars("equity_bars_1d_yahoo_adj", ...)`.
- Date range: 2016-01-01 to present — same window as both prior trials,
  for direct comparability against the ungated version's own numbers.

## Implementation notes

- Weight mode (per `qj-strategy-ideas`): cross-sectional rank-and-hold,
  reusing `strategies/low_volatility_anomaly.py`'s `_vol_panel`/quintile-
  selection logic (`_compute_signals`, the eligible-score/quintile-cutoff
  block of `_compute_weights`) essentially unchanged — the new work is
  the regime gate layered on top, not the underlying signal.
- Regime gate mechanics: model directly on
  `sctr_momentum_regime_gated.py`'s `_build_regime_gated_weights`
  pattern — a `trend_down`/`elevated_risk` dates-indexed Series computed
  once, then on each rebalance date either run the existing lowest-vol-
  quintile selection (gate active / elevated risk) or zero out
  everything for full-market-or-cash exposure (gate inactive / calm
  regime). Needs an explicit decision at IMPLEMENT: "full-market" default
  (e.g. equal-weight the whole eligible PIT universe, or just hold SPY
  directly) vs. plain cash — the backlog idea says "full-market/cash
  exposure", leaving this as an open implementation choice, not decided
  here; picking directly-hold-SPY as the default is the simplest,
  lowest-researcher-degrees-of-freedom option and should be preferred
  unless it proves awkward mechanically.
- Regime signal candidate (primary): binary gate on whether PIT-resolved
  SPY closes below its own 200-day SMA — identical construction to
  `sctr_momentum_regime_gated.py`'s trend gate, just reused as the
  "elevated risk" signal instead of a "pause new entries" signal. This
  keeps the new researcher degree of freedom (which signal, what
  threshold) minimal by copying an already-shipped, already-reviewed
  choice rather than inventing a new one.
- Monthly rebalance (`RebalancePolicy(frequency="BME")`), matching the
  ungated version's cadence — the regime gate is evaluated at the same
  rebalance frequency as the vol-quintile signal, not on a separate/finer
  schedule, to avoid adding an undisclosed second tunable cadence.
- Selection when gated-on: identical to the ungated version — lowest-vol
  quintile, equal-weighted, `max_position_size=0.10`.
- Missing-value handling: reuse `MISSING_VOL_SENTINEL` pattern from
  `low_volatility_anomaly.py` for the same all-finite-signal constraint.

## Evaluation plan

Written before the BACKTEST stage runs.

- Benchmark: `benchmark_symbol="SPY"` — same as both prior trials.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=24, test_months=6)`)
  — same as the ungated Low-volatility anomaly trial, for comparability;
  expect the same lake API `read_bars`/`read_features` recency defect
  (`knowledge.md`) to block most folds again — re-bisect before spending
  a full run, per the precedent set in both prior trials' BACKTEST
  stages, rather than assume it's fixed.
- `purge_days`/`embargo_pct`: `WalkForwardConfig` defaults, unless
  IMPLEMENT surfaces a reason to widen them.
- Deflated Sharpe / PBO: `n_trials` for this family counted from
  `trial-registry.md` — this is the 2nd row in the "Technical /
  risk-based" family (after the ungated Low-volatility anomaly trial),
  so `n_trials=2` for this family's DSR calculation, not 1.
- Cost sweep: mandatory regardless of turnover; the regime gate's own
  on/off switching adds a source of turnover distinct from the
  vol-quintile roster churn (full liquidation/re-entry around each gate
  flip) — worth checking whether this makes the strategy more
  cost-sensitive than the ungated version's already-370%-turnover
  result, not assumed either way.
- Regime evidence: pre-registered expectation — since the strategy is
  *designed* to be defensive only during elevated-risk regimes, the
  crisis-analysis breakdown should show the gate active (and the
  low-vol tilt held) through both COVID and the 2022 bear market; if the
  SPY-200d-SMA gate lags a fast crash (as trend-following gates
  generally do) and misses part of a drawdown, that's a concrete,
  bisectable thing to check and report, not assume away.
- Direct comparison baseline: the ungated Low-volatility anomaly's own
  full-period IR (-0.41) and both crisis-window numbers (+3.09/+11.74pts
  vs SPY) are the natural bar this variant needs to beat on the
  full-period IR gate while preserving (not eroding) the crisis
  protection — that's the whole point of the regime-gate mechanism
  change.

## Results

_Not yet run — filled in at BACKTEST._

## Regime evidence

_Filled in at REVIEW._

## Verdict & lessons

_Filled in at REVIEW._
