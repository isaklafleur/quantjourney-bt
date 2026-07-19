# Research loop — a quantjourney-bt-native daily strategy research pipeline

- **Status:** Approved, pending implementation plan.
- **Date:** 2026-07-18.

## Goal

Port the operating model of IMQuantFund's `.claude/skills/quant-research-loop`
— a daily pipeline that advances exactly one stage (ideate, spec, implement,
backtest, review) toward a steady cadence of validated strategies — into
`quantjourney-bt`, as the primary, independent research loop going forward.
This is a deliberate scope shift: research effort is moving from
IMQuantFund's own strategy/backtest code to `quantjourney-bt`
(`docs/superpowers/specs/2026-07-18-lake-api-client-design.md` built the data
path for this; this spec builds the process on top of it). IMQuantFund's own
loop is not being extended further by this change.

Unlike IMQuantFund, `quantjourney-bt` is a public, PyPI-published,
Apache-2.0 library — `strategies/*.py` genuinely ships in the sdist
(confirmed: `sctr_momentum_regime_gated.py` and
`validate_sctr_momentum_regime_gated.py` are both listed in
`release/public_artifacts.txt`). That difference shapes two of this design's
biggest departures from IMQuantFund's loop: no paper-trading handoff (this
loop has no successor pipeline; it does have a real terminal state, "Ship"),
and a git branch/worktree gate between "code exists" and "code is public."

## State files (read order matters, same principle as IMQuantFund's loop)

| File | Role |
|------|------|
| `docs/research/knowledge.md` | Distilled lessons — read FIRST, updated after every REVIEW. Includes a regime-evidence section (see "Regime evidence" below). |
| `docs/research/backlog.md` | Scored idea queue + the single WIP slot. |
| `docs/research/trial-registry.md` | Append-only ledger of every trial (including failed variants). |
| `docs/research/strategies/<name>.md` | One spec per strategy idea (`_TEMPLATE.md` defines the required sections). |
| `docs/research/loop-log.md` | One timestamped line per loop invocation. |

No `regimes.md`. IMQuantFund's version encodes an a-priori regime taxonomy
(bull/bear/high-vol/low-vol definitions shared across trials) this project
has no equivalent of building. Regime evidence instead comes from the
existing report system's crisis-analysis breakdown (GFC/COVID/2022:
per-crisis return, vol, drawdown, beta — already computed by the reporting
pipeline `qj-report-analyst` reads) and gets distilled into `knowledge.md`
directly rather than a separate knowledge base file.

## Daily state machine

Same shape as IMQuantFund's loop, one stage per run:

1. **ORIENT** — `git status --short` first (never `git add -A`; only stage
   files this loop created/edited). Read `knowledge.md`, `backlog.md`, the
   last ~3 registry rows, the last `loop-log.md` lines. Determine today's
   stage from the WIP slot.
2. If WIP exists, advance it one stage (see "Pipeline stages" below).
3. Else if backlog "Ready" has a viable top idea → **PROMOTE**: move it to
   WIP, write its spec from `_TEMPLATE.md`, create its research branch/
   worktree (see "Git workflow" below). If the idea's data prerequisite
   fails (checked against what `lake_api`/`local_lake` actually serve — see
   "Data scope"), note it, move it to Blocked, take the next.
4. Else (backlog empty/stale) → **IDEATE**: generate 5-7 structurally
   different ideas constrained to the data catalog (equity daily bars +
   the six research-tier feature datasets `lake_api.read_features` covers:
   `technical_features`, `quality_features`, `sctr_features`,
   `roic_features`, `value_features`, `earnings_surprise`), dedupe against
   the registry + `knowledge.md`'s "avoid" list + the existing backlog,
   score (originality, simplicity, robustness, overfit risk,
   implementability), rank, append to backlog. No backtests today.

One stage per run — never spec+implement+backtest in a single day, same
overfitting-control rationale as IMQuantFund's loop.

## Pipeline stages

- **SPEC → IMPLEMENT**: write `strategies/<name>.py` in the research
  branch/worktree (see below), using the existing `qj-strategy-ideas`
  skill to decide weight- vs. order-mode and find the nearest existing
  pattern, and `qj-strategy-author` to keep the implementation clean and
  conventional. Data access via `Backtester(source="minio")`
  (`backtester/lake_api.py` for bars/features, `backtester/local_lake.py`
  for `market_ref_bars_1d_yahoo_adj`/PIT universe — see the lake-api-client
  spec for why the split exists). Run the existing `qj-strategy-reviewer`
  skill's checklist (look-ahead, exposure, cost realism, mode fit) against
  the new code before moving on.
- **IMPLEMENT → BACKTEST**: preflight both data paths (see "Infra
  preflight" below). Run the backtest via `Backtester(source="minio")`,
  then the mandatory gates (see "Gates" below): benchmark IR, walk-forward
  robustness, deflated Sharpe, PBO, a cost sweep. Read the resulting
  report using the `qj-report-analyst` skill (headline metrics, plots,
  walk-forward diagnostics, red flags) to judge trustworthiness before
  recording results. Holdout is evaluated once, here.
- **BACKTEST → REVIEW**: append a timestamped registry row (result, gate
  pass/fail per gate, verdict, lessons, honest `n_trials` for the family),
  distill new lessons (including regime/crisis evidence) into
  `knowledge.md`, update the spec's Status, re-rank/prune the backlog,
  clear the WIP slot. Verdict is one of **Archive / Improve / Merge /
  Ship** (see "Verdicts" below) — this determines what happens to the
  research branch.

## Git workflow

Each idea promoted from backlog to WIP gets its own branch/worktree
(`research/<strategy-slug>`, created the same way this session created
`worktree-lake-api-client` — native worktree tool preferred, git fallback
otherwise). SPEC, IMPLEMENT, and BACKTEST all happen there. This solves
the public-repo problem IMQuantFund never had: an idea that turns out to be
noise never touches `main`, so `strategies/` never carries abandoned
research.

`docs/research/`'s state files are the exception — they commit straight to
`main` after every stage, regardless of verdict, matching IMQuantFund's
"the registry is always visible, append-only" principle. Research notes
are not the same risk as shipping an unvalidated strategy in the sdist, so
they don't need the same gate. Concretely: the loop makes two kinds of
commits per stage — one on the research branch (code), one on `main`
(process docs) — except at IDEATE (no branch exists yet; backlog updates
go straight to `main`) and ORIENT (read-only, no commit).

## Verdicts

| Verdict | Meaning | Git action |
|---|---|---|
| **Archive** | Idea doesn't clear the gates, no salvageable variant | Branch not merged. Delete it or park it — the loop logs the decision in the registry either way; disposal is a judgment call at review time, not automated. |
| **Improve** | Close, but a specific variant is worth trying | Branch stays alive (not merged); spawns a follow-up backlog idea referencing it. |
| **Merge** | A real finding, but not a standalone strategy (e.g. a feature/signal worth folding into an existing sleeve) — named for what happens to the *finding*, not the git branch | The insight text is merged into `knowledge.md` on `main`. No `strategies/` file is created, and the research branch itself is **not** git-merged — don't conflate the two "merge"s. |
| **Ship** | Clears every mandatory gate | `strategies/<name>.py` (+ any validation script, following the `validate_sctr_momentum_regime_gated.py` precedent) merges into `main`, added to `release/public_artifacts.txt` (`sdist` target) — identical treatment to `sctr_momentum_regime_gated.py`. This is the loop's terminal state; there is no paper-trading follow-up. |

"Ship" replaces IMQuantFund's "Production Candidate" naming — there's no
paper-trading pipeline downstream in this project, so "Ship" (merge to
`main`, join the public sdist) is the actual terminal, not a handoff point.

## Gates

Mapped onto `quantjourney-bt`'s existing evaluation primitives — no custom
evaluation code needed, unlike IMQuantFund which built its own
(`imqf_backtest.evaluate_by_regime` etc.):

- **IR vs. lazy benchmark (mandatory).** `backtester.engines.benchmark`'s
  `excess_return`/`active_return`/`compute_benchmark_summary`, against the
  `Backtester`'s existing `benchmark_symbol` config. A high-Sharpe/
  zero-IR result is beta and gets rejected, same rule as IMQuantFund's
  registry row 1 lesson.
- **Walk-forward robustness (mandatory).** `backtester.walkforward.
  WalkForwardEngine` with `WalkForwardConfig` — rolling, expanding, or
  anchored scheme chosen per the spec's evaluation plan, with
  `purge_days`/`embargo_pct` set as needed on top of whichever scheme is
  picked (not a separate scheme; `cpcv` exists as a config value but
  isn't implemented yet); Sharpe decay IS→OOS is a reject signal per
  `qj-report-analyst`'s existing guidance.
- **Deflated Sharpe, honest about trial count.**
  `backtester.walkforward.statistics.deflated_sharpe.deflated_sharpe`,
  with `n_trials` sourced by counting that strategy family's rows in
  `trial-registry.md` — same accounting principle as IMQuantFund's
  registry-driven `n_trials`.
- **Overfit probability.** `backtester.walkforward.statistics.pbo.
  probability_of_backtest_overfitting`.
- **Cost sweep** for turnover-heavy strategies — vary
  `backtester/execution/`'s commission/slippage configuration across
  runs, confirm the edge survives realistic costs (`qj-report-analyst`'s
  existing "a strategy that only works at zero cost does not work" rule).
- **Regime evidence** (diagnostic, not a hard gate) — the report's
  existing crisis-analysis breakdown, judged via `qj-report-analyst`,
  distilled into `knowledge.md`.

Target Sharpe > 1.5 net is the aspiration, same as IMQuantFund; IR and
robustness gates are mandatory regardless of Sharpe. Cadence target:
2-3 Shipped strategies/month — a planning guide, never a reason to loosen
a gate. A month with zero Ships because nothing cleared the bar is a
correct outcome, not a failure of the loop.

## Data scope

Ideation is constrained to what `backtester/lake_api.py` and
`backtester/local_lake.py` actually serve: US equities, daily bars
(`equity_bars_1d_yahoo_adj`), the six research-tier feature datasets
listed above, and PIT S&P 500/NASDAQ-100/Dow 30 membership. No intraday,
futures, forex, options, or order flow — same constraint IMQuantFund's
loop already operates under, inherited directly since it's the same
underlying lake.

## Infra preflight (before any BACKTEST stage)

Both data paths need to be reachable, since the two migrated datasets
route over HTTP and two stay on direct MinIO:

- Lake API: a lightweight reachability check against `QJ_LAKE_API_URL`
  (e.g. hitting its docs/health surface) before running `lake_api.
  read_bars`/`read_features` for real.
- MinIO: the existing `QJ_LOCAL_LAKE_*`-configured `local_lake.read_pit`
  path succeeding on a small probe read.

If either is down: log the blocker to `loop-log.md` and stop — do not fake
numbers or switch stages, same rule as IMQuantFund's loop.

## Skill orchestration

The loop skill (`skills/qj-research-loop/SKILL.md`) is an orchestrator, not
a strategy-writing guide — `quantjourney-bt` already has craft skills
IMQuantFund's loop had no equivalent of, so the loop skill defers to them
instead of re-explaining their content:

- `qj-strategy-ideas` — at SPEC/IMPLEMENT, decide weight- vs. order-mode
  and find the nearest existing pattern to start from.
- `qj-strategy-author` — keep the new strategy file clean and
  conventional.
- `qj-config-helper` — rebalance policy, risk overlay, and `Backtester`
  configuration choices.
- `qj-strategy-reviewer` — correctness checklist (look-ahead, exposure,
  cost realism, mode fit) before a strategy's code is trusted.
- `qj-report-analyst` — interpreting the backtest report and walk-forward
  diagnostics; judging trustworthiness.

## Hard rules (inherited from IMQuantFund's loop, adapted)

- All data via `backtester.lake_api`/`backtester.local_lake` — never
  reach for `yfinance`/other sources mid-loop; that would silently break
  PIT correctness.
- Every backtest, including failed variants, gets a registry row;
  registry is append-only (strike-through, never edit/delete).
- Full-calendar evaluation; the engine's existing `shift(1)` booking
  convention is the PIT law — no strategy may see its own forward return.
- No TODO stubs, skipped tests, or placeholder results — a blocker is
  logged honestly in `loop-log.md` instead.
- One stage per run.

## Out of scope for this spec

- The `_TEMPLATE.md` spec template's exact section-by-section content,
  the loop skill's exact file text, and the registry/backlog table
  schemas — implementation-level detail for the plan, not a design
  decision.
- Any paper-trading, live-trading, or execution-venue integration —
  explicitly not this project's mandate (confirmed by the "Ship" verdict
  being the loop's actual terminal state, not a handoff).
- Changes to IMQuantFund's own `quant-research-loop` skill or its
  `docs/research/` — read-only reference, not touched by this work.
- Automating branch disposal for the Archive verdict (delete vs. park) —
  left as a judgment call logged in the registry, not scripted.
