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

**Low-volatility anomaly** — Promoted 2026-07-20 from Ready rank 1. Spec
written: `docs/research/strategies/low-volatility-anomaly.md`. Research
branch/worktree: `worktree-low-vol-anomaly` (native worktree tool used,
same `worktree-<slug>` naming as Quality composite — see that spec for
why `research/<slug>` isn't used in this environment). Code written
2026-07-21: `strategies/low_volatility_anomaly.py`, smoke-tested and
committed on the research branch. BACKTEST run 2026-07-21: mandatory IR
gate **FAIL** (IR -0.41, cumulative excess -152pts vs SPY,
2016-01-04→2026-07-20 — more decisive than Quality composite's -0.26),
cost-sweep **PASS**, walk-forward **BLOCKED** (same confirmed lake API
`read_bars` end-date defect as Quality composite, re-bisected today).
Real regime evidence gathered (COVID/2022 downside protection, +3.09pts
/+11.74pts vs SPY) — first crisis-analysis data this loop has recorded.
Full detail: the spec's Results section. No registry row yet. Next
stage: BACKTEST → REVIEW.

## Ready (ranked)

| Rank | Idea | Family | Lineage | Orig. | Simpl. | Robust. | Overfit | Impl. | Notes |
|------|------|--------|---------|-------|--------|---------|---------|-------|-------|
| 1 | Post-earnings-announcement drift (PEAD): long high-`sue` names, hold a fixed window after the earnings event | Fundamental, event-driven | Ball & Brown (1968) / Bernard-Thomas (1989); IMQuantFund has its own `pead_signal.py` — this is an independent construction, not a port | 3 | 4 | 4 | 4 | 3 | `earnings_surprise` covers fiscal Q1-Q3 only (no Q4/annual row per the source docstring) — needs an explicit gap-handling decision. Event-window entry/exit (not a steady daily panel rank) is more implementation friction than the others; may need order-mode or a custom weight-schedule rather than the straightforward weight-mode rank-and-hold pattern. Concentrated turnover around earnings dates — cost-sensitive. |
| 2 | Value composite (long/cash): combine earnings yield (`eps`/price) + book-to-market (`book_value_per_share`/price) | Fundamental value | Fama-French (1992) value factor; new construction, not a port of IMQuantFund's `value_signal.py` | 2 | 4 | 3 | 4 | 4 | `value_features` gives `eps`/`book_value_per_share`; needs joining against daily price from `equity_bars_1d_yahoo_adj` to form ratios. `book_value_per_share` is null for ~half of company-years (per the source docstring — book value's nearest-join tolerance often misses) — must fall back to earnings-yield-only correctly, not silently drop rows. Value has had a rough decade in some regimes — real robustness question to test, not assumed. |
| 3 | ROIC + momentum blend: combine `roic` (quality) with `ret_60d` (technical momentum) — "quality at a reasonable momentum" | Fundamental × technical combination | Novel combination for this loop; no direct IMQuantFund analog found | 4 | 3 | 3 | 3 | 4 | Both `roic_features` and `technical_features.ret_60d` directly available. The combination methodology itself (z-score blend vs. sequential screen vs. double-sort) is an open design choice with several viable options — more researcher degrees of freedom than a single factor, hence the lower overfit-risk score. PIT alignment between quarterly ROIC and daily momentum needs a careful as-of join. |
| 4 | Cross-sectional RSI/Bollinger mean-reversion: rank by how oversold (`rsi_14` low + close near `bb_low`), short holding period | Technical, contrarian | Classic technical reversion; distinct from this repo's existing W03/W21 examples (cross-sectional universe selection vs. a single fixed basket) | 2 | 5 | 2 | 2 | 5 | `rsi_14`/`bb_low`/`bb_mid`/`bb_high` all directly in `technical_features`. Short-horizon technical reversion is notoriously fragile out-of-sample and highly cost-sensitive — mandatory cost-sweep gate, and a quality/eligibility filter is worth considering to avoid buying names that are oversold for a real fundamental reason ("falling knives"), though that's a design decision for SPEC, not decided here. |
| 5 | OBV-confirmed breakout: N-day price high + rising `obv` as trend-continuation confirmation | Technical, breakout / trend-initiation | Classic technical breakout + volume-confirmation heuristic; no direct IMQuantFund analog found | 3 | 3 | 2 | 2 | 4 | `obv`/`volume_sma_20` in `technical_features`; "N-day high" derived directly from the price panel. Breakout lookback window and confirmation threshold are exactly the kind of parameters prone to curve-fitting — lowest overfit-risk score in the batch alongside #4. Likely turnover-heavy around breakout attempts. |

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

## Blocked

Ideas whose data prerequisite failed a PROMOTE-time check. One line each:
idea, what's missing, date checked.

_Empty._
