# Value composite — research spec

- **Status:** WIP (BACKTEST complete; next stage BACKTEST → REVIEW)
- **Family:** Fundamental value
- **Promoted from backlog:** 2026-07-21, rank 1
- **Code:** `strategies/value_composite.py` on `worktree-value-composite`
  (commit `4faac4d`). Reused `quality_composite.py`'s
  `_fetch_market_data`-override/graft pattern; earnings-yield and
  book-to-market are each cross-sectional z-scored then combined via
  elementwise nanmean (fallback to earnings-yield-only when
  book-to-market is null). Smoke-tested end-to-end on 10 tickers over a
  recent window (3/10 names selected at the top-quartile cutoff, weights
  capped at 0.10, all-finite signal); full `pytest tests/ -q` green (201
  passed).

## Hypothesis

Combine earnings yield (`eps` / price) and book-to-market
(`book_value_per_share` / price) into a single value composite, hold the
top-quartile long, cash otherwise — the classic Fama-French (1992) value
factor construction, applied here as a new construction rather than a port
of IMQuantFund's own `value_signal.py`. The hypothesized edge is
behavioral/structural: cheap-relative-to-fundamentals stocks earn a premium
either because investors systematically overextrapolate recent growth into
high-multiple names (behavioral) or because value stocks bear genuine
distress/leverage risk not fully priced by a simple market beta
(risk-based) — the literature doesn't settle which, and this spec doesn't
need it to; either mechanism predicts the same testable outcome (top-
quartile cheap names outperform on a risk-adjusted, benchmark-relative
basis). Ranked #1 in the backlog primarily for low overfit risk (4/5) and
solid implementability (4/5), not a strong prior of full-cycle
profitability — value has had a well-documented rough decade in parts of
this sample, which is exactly the robustness question this WIP is meant to
test rather than assume.

## Data & universe

- `backtester.lake_api.read_features("value_features", tickers=..., as_of=...)`
  — confirmed live at IMPLEMENT (2026-07-22, PIT S&P 500 universe probe,
  709 tickers / 1072 rows): columns are `ticker`, `event_time`, `cik`,
  `knowledge_time`, `eps`, `stockholders_equity`, `shares_outstanding`,
  `book_value_per_share`, `source`, `dataset` — `eps` and
  `book_value_per_share` both present as the backlog idea assumed.
- Needs joining against daily price (`equity_bars_1d_yahoo_adj` via
  `backtester.lake_api.read_bars`, same source every prior strategy in
  this loop uses for eligibility/mode data) to form the two ratios:
  earnings yield = `eps` / `adj_close`, book-to-market =
  `book_value_per_share` / `adj_close`.
- `book_value_per_share` is null for ~16.9% of rows (confirmed by the
  same live probe, 709-ticker PIT S&P 500 sample) — much lower than the
  ~50% this spec initially guessed by analogy to `quality_features`'
  `gross_profitability`; the two datasets' null rates are independent
  properties, not transferable (same lesson `quality_composite` already
  taught: verify, don't assume, per-dataset). The composite falls back to
  earnings-yield-only explicitly for that ~17%, mirroring
  `quality_composite.py`'s elementwise-nanmean pattern rather than
  silently dropping rows. `eps` itself is null for 0% of rows.
- Universe: PIT S&P 500 membership via
  `backtester.local_lake.pit_sp500_ticker_universe` — same choice as
  every prior WIP in this loop, for the same reason (reasonably liquid,
  well-covered names for a first pass).
- Date range: 2016-01-01 to present, matching every prior trial's range;
  `value_features` coverage before that is unconfirmed and should be
  checked at IMPLEMENT, not assumed here.
- `knowledge_time` is genuinely spread across history (2009-2026 in the
  same probe), matching `quality_features`' pattern rather than
  `technical_features`' bulk-clustered-near-"now" pattern — confirmed
  directly, not assumed, per `knowledge.md`'s standing lesson.

## Implementation notes

- Weight mode (per `qj-strategy-ideas`): portfolio rank-and-hold
  thinking, not execution logic. Nearest existing pattern in this repo is
  `strategies/quality_composite.py` (same shape: two-factor fundamental
  composite, PIT S&P 500, quarterly rebalance, long/cash) — reuse its
  `_fetch_market_data` override pattern (`build_local_minio_bt_payload`
  still has no generic research-tier-feature hook, confirmed by that
  strategy and unchanged since) to graft a `value_composite_score`
  parameter field, its cross-sectional z-score/nanmean combination
  shape, and its knowledge_time-anchored `merge_asof` forward-fill for
  the fundamental data — adapted from fiscal-year-end filings to
  whatever cadence `value_features` turns out to use.
- Combine earnings yield and book-to-market via cross-sectional
  z-scoring each factor separately (mean 0, std 1, within the eligible
  universe on each rebalance date) then averaging — same
  simplest-defensible-combination choice `quality_composite.py` made,
  avoiding an arbitrary weighting scheme for a first WIP on this family.
- Explicit fallback to earnings-yield-only when book-to-market is null
  (elementwise nanmean, not silent NaN propagation) — required given the
  ~50% null rate the backlog idea already flagged.
- Rebalance policy (`qj-config-helper`): quarterly
  (`RebalancePolicy(frequency="BQE")`) unless IMPLEMENT's live probe of
  `value_features`' update cadence suggests otherwise — matches every
  prior fundamental-composite trial's reasoning (daily/monthly
  rebalancing would add turnover without adding information for
  filing-cadence data).
- Position cap: equal-weight within the top quartile, capped at
  `max_position_size=0.10`, same as `quality_composite.py`.

## Evaluation plan

Written before the BACKTEST stage runs.

- Benchmark: `benchmark_symbol="SPY"` — same lazy benchmark used by every
  prior trial in this loop, appropriate since the universe is itself
  S&P 500-drawn.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=36, test_months=12)`),
  matching `quality_composite`'s reasoning (filing-cadence fundamental
  data benefits from a longer train window per fold) unless IMPLEMENT's
  cadence probe suggests a different split. **Known blocker to check
  first**: `knowledge.md` documents a still-unresolved lake API server
  defect where `read_bars`'s `end` param (and `read_features`'s `as_of`
  param) return zero rows for any date outside roughly the last 2-3
  weeks of wall-clock time — re-bisect at BACKTEST time per the standing
  lesson (don't assume it's fixed, don't assume it's still broken)
  before spending a full `WalkForwardEngine` run.
- `purge_days`/`embargo_pct` left at `WalkForwardConfig` defaults unless
  IMPLEMENT surfaces a reason to widen them.
- Deflated Sharpe / PBO: standard; `n_trials=1` for this new
  "Fundamental value" family (first trial).
- Cost sweep: run per the mandatory gate; quarterly rebalance suggests
  low sensitivity (same expectation as `quality_composite`, which
  passed), not assumed without running it.
- Regime evidence: no strong a-priori regime prediction pre-registered
  here — value's own literature is genuinely mixed across cycles
  (unlike low-volatility's clean defensive story), so record what the
  crisis-analysis breakdown actually shows without a directional
  expectation to confirm or deny.

## Results

Filled in at BACKTEST (2026-07-22). Infra preflight: Lake API `/docs`
200 (default `http://localhost:8000`, no `QJ_LAKE_API_URL` override in
`.env`); MinIO `pit_sp500_ticker_universe` returned 500 tickers on a
small probe read. Re-bisected the standing `lake_api.read_bars` `end`-
date recency defect before committing to a walk-forward run: unchanged
— `end=2020-01-01`/`2023-06-15`/`2026-07-03` all return 0 rows,
`end=2026-07-22` returns 1896 rows (single-ticker probe), 5th
consecutive trial confirming it. All runs: `Backtester(source="minio")`,
`benchmark_symbol="SPY"`, `weight_cost_model=FixedBpsWeightCostModel
(total_bps=10.0)` unless noted, PIT S&P 500 universe (709 tickers ever-
members), 2016-01-01 to 2026-07-20.

**Full-period backtest** (`strategies/value_composite.py`'s own
`main()`): Sharpe 0.74 (performance-report table) / 0.6407 (summary
footer — same two-report-surface annualization-convention discrepancy
noted for every prior trial in this loop), CAGR 13.77%, Total Return
289.66%, Max Drawdown -44.50%, annualized volatility 20.30%/20.31%,
annualized turnover 208.19%, 43 quarterly rebalances. Full report:
`reports/ValueComposite/` (gitignored scratch output, not committed).

**IR vs. benchmark (mandatory) — FAIL, but the closest to zero of any
trial in this loop.** Benchmark returns sourced from
`local_lake.read_pit("processed", "market_ref_bars_1d_yahoo_adj",
tickers=["SPY"])` (2649 aligned trading days, 2016-01-05→2026-07-20).
`excess_return`: -48.23 cumulative percentage points below SPY over the
full period. `active_return` (annualized): -1.27%/yr. Annualized
tracking error: 10.71%. Information ratio (active return mean / active
return std, annualized — same manual computation as every prior trial,
no dedicated `information_ratio` helper in `backtester.engines.
benchmark`): **-0.059**. Decisively better than every prior trial in
this loop (Quality -0.26, Low-vol -0.41, Regime-gated low-vol -0.41,
PEAD -0.48) — a near-flat information ratio rather than a decisive
beta signature, though still technically a gate failure since it's
negative, not zero or positive.

**Cost sweep (mandatory) — PASS.** Sharpe/CAGR at 0/5/10/20 bps total
cost: 0.6482/13.95%, 0.6445/13.86%, 0.6407/13.77%, 0.6332/13.60%
(~2.3% relative Sharpe decay). Edge is not cost-sensitive, consistent
with the quarterly rebalance cadence and lower turnover than the
event-driven/technical trials in this loop.

**Walk-forward robustness (mandatory) — BLOCKED.** Same confirmed lake
API `read_bars`/`read_features` recency defect (see re-bisection above)
would strand nearly every fold of the spec's rolling train=36mo/
test=12mo scheme, so a full `WalkForwardEngine` run was skipped rather
than reproduce an already-predictable near-total-failure result — same
judgment call as all four prior trials. Deflated Sharpe / PBO
consequently also BLOCKED / N/A.

## Regime evidence

Diagnostic, computed directly from `equity_curve.csv` vs. the same SPY
series used for the IR gate (2026-07-22): COVID crash
(2020-02-19→2020-03-23) strategy -43.89% vs SPY -33.72% (**-10.17pts**,
underperformed decisively — the largest crisis-window gap of any trial
in this loop, in either direction); 2022 bear market
(2022-01-03→2022-10-12) strategy -18.37% vs SPY -24.50% (**+6.13pts**,
outperformed). No GFC window in range (data starts 2016-01-04). Like
PEAD, this is a mixed rather than consistently protective/exposed
pattern, consistent with the spec's own pre-registered expectation that
value's literature is genuinely mixed across cycles (no a-priori
directional prediction was made). The COVID underperformance is
notably large and worth flagging at REVIEW: a fast, liquidity-driven
panic sell-off is exactly the kind of regime where "cheap on trailing
fundamentals" can mean "cheap because the market is pricing in real
distress risk" (value's classic value-trap failure mode), whereas the
slower, valuation-driven 2022 decline rewarded the same tilt.

## Verdict & lessons

_Not yet decided — filled in at REVIEW._
