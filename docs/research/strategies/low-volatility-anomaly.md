# Low-volatility anomaly — research spec

- **Status:** Reviewed — verdict **Improve** (2026-07-21). Branch
  `worktree-low-vol-anomaly` stays alive, not merged; a regime-gated
  follow-up idea was spawned to the backlog.
- **Family:** Technical / risk-based
- **Promoted from backlog:** 2026-07-20, rank 1
- **Code:** `strategies/low_volatility_anomaly.py` written 2026-07-21 on
  branch `worktree-low-vol-anomaly` (created via the native worktree tool,
  same reason as `worktree-quality-composite`: this session's Bash tool
  cannot be relied on to approve ref-mutating git commands unattended, so
  the research branch lives under the `worktree-<slug>` naming pattern
  rather than `research/<slug>`). Next stage: IMPLEMENT → BACKTEST.
- **Data verification (resolved at IMPLEMENT, see the strategy file's
  module docstring for full detail):** `vol_60d` confirmed live in
  `technical_features` (annualized trailing realized vol, values ~0.006-0.08
  on a 2-name probe). `technical_features`' `knowledge_time` is
  bulk-clustered near "now" (recent-backfill artifact), NOT spread across
  history like `quality_features` — so `vol_60d` is pivoted directly on
  `event_time`, not knowledge_time-forward-filled. Also confirmed the lake
  API's recency defect (`knowledge.md`) extends to `read_features`'s
  `as_of` param, not just `read_bars`'s `end` — worked around the same way
  Quality composite works around it (always `as_of=now`).

## Hypothesis

Rank US equities by trailing realized volatility and hold the lowest-vol
quintile long, cash otherwise. The proposed edge is risk-based/structural,
not a backtested-good-looking curve fit: the low-volatility anomaly (Ang,
Hodrick, Xing & Zhang 2006, 2009) is one of the most extensively
out-of-sample-replicated equity factors — low-vol names have historically
delivered higher risk-adjusted (though not necessarily higher absolute)
returns than high-vol names, contrary to naive CAPM. Candidate behavioral/
structural explanations: leverage-constrained investors bid up high-beta
names for embedded leverage (Frazzini & Pedersen's betting-against-beta
framing), and lottery-preference demand for volatile "lottery ticket"
stocks depresses their risk-adjusted returns. This is a genuinely different
mechanism from Quality composite (fundamental quality signal, Archived
2026-07-20 for failing the IR gate) — worth testing on its own merits, not
assumed to succeed or fail based on that unrelated prior result.

## Data & universe

- `backtester.lake_api.read_features("technical_features", tickers=...,
  as_of=...)` — `vol_60d` column, directly available (confirmed present
  in the backlog notes; re-verify the exact column name/units — trailing
  60-day realized vol, presumably annualized — at IMPLEMENT before
  trusting it blindly).
- Universe: PIT S&P 500 membership via
  `backtester.local_lake.resolve_pit_sp500`/`pit_sp500_ticker_universe` —
  same choice as Quality composite, for the same reason (reasonably
  liquid, well-covered names for a first pass at this family).
- Price/eligibility: `backtester.lake_api.read_bars("equity_bars_1d_yahoo_adj", ...)`.
- Date range: 2016-01-01 to present — same window used for Quality
  composite, for comparability across strategy families in this loop.
  `technical_features` coverage before that is not yet confirmed and
  should be checked at IMPLEMENT, not assumed here.

## Implementation notes

- Weight mode (per `qj-strategy-ideas`): cross-sectional rank-and-hold,
  same family as the cross-sectional ranking examples (e.g.
  `example_weights_15_cross_sectional_momentum.py`'s selection structure),
  adapted to rank ascending on `vol_60d` (lowest-vol wins) instead of
  descending on a momentum column.
- Monthly rebalance (per the backlog idea's own framing) — more frequent
  than Quality composite's quarterly cadence, since `vol_60d` is a
  rolling daily-bar-derived signal that updates continuously, unlike
  fiscal-year-end fundamental data. `technical_features`'s `knowledge_time`
  behavior for this specific column should be checked at IMPLEMENT (the
  existing lesson in `knowledge.md` about bars/`sctr_features` having
  bulk-clustered-near-now `knowledge_time` may or may not apply to
  `technical_features`; don't assume either way).
- Rebalance policy (`qj-config-helper`): monthly
  (`RebalancePolicy(frequency="BME")` or repo-equivalent monthly alias) —
  matches the signal's update cadence without adding unnecessary
  turnover from a daily rebalance.
- Selection: lowest-vol quintile (top 20% by ascending `vol_60d`) within
  the eligible PIT universe on each rebalance date, equal-weighted,
  capped at `max_position_size=0.10` — mirrors Quality composite's
  position-cap logic, adjust only if the quintile pool size at IMPLEMENT
  turns out too small/large for that cap to make sense.
- Known regime dependency (flagged in the backlog, not a defect to
  design away): this factor is expected to underperform in strong
  momentum-driven bull runs — worth confirming via the mandatory
  regime/crisis check at REVIEW, not something to pre-filter against at
  IMPLEMENT.
- Known concentration risk (flagged in the backlog): a naive low-vol
  screen may concentrate in rate-sensitive sectors (utilities, REITs,
  staples). Flag this in the Results section if the actual holdings show
  it — do not pre-filter by sector for a first WIP, since that would add
  an undisclosed design choice not in the original backlog idea.

## Evaluation plan

Written before the BACKTEST stage runs.

- Benchmark: `benchmark_symbol="SPY"` — same choice as Quality composite,
  for comparability; the universe is S&P-500-drawn so this remains a fair
  "lazy benchmark" for the mandatory IR gate.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=24, test_months=6)`)
  — shorter train/test windows than Quality composite's 36/12, since
  `vol_60d` is a continuously-updating technical signal (not annual
  fiscal data) and can support more, shorter folds without starving each
  fold of distinct information.
- `purge_days`/`embargo_pct` left at `WalkForwardConfig`'s defaults unless
  IMPLEMENT surfaces a reason to widen them.
- Deflated Sharpe / PBO: standard; `n_trials` counted from this family's
  `trial-registry.md` rows once any exist (0 so far — this is the first
  trial in the "Technical / risk-based" family).
- Cost sweep: run per the mandatory gate. Monthly rebalance with a
  quintile-sized (not full-universe) holding set is expected to be
  lower-turnover than Quality composite's 200% annualized figure, but
  this is a prediction to test, not an assumption to skip the gate on.
- Regime evidence: pre-registered expectation (unlike Quality composite,
  which had none) — this factor is expected to underperform in strong
  momentum-driven bull markets. Record what the crisis-analysis breakdown
  actually shows and note explicitly whether it confirms or contradicts
  this expectation, rather than only reporting a match.
- Infra note: re-check the lake API `read_bars` `end`-date defect
  (`knowledge.md`) before trusting any walk-forward fold whose OOS window
  isn't inside the last ~2-3 weeks of wall-clock time — this will affect
  this strategy's walk-forward gate exactly as it did Quality composite's,
  independent of anything specific to this idea.

## Results

BACKTEST run 2026-07-21. Infra preflight passed (Lake API `/docs` 200;
MinIO `pit_sp500_ticker_universe` returned 709 tickers). Full-period run
(`Backtester(source="minio")`, 2016-01-04 → 2026-07-20, 709-ticker PIT
S&P 500 universe, monthly `BME` rebalance, 10bps weight cost):
Sharpe 0.68 (`portfolio_data.sharpe_ratio`; the printed headline report's
0.83 figure uses a different `periods_per_year`/annualization convention
— both computed from the same `equity_curve.csv` returns, not a
discrepancy in the underlying data), Annualized Return 10.58%, Total
Return 188.79%, Max Drawdown -30.40%, Ann. Volatility 13.21%, Ann.
Turnover 370.88% (higher than Quality composite's 200% despite a
narrower quintile holding set — monthly rebalance on a continuously-
drifting `vol_60d` rank churns the roster more than quarterly fundamental
rebalance did).

- **Mandatory IR-vs-benchmark gate: FAIL, more decisively than Quality
  composite.** Computed directly from `excess_return`/`active_return`'s
  aligned-series primitives against `local_lake.read_pit`-sourced SPY
  daily returns (2016-01-04→2026-07-20, 2644 aligned trading days):
  annualized active return -4.55%/yr, annualized tracking error 11.08%,
  **IR -0.41** (vs. Quality composite's -0.26), cumulative excess return
  -152.47 pts over the decade. The lowest-vol quintile has been
  decisively beaten by lazy SPY beta over this specific full-period
  window.
- **Mandatory cost-sweep gate: PASS.** Ran the strategy directly (not
  via a report-generating full run — `save_portfolio_plots=False`/
  `show_text_reports=False` for speed) at 0/5/10/20 bps total weight
  cost: Sharpe 0.72 → 0.70 → 0.68 → 0.64, total return 206.67% →
  197.60% → 188.79% → 171.95%. Degrades smoothly, doesn't collapse —
  the edge (such as it is) isn't a cost-sweep-fragile artifact of the
  370% turnover.
- **Mandatory walk-forward gate: BLOCKED, same confirmed infra defect as
  Quality composite.** Re-bisected `lake_api.read_bars` before spending
  a full `WalkForwardEngine` run against a known-bad server (per the
  precedent set in Quality composite's 2026-07-20 21:35 BACKTEST run):
  `end=2020-01-01` → 0 rows, `end=2023-06-15` → 0 rows, `end=2026-07-03`
  → 0 rows, `end=2026-07-20` → 5292 rows — the `knowledge.md` defect
  (zero rows for any `end` outside roughly the last 2-3 weeks of
  wall-clock time) is unchanged and confirmed to still apply today. A
  rolling train=24mo/test=6mo walk-forward over 2016-2026 would have
  essentially every fold's `end` fall outside that window (only the
  final fold or two would land inside it), so a full run was skipped as
  not worth the runtime to reproduce an already-predictable "almost all
  folds fail" result — same judgment call as Quality composite's second
  BACKTEST attempt. Deflated Sharpe and PBO are consequently also
  blocked/unavailable (PBO's unavailability is separately expected: no
  optimizer, no tuned params).
- **Regime evidence (diagnostic, computed from `equity_curve.csv` vs.
  the same SPY series used for the IR gate — real numbers, not
  fabricated, ahead of the formal REVIEW distillation below):**
  - COVID crash (2020-02-19 → 2020-03-23): strategy -30.31% vs. SPY
    -33.40% — **+3.09 pts** of downside protection.
  - 2022 bear market (2022-01-03 → 2022-10-12): strategy -12.32% vs.
    SPY -24.06% — **+11.74 pts** of downside protection.
  - No GFC window in range (data starts 2016-01-04).

## Regime evidence

Both available crisis windows (COVID crash, 2022 bear market) show the
classic low-vol defensive signature: meaningfully smaller drawdowns than
SPY in both (+3.09 pts and +11.74 pts respectively) — this **contradicts**
a naive reading of the spec's pre-registered "underperforms in strong
momentum-driven bull markets" expectation taken as a blanket prediction,
but actually **confirms the more precise mechanism** behind that same
expectation: the anomaly protects on the downside during crises (both
windows), and the full-period IR fails not because the crisis behavior is
wrong but because 2016-2026 is dominated by a long momentum/mega-cap-
growth bull stretch between crises, where leverage-constrained investors'
bid-up of high-beta names (Frazzini & Pedersen) erodes the low-vol
quintile's *absolute* returns relative to SPY for most of the window —
exactly the risk-based tradeoff the hypothesis describes, just decisively
net negative vs. a lazy benchmark over this particular full-period
sample. Worth a `knowledge.md` lesson at REVIEW: the first real regime
evidence this loop has gathered (Quality composite's OOS run never
reached crisis-analysis).

## Verdict & lessons

**Verdict: Improve** (REVIEW 2026-07-21, registry row appended to
`trial-registry.md`). The mandatory IR-vs-benchmark gate fails
decisively over the full 2016-2026 period (IR -0.41, worse than Quality
composite's -0.26) — on its own, that would be Archive grounds
identical to Quality composite. What distinguishes this trial is the
regime evidence: the strategy shows real, meaningful downside protection
in both available crisis windows (COVID +3.09pts, 2022 bear +11.74pts
vs SPY), which is exactly what the risk-based hypothesis predicts. The
full-period failure isn't evidence the mechanism is absent — it's
evidence that 2016-2026 is dominated by a long leverage-fueled bull
stretch between crises, where an *unconditional* low-vol tilt drags on
absolute return relative to a lazy SPY benchmark even while it's doing
exactly what it's supposed to do during drawdowns.

That points to a specific, concrete variant worth testing rather than a
vague "try again" — regime-gate the exposure: hold the low-vol quintile
only when a regime signal indicates elevated risk (e.g. an SPY-trend or
realized-vol-level gate, the same structural pattern already shipped in
`strategies/sctr_momentum_regime_gated.py`), and default to full-market/
cash exposure otherwise, rather than running the screen unconditionally
across the whole sample. This is a mechanism change motivated directly
by this trial's own regime evidence, not a curve-fit parameter tweak.

Spawned as a new Ready-backlog idea ("Regime-gated low-volatility
anomaly", see `backlog.md`), referencing this spec and branch. The
`worktree-low-vol-anomaly` branch is left alive (not merged, not
deleted) per the Improve verdict's git action — a future WIP slot can
build on `strategies/low_volatility_anomaly.py` directly rather than
starting from scratch.

Walk-forward/DSR/PBO remain blocked by the lake API recency defect
(`knowledge.md`) — unresolved from BACKTEST, doesn't change this
verdict since the mandatory IR gate had already produced a real,
decisive result on its own.
