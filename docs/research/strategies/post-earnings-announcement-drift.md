# Post-earnings-announcement drift (PEAD) — research spec

- **Status:** Archived (REVIEW complete, 2026-07-21)
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

## Code

`strategies/post_earnings_announcement_drift.py`, committed on
`worktree-pead` (`a6add37`). Live-probed `earnings_surprise` before
writing any code (see below) rather than trusting the backlog's assumed
schema.

Schema confirmed: columns are `ticker`, `event_time` (fiscal period end),
`cik`, `knowledge_time`, `net_income`, `net_income_prev_year`, `yoy_diff`,
`sue`, `source`, `dataset`. `sue` is present as assumed. `knowledge_time`
lags `event_time` by ~26-38 days (mean 32) and is genuinely spread across
history (2008-2026 for large caps) — behaves like `quality_features`, not
`technical_features` — so PIT handling uses the same
`knowledge_time`-anchored `merge_asof` forward-fill `quality_composite.py`
established, extended with a companion days-since-event panel so entries
gate to "shortly after" an announcement (`ENTRY_WINDOW_DAYS=5` trading
days) rather than any day a stale SUE value is still on file.

Confirmed the fiscal Q4/annual gap flagged in the backlog/spec: both AAPL
(fiscal Q4 = Sept quarter) and MSFT (fiscal Q4 = June quarter) are
consistently missing that one quarter's row every year starting around
fiscal 2021 — dataset-wide, not ticker-specific. Handling choice made:
no special-casing, that quarter simply produces no signal for the
affected name that year (spec's simpler option; no fabricated
staleness-capped carry-forward).

Confirmed entry-pool density against the real 2023 PIT S&P 500 universe
(514 names): weekly announcement counts are highly seasonal (median
7/week) but 100+ names report in each of the four one-week earnings-season
peaks/year (max observed 171) — set `MIN_ELIGIBLE_FOR_QUINTILE=10` low
enough to activate during those peaks while naturally sitting idle most
other weeks (expected for an event-driven strategy, not a bug).

Design choices made (mode/cutoff/window were left open by the spec):
weight mode with an event-driven eligibility mask, modeled directly on
`sctr_momentum_regime_gated.py`'s day-by-day incumbent-priority
`_build_regime_gated_weights` pattern (see `_build_pead_weights`) but with
purely time-based exit (fixed `HOLDING_DAYS=60` trading days) instead of
threshold-based hold/exit — the defining PEAD mechanic per Bernard &
Thomas 1989. Top quintile (`SUE_TOP_QUANTILE=0.80`), not decile, chosen
for a more diversified long book given the small daily entry-pool sizes.
Daily rebalance (`RebalancePolicy(frequency="D")`), unlike the
calendar-rebalanced trials so far, since entries can occur on any trading
day. Ran the `qj-strategy-reviewer` checklist against the file (timing,
data handling, weights/exposure, costs, mode fit) — no issues found; the
equal-weight cap formula (`min(1/len(held), max_position_size)`) is the
same one already used in `low_volatility_anomaly.py`/`quality_composite.py`
and keeps weight sums ≤ 1 by construction.

Smoke-tested end-to-end (`strategies/_smoke_pead.py`, committed alongside):
15 tickers, 2024-01-02→2026-07-20, 638 dates/rebalances, 60 days with a
non-zero position, max row-sum 0.30 (≤ cap), all-finite weights and SUE
signal. Full `pytest tests/ -q` green after (169 passed) — no manifest
fix needed this time since the spec file was already added to
`release/public_artifacts.txt` at PROMOTE.

## Results

Infra preflight passed: Lake API `/docs` 200; MinIO `pit_sp500_ticker_universe`
returned 709 tickers. Ran the full-period backtest (`Backtester(source="minio")`,
2016-01-04→2026-07-20, 709-ticker PIT S&P 500 universe, daily rebalance
(`RebalancePolicy(frequency="D")`), 10bps cost, via a scratch driver script
importing `PostEarningsAnnouncementDrift` from `worktree-pead`, deleted after
the run): Sharpe 0.73, Sortino 1.02, Annualized Return 11.87%, Total Return
226.18% (print_summary) / 230.52% (independently computed from
`equity_curve.csv`'s `net_asset_value` — same two-report-surface
annualization-convention discrepancy on the same underlying returns already
noted for the Low-volatility anomaly trial, not a real inconsistency), Max
Drawdown -37.28%, Calmar 0.32, Ann. Vol 17.51%, Ann. Turnover 702.59% (by far
the highest of any trial in this loop, as the spec anticipated for a
turnover-heavy event strategy with daily rebalance).

Mandatory IR-vs-benchmark gate: **FAIL**, the most decisive of any trial so
far — IR -0.48, active return -2.82%/yr, cumulative excess -111.54pts vs SPY,
2016-01-04→2026-07-20 (computed via the same `excess_return`/`active_return`-
style aligned-daily-series method as all three prior trials, no
`information_ratio` helper exists). Notably, the annualized tracking error
(5.83%) is much *lower* than the low-volatility trials' (~11pts implied) —
investigated why rather than assumed: `weights.csv` shows the strategy holds
72 names on average (min 0, max 114) and is invested (gross exposure >0.1%)
on 99.96% of days, mean gross exposure 0.95 — i.e. despite genuinely sparse
*new*-entry weeks (median 7 qualifying announcements/week, per the code's own
docstring), the fixed 60-trading-day hold means overlapping cohorts from
consecutive entry weeks keep the book almost continuously ~95% invested
across ~70-90 names. This is a broad, highly-diversified long book in
practice, not the "idle most other weeks" character the code's docstring
implies (that docstring's claim is about new-entry cadence, not net market
exposure) — closer to the market in composition, hence lower tracking error,
but the IR gate still fails more decisively than any prior trial because the
active-return drag is large relative to that smaller tracking error.

Mandatory cost-sweep gate: **PASS**, but the steepest degradation of any
trial so far, as the spec anticipated — Sharpe 0.819→0.775→0.73→0.641 across
0/5/10/20bps (a ~22% relative decay 0bps→20bps, vs. Quality composite's
~1.7%, Low-vol's ~11%, Regime-gated's ~5%), total return 284.01%→253.92%→
226.18%(printed)/230.52%(computed)→177.05%. Consistent with the 702.59%
annualized turnover being far higher than any prior trial's. The edge
survives realistic costs (stays clearly positive-Sharpe at 20bps) but is
genuinely more cost-sensitive than every prior strategy in this loop.

Mandatory walk-forward gate: **BLOCKED** — re-bisected `lake_api.read_bars`'s
`end`-date defect before spending a full `WalkForwardEngine` run (same
judgment call as all three prior trials): confirmed unchanged today
(`end=2020-01-01`/`2023-06-15`/`2026-07-03` all 0 rows, `end=2026-07-21`
returns 5300 rows) — 4th consecutive trial hitting the identical server-side
defect. A rolling train=24mo/test=6mo walk-forward would strand nearly every
fold's `end` outside the ~2-3-week served window, so skipped running it in
full rather than reproduce an already-predictable non-result; DSR/PBO
consequently also blocked/N/A.

## Regime evidence

Gathered directly from `equity_curve.csv`'s `net_asset_value` vs. the same
SPY series used for the IR gate (diagnostic, not a gate; PEAD's behavioral
mechanism has no clear a-priori crisis-regime prediction, so this is
exploratory per the spec). Mixed, not uniformly protective or exposed:

- **COVID crash** (2020-02-19→2020-03-23): strategy -37.28% vs SPY -33.72%
  (**-3.56pts**, underperformed) — the strategy was ~95% gross-invested
  across ~72 names throughout the entire window (confirmed directly from
  `weights.csv`, not assumed), so positions opened on pre-crash earnings
  surprises were fully exposed to the crash alongside the broad market, with
  no defensive mechanism to reduce that exposure — unlike the low-volatility
  trials, which showed genuine crisis protection by construction.
- **2022 bear market** (2022-01-03→2022-10-12): strategy -16.08% vs SPY
  -24.50% (**+8.42pts**, outperformed) — same ~95% gross exposure held
  throughout this window too (also confirmed from `weights.csv`), so this
  isn't a being-in-cash effect; more likely reflects which names' SUE-driven
  drift happened to hold up better during a slower, valuation-driven decline
  than a market-wide panic like COVID.
- No GFC window in range (data starts 2016-01-04), consistent with every
  prior trial in this loop.

## Verdict & lessons

**Archive.** The mandatory IR-vs-benchmark gate failed more decisively
than any prior trial in this loop (-0.48 vs. Quality composite's -0.26,
Low-vol's -0.41, Regime-gated Low-vol's -0.41), and — unlike the
low-volatility family, whose consistent crisis-window protection in both
available windows motivated Improve — PEAD's regime evidence is mixed,
not consistently compensating: it underperformed in the COVID crash
(-3.56pts) and outperformed in the 2022 bear (+8.42pts). Per the spec's
own pre-registration, PEAD's behavioral mechanism has no a-priori
crisis-regime prediction to confirm or contradict, so this mixed result
reads as noise rather than a signature worth building a gated variant
around — there is no single, clear "protect in window X" finding the way
the low-vol family had to motivate a specific next design. Combined with
the steepest cost-sweep decay of any trial (~22% Sharpe decay 0→20bps,
vs. every prior trial's <11%) and the highest turnover (702.59%
annualized), the strategy's edge is both weak on a risk-adjusted,
benchmark-relative basis and unusually fragile to real-world cost
assumptions. No specific salvageable variant presents itself the way
regime-gating did for low-vol, so Archive rather than Improve.

Lessons distilled to `knowledge.md`:
- A fixed-holding-window event strategy with a sparse weekly entry rate
  (median 7/week here) is not the same as a sparsely-invested strategy:
  overlapping cohorts from consecutive entry weeks kept this book ~95%
  gross-invested across ~72-90 names on 99.96% of days — a broad,
  market-like long book in practice, confirmed directly from
  `weights.csv`, not assumed. Don't infer net exposure from entry-event
  sparsity for any future fixed-hold event-driven design in this loop.
- A behavioral (non-risk-based) mechanism's regime evidence can be
  genuinely mixed (protective in one crisis, not in another) without
  that being a bug or a modeling error — it just means the mixed result
  carries little design signal, unlike a risk-based mechanism's
  consistent-by-construction regime signature (contrast with the
  low-volatility family).
- Turnover-heavy event strategies can show *lower* tracking error than
  calendar-rebalanced factor screens despite a decisively worse IR
  (PEAD: 5.83% ann. TE vs. low-vol's ~11pts implied) precisely because a
  near-continuously-invested, broadly diversified book is closer in
  composition to the benchmark — don't use tracking-error magnitude
  alone as a proxy for how much a strategy's exposure resembles the
  benchmark's.
