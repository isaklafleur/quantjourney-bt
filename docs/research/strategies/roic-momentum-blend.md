# ROIC + momentum blend — research spec

- **Status:** WIP (promoted 2026-07-22; spec written, no code yet)
- **Family:** Fundamental × technical combination
- **Promoted from backlog:** 2026-07-22, rank 1

## Hypothesis

"Quality at a reasonable momentum": combine capital-efficiency
profitability (ROIC = NOPAT / Invested Capital, quality-investing
lineage) with a trailing price-momentum tilt (`technical_features.
ret_60d`), on the argument that a firm compounding capital efficiently
*and* currently showing price momentum is more likely riding a genuine
improving-fundamentals trend than either signal alone would suggest —
ROIC alone doesn't confirm the market has noticed yet, and momentum
alone doesn't confirm the underlying business is actually good
(vulnerable to pure sentiment/multiple expansion with no fundamental
support). This is the loop's first fundamental × technical combination:
every prior trial combined either two fundamental signals (Quality
composite, Value composite) or ran a single technical/behavioral signal
alone (Low-volatility anomaly, PEAD). Ranked #1 in Ready primarily for
novelty (originality 4/5) and solid implementability (4/5); the
combination methodology itself (z-score blend vs. sequential screen vs.
double-sort) is a genuinely open design choice with more researcher
degrees of freedom than a single-mechanism strategy, hence a lower
overfit-risk score (3/5) than Value composite's (4/5) — not a strong
prior of profitability either way.

## Data & universe

- `roic_features` via `backtester.lake_api.read_features` — one of the
  six research-tier feature datasets in the served catalog (Data scope),
  so the data prerequisite check at PROMOTE passes. Its real column
  schema (the backlog's assumed `roic` field), null rate, and
  `knowledge_time` behavior are all unconfirmed in-repo (no live probe
  or fixture found) and are deferred to a mandatory IMPLEMENT-time live
  probe rather than guessed here — every prior research-tier dataset
  this loop has actually probed differed from its initial assumption in
  some way (`quality_features`' ~50-58% null rate, `value_features`'
  much-lower ~16.9% null rate, `technical_features`' bulk-clustered
  `knowledge_time`, `earnings_surprise`'s fiscal-Q4 gap).
- `technical_features.ret_60d` via the same `read_features` path —
  `technical_features` itself is already confirmed live and
  event_time-anchored by the Low-volatility anomaly trial (bulk-clustered
  `knowledge_time` near "now"; its sibling column `vol_60d` is pivoted
  directly on `event_time`, mirroring `backtester.local_data.
  _sctr_rank_panel`). `ret_60d` is *expected*, not yet directly
  confirmed, to share `vol_60d`'s event_time/knowledge_time behavior
  since both are columns of the same dataset — a working assumption to
  verify at IMPLEMENT, not a certainty (coverage/cadence properties
  don't reliably transfer even within one dataset, per the standing
  lesson from `value_features` vs. `quality_features`'s independent
  null rates).
- Universe: PIT S&P 500 membership (`pit_sp500_ticker_universe`) — same
  choice as every prior WIP in this loop.
- Date range: 2016-01-01 to present, matching every prior trial;
  `roic_features` coverage before that is unconfirmed and should be
  checked at IMPLEMENT, not assumed here.
- Unlike Value composite, neither factor needs a further price-ratio
  construction (no dividing by `adj_close`) — both ROIC and `ret_60d`
  are already feature-dataset columns; price data is only needed for the
  shared builder's eligibility/mode plumbing, not the signal itself.

## Implementation notes

- Weight mode (per `qj-strategy-ideas`): portfolio rank-and-hold, same
  as every strategy in this loop so far.
- Nearest existing pattern: two, not one — `quality_composite.py`'s
  `_fetch_market_data`-override graft for the fundamental leg (ROIC,
  quarterly-filing-cadence, `knowledge_time`-anchored `merge_asof`
  forward-fill, same PIT shape as fiscal ROIC data) and
  `low_volatility_anomaly.py`'s `event_time`-pivot for the technical leg
  (`ret_60d`, same dataset family as `vol_60d`). This is the first
  strategy in the loop needing both PIT-join styles simultaneously in
  one composite — exactly the risk the backlog idea itself flagged
  ("PIT alignment between quarterly ROIC and daily momentum needs a
  careful as-of join").
- Combination methodology: cross-sectional z-score each factor
  separately (mean 0, std 1 within the eligible universe on each
  rebalance date), then average via elementwise nanmean — the same
  simplest-defensible-combination choice `quality_composite.py` and
  `value_composite.py` both made, rather than a sequential screen or
  double-sort (both viable per the backlog idea's own framing, but add
  more researcher degrees of freedom than this loop's established
  default). Revisit only if IMPLEMENT's live probe surfaces a concrete
  reason not to (e.g. near-non-overlapping coverage making a z-score
  nanmean degenerate).
- Rebalance policy (`qj-config-helper`): monthly
  (`RebalancePolicy(frequency="BME")`) — matches Low-volatility
  anomaly's reasoning (a continuously-updating technical/momentum leg
  would go stale for up to a quarter under the fundamental composites'
  quarterly cadence) rather than Quality/Value composite's quarterly
  choice (appropriate only when every leg is filing-cadence data).
  Revisit at IMPLEMENT if `roic_features`' real update cadence argues
  otherwise.
- Position cap: equal-weight within the top quartile, capped at
  `max_position_size=0.10`, same as every prior composite.
- Missing-value handling: expect a `MISSING_SCORE_SENTINEL`-style
  fallback (a value safely outside any real top-quartile cutoff) for
  names missing either factor on a given date, mirroring
  `quality_composite.py`/`value_composite.py`'s all-finite-signal
  constraint — the engine's own signal validation rejects NaN.

## Evaluation plan

Written before the BACKTEST stage runs.

- Benchmark: `benchmark_symbol="SPY"`, same lazy benchmark as every
  prior trial in this loop.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=24, test_months=6)`)
  — matches Low-volatility anomaly's choice (a shorter window than the
  36/12-month fundamental-only composites, since the momentum leg is
  faster-moving) unless IMPLEMENT's cadence probe argues otherwise.
  **Known blocker to check first**: `knowledge.md` documents a
  still-unresolved lake API server defect where `read_bars`'s `end`
  param (and `read_features`'s `as_of` param) return zero rows for any
  date outside roughly the last 2-3 weeks of wall-clock time —
  re-bisect at BACKTEST time per the standing lesson (don't assume
  fixed, don't assume still-broken) before spending a full
  `WalkForwardEngine` run.
- `purge_days`/`embargo_pct` left at `WalkForwardConfig` defaults unless
  IMPLEMENT surfaces a reason to widen them.
- Deflated Sharpe / PBO: standard; `n_trials=1` for this new
  "Fundamental × technical combination" family (first trial).
- Cost sweep: run per the mandatory gate; monthly rebalance suggests
  moderate cost sensitivity — between the quarterly composites' low
  sensitivity and the daily/event-driven trials' high sensitivity — not
  assumed without running it.
- Regime evidence: no strong a-priori regime prediction pre-registered.
  ROIC (quality-linked) motivates some expectation of defensive
  characteristics analogous to Quality composite, but the momentum leg
  pulls the other way (momentum crashes around sharp market reversals
  are well documented), so the net regime signature is genuinely
  unclear ahead of time — record what the crisis-analysis breakdown
  actually shows without a directional expectation to confirm or deny.

## Results

Not yet run — filled in at BACKTEST.

## Regime evidence

Not yet gathered — filled in at REVIEW.

## Verdict & lessons

Not yet reached — filled in at REVIEW.
