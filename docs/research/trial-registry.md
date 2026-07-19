# Trial Registry

Append-only ledger of every backtest run by the research loop, including
failed variants (doc: `skills/qj-research-loop/SKILL.md`). Never edit or
delete a row — if a result is superseded, strike it through
(`~~like this~~`) and add a new row; the history is the point. `n_trials`
for a strategy family's deflated Sharpe calculation is the count of that
family's rows here — count honestly, including the failed ones.

| Timestamp | Strategy | Family | Stage | IR vs. benchmark | Deflated Sharpe | PBO | Cost-sweep survives | Verdict | n_trials (family) | Lessons |
|---|---|---|---|---|---|---|---|---|---|---|

_Empty — no trials yet._
