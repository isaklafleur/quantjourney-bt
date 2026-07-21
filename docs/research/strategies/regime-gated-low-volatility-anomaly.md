# Regime-gated low-volatility anomaly — research spec

- **Status:** Archived (REVIEW 2026-07-21 — IR gate FAIL, cost-sweep
  PASS, walk-forward BLOCKED, verdict Archive)
- **Family:** Technical / risk-based, regime-conditional
- **Promoted from backlog:** 2026-07-21, rank 1
- **Code:** `strategies/regime_gated_low_volatility_anomaly.py` written on
  branch `worktree-regime-gated-low-vol` (native worktree tool, same
  reason as `worktree-low-vol-anomaly`/`worktree-quality-composite`: this
  session's Bash tool cannot be relied on to approve ref-mutating git
  commands unattended). Branched from `worktree-low-vol-anomaly`'s base
  (`main`), not from `worktree-low-vol-anomaly` itself — the two branches
  are independent; the vol-ranking/quintile-selection logic
  (`_vol_panel`, the eligible-score/quintile-cutoff block) was hand-copied
  from `strategies/low_volatility_anomaly.py` essentially unchanged, per
  the spec's own instruction, rather than git-merging branches. Regime
  gate reuses the `spy_trend_down` field already computed unconditionally
  by `backtester.local_data._spy_trend_down`/`_parameters_panel` for every
  `build_local_minio_bt_payload` call (originally added for
  `sctr_momentum_regime_gated.py`) — no `local_data.py` change was needed.
  Default exposure when the gate is inactive is equal-weight the full
  PIT-eligible universe, not a direct SPY hold: `SPY` is confirmed absent
  from `equity_bars_1d_yahoo_adj` (live probe, 2026-07-21), so holding it
  directly would need a second foreign price series grafted into the
  engine's core payload — a bigger change than the existing
  "parameters"-panel-only graft this file already uses for `vol_60d`; see
  the strategy file's module docstring for full detail. `qj-strategy-reviewer`
  checklist run against the file (timing, data handling, weights/exposure,
  costs, mode fit) — no issues found. Smoke-tested on 15 tickers over a
  recent window (638 dates, 31 rebalances, all weight sums ≤ cap, all-finite
  signals, 54/638 elevated-risk days) via the repo's existing
  `_smoke_regime_gated.py`. Next stage: IMPLEMENT → BACKTEST.

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

BACKTEST run 2026-07-21. Infra preflight passed (Lake API `/docs` 200;
MinIO `pit_sp500_ticker_universe` returned 709 tickers). Full-period run
(`RegimeGatedLowVolatilityAnomaly(source="minio")`, 2016-01-01 →
2026-07-21, 709-ticker PIT S&P 500 universe, monthly `BME` rebalance,
10bps weight cost): Sharpe 0.80, Total Return 216.53%, CAGR 11.58%, Max
Drawdown -31.81%, Ann. Volatility 15.10%, Ann. Turnover 285.30% (lower
than the ungated version's 370.88% — full-market weighting on calm days
turns over less than running the vol-quintile screen unconditionally,
but still higher than Quality composite's 200%, since the regime gate's
own on/off flips add roster churn on top of the quintile's own drift).
Regime gate active (elevated-risk / low-vol-quintile held) on 449/2650
trading days (~17%) over the full window.

- **Mandatory IR-vs-benchmark gate: FAIL.** Computed identically to both
  prior trials (`excess_return`/`active_return`-style aligned-series
  math against `local_lake.read_pit`-sourced SPY daily returns,
  2016-01-01→2026-07-21, 2644 aligned trading days): annualized active
  return -3.54%/yr, annualized tracking error 8.63%, **IR -0.41**
  (numerically close to the ungated version's -0.41 despite different
  underlying active-return/tracking-error components — a coincidence in
  the ratio, not a sign the gate did nothing; turnover, drawdown, and
  the regime-evidence numbers below all differ from the ungated run),
  cumulative excess return -123.41pts over the decade. The regime gate
  did **not** clear the mandatory IR gate the ungated version failed —
  full-market default exposure during the ~83% of calm days still drags
  on relative return versus lazy SPY beta, just via a different
  mechanism (beta-neutral-ish broad-market exposure instead of a
  concentrated low-vol tilt).
- **Mandatory cost-sweep gate: PASS.** Ran the strategy directly
  (`save_portfolio_plots=False`/`show_text_reports=False` for speed) at
  0/5/10/20bps total weight cost: Sharpe 0.824 → 0.813 → 0.802 → 0.780,
  total return 227.92% → 222.17% → 216.53% → 205.52%. Degrades smoothly;
  the added regime-gate-flip turnover doesn't make the strategy
  meaningfully more cost-sensitive than the ungated version.
- **Mandatory walk-forward gate: BLOCKED, same confirmed infra defect as
  both prior trials.** Re-bisected `lake_api.read_bars` before spending a
  full `WalkForwardEngine` run against a known-bad server (same judgment
  call as both prior trials' BACKTEST stages): `end=2020-01-01` → 0
  rows, `end=2023-06-15` → 0 rows, `end=2026-07-03` → 0 rows,
  `end=2026-07-21` → 5300 rows — the `knowledge.md` defect (zero rows
  for any `end` outside roughly the last 2-3 weeks of wall-clock time)
  is unchanged and confirmed to still apply today, for the third
  consecutive trial. A rolling train=24mo/test=6mo walk-forward over
  2016-2026 would fail nearly every fold identically, so a full run was
  skipped as not worth the runtime to reproduce an already-predictable
  result. Deflated Sharpe and PBO are consequently also blocked/
  unavailable (PBO's unavailability is separately expected: no
  optimizer, no tuned params). `n_trials` for this family's eventual DSR
  once the walk-forward gate is unblocked is counted honestly from
  `trial-registry.md` at REVIEW (this is the 3rd trial in "Technical /
  risk-based": SCTR-momentum-regime-gated was Shipped before this loop
  existed and isn't in the registry, Low-volatility anomaly is row 1,
  so registry `n_trials=2` for this row, per the spec's own Evaluation
  plan above).
- **Regime evidence (diagnostic, computed from `equity_curve.csv` vs. the
  same SPY series used for the IR gate — real numbers, ahead of the
  formal REVIEW distillation below):**
  - COVID crash (2020-02-19 → 2020-03-23): strategy -31.53% vs. SPY
    -33.40% — **+1.87pts** of downside protection (less than the
    ungated version's +3.09pts).
  - 2022 bear market (2022-01-03 → 2022-10-12): strategy -16.78% vs.
    SPY -24.06% — **+7.27pts** of downside protection (less than the
    ungated version's +11.74pts).
  - No GFC window in range (data starts 2016-01-04).
  - **Gate-lag diagnostic** (the spec's own pre-registered check):
    directly measured the binary `spy_trend_down` flag within each
    crisis window. COVID: elevated on only 16/24 trading days in the
    window — the SPY-200d-SMA trend gate took until 2020-02-27 (day 6 of
    a 24-day, -33% crash) to flip, so the strategy held full-market
    exposure through the crash's fastest, worst days. 2022 bear:
    elevated on 153/196 days — the gate flipped by 2022-01-21 (day 13 of
    a slower, ~9-month decline), so it caught most of that drawdown.
    This directly explains both the diminished protection versus the
    ungated version (which holds the defensive tilt unconditionally,
    with no entry lag) and the difference in protection between the two
    crises: a trend-following gate built on a 200-day SMA is structurally
    too slow to catch a crash as fast as COVID's, but catches a slower
    grind like 2022 reasonably well. Confirms the pre-registered
    expectation in the Evaluation plan above rather than contradicting
    it.

## Regime evidence

Both crisis windows show real but *diminished* downside protection versus
the ungated Low-volatility anomaly, and the gap is fully explained by
the gate-lag diagnostic in the Results section above:

- COVID crash (2020-02-19→2020-03-23): strategy -31.53% vs SPY -33.40%
  (**+1.87pts**, vs. the ungated version's +3.09pts) — the SPY-200d-SMA
  gate was elevated on only 16/24 trading days of the crash, missing its
  fastest, worst days (didn't flip until day 6 of 24).
- 2022 bear market (2022-01-03→2022-10-12): strategy -16.78% vs SPY
  -24.06% (**+7.27pts**, vs. the ungated version's +11.74pts) — the gate
  was elevated on 153/196 days, catching most of the slower decline
  (flipped by day 13 of a ~9-month grind).
- No GFC window in range (data starts 2016-01-04).

Net: a trend-following regime gate built on a 200-day SMA is
structurally too slow for fast crashes, adequate for slow ones — a
speed/coverage trade-off, not a free improvement. This is a real,
bisectable property of this gate construction, not an assumption.

## Verdict & lessons

**Archive.** The regime gate does not clear the mandatory IR gate: IR is
-0.41, numerically unchanged from the ungated version despite the
structural change (different active-return/tracking-error components,
same ratio). Worse, it *reduced* the crisis-window protection that was
the entire motivation for trying this variant (COVID +1.87pts vs.
ungated +3.09pts, 2022 bear +7.27pts vs. ungated +11.74pts) — the
gate-lag diagnostic explains the mechanism (a 200-day SMA trend gate
lags fast crashes).

More important than the lag finding: the regime gate was only ever
active on 449/2650 days (~17%) of the full period, so it structurally
cannot address the source of the full-period IR failure, which comes
from the other ~83% of (calm, bull-dominated) days where the low-vol
tilt's opportunity cost accumulates — the same drag the ungated version
showed. A defense-only-during-crises mechanism cannot rescue a
full-period benchmark-relative gate failure whose cause isn't
concentrated in crisis windows to begin with. A faster or differently-
constructed regime signal (e.g. the realized-vol-level alternative the
spec's Data & universe section flagged but didn't use) would likely
trade crisis-timing precision for the same structural ceiling — improve
the gate-lag diagnostic, not the full-period IR gate — so this is
treated as Archive rather than spawning a third Improve iteration on
this family. The underlying risk-based mechanism (low-vol names show
genuine crisis defensiveness) remains real, per both trials' regime
evidence; the specific "gate a low-vol tilt behind a trend signal"
construction is what doesn't clear the bar. Branch
`worktree-regime-gated-low-vol` left parked (not merged, not deleted —
an unattended run doesn't delete branches). Lessons distilled into
`knowledge.md` (crisis-only gates can't fix calm-period drag; the
200d-SMA gate-lag measurement) plus an Avoid-list entry for this
specific construction.
