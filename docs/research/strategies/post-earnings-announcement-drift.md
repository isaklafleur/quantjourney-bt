# Post-earnings-announcement drift (PEAD) — research spec

- **Status:** WIP
- **Family:** Fundamental, event-driven
- **Promoted from backlog:** 2026-07-21, rank 1

## Hypothesis

Post-earnings-announcement drift: stock prices underreact to earnings
surprises, so returns drift in the direction of the surprise for weeks
after the announcement rather than jumping to a new fair value
immediately (Ball & Brown 1968; formalized by Bernard & Thomas 1989).
Behavioral mechanism, not a risk-based one — investors (and
sell-side/analyst consensus) update slowly on new information, so a
name with a large positive standardized unexpected earnings (SUE) tends
to keep outperforming for a fixed post-event window, and a large
negative one keeps underperforming.

This is an independent construction for this loop, not a port of
IMQuantFund's own `pead_signal.py` (that file lives in a different
project and isn't available here) — the signal definition, universe,
and event-window mechanics below are built from scratch against this
repo's own data (`earnings_surprise`) and evaluation primitives.

## Data & universe

- `backtester.lake_api.read_features("earnings_surprise", tickers=...,
  as_of=datetime.now(UTC).date())` — expected to carry a
  standardized-unexpected-earnings-style column (`sue` per the backlog
  idea's framing); the real column name, units, and `knowledge_time`
  behavior are **unverified** and must be live-probed at IMPLEMENT
  before any code is written against them, per this loop's established
  practice (`knowledge.md`'s recurring lesson: never write a strategy
  against a guessed schema — `technical_features`/`quality_features`
  both had knowledge_time behavior that differed from assumption when
  actually probed). Apply the same `as_of=datetime.now(UTC).date())`
  workaround as every prior trial for the lake API's confirmed
  `read_features` recency defect (`knowledge.md`).
- **Known data gap, flagged in the backlog and carried here unresolved
  until IMPLEMENT probes it:** `earnings_surprise` covers fiscal Q1-Q3
  only — no Q4/annual row, per the dataset's own source docstring
  referenced in the backlog. This needs an explicit gap-handling
  decision at IMPLEMENT (e.g. skip Q4 entry windows entirely, or carry
  forward the most recent available surprise with a staleness cap) —
  not decided here, and not safe to paper over silently.
- Universe: PIT S&P 500 membership via
  `backtester.local_lake.pit_sp500_ticker_universe`, matching every
  strategy in this loop so far (Quality composite, Low-volatility
  anomaly, Regime-gated low-volatility anomaly).
- Price/eligibility: `backtester.lake_api.read_bars("equity_bars_1d_yahoo_adj", ...)`.
- Date range: 2016-01-01 to present, for direct comparability with
  every prior trial's IR/regime-evidence numbers, subject to
  `earnings_surprise`'s own real history coverage (unverified — confirm
  at IMPLEMENT rather than assume it matches the other datasets' 2016+
  range).

## Implementation notes

- Mode is an **open question for IMPLEMENT to resolve**, per the
  backlog idea's own flag: this is an event-driven entry (buy shortly
  after a qualifying earnings surprise, hold a fixed window, then exit)
  rather than a steady daily cross-sectional rank-and-hold panel like
  every prior trial in this loop. `qj-strategy-ideas` should decide
  weight-mode-with-an-event-driven-eligibility-mask vs. true order-mode
  vs. a custom weight schedule — use `strategies/sctr_momentum_regime_gated.py`
  and the existing `strategies/example_wf_*`/`example_weights_*` files as
  reference points for the nearest pattern, not a strategy already in
  this research loop (none of the three prior trials are event-driven).
- Signal: rank/filter names by SUE magnitude at each qualifying earnings
  event; go long the high-SUE tail (top decile or quintile — exact cut
  is an IMPLEMENT design choice, not decided here). Short leg is
  explicitly out of scope for the first trial (long/cash, matching every
  prior strategy in this loop) unless IMPLEMENT finds a compelling
  reason to add one.
- Holding window: fixed post-event window (the classic PEAD
  construction holds ~60 trading days; exact length is an IMPLEMENT
  design choice, to be pre-registered in the Evaluation plan before
  BACKTEST runs, not tuned after seeing results).
- Missing-value / gap handling: names without a qualifying recent
  surprise (including the Q4 gap above) are simply not eligible that
  period — same all-finite-signal-or-excluded discipline as
  `MISSING_VOL_SENTINEL` in `low_volatility_anomaly.py`, adapted to an
  event-eligibility mask rather than a continuous score.
- Cost sensitivity: the backlog idea explicitly flags this as
  concentrated turnover around earnings dates — cost-sensitive by
  construction, so the mandatory cost-sweep gate matters more here than
  in the calendar-rebalanced trials so far.
- If `build_local_minio_bt_payload` still has no generic hook for
  research-tier features by the time this reaches IMPLEMENT
  (`knowledge.md`'s standing lesson), override `_fetch_market_data`
  directly, following the pattern already used for `quality_features`/
  `technical_features` in the prior three strategy files.

## Evaluation plan

Written before the BACKTEST stage runs.

- Benchmark: `benchmark_symbol="SPY"` — same as every prior trial.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=24, test_months=6)`)
  as a starting point, matching the two low-volatility trials — but
  re-bisect the lake API's confirmed `read_bars`/`read_features`
  recency defect (`knowledge.md`) before spending a full run, per the
  precedent set in all three prior trials' BACKTEST stages, rather than
  assume it's fixed. An event-driven strategy's fold boundaries may also
  need to respect earnings-event dates rather than pure calendar months
  — a design question for IMPLEMENT/BACKTEST to resolve, not assumed
  away here.
- `purge_days`/`embargo_pct`: `WalkForwardConfig` defaults, unless
  IMPLEMENT surfaces a reason to widen them (e.g. to avoid a fold
  boundary splitting a single earnings-event holding window).
- Deflated Sharpe / PBO: this is the first "Fundamental, event-driven"
  family trial — `n_trials=1` for this family's DSR calculation, counted
  from `trial-registry.md` at REVIEW.
- Cost sweep: mandatory, and expected to bind harder than any prior
  trial given the backlog idea's own concentrated-turnover-around-events
  flag — don't assume it passes just because every prior trial's cost
  sweep did.
- Regime evidence: diagnostic only, gathered from the report's
  crisis-analysis breakdown (or, if the strategy's own equity curve
  doesn't span a crisis window cleanly given event-driven position
  timing, computed directly from `equity_curve.csv` vs. SPY the same way
  all three prior trials did). No specific pre-registered expectation —
  PEAD's behavioral mechanism doesn't have as clear an a-priori
  crisis-regime prediction as the low-volatility anomaly's risk-based
  one, so this is exploratory rather than a check against a stated
  hypothesis.

## Results

Not yet run — filled in at BACKTEST.

## Regime evidence

Not yet available — filled in at REVIEW.

## Verdict & lessons

Not yet available — filled in at REVIEW.
