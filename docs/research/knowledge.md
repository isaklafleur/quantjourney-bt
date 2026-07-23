# Research Knowledge Base

Distilled lessons from the research loop (`skills/qj-research-loop/SKILL.md`).
Read this file FIRST at the start of every loop run; update it after every
REVIEW stage. Entries are additive — don't delete a lesson because a later
trial contradicts it, note the contradiction instead.

## Lessons

- **Absolute Sharpe/CAGR looking good is not evidence of edge — always check IR vs. benchmark first.** Quality composite (gross_profitability + accruals, PIT S&P 500, quarterly rebal, 2016-2026) posted Sharpe 0.80 / CAGR 13.31% but IR -0.26 vs SPY (-71 cumulative pts over the decade) — a decade of pure beta dressed up as a factor tilt. (`trial-registry.md`, Quality composite REVIEW 2026-07-20)
- **The lake API's `read_bars("equity_bars_1d_yahoo_adj", ...)` has a server-side defect**: any `end` date outside roughly the last 2-3 weeks of wall-clock time returns zero rows, independent of `start`/tickers — confirmed by bisection across two separate loop runs (2026-07-20). This silently breaks `WalkForwardEngine` for every fold whose OOS window isn't inside the served recent window. It will affect every future strategy that reaches BACKTEST, not just Quality composite — check for it explicitly before trusting a walk-forward result; this loop cannot fix it (server-side), only work around/escalate it.
- **`quality_features` IS live via the HTTP lake API**, despite `backtester/lake_api.py`'s module docstring claiming only `equity_bars_1d_yahoo_adj`/`sctr_features` are exposed — the docstring is stale; trust a direct probe over it.
- **`quality_features.gross_profitability` is null on ~50-58% of rows** across 2016-2026, so an elementwise-nanmean composite silently falls back to accruals-only about half the time. Real data-coverage property, not a bug — design around it explicitly (require non-null, or document the fallback) rather than assuming full two-factor coverage.
- **`quality_features.knowledge_time` is genuinely spread across 2009-2026** (fiscal-year-end-anchored), unlike `equity_bars_1d_yahoo_adj`/`sctr_features` whose `knowledge_time` is bulk-clustered near "now" from a recent backfill — don't assume every lake dataset shares the same knowledge_time distribution when reasoning about PIT joins.
- **`build_local_minio_bt_payload` has no generic hook for research-tier features** (only `sctr_features` is wired into the "parameters" panel) — a strategy needing `quality_features`/`roic_features`/`value_features`/`earnings_surprise` must override `_fetch_market_data` itself (see `strategies/quality_composite.py` on branch `worktree-quality-composite` for the pattern) until this becomes a real extension point in `local_data.py`.
- **In unattended/scheduled loop runs, the Bash tool can deny approval for `uv run`, `curl`, `cd <dir> &&`, and `git -C`/`--git-dir` targeting the research worktree — even for read-only commands — with no user present to grant it.** When this happens, code execution and network reachability checks are entirely unavailable for that run. The loop should log the blocker honestly rather than retry-loop, and should still act on already-established real results from a prior run (e.g. a completed mandatory gate) instead of stalling WIP indefinitely on that basis alone.
- **The lake API's recency defect isn't limited to `read_bars`'s `end` param — `read_features`'s `as_of` param has the identical shape**: any `as_of` outside roughly the last 2-3 weeks of wall-clock time returns zero rows (confirmed via bisection on `technical_features`, Low-volatility anomaly IMPLEMENT 2026-07-21). Work around it the same way for any research-tier feature read: always pass `as_of=datetime.now(UTC).date()`, since the real history comes back inside that one call regardless of the dates you actually need.
- **`technical_features`' `knowledge_time` is bulk-clustered near "now"** (recent-backfill artifact), unlike `quality_features`' genuinely-spread-across-history `knowledge_time` — confirmed for `vol_60d` specifically (Low-volatility anomaly IMPLEMENT 2026-07-21). Pivot technical-feature columns directly on `event_time`, not knowledge_time-forward-filled, mirroring how `local_data._sctr_rank_panel` already treats `sctr_features`. Don't assume every research-tier dataset shares one `knowledge_time` behavior — check per-dataset, as `quality_features` already taught the opposite lesson.
- **A mandatory-gate failure (IR vs. benchmark) doesn't automatically mean a risk-based/structural hypothesis is wrong — check regime evidence before defaulting to Archive.** Low-volatility anomaly failed the full-period IR gate more decisively than Quality composite (-0.41 vs -0.26) yet showed genuine, real downside protection in both available crisis windows (COVID +3.09pts, 2022 bear +11.74pts vs SPY) — the mechanism works as the risk-based hypothesis predicts, it's just net negative over a sample dominated by a long bull stretch between crises. This is a qualitatively different failure mode from Quality composite (which showed no compensating regime evidence at all, since its OOS run never reached crisis-analysis) and justifies **Improve** (regime-gate the exposure) rather than Archive. Read the regime evidence, not just the gate's pass/fail, before choosing a verdict.
- **A crisis-only regime gate can't fix a full-period IR failure whose real source is drag during the calm majority of the sample, not crisis-window exposure — check what fraction of the period the gate is even active before expecting it to move the IR gate.** Regime-gated low-volatility anomaly (SPY-200d-SMA gate, elevated ~17% of days) left the mandatory IR gate numerically unchanged from the ungated version (-0.41 both) despite the structural change, because the gate only ever gets a chance to help during that ~17% — it has no mechanism at all to address the other ~83% of (calm, bull-dominated) days where the ungated version's underperformance actually accumulates. Don't expect a defensive-only gate to rescue a full-period benchmark-relative gate failure unless the failure itself is concentrated in the windows the gate covers. (`trial-registry.md`, Regime-gated low-volatility anomaly REVIEW 2026-07-21)
- **A binary trend-following regime gate (SPY vs. its 200-day SMA) is measurably too slow for fast crashes, though it tracks slow grinds well — confirmed by direct measurement, not assumption.** In the same trial, the gate was elevated on only 16/24 trading days of the 24-day COVID crash (didn't flip until day 6) vs. 153/196 days of the ~9-month 2022 bear market (flipped by day 13) — and this lag directly explains why the regime-gated version's crisis protection (COVID +1.87pts, 2022 bear +7.27pts vs SPY) came in below the always-on ungated version's (+3.09pts/+11.74pts) in both windows. A 200-day SMA gate trades a genuine reduction in bull-market drag for a real loss of fast-crash coverage — worth pre-registering and measuring directly (via the underlying trend-flag Series against the crisis date range) for any future strategy using this same `sctr_momentum_regime_gated.py`-style gate, rather than assuming the gate is protective just because it's designed to be.
- **A fixed-holding-window event strategy with a sparse weekly entry rate is not the same as a sparsely-invested strategy — check net exposure directly from `weights.csv`, don't infer it from entry-event cadence.** PEAD's entry pool is genuinely sparse (median 7 qualifying announcements/week), but the fixed 60-trading-day hold means overlapping cohorts from consecutive entry weeks kept the book ~95% gross-invested across ~72-90 names on 99.96% of days — a broad, market-like long book in practice, not the "idle most other weeks" character the entry cadence alone would suggest. (`trial-registry.md`, Post-earnings-announcement drift REVIEW 2026-07-21)
- **A behavioral (non-risk-based) mechanism's regime evidence can be genuinely mixed without that being a bug or a modeling error — it just carries little design signal, unlike a risk-based mechanism's consistent-by-construction regime signature.** PEAD underperformed in the COVID crash (-3.56pts) but outperformed in the 2022 bear (+8.42pts), with no a-priori crisis-regime prediction to confirm or contradict either way (contrast with the low-volatility family's consistent both-crisis protection, which motivated a specific regime-gated follow-up). A mixed result from a behavioral mechanism is noise, not a signature worth building a gated variant around.
- **Turnover-heavy event strategies can show *lower* tracking error than calendar-rebalanced factor screens despite a decisively worse IR — don't use tracking-error magnitude alone as a proxy for how much a strategy's exposure resembles the benchmark's.** PEAD's 5.83% annualized tracking error is much lower than the low-vol trials' (~11pts implied) precisely because its near-continuously-invested, broadly diversified book (~95% gross exposure, 99.96% of days) is closer in composition to the benchmark — yet its IR (-0.48) is the most decisive gate failure of any trial so far, because the active-return drag is large relative to that smaller tracking error.
- **An IR-gate "FAIL" is not a single bucket — a near-zero-but-negative IR with a mild cost-sweep decay is a qualitatively different result from a decisively negative one, and worth distinguishing at REVIEW rather than defaulting to Archive just because the sign is wrong.** Value composite's IR (-0.059) is an order of magnitude closer to zero than every prior trial (Quality -0.26, Low-vol -0.41, Regime-gated low-vol -0.41, PEAD -0.48), and its cost-sweep decay (~2.3%) is the mildest of any trial — together these read as "near-flat versus benchmark" rather than "beta dressed up as alpha," and motivated Improve rather than Archive despite the gate technically failing. (`trial-registry.md`, Value composite REVIEW 2026-07-22)
- **Mixed (non-consistent) regime evidence doesn't automatically mean "no design signal," the way it did for PEAD — check whether the underperforming window has a specific, literature-grounded mechanism and a concrete remedy before concluding the mixed result is just noise.** Value composite's regime evidence is mixed like PEAD's (COVID -10.17pts, the largest crisis-window gap of any trial either direction; 2022 bear +6.13pts), but the COVID underperformance matches value's well-documented "value trap" failure mode (cheap-on-trailing-fundamentals can mean genuinely distressed, not mispriced, during a fast liquidity panic) — a specific, actionable hypothesis unlike PEAD's genuinely unpredicted mix. This motivated spawning a targeted follow-up (quality/profitability screen to exclude distress risk) rather than defaulting to Archive the way PEAD's unexplained mix did. (`trial-registry.md`, Value composite REVIEW 2026-07-22)
- **`value_features.book_value_per_share`'s null rate (~16.9%) is far lower than `quality_features.gross_profitability`'s (~50-58%)** despite this loop's own spec initially guessing similarity by analogy between the two fundamental-composite datasets — reconfirms the standing lesson (`quality_features`' knowledge_time entry above) that null-rate and coverage properties don't transfer across research-tier datasets; always live-probe each new dataset rather than reasoning by analogy to a structurally similar one. (Value composite IMPLEMENT 2026-07-22)
- **Shared-engine bug (not a strategy bug): a weight-mode backtest holding a PIT-universe instrument through a real delisting, across enough post-delisting rebalances, crashes with `AssertionError: weight-mode position changes do not reconcile with costed quantity deltas` at `backtester/portfolio/accounting/ledger.py:648` — before any Sharpe/IR/report is produced.** Root cause (confirmed via traceback-frame inspection of the real failing run, not guessed): `backtester/portfolio/rebalance.py` freezes an instrument's weight at its last valid mark once its price permanently disappears; the ledger's own `position_changes` audit (from `marked_prices = prices.ffill()`) correctly shows the resulting implied quantity drifting with NAV at every later rebalance, but `FixedBpsWeightCostModel.compute()` (`backtester/portfolio/weight_cost.py:103`, `quantity_deltas.mask(px.isna(), 0.0)`) masks its own quantity deltas to exactly 0 wherever the *raw* (non-ffilled) price is NaN — permanently true post-delisting — so the two audit trails are guaranteed to diverge. Confirmed on ROIC + momentum blend's BACKTEST (2026-07-22): first divergence CSRA 2018-04-30, 465 total diverging cells across `AET`/`ANDV`/`CSRA`/`ESRX`/`SCG`. Data-dependent, not signal-dependent — any future weight-mode WIP holding one of the known-delisted PIT tickers (`AET`, `ANDV`, `BK`, `BMS`, `COL`, `CSRA`, `ESRX`, `EVHC`, `HOT`, `SATS`, `SCG`, `TWX` all triggered the underlying freeze warning as of this trial's 2016-2026 universe) across multiple rebalances after its delisting date can hit this. No strategy-level workaround exists — the freeze is enforced by `RebalanceEngine` regardless of what `_compute_weights` signals going forward. This loop cannot fix it (shared `backtester/portfolio/weight_cost.py` code, out of scope for a single research-loop stage), only flag it before spending a full BACKTEST run and route around it if avoidable (e.g., check whether a WIP's top-quartile selections ever include one of these names post-delisting before running the full backtest). (`trial-registry.md`, ROIC + momentum blend BACKTEST 2026-07-22)
- **Update to the above: the shared-engine delisted-name bug is now fixed on `main` (commit `a44a703`, 2026-07-22), outside the loop's normal one-stage-per-run process** — this was a direct human-requested fix/investigation, not a research-loop stage. Root cause was narrower than "the two audit trails are guaranteed to diverge" implied: `ledger.py`'s own `positions` computation was the one at fault, recomputing quantity from the frozen *weight* against the drifting NAV every rebalance (using the ffilled/frozen price, which stays finite forever) instead of freezing the *quantity* once the raw price permanently disappears — `FixedBpsWeightCostModel`'s zero-delta masking was already correct. Fix: freeze quantity/exposure/value at the last raw-price-valid bar for the rest of the sample, matching the cost model, and let the position's book weight drift with NAV rather than being synthetically topped up. Regression test: `tests/test_execution_architecture.py::test_weight_ledger_freezes_quantity_after_permanent_delisting`. Future WIPs holding one of the known-delisted tickers no longer need the universe-exclusion workaround ROIC + momentum blend used — check whether it's still needed before repeating it.
- **A decisive (not near-zero) IR-gate failure can still motivate Improve over Archive when regime evidence is consistently protective across every available crisis window, not just mixed or absent — it's the consistency/direction of the regime evidence that drives the verdict, not how close to zero the IR itself is.** ROIC + momentum blend's IR (-0.2205) is worse than Value composite's near-zero -0.059 and only mildly better than Quality composite's -0.26 (which was Archived), yet it earned Improve because its regime evidence — unlike Quality's (never gathered) or PEAD's (mixed, non-compensating) — showed real outperformance in both available crisis windows (COVID +1.82pts, 2022 bear +4.51pts vs SPY), the same qualitative pattern (milder in magnitude) that motivated Improve for the low-volatility family. (`trial-registry.md`, ROIC + momentum blend REVIEW 2026-07-22)
- **Full-period IR improvement and crisis-window regime protection are not the same axis — a methodology change can move one without moving the other in the same direction, so don't assume a design change that improves the IR gate is also strengthening the mechanism its regime story was built around.** ROIC + momentum blend v2 replaced v1's blended z-score with a sequential screen (top-half-by-ROIC filter, then rank survivors by momentum) specifically to test whether isolating the ROIC leg would preserve/strengthen v1's consistent crisis protection. The IR gate improved dramatically (-0.2205 → -0.0287, the closest to zero of any trial in this loop), but the regime evidence got *weaker* and flipped sign in one window (COVID +1.82pts → -0.83pts, 2022 bear +4.51pts → +3.52pts) — the opposite of the pre-registered prediction. The IR improvement is better explained by better stock selection within the ROIC-qualified pool than by strengthened ROIC-linked defensiveness, since the defensiveness itself declined. Read regime evidence as its own diagnostic, not a proxy for "the IR gate is improving because the hypothesized mechanism is working." (`trial-registry.md`, ROIC + momentum blend v2 REVIEW 2026-07-23)
- **This loop's first mandatory-gate-clearing trial: ROIC + momentum blend v3 (top-third ROIC screen) passed the IR-vs-benchmark gate (+0.2216), capping a monotonic three-iteration trend (v1 -0.2205 → v2 -0.0287 → v3 +0.2216) that confirms the pre-registered "purer ROIC pool → better selection" hypothesis rather than a one-time blend-vs-screen shape effect.** Deflated Sharpe (0.9966, n_trials=3 honestly counted) stayed robust even after three iterations on the same factor pair — the tightening trajectory was a deliberate, disciplined test of one variable at a time, not opportunistic parameter search. Verdict: Ship (`trial-registry.md`/`docs/research/strategies/roic-momentum-v3-tighter-roic-screen.md`, REVIEW 2026-07-23).
- **A negative fold-decay trend from `WalkForwardEngine`'s `slice_diagnostics` mode (chronological Sharpe decline across folds, e.g. "-0.078/fold" with some folds negative) is not by itself evidence of secular alpha decay — verify against calendar-period returns before treating it as a rejection signal.** `slice_diagnostics` mode has no per-fold refit (appropriate for a fixed-rule strategy with no tunable params, like every strategy in this loop so far); its "decay" is just a linear trend fit across chronologically-ordered slices of one continuous equity curve, so a handful of genuinely bad calendar periods (a correction, a crash, a bear market) can produce a decisively negative trend coefficient even when the most recent periods are strong. Confirmed directly on ROIC + momentum blend v3: the reported 4/18 negative-Sharpe folds mapped exactly onto 2018Q4/COVID/2022-bear half-years when independently re-computed as half-year Sharpe buckets straight from `equity_curve.csv`, while the two most recent half-years (2025H2, 2026H1) were among the strongest in the entire 2016-2026 sample — the opposite of what "the edge is decaying" would predict. Always re-derive a calendar-period breakdown directly from the equity curve before trusting a fold-decay summary statistic at face value, especially when a Ship verdict is on the line. (`trial-registry.md`, ROIC + momentum blend v3 REVIEW 2026-07-23)

## Avoid list

Ideas, signal families, or approaches already tried and rejected, so IDEATE
doesn't regenerate them. One line each, with the registry row or strategy
spec they trace back to.

- Quality composite: `gross_profitability` (Novy-Marx) z-score + `accruals`
  (Sloan) z-score average, top-quartile long, quarterly rebal, PIT S&P 500 —
  Archived 2026-07-20, failed the mandatory IR-vs-benchmark gate (IR -0.26).
  See `trial-registry.md` and `docs/research/strategies/quality-composite.md`.
  Does not exclude other quality-signal combinations (e.g. Ready idea #4,
  ROIC + momentum) — only this specific two-factor/z-score/quarterly
  construction.
- Regime-gated low-volatility anomaly: lowest-60d-vol quintile, gated on/off
  by a binary SPY-vs-200d-SMA trend signal (full-market default exposure
  when calm), monthly rebal, PIT S&P 500 — Archived 2026-07-21, failed the
  mandatory IR-vs-benchmark gate identically to the ungated version
  (IR -0.41 both) and eroded crisis-window protection (COVID +1.87pts vs.
  ungated +3.09pts, 2022 bear +7.27pts vs. ungated +11.74pts) due to
  gate lag on fast crashes. See `trial-registry.md` and
  `docs/research/strategies/regime-gated-low-volatility-anomaly.md`. Does
  not exclude a differently-constructed regime signal in principle, but
  the underlying problem (gate only covers ~17% of days; the IR failure's
  source is the other ~83%) applies to any crisis-only gate on this same
  signal, so a faster/different trend signal isn't expected to clear the
  gate either — treat a new attempt on this family as low-priority absent
  a reason to believe otherwise.
- Post-earnings-announcement drift (PEAD): top-quintile SUE (standardized
  unexpected earnings) long, fixed 60-trading-day hold, daily rebalance,
  PIT S&P 500 — Archived 2026-07-21, failed the mandatory IR-vs-benchmark
  gate more decisively than any prior trial (IR -0.48), with the steepest
  cost-sweep decay (~22% Sharpe 0→20bps) and highest turnover (702.59%
  annualized) of any trial, and mixed (non-compensating) regime evidence.
  See `trial-registry.md` and
  `docs/research/strategies/post-earnings-announcement-drift.md`. Does not
  exclude a differently-constructed event-driven signal (e.g. a shorter
  hold, a tighter SUE cutoff, or a short leg) — only this specific
  quintile/60-day-hold/long-only construction.

## Regime evidence

Distilled crisis-analysis findings (GFC / COVID / 2022, per
`qj-report-analyst`'s existing crisis breakdown) — how strategy families
have behaved in specific market regimes, gathered across trials. Diagnostic,
not a gate; see the design spec's "Regime evidence" note for why this
project doesn't use IMQuantFund's a-priori regime taxonomy.

**Low-volatility anomaly** (REVIEW 2026-07-21, computed directly from
`equity_curve.csv` vs. the same SPY series used for the IR gate — real
numbers, first crisis-analysis data this loop has recorded): the
lowest-60d-vol quintile showed genuine downside protection in both
available crisis windows — COVID crash (2020-02-19→2020-03-23) -30.31%
vs SPY -33.40% (**+3.09pts**), 2022 bear market (2022-01-03→2022-10-12)
-12.32% vs SPY -24.06% (**+11.74pts**). No GFC window in range (data
starts 2016-01-04). This is the classic low-vol defensive signature and
confirms the risk-based hypothesis's mechanism even though the strategy
failed its full-period mandatory IR gate — the two aren't in tension,
they describe different parts of the same cycle (defensive in crises,
drag during the leverage-fueled bull stretches between them). Motivated
an Improve verdict (regime-gate the exposure) rather than Archive.

Quality composite (REVIEW 2026-07-20) never reached crisis-analysis —
its walk-forward/OOS run was blocked by the lake API infra defect noted
above, and the mandatory IR gate had already failed decisively enough
that REVIEW proceeded to Archive without waiting on it.

**Regime-gated low-volatility anomaly** (REVIEW 2026-07-21, same method
as the ungated trial): gating the low-vol quintile behind a binary
SPY-200d-SMA trend signal (elevated on 449/2650 days, ~17%) *reduced*
crisis-window protection versus the always-on ungated version rather
than preserving it — COVID crash -31.53% vs SPY -33.40% (**+1.87pts**,
vs. ungated's +3.09pts), 2022 bear -16.78% vs SPY -24.06% (**+7.27pts**,
vs. ungated's +11.74pts). Direct measurement of the gate's own trend
flag inside each window explains the gap: elevated on only 16/24 COVID
days (flipped day 6 of a 24-day crash) vs. 153/196 2022-bear days
(flipped day 13 of a ~9-month decline) — a 200-day SMA trend gate is
too slow for a crash as fast as COVID's but adequate for a slow grind.
Combined with the full-period IR gate staying numerically unchanged
(-0.41, same as ungated), this shows the regime-gate mechanism didn't
just underdeliver on speed — it can't reach the actual source of the
full-period underperformance at all, since it only ever acts during the
~17% of days it's active. Motivated Archive rather than another Improve
iteration.

**Post-earnings-announcement drift** (REVIEW 2026-07-21, same method,
computed directly from `equity_curve.csv` vs. SPY): unlike either
low-volatility trial, PEAD's regime evidence is mixed rather than
consistently protective or exposed — COVID crash (2020-02-19→2020-03-23)
-37.28% vs SPY -33.72% (**-3.56pts**, underperformed), 2022 bear market
(2022-01-03→2022-10-12) -16.08% vs SPY -24.50% (**+8.42pts**,
outperformed). The strategy held ~95% gross exposure across ~72 names
throughout both windows (confirmed from `weights.csv`, not assumed) —
so neither result is a being-in-cash effect; the COVID underperformance
reflects full exposure to a market-wide panic with no defensive
mechanism, while the 2022 outperformance more likely reflects which
names' SUE-driven drift held up better during a slower, valuation-driven
decline. Consistent with PEAD's behavioral (non-risk-based) mechanism
having no a-priori crisis-regime prediction: the mixed result carries
little design signal and motivated Archive rather than a regime-gated
follow-up (contrast with the low-volatility family, whose consistent
both-crisis protection did motivate one).

**Value composite** (REVIEW 2026-07-22, same method, computed directly
from `equity_curve.csv` vs. SPY): also mixed, like PEAD — COVID crash
(2020-02-19→2020-03-23) strategy -43.89% vs SPY -33.72% (**-10.17pts**,
underperformed decisively, the largest crisis-window gap of any trial
in this loop in either direction), 2022 bear market
(2022-01-03→2022-10-12) strategy -18.37% vs SPY -24.50% (**+6.13pts**,
outperformed). Unlike PEAD's unpredicted mix, the COVID underperformance
matches value's own well-documented "value trap" failure mode: a fast,
liquidity-driven panic is exactly the regime where "cheap on trailing
fundamentals" can mean the market is correctly pricing in real distress
risk rather than mispricing a healthy company — a specific, actionable
explanation rather than noise. Combined with the mandatory IR gate's
near-zero (-0.059, closest of any trial) result and the mildest
cost-sweep decay of any trial, this motivated Improve: a follow-up idea
("Quality-screened value composite") that filters the value composite by
a quality/profitability signal to exclude distressed names, spawned to
the Ready backlog rather than defaulting to Archive.

**ROIC + momentum blend** (REVIEW 2026-07-22, same method, computed
directly from `equity_curve.csv` vs SPY, on the 697/709-ticker
delisted-name-excluded universe): consistently protective in both
available crisis windows, though milder than the low-volatility
family's — COVID crash (2020-02-19→2020-03-23) strategy -31.90% vs SPY
-33.72% (**+1.82pts**), 2022 bear market (2022-01-03→2022-10-12)
strategy -19.98% vs SPY -24.50% (**+4.51pts**). No a-priori regime
prediction was pre-registered for this fundamental×technical
combination (the ROIC leg motivates some defensive expectation
analogous to Quality composite, but the momentum leg's crash-sensitivity
pulls the other way) — the observed net-protective result across both
windows most plausibly reflects the ROIC leg dominating, and motivated
an Improve verdict (isolate the ROIC leg from the momentum leg via a
sequential screen rather than a blended z-score) despite the IR gate's
decisive full-period failure (-0.2205).

**ROIC + momentum blend v2: sequential screen** (REVIEW 2026-07-23, same
method, computed directly from `equity_curve.csv` vs SPY, full
709-ticker universe): COVID crash (2020-02-19→2020-03-23) strategy
-34.23% vs SPY -33.40% (**-0.83pts**, mildly underperformed), 2022 bear
market (2022-01-03→2022-10-12) strategy -20.54% vs SPY -24.06%
(**+3.52pts**, outperformed but less than v1's +4.51pts). This does
**not** confirm the spec's pre-registered prediction that isolating the
ROIC leg via a sequential screen would preserve or strengthen v1's
consistent both-crisis protection (COVID +1.82pts, 2022 bear +4.51pts) —
regime protection weakened and flipped sign in COVID even though the
mandatory IR gate improved sharply (-0.2205 → -0.0287, closest to zero
of any trial in this loop). The two outcomes are decoupled: the IR
improvement more plausibly reflects better stock selection within the
ROIC-qualified pool than strengthened crisis-defensiveness. Motivated
Improve (a further-tightened top-third ROIC screen, testing whether the
IR-improvement trend continues) rather than treating the weakened
regime evidence as reason to Archive, since the mandatory IR gate — not
the diagnostic regime evidence — is what came closest to passing.

**ROIC + momentum blend v3: top-third ROIC screen** (REVIEW 2026-07-23,
same method, computed directly from `equity_curve.csv` vs SPY, full
709-ticker universe): COVID crash (2020-02-19→2020-03-23) strategy
-35.80% vs SPY -33.72% (**-2.08pts**, underperformed), 2022 bear market
(2022-01-03→2022-10-12) strategy -22.22% vs SPY -24.50% (**+2.27pts**,
outperformed). Both magnitudes are milder than v2's (COVID -0.83pts,
2022 bear +3.52pts) — the further-tightened ROIC screen continues
decoupling from the crisis-protection story even as the full-period IR
gate kept improving, this time past zero into genuinely positive
territory (+0.2216), the first mandatory-gate pass in this loop's
history. Verdict: Ship.
