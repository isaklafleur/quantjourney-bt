# <Strategy Name> — research spec

- **Status:** Draft | WIP | Shipped | Archived | Improve (superseded by <link>) | Merged (folded into a `knowledge.md` lesson)
- **Family:** <signal family, e.g. cross-sectional momentum, mean reversion, quality composite>
- **Promoted from backlog:** <date>, rank <N>

## Hypothesis

What's the proposed edge, and why should it exist (behavioral, structural,
or risk-based reason — not just "the backtest looked good")?

## Data & universe

Which datasets (`backtester.lake_api`/`backtester.local_lake` names),
which universe (all-equities / sp500 / nasdaq100 / dow30), and the date
range this will be evaluated over.

## Implementation notes

Weight mode or order mode (per `qj-strategy-ideas`), the nearest existing
`strategies/` file this is modeled on, and any config decisions
(`qj-config-helper`: rebalance policy, risk overlay, position caps).

## Evaluation plan

Written *before* the BACKTEST stage runs. Which walk-forward scheme
(rolling / expanding / anchored — see
`backtester.walkforward.WalkForwardConfig`) plus its `purge_days`/
`embargo_pct` settings, the benchmark symbol for the IR gate, and
whether a cost sweep applies (turnover-heavy strategies only).

## Results

Filled in at BACKTEST. Gate-by-gate outcome (IR, deflated Sharpe, PBO,
cost-sweep, walk-forward Sharpe decay), plus a link to the
`trial-registry.md` row(s).

## Regime evidence

Filled in at REVIEW, from the report's crisis-analysis breakdown
(GFC / COVID / 2022). Diagnostic only — see `knowledge.md`'s "Regime
evidence" section for the running cross-strategy picture.

## Verdict & lessons

Filled in at REVIEW. One of Archive / Improve / Merge / Ship, plus the
specific lessons distilled into `knowledge.md`.
