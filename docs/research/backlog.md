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

_Empty — no idea currently in progress._

## Ready (ranked)

| Rank | Idea | Family | Lineage | Orig. | Simpl. | Robust. | Overfit | Impl. | Notes |
|------|------|--------|---------|-------|--------|---------|---------|-------|-------|
| 1 | Quality composite (long/cash): rank by `gross_profitability` (Novy-Marx) + low `accruals` (Sloan), long top quartile | Fundamental quality | Novy-Marx (2013) + Sloan (1996); new construction, not a port of IMQuantFund's `quality_signal.py` | 3 | 5 | 4 | 5 | 5 | `quality_features` has both columns directly (per-cik, fiscal-year-end). Needs PIT as-of join from fiscal-year-end to daily universe. Lowest overfit risk of the batch — two well-documented factors, only free choices are quantile cutoff and rebalance cadence. |
| 2 | Low-volatility anomaly: rank by `vol_60d` ascending, long lowest-vol quintile, monthly rebalance | Technical / risk-based | Ang et al. (2006) low-vol anomaly; no direct IMQuantFund analog found | 2 | 5 | 4 | 5 | 5 | `vol_60d` directly in `technical_features`. Known regime dependency: underperforms in strong momentum-driven bull runs — worth the mandatory regime/crisis check, not a defect. Naive version may concentrate in rate-sensitive sectors; flag, don't pre-filter. |
| 3 | Post-earnings-announcement drift (PEAD): long high-`sue` names, hold a fixed window after the earnings event | Fundamental, event-driven | Ball & Brown (1968) / Bernard-Thomas (1989); IMQuantFund has its own `pead_signal.py` — this is an independent construction, not a port | 3 | 4 | 4 | 4 | 3 | `earnings_surprise` covers fiscal Q1-Q3 only (no Q4/annual row per the source docstring) — needs an explicit gap-handling decision. Event-window entry/exit (not a steady daily panel rank) is more implementation friction than the others; may need order-mode or a custom weight-schedule rather than the straightforward weight-mode rank-and-hold pattern. Concentrated turnover around earnings dates — cost-sensitive. |
| 4 | Value composite (long/cash): combine earnings yield (`eps`/price) + book-to-market (`book_value_per_share`/price) | Fundamental value | Fama-French (1992) value factor; new construction, not a port of IMQuantFund's `value_signal.py` | 2 | 4 | 3 | 4 | 4 | `value_features` gives `eps`/`book_value_per_share`; needs joining against daily price from `equity_bars_1d_yahoo_adj` to form ratios. `book_value_per_share` is null for ~half of company-years (per the source docstring — book value's nearest-join tolerance often misses) — must fall back to earnings-yield-only correctly, not silently drop rows. Value has had a rough decade in some regimes — real robustness question to test, not assumed. |
| 5 | ROIC + momentum blend: combine `roic` (quality) with `ret_60d` (technical momentum) — "quality at a reasonable momentum" | Fundamental × technical combination | Novel combination for this loop; no direct IMQuantFund analog found | 4 | 3 | 3 | 3 | 4 | Both `roic_features` and `technical_features.ret_60d` directly available. The combination methodology itself (z-score blend vs. sequential screen vs. double-sort) is an open design choice with several viable options — more researcher degrees of freedom than a single factor, hence the lower overfit-risk score. PIT alignment between quarterly ROIC and daily momentum needs a careful as-of join. |
| 6 | Cross-sectional RSI/Bollinger mean-reversion: rank by how oversold (`rsi_14` low + close near `bb_low`), short holding period | Technical, contrarian | Classic technical reversion; distinct from this repo's existing W03/W21 examples (cross-sectional universe selection vs. a single fixed basket) | 2 | 5 | 2 | 2 | 5 | `rsi_14`/`bb_low`/`bb_mid`/`bb_high` all directly in `technical_features`. Short-horizon technical reversion is notoriously fragile out-of-sample and highly cost-sensitive — mandatory cost-sweep gate, and a quality/eligibility filter is worth considering to avoid buying names that are oversold for a real fundamental reason ("falling knives"), though that's a design decision for SPEC, not decided here. |
| 7 | OBV-confirmed breakout: N-day price high + rising `obv` as trend-continuation confirmation | Technical, breakout / trend-initiation | Classic technical breakout + volume-confirmation heuristic; no direct IMQuantFund analog found | 3 | 3 | 2 | 2 | 4 | `obv`/`volume_sma_20` in `technical_features`; "N-day high" derived directly from the price panel. Breakout lookback window and confirmation threshold are exactly the kind of parameters prone to curve-fitting — lowest overfit-risk score in the batch alongside #6. Likely turnover-heavy around breakout attempts. |

Explicitly avoided: pure `sctr_features`/`rank`-based selection without a genuinely
different structural twist — `strategies/sctr_momentum_regime_gated.py` already
ships that idea (SCTR rank + SPY-trend regime gate); re-proposing it here without
a real mechanism change would just be relitigating a Shipped strategy, not a new
idea.

## Blocked

Ideas whose data prerequisite failed a PROMOTE-time check. One line each:
idea, what's missing, date checked.

_Empty._
