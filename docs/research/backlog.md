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

Post-earnings-announcement drift (PEAD) — promoted 2026-07-21 from Ready
rank 1. Spec: `docs/research/strategies/post-earnings-announcement-drift.md`.
Research branch/worktree: `worktree-pead` (`strategies/post_earnings_announcement_drift.py`
committed at `a6add37`). BACKTEST complete: IR -0.48 FAIL (most decisive yet),
cost-sweep PASS (steepest decay yet, ~22% Sharpe 0bps→20bps), walk-forward
BLOCKED (same lake API `end`-date defect, 4th consecutive trial). Next stage:
BACKTEST → REVIEW.

## Ready (ranked)

| Rank | Idea | Family | Lineage | Orig. | Simpl. | Robust. | Overfit | Impl. | Notes |
|------|------|--------|---------|-------|--------|---------|---------|-------|-------|
| 1 | Value composite (long/cash): combine earnings yield (`eps`/price) + book-to-market (`book_value_per_share`/price) | Fundamental value | Fama-French (1992) value factor; new construction, not a port of IMQuantFund's `value_signal.py` | 2 | 4 | 3 | 4 | 4 | `value_features` gives `eps`/`book_value_per_share`; needs joining against daily price from `equity_bars_1d_yahoo_adj` to form ratios. `book_value_per_share` is null for ~half of company-years (per the source docstring — book value's nearest-join tolerance often misses) — must fall back to earnings-yield-only correctly, not silently drop rows. Value has had a rough decade in some regimes — real robustness question to test, not assumed. |
| 2 | ROIC + momentum blend: combine `roic` (quality) with `ret_60d` (technical momentum) — "quality at a reasonable momentum" | Fundamental × technical combination | Novel combination for this loop; no direct IMQuantFund analog found | 4 | 3 | 3 | 3 | 4 | Both `roic_features` and `technical_features.ret_60d` directly available. The combination methodology itself (z-score blend vs. sequential screen vs. double-sort) is an open design choice with several viable options — more researcher degrees of freedom than a single factor, hence the lower overfit-risk score. PIT alignment between quarterly ROIC and daily momentum needs a careful as-of join. |
| 3 | Cross-sectional RSI/Bollinger mean-reversion: rank by how oversold (`rsi_14` low + close near `bb_low`), short holding period | Technical, contrarian | Classic technical reversion; distinct from this repo's existing W03/W21 examples (cross-sectional universe selection vs. a single fixed basket) | 2 | 5 | 2 | 2 | 5 | `rsi_14`/`bb_low`/`bb_mid`/`bb_high` all directly in `technical_features`. Short-horizon technical reversion is notoriously fragile out-of-sample and highly cost-sensitive — mandatory cost-sweep gate, and a quality/eligibility filter is worth considering to avoid buying names that are oversold for a real fundamental reason ("falling knives"), though that's a design decision for SPEC, not decided here. |
| 4 | OBV-confirmed breakout: N-day price high + rising `obv` as trend-continuation confirmation | Technical, breakout / trend-initiation | Classic technical breakout + volume-confirmation heuristic; no direct IMQuantFund analog found | 3 | 3 | 2 | 2 | 4 | `obv`/`volume_sma_20` in `technical_features`; "N-day high" derived directly from the price panel. Breakout lookback window and confirmation threshold are exactly the kind of parameters prone to curve-fitting — lowest overfit-risk score in the batch alongside #4 (now #5). Likely turnover-heavy around breakout attempts. |

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

## Blocked

Ideas whose data prerequisite failed a PROMOTE-time check. One line each:
idea, what's missing, date checked.

_Empty._
