# Strategy Idea Backlog

Scored queue feeding the daily research loop
(`skills/qj-research-loop/SKILL.md`). One idea at a time is promoted to WIP
and carried through spec → implement → backtest → review. Scores are 1-5
(higher = better; overfit-risk 5 = *low* risk). Ideas must be implementable
with the data `backtester.lake_api`/`backtester.local_lake` actually serve:
US equity daily bars and PIT S&P 500/NASDAQ-100/Dow 30 membership, plus the
six research-tier feature datasets (`technical_features`, `quality_features`,
`sctr_features`, `roic_features`, `value_features`, `earnings_surprise`) —
no intraday, futures, forex, options, or order flow.

## WIP (max 1)

**Value composite** — promoted 2026-07-21 (Ready rank 1). Spec:
`docs/research/strategies/value-composite.md`. Code written:
`strategies/value_composite.py` on `worktree-value-composite` (commit
`4faac4d`). Stage: BACKTEST done (IR -0.059 FAIL but closest-to-zero of
any trial so far, cost sweep PASS, walk-forward BLOCKED per the
standing lake API defect), next is BACKTEST → REVIEW.

## Ready (ranked)

| Rank | Idea | Family | Lineage | Orig. | Simpl. | Robust. | Overfit | Impl. | Notes |
|------|------|--------|---------|-------|--------|---------|---------|-------|-------|
| 1 | ROIC + momentum blend: combine `roic` (quality) with `ret_60d` (technical momentum) — "quality at a reasonable momentum" | Fundamental × technical combination | Novel combination for this loop; no direct IMQuantFund analog found | 4 | 3 | 3 | 3 | 4 | Both `roic_features` and `technical_features.ret_60d` directly available. The combination methodology itself (z-score blend vs. sequential screen vs. double-sort) is an open design choice with several viable options — more researcher degrees of freedom than a single factor, hence the lower overfit-risk score. PIT alignment between quarterly ROIC and daily momentum needs a careful as-of join. |
| 2 | Cross-sectional RSI/Bollinger mean-reversion: rank by how oversold (`rsi_14` low + close near `bb_low`), short holding period | Technical, contrarian | Classic technical reversion; distinct from this repo's existing W03/W21 examples (cross-sectional universe selection vs. a single fixed basket) | 2 | 5 | 2 | 2 | 5 | `rsi_14`/`bb_low`/`bb_mid`/`bb_high` all directly in `technical_features`. Short-horizon technical reversion is notoriously fragile out-of-sample and highly cost-sensitive — mandatory cost-sweep gate, and a quality/eligibility filter is worth considering to avoid buying names that are oversold for a real fundamental reason ("falling knives"), though that's a design decision for SPEC, not decided here. |
| 3 | OBV-confirmed breakout: N-day price high + rising `obv` as trend-continuation confirmation | Technical, breakout / trend-initiation | Classic technical breakout + volume-confirmation heuristic; no direct IMQuantFund analog found | 3 | 3 | 2 | 2 | 4 | `obv`/`volume_sma_20` in `technical_features`; "N-day high" derived directly from the price panel. Breakout lookback window and confirmation threshold are exactly the kind of parameters prone to curve-fitting — lowest overfit-risk score in the batch alongside #4 (now #5). Likely turnover-heavy around breakout attempts. |

Explicitly avoided: pure `sctr_features`/`rank`-based selection without a genuinely
different structural twist — `strategies/sctr_momentum_regime_gated.py` already
ships that idea (SCTR rank + SPY-trend regime gate); re-proposing it here without
a real mechanism change would just be relitigating a Shipped strategy, not a new
idea.

Explicitly avoided: `gross_profitability` (z-score) + `accruals` (z-score),
averaged, top-quartile long, quarterly rebal — tried as "Quality composite",
Archived 2026-07-20 (failed the mandatory IR-vs-benchmark gate, IR -0.26).
See `knowledge.md`'s Avoid list. A differently-combined quality signal (e.g.
idea #4 below) is not excluded by this.

Explicitly avoided: lowest-60d-vol quintile gated on/off by a binary
SPY-vs-200d-SMA trend signal — tried as "Regime-gated low-volatility
anomaly", Archived 2026-07-21 (IR -0.41, unchanged from the ungated
version; gate only active ~17% of days, can't address the calm-period
drag that causes the full-period IR failure). See `knowledge.md`'s Avoid
list. Low priority for any future attempt on this family (faster/
different regime signal) absent a reason to believe the structural
ceiling doesn't apply.

Explicitly avoided: top-quintile SUE (standardized unexpected earnings)
long, fixed 60-trading-day hold, daily rebalance — tried as
"Post-earnings-announcement drift", Archived 2026-07-21 (IR -0.48, most
decisive gate failure of any trial so far; steepest cost-sweep decay and
highest turnover of any trial; mixed, non-compensating regime evidence).
See `knowledge.md`'s Avoid list. A differently-constructed event-driven
signal (shorter hold, tighter SUE cutoff, or a short leg) is not excluded
by this.

## Blocked

Ideas whose data prerequisite failed a PROMOTE-time check. One line each:
idea, what's missing, date checked.

_Empty._
