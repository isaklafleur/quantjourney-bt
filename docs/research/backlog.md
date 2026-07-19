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

_Empty — run IDEATE to populate._

## Blocked

Ideas whose data prerequisite failed a PROMOTE-time check. One line each:
idea, what's missing, date checked.

_Empty._
