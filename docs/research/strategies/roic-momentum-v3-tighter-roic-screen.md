# ROIC + momentum blend v3: tighter ROIC screen — research spec

- **Status:** Draft (PROMOTE stage — spec only, no code yet)
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
- **Eligibility-count thresholds — flagged as an open design question for
  IMPLEMENT, not decided here.** v2 used `MIN_ELIGIBLE_FOR_SCREEN=16`
  (so a median split leaves >= 8 survivors) and
  `MIN_SURVIVORS_FOR_QUARTILE=8` (so the top quartile of survivors has
  >= 2 names). A top-third split of the same 16-name floor would leave
  only ~5 survivors — below v2's own `MIN_SURVIVORS_FOR_QUARTILE=8`
  threshold — so IMPLEMENT must either raise `MIN_ELIGIBLE_FOR_SCREEN`
  (e.g. to ~24, so a third leaves >= 8) or lower
  `MIN_SURVIVORS_FOR_QUARTILE` proportionally; whichever is chosen, log
  the reasoning explicitly rather than silently reusing v2's numbers,
  and confirm at BACKTEST how many days/rebalances the tighter screen
  leaves the book empty relative to v2, particularly in early years or
  periods of higher `roic` nullness.

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

_Not yet run — filled in at BACKTEST._

## Regime evidence

_Not yet gathered — filled in at REVIEW._

## Verdict & lessons

_Not yet decided — filled in at REVIEW._
