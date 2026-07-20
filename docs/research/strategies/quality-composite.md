# Quality composite — research spec

- **Status:** WIP (IMPLEMENT done 2026-07-20; BACKTEST partially run
  2026-07-20 — IR-vs-benchmark and cost-sweep gates complete, walk-forward
  (and its downstream deflated-Sharpe/PBO) blocked on a lake API infra bug;
  next is retry walk-forward once fixed)
- **Family:** Fundamental quality
- **Promoted from backlog:** 2026-07-20, rank 1
- **Code:** `strategies/quality_composite.py` on branch
  `worktree-quality-composite` (see backlog.md's WIP note for why this
  isn't `research/quality-composite`)

## Hypothesis

Rank US equities by a two-factor quality composite — gross profitability
(Novy-Marx 2013: `GrossProfit / Assets`) and low cash-flow accruals (Sloan
1996: `(NetIncome - OCF) / Assets`, lower/more negative preferred) — and
hold the top-quartile long, cash otherwise. The hypothesized edge is
structural, not just backtested-good-looking: high gross profitability
captures a durable competitive/margin advantage that tends to persist
across periods (a "quality" premium distinct from raw earnings level),
while low accruals identify firms whose reported earnings are closer to
real cash generation (less prone to earnings management or subsequent
mean-reversion in reported profitability). Both factors have decades of
academic out-of-sample replication outside this specific dataset, which is
why this idea was ranked #1 in the backlog: lowest overfit risk of the
batch, not the highest expected Sharpe.

## Data & universe

- `backtester.lake_api.read_features("quality_features", tickers=..., as_of=...)`
  — per-cik, fiscal-year-end rows with `gross_profitability` and
  `accruals` (confirmed present in IMQuantFund's
  `imqf_research.fundamental_features.compute_quality_features`).
- `quality_features` is keyed by `cik`, not `ticker` — confirm at
  IMPLEMENT whether the rows returned by `read_features` already carry a
  usable ticker column (the source module's `_ticker_map` join suggests
  this mapping exists upstream in the lake) before assuming any extra
  join is needed client-side.
- Universe: PIT S&P 500 membership via
  `backtester.local_lake.resolve_pit_sp500`/`pit_sp500_ticker_universe` —
  keeps a first WIP to reasonably liquid, well-covered names; revisit
  (e.g. `all_equities`) only if S&P 500 coverage of `quality_features`
  turns out too sparse at IMPLEMENT.
- Price/eligibility: `backtester.lake_api.read_bars("equity_bars_1d_yahoo_adj", ...)`.
- Date range: 2016-01-01 to present, matching the range already validated
  for the SCTR port; `quality_features` coverage before that is not yet
  confirmed and should be checked at IMPLEMENT, not assumed here.

## Implementation notes

- Weight mode (per `qj-strategy-ideas`): this is portfolio rank-and-hold
  thinking, not order/execution logic — closest existing pattern in this
  repo is a cross-sectional weight-mode ranking example (e.g.
  `example_weights_15_cross_sectional_momentum.py`'s ranking-and-selection
  structure), adapted to rank on the two fundamental columns instead of a
  price-momentum column.
- Combine `gross_profitability` and `accruals` into a single composite
  score via cross-sectional z-scoring each factor separately (mean 0, std
  1, computed within the eligible universe on each rebalance date) then
  averaging — the simplest defensible combination method, avoiding an
  arbitrary weighting scheme for a first WIP.
- Fiscal-year-end data means the composite score only updates once a year
  per company; the panel between updates should forward-fill the most
  recently known score, respecting `knowledge_time`/PIT — never fill with
  a not-yet-known value.
- Rebalance policy (`qj-config-helper`): quarterly
  (`RebalancePolicy(frequency="BQE")`), reasonable given the annual update
  cadence of the underlying data — daily/monthly rebalancing would just
  add turnover without adding information.
- Position cap: equal-weight within the top quartile, capped at
  `max_position_size=0.10` (assumes at least ~10 names in the top-quartile
  pool from a ~40-80 name S&P 500-drawn universe with full data coverage).

## Evaluation plan

Written before the BACKTEST stage runs.

- Benchmark: `benchmark_symbol="^GSPC"` (S&P 500) — the universe is
  itself S&P 500-drawn, so this is a fair "lazy benchmark" for the
  mandatory IR gate.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=36, test_months=12)`)
  — 3 years train / 1 year test, since fiscal-year-end data only updates
  annually and a shorter train window risks too few distinct annual
  snapshots per fold.
- `purge_days`/`embargo_pct` left at `WalkForwardConfig`'s defaults unless
  IMPLEMENT surfaces a reason to widen them — fiscal-year-end reporting
  lag is already handled by the lake's own `knowledge_time` PIT
  resolution, not by the walk-forward embargo.
- Deflated Sharpe / PBO: standard; `n_trials` counted from this family's
  `trial-registry.md` rows once any exist.
- Cost sweep: not expected to be critical given quarterly rebalancing
  (low turnover relative to e.g. the RSI/BB mean-reversion backlog idea),
  but still run per the mandatory gate — not skipped on that assumption.
- Regime evidence: no strong a-priori regime prediction for this factor
  (unlike, say, the low-volatility idea's known bull-market
  underperformance) — record what the crisis-analysis breakdown actually
  shows without a pre-registered expectation to confirm or deny.

## Results

_Partially filled in at BACKTEST (2026-07-20); walk-forward re-run pending
an infra fix. All runs: `Backtester(source="minio")`, `benchmark_symbol=
"SPY"`, `weight_cost_model=FixedBpsWeightCostModel(total_bps=10.0)` unless
noted, PIT S&P 500 universe (706 tickers ever-members 2016-2026),
2016-01-01 to 2026-07-14._

**Full-period backtest** (`strategies/quality_composite.py`'s own
`main()`, plus a re-run with `skip_analysis=True` for the gates below —
consistent to 3 decimals): Sharpe 0.80, Sortino 1.13, CAGR 13.31%,
Max Drawdown -33.69%, Calmar 0.40, annualized volatility 17.53%,
annualized turnover 200.47%. Full report: `reports/QualityComposite/`
(gitignored scratch output, not committed).

**IR vs. benchmark (mandatory) — FAIL.** Benchmark returns sourced from
`local_lake.read_pit("processed", "market_ref_bars_1d_yahoo_adj",
tickers=["SPY"])` (2643 aligned trading days). `excess_return`: -71.0
cumulative percentage points below SPY over the full period.
`active_return` (annualized): -1.89%/yr. Information ratio (active
return mean / active return std, annualized — no dedicated
`information_ratio` helper exists in `backtester.engines.benchmark`, so
computed directly from the aligned daily series per the module's
`excess_return`/`active_return` primitives): **-0.26**. Despite a
respectable absolute Sharpe, the strategy meaningfully underperforms its
own "lazy benchmark" risk-adjusted over the full decade — this is the
single most important finding of this BACKTEST run and a strong signal
toward Archive at REVIEW, independent of the walk-forward blocker below.

**Cost sweep (mandatory) — PASS.** Sharpe/CAGR at 0/5/10/20 bps total
cost: 0.813/13.55%, 0.810/13.48%, 0.806/13.42%, 0.799/13.28%. Edge is not
cost-sensitive (quarterly rebalance keeps per-trade cost drag small
despite 200% annualized turnover) — confirms the spec's evaluation-plan
prediction rather than overturning it.

**Walk-forward robustness (mandatory) — BLOCKED, not merely failing.**
Ran `WalkForwardEngine` per the evaluation plan (`scheme="rolling"`,
`train_months=36`, `test_months=12`, default `purge_days=5`/
`embargo_pct=0.01`), `backtester_factory=`-based per-fold refit (8 folds
generated over 2016-2026). 7/8 folds failed with the *same* underlying
cause: `lake_api.read_bars("equity_bars_1d_yahoo_adj", ...)` returns
**zero rows whenever `end` predates roughly the last 2-3 weeks of
wall-clock time**, independent of `start` or which tickers are
requested — confirmed by direct bisection (as of this run, 2026-07-20:
`end=2026-07-03` → 0 rows, `end=2026-07-04` → 5278 rows, for a 2-ticker/
10-year probe query; the full-period backtest above only worked because
its `end` was recent). This is a lake API server defect, not a strategy
or PIT-handling bug — it will silently block the walk-forward gate for
*every* future strategy in this loop that reaches BACKTEST, not just this
one, until fixed server-side. Only fold 7 (OOS 2026-01-05→2026-07-10,
inside the served window) produced a real result: OOS Sharpe 1.25, OOS
CAGR 16.77%, IS Sharpe 0.86 (overfit ratio 0.69, efficiency 1.45). These
numbers are **not** reported as a passing walk-forward result — one
surviving fold out of eight is not evidence of robustness, it's one
year's slice. The engine's own aggregate (`deflated_sharpe=0.81`,
`sharpe_decay=0.0`) inherits the same single-fold reliability caveat and
should not be read as a real DSR either.

**Deflated Sharpe — BLOCKED** (same root cause; would need the full,
multi-fold OOS series to be meaningful, not the one surviving fold's).

**Overfit probability (PBO) — unavailable, as documented, not a
defect.** `WalkForwardConfig.pbo_trials=0` (no optimizer; this strategy
has no tuned hyperparameters to sweep) → the rank-based PBO the engine
implements needs `pbo_trials>=2` with an optimizer; the older fold-level
`probability_of_backtest_overfitting` is deprecated and always returns
NaN per its own module docstring. Reported as unavailable, never as a
reassuring 0, per the skill's hard rules.

**Regime evidence:** not evaluated this run — deferred to REVIEW once
walk-forward completes, per the spec's own plan.

## Regime evidence

_Filled in at REVIEW._

## Verdict & lessons

_Filled in at REVIEW._
