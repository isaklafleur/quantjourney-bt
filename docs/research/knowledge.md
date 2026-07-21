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

## Regime evidence

Distilled crisis-analysis findings (GFC / COVID / 2022, per
`qj-report-analyst`'s existing crisis breakdown) — how strategy families
have behaved in specific market regimes, gathered across trials. Diagnostic,
not a gate; see the design spec's "Regime evidence" note for why this
project doesn't use IMQuantFund's a-priori regime taxonomy.

_None gathered yet. Quality composite (REVIEW 2026-07-20) never reached
crisis-analysis — its walk-forward/OOS run was blocked by the lake API
infra defect noted above, and the mandatory IR gate had already failed
decisively enough that REVIEW proceeded to Archive without waiting on it.
Next strategy to clear IR + walk-forward should populate this properly._
