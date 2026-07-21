# Low-volatility anomaly — research spec

- **Status:** WIP
- **Family:** Technical / risk-based
- **Promoted from backlog:** 2026-07-20, rank 1
- **Code:** none yet — next stage is SPEC → IMPLEMENT, on branch
  `worktree-low-vol-anomaly` (created via the native worktree tool, same
  reason as `worktree-quality-composite`: this session's Bash tool cannot
  be relied on to approve ref-mutating git commands unattended, so the
  research branch lives under the `worktree-<slug>` naming pattern rather
  than `research/<slug>`).

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

_Not yet run. Next stage: IMPLEMENT._

## Regime evidence

_Not yet gathered. Deferred to REVIEW, per the evaluation plan's
pre-registered expectation above._

## Verdict & lessons

_Not yet reached. Deferred to REVIEW._
