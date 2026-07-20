# Quality composite — research spec

- **Status:** WIP
- **Family:** Fundamental quality
- **Promoted from backlog:** 2026-07-20, rank 1

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

_Filled in at BACKTEST._

## Regime evidence

_Filled in at REVIEW._

## Verdict & lessons

_Filled in at REVIEW._
