# ROIC + momentum blend v3: tighter ROIC screen — research spec

- **Status:** REVIEW complete (2026-07-23). **Verdict: Ship.** Merged into
  `main` as `strategies/roic_momentum_v3_tighter_roic_screen.py`.
- **Family:** Fundamental × technical combination (v3 of ROIC + momentum
  blend — same sequential-screen methodology as v2, tighter ROIC cutoff)
- **Promoted from backlog:** 2026-07-23, rank 1

## Hypothesis

Direct follow-up to ROIC + momentum blend v2: sequential screen (Improve,
REVIEW 2026-07-23, `docs/research/strategies/roic-momentum-sequential-screen.md`,
branch `worktree-roic-momentum-v2`, parked not merged). Across two
methodology iterations on the same ROIC/`ret_60d` factor pair, the
mandatory IR-vs-benchmark gate has improved monotonically and
substantially: v1's blended z-score scored IR -0.2205; v2's sequential
screen (top-half-by-ROIC filter, then rank survivors by `ret_60d`) scored
IR -0.0287 — an order of magnitude closer to zero, and the closest of
any trial in this loop (surpassing Value composite's -0.059).

v2's own REVIEW read the IR improvement as most plausibly driven by
better stock selection *within* the ROIC-qualified pool, not by
strengthened ROIC-linked defensiveness (regime evidence actually
weakened v1 → v2: COVID +1.82pts → -0.83pts, 2022 bear +4.51pts →
+3.52pts). If that read is correct — a purer/higher-ROIC survivor pool
produces better full-period risk-adjusted selection, independent of the
regime-protection story — then tightening the ROIC screen further should
continue moving the IR gate toward (or across) zero, since it further
narrows the momentum-ranking pool to progressively higher-quality names.

v3 tests this directly: same two-step sequential screen as v2, but the
first-stage ROIC filter becomes a **top-third** cutoff instead of v2's
median (top-half) split. Everything else — data, universe, rebalance
cadence, momentum ranking on survivors, position sizing — is unchanged,
consistent with this loop's "one variable at a time" discipline for
Improve follow-ups (PEAD's/Value composite's/v2's own precedent).

Two outcomes are both informative and neither is a "failure" of the
idea: (a) the IR-improvement trend continues or crosses zero, supporting
the "purer ROIC pool → better selection" read; or (b) the trend
flattens/reverses, which would instead suggest v1→v2's improvement was
closer to a one-time methodology-shape effect (blend → screen) than a
continuously-exploitable "tighter is better" gradient — worth knowing
either way before proposing a v4.

## Data & universe

Identical to v1/v2 (`roic-momentum-blend.md` / `roic-momentum-sequential-screen.md`)
— no new data prerequisite; both datasets already live-probed and
confirmed across those two trials' IMPLEMENT stages. Restated here
rather than re-probed, per the loop's now-standing practice for direct
same-family follow-ups; a fresh live check still happens at this v3's
own IMPLEMENT stage if anything looks off.

- `roic_features` via `backtester.lake_api.read_features` — `roic`
  (NOPAT / Invested Capital) null on ~53.75% of rows; `knowledge_time`
  genuinely spread 2009-2026 (fiscal-filing-anchored).
- `technical_features.ret_60d` via the same `read_features` path — null
  on <1% of rows; `knowledge_time` bulk-clustered near "now" (recent-
  backfill artifact) — pivot on `event_time`, not knowledge_time-forward-
  filled, per the standing `technical_features` lesson in `knowledge.md`.
- Universe: PIT S&P 500 membership (`pit_sp500_ticker_universe`), full
  709-ticker universe — the shared-engine delisted-name ledger bug (fixed
  on `main`, commit `a44a703`) needs no workaround, same as v2.
- Date range: 2016-01-01 to present, matching every prior trial.

## Implementation notes

- Weight mode (per `qj-strategy-ideas`): portfolio rank-and-hold, same as
  every strategy in this loop so far.
- Nearest existing pattern: `strategies/roic_momentum_sequential_screen.py`
  (v2) itself — same two-leg data-fetch plumbing, same sequential-screen
  shape. The only design change under test is the first-stage screen
  threshold: **top-third by ROIC** (approximately the 67th percentile
  cutoff among eligible names) instead of v2's median (50th percentile)
  split. Rank survivors by `ret_60d` (highest first) and take the top
  quartile *of the tightened screened subset* as the long book — same
  second-stage logic as v2, unchanged.
- Rebalance policy (`qj-config-helper`): monthly
  (`RebalancePolicy(frequency="BME")`) — unchanged from v1/v2.
- Position cap: equal-weight within the final selected set, capped at
  `max_position_size=0.10`, same as every prior composite.
- Missing-value handling: unchanged from v2 — a name missing `roic`
  cannot pass the screen (excluded, not defaulted), a name missing
  `ret_60d` cannot be ranked among survivors (excluded).
- **Eligibility-count thresholds (resolved at IMPLEMENT):** raised
  `MIN_ELIGIBLE_FOR_SCREEN` from v2's 16 to **24**, so a top-third split
  still leaves >= 8 survivors (matching v2's own post-split survivor
  floor exactly, rather than compounding a second threshold change).
  `MIN_SURVIVORS_FOR_QUARTILE` stays at v2's **8** unchanged, so the
  second-stage logic is byte-for-byte identical to v2 — only the
  first-stage cutoff and its supporting eligible-count floor changed.
  Chose the spec's first suggested option (raise
  `MIN_ELIGIBLE_FOR_SCREEN`) over lowering `MIN_SURVIVORS_FOR_QUARTILE`,
  to keep the momentum-ranking step's own minimum-survivor bar consistent
  across v2/v3 for a cleaner comparison. Smoke-tested on 40 tickers
  (2024-01-02→present, `_smoke_roic_momentum_v3.py`): all 638 dates
  produced a non-empty selection (up to 3 names/day at this small
  sample size), all weights/signals finite, row sums <= the 0.10 cap —
  confirm at BACKTEST how many days/rebalances the tighter screen leaves
  the book empty on the full 709-ticker universe relative to v2,
  particularly in early years or periods of higher `roic` nullness.

## Evaluation plan

Written before the BACKTEST stage runs. Unchanged from v1/v2 except the
family trial count.

- Benchmark: `benchmark_symbol="SPY"`, same lazy benchmark as every prior
  trial in this loop.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=24, test_months=6)`)
  — same as v1/v2. **Known blocker to check first**: `knowledge.md`
  documents the still-unresolved lake API recency defect (`read_bars`'s
  `end` / `read_features`'s `as_of` return zero rows outside ~last 2-3
  weeks of wall-clock time) — re-bisect at BACKTEST time per the
  standing lesson (8 consecutive trials have now confirmed it unchanged;
  don't assume fixed without checking).
- `purge_days`/`embargo_pct` left at `WalkForwardConfig` defaults unless
  IMPLEMENT surfaces a reason to widen them.
- Deflated Sharpe / PBO: `n_trials=3` for the "Fundamental × technical
  combination" family — this is the third trial (v1, v2 count as the
  first two), counted honestly per the registry's own rows for this
  family.
- Cost sweep: run per the mandatory gate. A further-narrowed survivor
  pool per rebalance could plausibly increase turnover/cost sensitivity
  versus v2's ~14.24% decay (0-20bps) if the tighter screen churns names
  in/out of the top-third bucket more often — measure directly, don't
  assume it matches.
- Regime evidence: directional prediction — since v2's regime protection
  already weakened relative to v1 despite the IR improving (the two axes
  are decoupled, per `knowledge.md`), no strong a-priori expectation that
  tightening further will restore v1's crisis protection. Record what
  actually happens without forcing the result to match either trial.

## Results

Full 709-ticker PIT universe, 2016-01-04→2026-07-21, `source="minio"`,
monthly (BME) rebalance, `Backtester(source="minio")`.

- **Primary run (10bps cost):** Sharpe 0.92, CAGR 17.16%, Total Return
  430.90%, Max Drawdown -35.80%, Annualized Volatility 19.36%, Annualized
  Turnover 637.25% (127 rebalances). Highest absolute Sharpe of any trial
  in this loop so far.
- **Mandatory IR-vs-benchmark gate: PASS** (first trial in this loop to
  clear it) — IR **+0.2216**, active return (annualized, geometric)
  +2.13%/yr, cumulative excess return +93.01pts vs SPY, tracking error
  (ann.) 9.60%, computed via `backtester.engines.benchmark.active_return`/
  `excess_return` against `SPY` daily returns read from
  `backtester.local_lake.read_pit("processed", "market_ref_bars_1d_yahoo_adj", ...)`.
  Note: `backtester.lake_api.read_bars("equity_bars_1d_yahoo_adj", tickers=["SPY"], ...)`
  returns **zero rows for SPY specifically** (confirmed via direct probe —
  SPY is simply not served by that HTTP dataset, unlike the per-ticker S&P
  500 constituents; AAPL over the same window returns rows fine) — this is
  a different failure mode from the already-documented recency defect and
  is why every prior trial's benchmark fetch must have used
  `market_ref_bars_1d_yahoo_adj` via `local_lake`, not `lake_api.read_bars`,
  for the benchmark leg specifically. Continues the monotonic IR-gate
  improvement trend across all three iterations of this family: v1
  -0.2205 → v2 -0.0287 → v3 **+0.2216**, crossing zero as the spec's
  pre-registered "purer ROIC pool → better selection" hypothesis
  predicted.
- **Mandatory walk-forward robustness gate: completed, not blocked** —
  first walk-forward result of substance in this loop's history (8
  consecutive prior trials were BLOCKED by the lake API `end`/`as_of`
  recency defect). Ran `WalkForwardEngine(config=WalkForwardConfig(scheme="rolling",
  train_months=24, test_months=6))` with **no `backtester_factory`**, i.e.
  `slice_diagnostics` mode: it slices the *already-fetched* full-period
  `portfolio_data` into IS/OOS windows entirely in-process, never touching
  the lake API again — sidestepping the recency defect completely rather
  than working around it. This is the methodologically correct choice
  here, not just a workaround: this strategy has no fitted/optimized
  parameters to refit per fold (the ROIC-tertile/momentum-quartile
  thresholds are fixed constants, not estimated from training data), so
  `per_fold_refit` mode would re-run identical fixed logic on each fold
  and add nothing a plain slice can't already show. Result: 18 rolling
  24mo/6mo folds, composite IS-slice Sharpe 0.81 [90% CI 0.31, 1.35],
  Sharpe decay **-0.078/fold** (declining trend flagged by the engine's
  own diagnostics), 4/18 folds with negative OOS-slice Sharpe, overfit
  ratio >2.5 in several folds (driven by near-zero IS Sharpe in those
  folds' denominators, not necessarily a distinct decay signal). Read
  as diagnostic evidence of temporal consistency, not a classic
  overfitting check (no optimizer/trial population exists for this
  fixed-rule strategy) — engine's own output labels this explicitly
  ("metrics are computed from a full-period NAV; pass backtester_factory
  for per-fold refit").
- **Deflated Sharpe: 0.9966** (n_trials=3 for the "Fundamental × technical
  combination" family — v1, v2, v3, counted honestly per
  `trial-registry.md`), computed via
  `backtester.walkforward.statistics.deflated_sharpe.deflated_sharpe`
  directly (not via the WF engine, since slice-diagnostics mode reports
  DSR as n/a — "not meaningful without independent trials"), using daily
  per-period Sharpes for all three family members (v1 0.7450 ann., v2
  0.7788 ann., both converted to daily via /√252; v3 computed directly
  from `equity_curve.csv`'s daily returns: 0.0578 daily, skew -0.582,
  kurtosis 13.53 raw). **PASS**, well above the 0.95 "robust" threshold.
- **Overfit probability (PBO): N/A** — `probability_of_backtest_overfitting`
  is deprecated in this codebase and always returns `nan` (fold-level
  Sharpes can't yield a real CSCV PBO); no optimizer/tuned-parameter
  population exists for this fixed-rule strategy family, same as every
  prior trial in this loop.
- **Mandatory cost-sweep gate: PASS**, mildest decay of the ROIC family
  and second-mildest of any trial in this loop (after Value composite's
  ~2.3%) — Sharpe 0.97→0.94→0.92→0.87 across 0/5/10/20bps (~10.3%
  relative decay), vs. v1's ~14.1% and v2's ~14.24%. Annualized turnover
  unchanged by cost level (637.25%, cost model doesn't affect the
  screen's own trading decisions).
- **Regime evidence (diagnostic):** mixed, milder than v2's in both
  directions — COVID crash (2020-02-19→2020-03-23) strategy -35.80% vs
  SPY -33.72% (**-2.08pts**, underperformed), 2022 bear market
  (2022-01-03→2022-10-12) strategy -22.22% vs SPY -24.50% (**+2.27pts**,
  outperformed). Both magnitudes are smaller than v2's (COVID -0.83pts,
  2022 bear +3.52pts) — the further-tightened ROIC screen continues
  decoupling from the crisis-protection story (per the standing
  `knowledge.md` lesson from v1→v2) while continuing to *improve* the
  full-period IR gate, now past zero into genuinely positive territory.

## Regime evidence

See "Results" above — gathered together with the other gates this run
since walk-forward was unblocked for the first time and there was no
reason to defer.

## Verdict & lessons

**Ship** — the first trial in this loop's history to clear the mandatory
IR-vs-benchmark gate (+0.2216), capping a monotonic three-iteration
trend (v1 -0.2205 → v2 -0.0287 → v3 +0.2216) that confirms the
pre-registered "purer ROIC pool → better selection" hypothesis. All
quantifiable mandatory gates clear: IR PASS, deflated Sharpe PASS
(0.9966, n_trials=3 honestly counted), cost-sweep PASS (mildest decay of
the family, ~10.3%). PBO N/A (fixed-rule strategy, no tunable
parameters — structurally low overfit risk).

The walk-forward diagnostic's reported -0.078/fold decay trend and 4/18
negative-Sharpe folds initially read like the "rolling Sharpe collapses
in recent years" red flag `qj-report-analyst` warns about. Independently
re-verified directly from `equity_curve.csv` via half-year Sharpe
buckets rather than trusting the fold-decay summary at face value: the
negative windows map exactly onto already-known adverse periods (2018H2
-0.79, 2020H1 COVID ≈-0.02, 2022H1 bear -1.73), while the two most
recent half-years (2025H2 1.81, 2026H1 2.23) are among the strongest of
the entire 2016-2026 sample — the opposite of secular alpha decay. Since
`slice_diagnostics` mode has no per-fold refit (appropriate here, as
this fixed-rule strategy has no tunable parameters to overfit), a
negative chronological trend coefficient can be dominated by a handful
of known crisis windows rather than genuine decay — this is now a
standing lesson in `knowledge.md`.

Regime evidence continued decoupling from the IR trend, consistent with
the standing v1→v2 lesson: COVID -2.08pts, 2022 bear +2.27pts, both
milder than v2's, while the full-period IR kept improving past zero.
This decoupling means the IR-gate pass should be read as "better stock
selection within an increasingly ROIC-qualified pool," not as evidence
of a strengthened risk-based/defensive mechanism — worth remembering if
a future family member's IR ever regresses, since the crisis-protection
story isn't what's carrying this result.

Git action: merged `strategies/roic_momentum_v3_tighter_roic_screen.py`
into `main`, added to `release/public_artifacts.txt` (alphabetical slot
between `strategies/README.md` and `strategies/sctr_momentum_regime_gated.py`).
Full test suite (202 passed) run before the merge commit. Branch
`worktree-roic-momentum-v3` left parked (not merged as a branch, not
deleted) — only the strategy file itself was merged, consistent with
this loop's git workflow (research branches hold SPEC/IMPLEMENT/BACKTEST
work; only the final artifact moves to `main` at Ship).
