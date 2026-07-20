#!/usr/bin/env bash
# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

# Invokes the qj-research-loop skill once, headlessly, for use by a
# scheduled launchd job (tools/com.quantjourney.research-loop.plist).
# Not part of the public sdist/wheel (tools/ is outside
# release/public_artifacts.txt's tracked roots).
#
# Overlap-safe: skips this invocation if a previous run's PID is still
# alive -- BACKTEST stages (walk-forward, deflated Sharpe, cost sweeps)
# can plausibly run past the hourly interval.
#
# Requires: the `claude` CLI on PATH, already authenticated interactively
# at least once (this script does not handle first-time login).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="$REPO_ROOT/.research-loop.lock"
LOG_DIR="$REPO_ROOT/.research-loop-logs"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
LOG_FILE="$LOG_DIR/$TIMESTAMP.log"

mkdir -p "$LOG_DIR"

if [ -f "$LOCK_FILE" ]; then
    old_pid="$(cat "$LOCK_FILE" 2>/dev/null || echo "")"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) skipped: previous run (pid $old_pid) still in progress" \
            >> "$LOG_DIR/skipped.log"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$REPO_ROOT"

# Distinguishes automated commits from the user's own interactive work in
# `git log` -- only affects commits made by this invocation's subprocesses,
# not global git config.
export GIT_AUTHOR_NAME="QJ Research Loop"
export GIT_AUTHOR_EMAIL="research-loop@quantjourney.local"
export GIT_COMMITTER_NAME="QJ Research Loop"
export GIT_COMMITTER_EMAIL="research-loop@quantjourney.local"

PROMPT="Follow skills/qj-research-loop/SKILL.md exactly. Run today's single \
research loop stage now (ORIENT, then advance the WIP one stage, or \
PROMOTE, or IDEATE, per the state machine). Obey the skill's hard rules, \
especially: never git add -A, only stage files this run created/edited; \
one stage per run, stop after finishing it; log any blocker (e.g. lake \
API or MinIO unreachable) honestly to docs/research/loop-log.md rather \
than faking a result. This is an unattended, scheduled invocation -- \
there is no human present to answer questions, so make the most \
reasonable call yourself on anything genuinely ambiguous and note the \
call you made in the loop log rather than waiting for a response that \
will not come."

claude -p "$PROMPT" \
    --dangerously-skip-permissions \
    --output-format text \
    > "$LOG_FILE" 2>&1

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) completed, log: $LOG_FILE" >> "$LOG_DIR/summary.log"
