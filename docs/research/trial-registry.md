# Trial Registry

Append-only ledger of every backtest run by the research loop, including
failed variants (doc: `skills/qj-research-loop/SKILL.md`). Never edit or
delete a row — if a result is superseded, strike it through
(`~~like this~~`) and add a new row; the history is the point. `n_trials`
for a strategy family's deflated Sharpe calculation is the count of that
family's rows here — count honestly, including the failed ones.

| Timestamp | Strategy | Family | Stage | IR vs. benchmark | Deflated Sharpe | PBO | Cost-sweep survives | Verdict | n_trials (family) | Lessons |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-20 22:32 | Quality composite | Fundamental quality | REVIEW | **FAIL** — IR -0.26, active return -1.89%/yr, cumulative excess -71pts vs SPY, 2016-01-01→2026-07-14 | BLOCKED — never completed; lake API `read_bars` server defect (zero rows for `end` outside ~last 2-3 weeks of wall-clock time) broke 7/8 walk-forward folds across every BACKTEST attempt; single-fold aggregate (0.81) not reported as a real DSR | N/A — `pbo_trials=0`, no optimizer/tuned params to sweep | **PASS** — Sharpe 0.813→0.799 across 0-20bps, edge not cost-sensitive | **Archive** | 1 | Respectable absolute Sharpe (0.80) and CAGR (13.31%) but decisively failed the mandatory IR-vs-benchmark gate — beta, not alpha, across the full decade. A mandatory-gate failure this clear is sufficient grounds for Archive on its own; the still-blocked walk-forward gate doesn't change the outcome either way, so REVIEW proceeded without waiting further (3rd consecutive BACKTEST-stage run stuck on the same infra defect, plus this run's own environment couldn't execute any code/network calls at all — see loop-log.md). Full detail: `docs/research/strategies/quality-composite.md`. |
