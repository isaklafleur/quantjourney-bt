# Research Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold `quantjourney-bt`'s own daily research pipeline — the `docs/research/` state files, a spec template, and the orchestrating `skills/qj-research-loop/SKILL.md` — so a future loop invocation has a complete, self-consistent starting point to read from.

**Architecture:** Pure documentation/scaffolding, no application code. Four small files establish the loop's persistent state (empty, ready for the first real invocation to populate), one template defines the shape of every future strategy spec, and one skill file orchestrates the daily state machine, deferring to `quantjourney-bt`'s existing `qj-*` skills and native `backtester.walkforward`/`backtester.engines.benchmark` modules for the actual craft and gates. Every cross-reference between these files must resolve to a real path by the end of the plan.

**Tech Stack:** Markdown only. No Python, no tests in the pytest sense — "testing" here means verifying files exist with the required structure and that every path/skill reference in the new content resolves to something real.

## Global Constraints

- New files only: `docs/research/knowledge.md`, `docs/research/backlog.md`, `docs/research/trial-registry.md`, `docs/research/loop-log.md`, `docs/research/strategies/_TEMPLATE.md`, `skills/qj-research-loop/SKILL.md`. One existing file modified: `skills/README.md`.
- No `docs/research/regimes.md` — per the design spec, regime evidence lives in `knowledge.md`'s own section instead.
- The loop skill's terminal verdicts are exactly: Archive / Improve / Merge / Ship (not IMQuantFund's "Production Candidate").
- `skills/qj-research-loop/SKILL.md` gets YAML frontmatter (`name`, `description`) even though the existing `qj-*` skills in this repo don't have any — those are manually-referenced style guides ("point the AI assistant at the relevant SKILL.md"); this one is an actively-invoked pipeline step ("Use when asked to run the research loop"), matching IMQuantFund's `quant-research-loop` skill's own use of frontmatter for that reason.
- Gates referenced in the skill must name real, existing `quantjourney-bt` symbols: `backtester.engines.benchmark.excess_return`/`active_return`/`compute_benchmark_summary`, `backtester.walkforward.WalkForwardEngine`/`WalkForwardConfig`, `backtester.walkforward.statistics.deflated_sharpe.deflated_sharpe`, `backtester.walkforward.statistics.pbo.probability_of_backtest_overfitting`.
- Feature dataset names, when listed, must exactly match: `technical_features`, `quality_features`, `sctr_features`, `roic_features`, `value_features`, `earnings_surprise`.
- Data access references must point at `backtester.lake_api` (bars + features) and `backtester.local_lake` (SPY market-ref bars + PIT membership) — never suggest `yfinance` or any other source for loop-driven research.

Spec: `docs/superpowers/specs/2026-07-18-research-loop-design.md`

---

### Task 1: `docs/research/` state file skeletons

**Files:**
- Create: `docs/research/knowledge.md`
- Create: `docs/research/backlog.md`
- Create: `docs/research/trial-registry.md`
- Create: `docs/research/loop-log.md`

**Interfaces:**
- Produces: four markdown files at fixed paths, each empty of real content but with the section structure the loop skill (Task 3) will read from and write into.

- [ ] **Step 1: Create `docs/research/knowledge.md`**

```markdown
# Research Knowledge Base

Distilled lessons from the research loop (`skills/qj-research-loop/SKILL.md`).
Read this file FIRST at the start of every loop run; update it after every
REVIEW stage. Entries are additive — don't delete a lesson because a later
trial contradicts it, note the contradiction instead.

## Lessons

_Empty — no loop runs yet._

## Avoid list

Ideas, signal families, or approaches already tried and rejected, so IDEATE
doesn't regenerate them. One line each, with the registry row or strategy
spec they trace back to.

_Empty — no loop runs yet._

## Regime evidence

Distilled crisis-analysis findings (GFC / COVID / 2022, per
`qj-report-analyst`'s existing crisis breakdown) — how strategy families
have behaved in specific market regimes, gathered across trials. Diagnostic,
not a gate; see the design spec's "Regime evidence" note for why this
project doesn't use IMQuantFund's a-priori regime taxonomy.

_Empty — no loop runs yet._
```

- [ ] **Step 2: Create `docs/research/backlog.md`**

```markdown
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
```

- [ ] **Step 3: Create `docs/research/trial-registry.md`**

```markdown
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
```

- [ ] **Step 4: Create `docs/research/loop-log.md`**

```markdown
# Loop Log

One line per loop invocation (doc: `skills/qj-research-loop/SKILL.md`).
Timestamped, not date-only — the loop can run more than once a day.

| Timestamp | Stage | Strategy/Topic | Outcome |
|---|---|---|---|

_Empty — no loop runs yet._
```

- [ ] **Step 5: Verify all four files exist with the expected section headers**

Run:
```bash
grep -l "^## Lessons" docs/research/knowledge.md
grep -l "^## WIP (max 1)" docs/research/backlog.md
grep -l "^| Timestamp | Strategy |" docs/research/trial-registry.md
grep -l "^| Timestamp | Stage |" docs/research/loop-log.md
```
Expected: each command prints its file's path (grep -l success), no errors.

- [ ] **Step 6: Commit**

```bash
git add docs/research/knowledge.md docs/research/backlog.md docs/research/trial-registry.md docs/research/loop-log.md
git commit -m "docs: scaffold research loop state files"
```

---

### Task 2: `docs/research/strategies/_TEMPLATE.md`

**Files:**
- Create: `docs/research/strategies/_TEMPLATE.md`

**Interfaces:**
- Consumes: nothing (standalone template).
- Produces: the fixed section structure every future `docs/research/strategies/<name>.md` spec must follow — Task 3's skill file references this template by path and by its section names, so they must match exactly: Hypothesis, Data & universe, Implementation notes, Evaluation plan, Results, Regime evidence, Verdict & lessons.

- [ ] **Step 1: Create the template**

```markdown
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
(rolling / expanding / anchored / purged-embargo — see
`backtester.walkforward.WalkForwardConfig`), the benchmark symbol for the
IR gate, and whether a cost sweep applies (turnover-heavy strategies only).

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
```

- [ ] **Step 2: Verify the template has all seven required section headers**

Run:
```bash
grep -c "^## " docs/research/strategies/_TEMPLATE.md
grep "^## " docs/research/strategies/_TEMPLATE.md
```
Expected: count is `7`, and the printed headers are exactly: `## Hypothesis`, `## Data & universe`, `## Implementation notes`, `## Evaluation plan`, `## Results`, `## Regime evidence`, `## Verdict & lessons`.

- [ ] **Step 3: Commit**

```bash
git add docs/research/strategies/_TEMPLATE.md
git commit -m "docs: add the research strategy spec template"
```

---

### Task 3: `skills/qj-research-loop/SKILL.md`

**Files:**
- Create: `skills/qj-research-loop/SKILL.md`

**Interfaces:**
- Consumes: the four state files from Task 1 (by path), the template from Task 2 (by path), and the existing skills `qj-strategy-ideas`, `qj-strategy-author`, `qj-config-helper`, `qj-strategy-reviewer`, `qj-report-analyst` (by name/path — these already exist in the repo, do not create or modify them).
- Produces: the orchestrating skill file itself, referenced by Task 4's `skills/README.md` entry.

- [ ] **Step 1: Create the skill file**

```markdown
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
```

- [ ] **Step 2: Verify the skill file's frontmatter and required sections**

Run:
```bash
head -4 skills/qj-research-loop/SKILL.md
grep "^## " skills/qj-research-loop/SKILL.md
```
Expected: the first 4 lines are the `---`-delimited frontmatter block with
`name: qj-research-loop` and a `description:` line. The section list
includes at least: `## State files (read order matters)`, `## Daily state
machine`, `## Pipeline stages`, `## Git workflow`, `## Verdicts`, `## Gates`,
`## Data scope`, `## Infra preflight (before any BACKTEST stage)`, `## Skill
orchestration`, `## Hard rules`, `## Finishing a run`.

- [ ] **Step 3: Verify every path/skill reference in the new file resolves**

Run:
```bash
test -f docs/research/knowledge.md && echo "knowledge.md OK"
test -f docs/research/backlog.md && echo "backlog.md OK"
test -f docs/research/trial-registry.md && echo "trial-registry.md OK"
test -f docs/research/loop-log.md && echo "loop-log.md OK"
test -f docs/research/strategies/_TEMPLATE.md && echo "_TEMPLATE.md OK"
test -f skills/qj-strategy-ideas/SKILL.md && echo "qj-strategy-ideas OK"
test -f skills/qj-strategy-author/SKILL.md && echo "qj-strategy-author OK"
test -f skills/qj-config-helper/SKILL.md && echo "qj-config-helper OK"
test -f skills/qj-strategy-reviewer/SKILL.md && echo "qj-strategy-reviewer OK"
test -f skills/qj-report-analyst/SKILL.md && echo "qj-report-analyst OK"
test -f backtester/lake_api.py && echo "lake_api.py OK"
test -f backtester/local_lake.py && echo "local_lake.py OK"
test -f backtester/walkforward/statistics/deflated_sharpe.py && echo "deflated_sharpe.py OK"
test -f backtester/walkforward/statistics/pbo.py && echo "pbo.py OK"
test -f backtester/engines/benchmark.py && echo "benchmark.py OK"
```
Expected: all 15 lines print their "OK" message — every file this skill
references by path actually exists in the repo.

- [ ] **Step 4: Commit**

```bash
git add skills/qj-research-loop/SKILL.md
git commit -m "feat: add the qj-research-loop orchestrating skill"
```

---

### Task 4: Wire into `skills/README.md`

**Files:**
- Modify: `skills/README.md`

**Interfaces:**
- Consumes: `skills/qj-research-loop/SKILL.md` (Task 3).

- [ ] **Step 1: Read the current file**

Read `skills/README.md` in full before editing — it currently lists 5
skills in a table plus a "Typical flow" section; confirm the exact text
to anchor the edit against (the table header row is
`| Skill | Use it to |` followed by `|:--|:--|`).

- [ ] **Step 2: Add a row to the skills table and a note distinguishing it from the others**

Insert a new row at the top of the existing table (the research loop is
the entry point that invokes the others, so it belongs first, not
appended):

```markdown
| [`qj-research-loop`](qj-research-loop/SKILL.md) | Run the daily research pipeline (ideate → spec → implement → backtest → review) that drives the other skills below. |
| [`qj-strategy-ideas`](qj-strategy-ideas/SKILL.md) | Turn an idea into a runnable strategy — weights vs orders, the nearest example, the two-method pattern. |
```

(The second line is the existing `qj-strategy-ideas` row, unchanged —
shown here only to make the insertion point unambiguous; the remaining
four existing rows below it are untouched.)

Immediately below the table (before the existing "## Typical flow"
heading), add:

```markdown
`qj-research-loop` is the one skill in this set meant to be actively
invoked ("run the research loop") rather than referenced while writing a
strategy by hand — the others are style guides it defers to at the
right pipeline stage.
```

- [ ] **Step 3: Verify the edit**

Run:
```bash
grep -n "qj-research-loop" skills/README.md
```
Expected: two matches — the table row and the explanatory sentence
below it.

- [ ] **Step 4: Commit**

```bash
git add skills/README.md
git commit -m "docs: list qj-research-loop in the skills catalog"
```
