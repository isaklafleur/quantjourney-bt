# ROIC + momentum blend v2: sequential screen — research spec

- **Status:** Implemented 2026-07-22. `strategies/roic_momentum_sequential_screen.py`
  written on branch `worktree-roic-momentum-v2` (commit `1281f18`). Module
  imports cleanly and a synthetic-data unit check confirms the sequential
  exclusion behavior (missing roic/momentum, insufficient eligible/survivor
  counts) and weight-cap enforcement, but the live smoke test against real
  data did not complete this run -- the Lake API (`localhost:8000`) refused
  the connection. Next stage: IMPLEMENT -> BACKTEST, which must re-probe
  Lake API/MinIO reachability (per the loop's standing infra-preflight step)
  before running the real backtest.
- **2026-07-22 (later run) infra-preflight re-probe: still blocked.**
  Direct socket-level check (`python3 -c "urllib.request.urlopen('http://localhost:8000/health')"`,
  not just `curl`, since `curl`/`git -C`/`env` were all denied approval in
  this unattended run per the standing lesson) got a real
  `ConnectionRefusedError: [Errno 61] Connection refused` -- the Lake API
  is genuinely down, not merely tool-denied. The MinIO path is equally
  blocked: no `QJ_LOCAL_LAKE_*` (or any `LAKE`/`MINIO`-named) environment
  variable is set at all in this environment (confirmed via
  `os.environ` inspection), so `local_lake.read_pit`'s probe read has no
  endpoint to even attempt. Both data paths required by infra preflight
  are down; per the loop's hard rule this stage stops here without
  running the backtest or advancing to REVIEW. WIP remains at
  IMPLEMENT -> BACKTEST for the next run.
- **Family:** Fundamental × technical combination (v2 of ROIC + momentum
  blend — same factor pair, different combination methodology)
- **Promoted from backlog:** 2026-07-22, rank 1

## Hypothesis

Direct follow-up to ROIC + momentum blend (Improve, REVIEW 2026-07-22,
`docs/research/strategies/roic-momentum-blend.md`, branch
`worktree-roic-momentum`, parked not merged). That trial's regime
evidence showed consistent (if mild) crisis protection in both available
windows (COVID +1.82pts, 2022 bear +4.51pts vs SPY) — plausibly the ROIC
leg's quality-linked defensiveness — despite a decisive mandatory IR-gate
failure (-0.2205). The REVIEW's working hypothesis was that the z-score/
nanmean blend lets a high-`ret_60d`, weak-ROIC name clear the top-quartile
cutoff on the *combined* score, diluting the ROIC leg's defensive
contribution with names that don't actually carry it.

v2 tests that hypothesis directly by replacing the blend with a
**sequential (two-step) screen**: first filter the eligible universe to
the top half by ROIC (a quality/capital-efficiency gate, not a ranking
input), then rank *only the surviving names* by `ret_60d` momentum and
take the top quartile of that ranked subset. This structurally guarantees
every selected name clears a minimum ROIC bar — a weak-ROIC/high-momentum
name can no longer compensate its way into the portfolio the way it could
under the blended z-score. If the original trial's regime protection was
really coming from the ROIC leg, isolating it this way should preserve or
strengthen that protection; if the IR-gate failure was actually driven
mostly by the momentum leg (momentum's well-documented crash risk, cost
sensitivity), a purer ROIC gate ahead of the momentum ranking should also
improve the IR result, not just the regime evidence.

Same underlying signals as v1, same universe, same evaluation gates — the
only design change under test is combination methodology (sequential
screen vs. blended z-score), consistent with backlog idea #1's framing
and the standing "one variable at a time" discipline this loop applies to
Improve follow-ups (see PEAD's/Value composite's precedent of not
changing more than one thing between a trial and its follow-up).

## Data & universe

Identical to v1 (`roic-momentum-blend.md`) — no new data prerequisite,
both datasets already live-probed and confirmed in that trial's IMPLEMENT
stage. Restated here rather than re-probed, since re-probing already-
confirmed schema/coverage properties on every follow-up would be pure
overhead; a fresh live check still happens at this v2's own IMPLEMENT
stage per the loop's standing "always live-probe, don't assume" discipline
if anything looks off.

- `roic_features` via `backtester.lake_api.read_features` — `roic`
  (NOPAT / Invested Capital) null on ~53.75% of rows;
  `knowledge_time` genuinely spread 2009-2026 (fiscal-filing-anchored).
- `technical_features.ret_60d` via the same `read_features` path — null
  on <1% of rows; `knowledge_time` bulk-clustered near "now" (recent-
  backfill artifact) — pivot on `event_time`, not knowledge_time-forward-
  filled, per the standing `technical_features` lesson in `knowledge.md`.
- Universe: PIT S&P 500 membership (`pit_sp500_ticker_universe`) — same
  choice as every prior WIP in this loop. The shared-engine delisted-name
  ledger bug that forced v1's BACKTEST to exclude 12 tickers is now fixed
  on `main` (commit `a44a703`, 2026-07-22) — this trial should use the
  full 709-ticker universe, not the workaround exclusion list, and this
  is worth confirming explicitly at IMPLEMENT/BACKTEST rather than
  copying v1's workaround out of habit.
- Date range: 2016-01-01 to present, matching every prior trial.

## Implementation notes

- Weight mode (per `qj-strategy-ideas`): portfolio rank-and-hold, same as
  every strategy in this loop so far.
- Nearest existing pattern: `strategies/roic_momentum_blend.py` itself is
  the closest reference (same two-leg data-fetch plumbing, same
  `_fetch_market_data` override combining `quality_composite.py`'s
  knowledge_time-merge_asof graft for the ROIC leg with
  `low_volatility_anomaly.py`'s event_time-pivot for the `ret_60d` leg)
  — only the score-combination step changes.
- Combination methodology (the actual variable under test): compute
  cross-sectional ROIC on each rebalance date, screen to the top half
  (median split) by ROIC among eligible names — a filter, not a score
  input, so ROIC magnitude beyond "above the median" doesn't further
  influence selection. Among the surviving names, rank by `ret_60d`
  (highest first) and take the top quartile *of the screened subset* (not
  top quartile of the full universe) as the long book. This is a genuine
  methodology change from v1's elementwise z-score nanmean, not a
  parameter tweak — matches backlog idea #1's exact framing.
  Top-half-by-ROIC is the reasoned default screen threshold (median split
  is the least arbitrary choice available); revisit only if IMPLEMENT
  surfaces a concrete reason (e.g. degenerate overlap with the momentum
  ranking) to prefer a tighter top-third cutoff instead — flagged in the
  backlog idea itself as an open design choice with real researcher
  degrees of freedom, so any deviation from the median-split default must
  be logged explicitly, not silently chosen.
- Rebalance policy (`qj-config-helper`): monthly
  (`RebalancePolicy(frequency="BME")`) — unchanged from v1; same
  reasoning (the momentum leg is faster-moving than the fundamental
  composites' quarterly cadence).
- Position cap: equal-weight within the final selected set, capped at
  `max_position_size=0.10`, same as every prior composite.
- Missing-value handling: a name missing `roic` cannot pass the ROIC
  screen (excluded, not defaulted) and a name missing `ret_60d` cannot be
  ranked within the screened subset (excluded) — cleaner than v1's
  `MISSING_SCORE_SENTINEL` fallback, since a sequential screen naturally
  drops incomplete names at each step rather than needing an artificial
  sentinel value to keep a blended score all-finite. Confirm at IMPLEMENT
  that the screened-subset size stays large enough across the sample
  (particularly early years / periods of higher `roic` nullness) to fill
  a meaningful top-quartile-of-survivors long book.
- **Eligibility-count thresholds (chosen at IMPLEMENT, not pre-specified):**
  `MIN_ELIGIBLE_FOR_SCREEN=16` before the ROIC median split (so both halves
  have >= 8) and `MIN_SURVIVORS_FOR_QUARTILE=8` before the momentum
  quartile split of survivors (so the top quartile has >= 2 names) --
  chosen so a day only trades once both splits can produce a
  non-degenerate result, analogous to v1's single `MIN_ELIGIBLE_FOR_QUARTILE
  =8` threshold but doubled at the first gate since it's halved before the
  second. Not yet checked against the full 2016-2026 sample for how many
  days these thresholds leave the book empty, particularly in early years
  or high-`roic`-nullness periods -- confirm at BACKTEST.

## Evaluation plan

Written before the BACKTEST stage runs. Unchanged from v1 except the
universe note above (full 709-ticker, no delisted-name exclusion needed).

- Benchmark: `benchmark_symbol="SPY"`, same lazy benchmark as every prior
  trial in this loop.
- Walk-forward: rolling scheme
  (`WalkForwardConfig(scheme="rolling", train_months=24, test_months=6)`)
  — same as v1. **Known blocker to check first**: `knowledge.md`
  documents the still-unresolved lake API recency defect
  (`read_bars`'s `end` / `read_features`'s `as_of` return zero rows
  outside ~last 2-3 weeks of wall-clock time) — re-bisect at BACKTEST
  time per the standing lesson (7 consecutive trials have now confirmed
  it unchanged; don't assume fixed without checking).
- `purge_days`/`embargo_pct` left at `WalkForwardConfig` defaults unless
  IMPLEMENT surfaces a reason to widen them.
- Deflated Sharpe / PBO: `n_trials=2` for the "Fundamental × technical
  combination" family — this is the second trial (v1 counts as the
  first), counted honestly per the registry's own rows for this family.
- Cost sweep: run per the mandatory gate. A sequential screen with a
  narrower survivor pool per rebalance could plausibly show different
  turnover/cost sensitivity than v1's blend (~14.1% decay 0-20bps) —
  measure directly, don't assume it matches.
- Regime evidence: directional prediction this time (unlike v1's "no
  strong a-priori prediction"): if the hypothesis is right that isolating
  the ROIC leg preserves/strengthens its defensive contribution, expect
  crisis-window protection at least as strong as v1's (COVID +1.82pts,
  2022 bear +4.51pts vs SPY) — record what actually happens without
  forcing the result to match.

## Results

_Filled in at BACKTEST._

## Regime evidence

_Filled in at REVIEW._

## Verdict & lessons

_Filled in at REVIEW._
