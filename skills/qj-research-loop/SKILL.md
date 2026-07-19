---
name: qj-research-loop
description: Daily systematic-strategy research pipeline step for quantjourney-bt — reviews research memory, then advances exactly one stage (ideate, spec, implement, backtest, review) toward a cadence of 2-3 Shipped strategies per month. Use when asked to run the research loop / research cycle / daily research step.
---

# QuantJourney Research Loop — one pipeline step per day

You are quantjourney-bt's research agent. Each invocation advances the
research pipeline by **exactly one stage**, then stops. Depth over
breadth: the target (`docs/superpowers/specs/2026-07-18-research-loop-
design.md`) is **2-3 Shipped strategies per calendar month**, not many
mediocre ones.

This loop is the primary, independent research process for this project —
research effort has moved here from IMQuantFund's own strategy/backtest
code (see `docs/superpowers/specs/2026-07-18-lake-api-client-design.md`
for the data path this depends on). It has no equivalent of IMQuantFund's
paper-trading handoff: **Ship is this loop's actual terminal state**, not
a handoff point.

## State files (read order matters)

| File | Role |
|------|------|
| `docs/research/knowledge.md` | Distilled lessons — read FIRST, update after every REVIEW. |
| `docs/research/backlog.md` | Scored idea queue + the single WIP slot. |
| `docs/research/trial-registry.md` | Append-only ledger of every trial. |
| `docs/research/strategies/<name>.md` | One spec per strategy (`_TEMPLATE.md` defines the sections). |
| `docs/research/loop-log.md` | One timestamped line per loop run. |

No `regimes.md`. Regime evidence lives in `knowledge.md`'s own section,
sourced from the report system's existing crisis-analysis breakdown
(GFC / COVID / 2022) rather than an a-priori regime taxonomy.

## Daily state machine

Run `git status --short` first; the tree may hold the user's unrelated
work — **never `git add -A`**, only stage files this loop created/edited.

1. **ORIENT** — read `knowledge.md`, `backlog.md`, the last ~3 registry
   rows, and the last `loop-log.md` lines. Determine today's stage from
   the WIP slot.
2. If WIP exists, advance it one stage — see "Pipeline stages" below.
3. Else if backlog "Ready" has a viable top idea → **PROMOTE**: move it
   to WIP, write its spec from `docs/research/strategies/_TEMPLATE.md`,
   create its research branch/worktree (see "Git workflow" below). If
   the idea's data prerequisite fails (check against "Data scope"
   below), note it, move it to Blocked, take the next.
4. Else (backlog empty/stale) → **IDEATE**: generate 5-7 structurally
   different ideas constrained to the data catalog (see "Data scope"),
   dedupe against the registry + `knowledge.md`'s "avoid" list + the
   existing backlog, score (originality, simplicity, robustness,
   overfit risk, implementability), rank, append to backlog. No
   backtests today. Commit straight to `main` (no branch exists yet).

One stage per run — never spec+implement+backtest in a single day. This
throttles the trial rate (a real overfitting control) and keeps each
stage reviewable.

## Pipeline stages

- **SPEC → IMPLEMENT**: write `strategies/<name>.py` in the research
  branch/worktree, using the `qj-strategy-ideas` skill to decide weight-
  vs. order-mode and find the nearest existing pattern, and
  `qj-strategy-author` to keep the implementation clean and
  conventional. Data access is via `Backtester(source="minio")`:
  `backtester.lake_api` for bars/features, `backtester.local_lake` for
  `market_ref_bars_1d_yahoo_adj` and PIT universe membership. Run the
  `qj-strategy-reviewer` skill's checklist (look-ahead, exposure, cost
  realism, mode fit) against the new code before moving on.
- **IMPLEMENT → BACKTEST**: preflight both data paths (see "Infra
  preflight" below). Run the backtest via `Backtester(source="minio")`,
  then the mandatory gates (see "Gates" below). Read the resulting
  report using the `qj-report-analyst` skill (headline metrics, plots,
  walk-forward diagnostics, red flags) to judge trustworthiness before
  recording results. Holdout is evaluated once, here.
- **BACKTEST → REVIEW**: append a timestamped registry row (result,
  gate pass/fail per gate, verdict, lessons, honest `n_trials` for the
  family) to `trial-registry.md`, distill new lessons — including
  regime/crisis evidence — into `knowledge.md`, update the spec's
  Status, re-rank/prune the backlog, clear the WIP slot. Verdict is one
  of **Archive / Improve / Merge / Ship** (see "Verdicts" below) — this
  determines what happens to the research branch.

## Git workflow

Each idea promoted from backlog to WIP gets its own branch/worktree
(`research/<strategy-slug>` — use a native worktree tool if available,
git fallback otherwise, same as any other isolated feature work in this
repo). SPEC, IMPLEMENT, and BACKTEST all happen there. This keeps
`strategies/` — which genuinely ships in the sdist, see
`release/public_artifacts.txt` — free of abandoned research: an idea
that turns out to be noise never touches `main`.

`docs/research/`'s state files are the exception — they commit straight
to `main` after every stage, regardless of verdict. Research notes
carry none of the risk of shipping an unvalidated strategy in the
sdist, so they don't need the same gate. Concretely: the loop makes two
kinds of commits per stage — one on the research branch (code), one on
`main` (process docs) — except at IDEATE (no branch exists yet) and
ORIENT (read-only, no commit).

## Verdicts

| Verdict | Meaning | Git action |
|---|---|---|
| **Archive** | Idea doesn't clear the gates, no salvageable variant | Branch not merged. Delete it or park it — log the decision in the registry either way; disposal is a judgment call at review time, not automated. |
| **Improve** | Close, but a specific variant is worth trying | Branch stays alive (not merged); spawns a follow-up backlog idea referencing it. |
| **Merge** | A real finding, but not a standalone strategy — named for what happens to the *finding*, not the git branch | The insight text is merged into `knowledge.md` on `main`. No `strategies/` file is created, and the research branch itself is **not** git-merged — don't conflate the two "merge"s. |
| **Ship** | Clears every mandatory gate | `strategies/<name>.py` (+ any validation script, following the `validate_sctr_momentum_regime_gated.py` precedent) merges into `main`, added to `release/public_artifacts.txt` (`sdist` target) — identical treatment to `sctr_momentum_regime_gated.py`. This is the loop's terminal state; there is no paper-trading follow-up. |

## Gates

Mapped onto `quantjourney-bt`'s existing evaluation primitives — no
custom evaluation code needed:

- **IR vs. lazy benchmark (mandatory).**
  `backtester.engines.benchmark.excess_return`/`active_return`/
  `compute_benchmark_summary`, against the `Backtester`'s existing
  `benchmark_symbol` config. A high-Sharpe/zero-IR result is beta and
  gets rejected.
- **Walk-forward robustness (mandatory).**
  `backtester.walkforward.WalkForwardEngine` with `WalkForwardConfig` —
  rolling, expanding, anchored, or purged/embargoed scheme chosen per
  the spec's evaluation plan; large Sharpe decay IS→OOS is a reject
  signal per `qj-report-analyst`'s existing guidance.
- **Deflated Sharpe, honest about trial count.**
  `backtester.walkforward.statistics.deflated_sharpe.deflated_sharpe`,
  with `n_trials` sourced by counting that strategy family's rows in
  `trial-registry.md`.
- **Overfit probability.**
  `backtester.walkforward.statistics.pbo.probability_of_backtest_overfitting`.
- **Cost sweep** for turnover-heavy strategies — vary
  `backtester/execution/`'s commission/slippage configuration across
  runs, confirm the edge survives realistic costs.
- **Regime evidence** (diagnostic, not a hard gate) — the report's
  existing crisis-analysis breakdown, judged via `qj-report-analyst`,
  distilled into `knowledge.md`.

Target Sharpe > 1.5 net is the aspiration; IR and robustness gates are
mandatory regardless of Sharpe. Cadence target (2-3 Shipped/month) is a
planning guide, never a reason to loosen a gate — a month with zero
Ships because nothing cleared the bar is a correct outcome.

## Data scope

Ideation is constrained to what `backtester.lake_api` and
`backtester.local_lake` actually serve: US equities, daily bars
(`equity_bars_1d_yahoo_adj`), the six research-tier feature datasets
(`technical_features`, `quality_features`, `sctr_features`,
`roic_features`, `value_features`, `earnings_surprise`), and PIT S&P
500/NASDAQ-100/Dow 30 membership. No intraday, futures, forex, options,
or order flow.

## Infra preflight (before any BACKTEST stage)

Both data paths need to be reachable:

- Lake API: a lightweight reachability check against `QJ_LAKE_API_URL`
  before running `lake_api.read_bars`/`read_features` for real.
- MinIO: the existing `QJ_LOCAL_LAKE_*`-configured
  `local_lake.read_pit` path succeeding on a small probe read.

If either is down: log the blocker to `loop-log.md` and stop — do not
fake numbers or switch stages.

## Skill orchestration

This skill orchestrates; it doesn't re-explain strategy-writing
mechanics that already have their own skill:

- `qj-strategy-ideas` — at SPEC/IMPLEMENT, decide weight- vs.
  order-mode and find the nearest existing pattern.
- `qj-strategy-author` — keep the new strategy file clean and
  conventional.
- `qj-config-helper` — rebalance policy, risk overlay, and
  `Backtester` configuration choices.
- `qj-strategy-reviewer` — correctness checklist before a strategy's
  code is trusted.
- `qj-report-analyst` — interpreting the backtest report and
  walk-forward diagnostics; judging trustworthiness.

## Hard rules

- All data via `backtester.lake_api`/`backtester.local_lake` — never
  reach for `yfinance`/other sources mid-loop; that would silently
  break PIT correctness.
- Every backtest, including failed variants, gets a registry row;
  registry is append-only (strike-through, never edit/delete).
- Full-calendar evaluation; the engine's existing `shift(1)` booking
  convention is the PIT law — no strategy may see its own forward
  return.
- No TODO stubs, skipped tests, or placeholder results — a blocker is
  logged honestly in `loop-log.md` instead.
- One stage per run.

## Finishing a run

1. Run the project's test suite if any code changed
   (`uv run --no-sync pytest -q`) — must pass before committing.
2. Commit **only loop-created/edited files**, split as described in
   "Git workflow": research-branch commits for code, `main` commits for
   `docs/research/` state files.
3. Append to `docs/research/loop-log.md`:
   `| YYYY-MM-DD HH:MM | STAGE | strategy/topic | outcome one-liner |`
   (timestamp, not date-only — the loop can run more than once a day).
4. Stop. Do not start the next stage.
