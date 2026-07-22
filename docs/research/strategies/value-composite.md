# Value composite — research spec

- **Status:** WIP (SPEC written; branch created, no code yet)
- **Family:** Fundamental value
- **Promoted from backlog:** 2026-07-21, rank 1
- **Code:** none yet. Research branch/worktree `worktree-value-composite`
  created via the native worktree tool (same reason as prior WIPs: this
  session's Bash tool cannot be relied on to approve ref-mutating git
  commands unattended). Branched from `main`. Next stage: SPEC → IMPLEMENT.

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
  — expected to carry `eps` and `book_value_per_share` per the backlog
  idea's framing; unconfirmed against the live server or any fixture in
  this repo (same caveat every prior spec has flagged for its own
  dataset) — must be live-probed at IMPLEMENT before writing any ranking
  code, not assumed.
- Needs joining against daily price (`equity_bars_1d_yahoo_adj` via
  `backtester.lake_api.read_bars`, same source every prior strategy in
  this loop uses for eligibility/mode data) to form the two ratios:
  earnings yield = `eps` / `adj_close`, book-to-market =
  `book_value_per_share` / `adj_close`.
- `book_value_per_share` is reported null for roughly half of
  company-years per `value_features`'s own source docstring (nearest-join
  tolerance misses) — confirm the real null rate at IMPLEMENT (as
  `quality_composite`'s `gross_profitability` null rate turned out to
  need live confirmation, not the docstring's word) and design the
  composite to fall back to earnings-yield-only explicitly when
  book-to-market is missing, mirroring `quality_composite.py`'s
  elementwise-nanmean pattern rather than silently dropping rows.
- Universe: PIT S&P 500 membership via
  `backtester.local_lake.pit_sp500_ticker_universe` — same choice as
  every prior WIP in this loop, for the same reason (reasonably liquid,
  well-covered names for a first pass).
- Date range: 2016-01-01 to present, matching every prior trial's range;
  `value_features` coverage before that is unconfirmed and should be
  checked at IMPLEMENT, not assumed here.
- `event_time`/`knowledge_time` behavior for `value_features` is
  unconfirmed — check directly at IMPLEMENT whether it follows
  `quality_features`' (genuinely spread across history) or
  `technical_features`' (bulk-clustered near "now") pattern, per
  `knowledge.md`'s standing lesson not to assume one dataset's
  knowledge_time shape from another's.

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

_Not yet run — filled in at BACKTEST._

## Regime evidence

_Not yet gathered — filled in at REVIEW._

## Verdict & lessons

_Not yet decided — filled in at REVIEW._
