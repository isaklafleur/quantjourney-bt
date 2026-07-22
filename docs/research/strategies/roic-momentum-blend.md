# ROIC + momentum blend — research spec

- **Status:** WIP (spec written 2026-07-22; code written 2026-07-22 on
  `worktree-roic-momentum`, commit `2f840df`; BACKTEST completed
  2026-07-22 after routing around the shared-engine bug via a
  universe exclusion — see Results below; next stage BACKTEST → REVIEW)
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

- `roic_features` via `backtester.lake_api.read_features` — confirmed
  live (IMPLEMENT 2026-07-22, 7-ticker probe): columns include `ticker`,
  `event_time`, `cik`, `knowledge_time`, `nopat`, `invested_capital`,
  `roic`, plus several intermediate NOPAT-derivation fields. `roic` is
  null on ~53.75% of rows (chained through `nopat`/`pretax_income`/
  `effective_tax_rate` all nulling together on the same rows) — comparable
  in magnitude to `quality_features.gross_profitability`'s ~50-58%, though
  independently confirmed, not assumed by analogy. `knowledge_time` is
  genuinely spread 2009-2026 (fiscal-filing-anchored), matching
  `quality_features`' pattern, not `technical_features`' bulk-clustered
  one — confirms the spec's working assumption.
- `technical_features.ret_60d` via the same `read_features` path —
  confirmed live and column-present (IMPLEMENT 2026-07-22): null on
  <1% of rows, `knowledge_time` bulk-clustered within hours of the read
  (unlike `roic_features`), `event_time` spans 1990-2026. Confirms the
  spec's working assumption that `ret_60d` shares `vol_60d`'s
  event_time/knowledge_time behavior (both columns of the same dataset).
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

**BLOCKED — no results obtained.** Infra preflight passed (Lake API
`/docs` 200; MinIO `pit_sp500_ticker_universe` 709 tickers via
`.env`-configured probe). Re-bisected the standing `lake_api.read_bars`/
`read_features` recency defect first: unchanged (`end=2020-01-01`/
`2023-06-15`/`2026-07-03` all 0 rows, `end=2026-07-22` returns 1896
rows) — 6th consecutive trial confirming it, so walk-forward would have
been BLOCKED as usual. But the run never got that far: the full-period
backtest itself (`source="minio"`, 2016-01-01→2026-07-22, 709-ticker PIT
S&P 500 universe, monthly rebalance, 10bps cost) crashed with
`AssertionError: weight-mode position changes do not reconcile with
costed quantity deltas` at `backtester/portfolio/accounting/ledger.py:648`,
before any Sharpe/IR/report could be produced — a strictly worse outcome
than every prior trial in this loop, which at least got full-period
numbers even when walk-forward was blocked.

Root-caused via `systematic-debugging` (traceback-frame inspection of the
real run's `position_changes` vs. `cost_breakdown.quantity_deltas`
DataFrames at the assertion site, 465 diverging cells): this is a
genuine bug in the shared engine
(`backtester/portfolio/weight_cost.py::FixedBpsWeightCostModel.compute`),
not in `strategies/roic_momentum_blend.py`. The rebalance engine
(`backtester/portfolio/rebalance.py`) freezes an instrument's weight at
its last valid mark once its price permanently disappears (delisting) —
logged as a `UserWarning` this run for `AET`/`ANDV`/`BK`/`BMS`/`COL`/
`CSRA`/`ESRX`/`EVHC`/`HOT`/`SATS`/`SCG`/`TWX`. With weight frozen but NAV
still drifting, the ledger's own `position_changes` audit (computed from
`marked_prices = prices.ffill()`) correctly shows a nonzero implied
quantity change at every subsequent rebalance (`target_value = frozen
weight × NAV`, divided by the frozen price). But
`FixedBpsWeightCostModel.compute()` additionally masks its
`quantity_deltas` to `0.0` wherever the *raw* (non-forward-filled) price
is NaN (`quantity_deltas.mask(px.isna(), 0.0)`,
`backtester/portfolio/weight_cost.py:103`) — which is permanently true
for a delisted name — so the two audit trails are guaranteed to diverge
whenever a frozen/delisted instrument's weight stays nonzero across
multiple post-delisting rebalances. First confirmed divergence: CSRA,
2018-04-30 (`position_changes=-0.295`, `quantity_deltas=0.0`); 5 total
instruments (`CSRA`, `ANDV`, `AET`, `ESRX`, `SCG`) affected across 465
cells before the assertion (added in commit `21c53a5`, "fix: reconcile
costs and causal open fills") halted the run at the first mismatch.

This is data-dependent, not signal-dependent — any weight-mode strategy
holding a PIT-universe name through a real delisting event across enough
rebalances afterward would trip it. ROIC + momentum blend is simply the
first WIP in this loop's history to do so (prior trials' selections
apparently never held one of these specific names that long past
delisting). No strategy-level workaround exists: the freeze is enforced
by `RebalanceEngine` regardless of what `_compute_weights` signals for
future dates, once an instrument's price has gone permanently NaN.
Fixing it requires a change to shared `backtester/portfolio/weight_cost.py`
code, which is out of scope for a single research-loop stage (this loop's
`docs/research/`-only commit discipline and one-stage-per-run throttle
both assume strategy-file-only code changes, not shared-engine patches).
Per the loop's hard rule against faking numbers, this run stops without a
Sharpe/IR/cost-sweep result rather than reporting anything from the
crashed run.

**Routing decision (2026-07-22, second BACKTEST run):** code execution and
lake/MinIO access were both available this run (unlike some prior
unattended runs), so rather than stopping again on the same blocker, this
run acted on the "routing decision" option the prior run's Next-stage note
left open: excluded the 12 tickers confirmed to trigger the frozen-weight/
cost-model divergence (`AET`, `ANDV`, `BK`, `BMS`, `COL`, `CSRA`, `ESRX`,
`EVHC`, `HOT`, `SATS`, `SCG`, `TWX`) from the PIT universe passed into the
`Backtester` constructor — a universe-input change for this run only, not
a change to `strategies/roic_momentum_blend.py`'s selection/ranking logic.
This is disclosed as an engine-limitation workaround, not a performance
choice: these are almost entirely M&A-driven delistings (acquired, not
bankrupt), so the exclusion is not expected to introduce material
survivorship bias, but it does mean this trial's universe (697 of 709 PIT
names) is not identical to every prior trial's (709). With the exclusion,
the full-period backtest (`source="minio"`, 2016-01-04→2026-07-20,
697-ticker PIT S&P 500 universe, monthly rebalance, 10bps cost) completed
without error: Sharpe 0.6925, Total Return 266.50%, Max Drawdown -32.64%,
Ann. Volatility 17.06%, 127 rebalances (avg 20.9 days apart).

Mandatory IR-vs-benchmark gate: **FAIL** — IR -0.2205, active return
-1.69%/yr, ann. tracking error 7.66%, cumulative excess -65.26pts vs SPY
over 2650 aligned trading days (strategy cumulative return 266.50% vs
SPY's 331.76%), computed via the same manual active-return-mean/std
annualized method as every prior trial (`market_ref_bars_1d_yahoo_adj`'s
`close` column, not `adj_close`, per the standing lesson from Value
composite's BACKTEST).

Mandatory cost-sweep gate: **PASS** — Sharpe 0.7450→0.7188→0.6925→0.6400
across 0/5/10/20bps (~14.1% relative decay), degrades smoothly; between
the fundamental-composite trials' low sensitivity (Value composite ~2.3%)
and the faster-rebalanced/event-driven trials' high sensitivity (PEAD
~22%), consistent with this strategy's monthly (not quarterly or daily)
cadence.

Mandatory walk-forward gate: **BLOCKED** — re-bisected `lake_api.read_bars`'s
`end`-date recency defect first: unchanged (`end=2020-01-01`/`2023-06-15`/
`2026-07-03` all 0 rows, `end=2026-07-22` returns 2650 rows), 7th
consecutive trial confirming it; DSR/PBO consequently also BLOCKED/N/A,
same judgment call as every prior trial.

Regime evidence (diagnostic) gathered directly from `equity_curve.csv` vs
the same SPY series: COVID crash (2020-02-19→2020-03-23) strategy -31.90%
vs SPY -33.72% (**+1.82pts**, outperformed), 2022 bear market
(2022-01-03→2022-10-12) strategy -19.98% vs SPY -24.50% (**+4.51pts**,
outperformed). Both crisis windows show modest outperformance — milder
than the low-volatility family's consistent, larger protection
(COVID +3.09/+1.87pts, 2022 bear +11.74/+7.27pts across the ungated/gated
trials) but in the same defensive direction, plausibly the ROIC
(quality-linked) leg's contribution given no strong a-priori regime
prediction was pre-registered for this combination.

## Regime evidence

See the Results section above (COVID +1.82pts, 2022 bear +4.51pts vs SPY,
both crisis windows outperformed, milder than the low-volatility family's
protection). Full REVIEW-stage synthesis to follow.

## Verdict & lessons

Not yet reached — filled in at REVIEW.
