#!/bin/zsh
# Single-attempt runner for the qj-research-loop (one pipeline stage per
# invocation). Normally runs INSIDE a cmux workspace pane (spawned by
# research_loop_daily.sh) so the run is visible live; also runs headless as
# that script's fallback.
#
# Adapted from IMQuantFund's scripts/research_loop_attempts.sh (same
# machine, same proven pattern) -- see that file's history for why this
# shape won out: a blind retry loop burned through usage-limit windows and
# a bare `claude -p --dangerously-skip-permissions` launchd invocation
# failed auth outside an interactive/cmux session. Try once; on any
# failure (including a usage-limit hit), log it and stop -- the next
# scheduled fire, at most 1 hour away, retries naturally and idempotently
# (state lives in docs/research/ files, not in this process).
#
# Pidfile lock: refuses to start a second attempt while a prior one
# (tracked by pid, not just presence of the lockfile) is still running --
# BACKTEST stages (walk-forward, deflated Sharpe, cost sweeps) can
# plausibly run past the hourly interval. Self-heals a stale lock left by
# a crashed attempt.
#
# RESEARCH_LOOP_IN_CMUX=1 -> post a cmux notification with the outcome and
# keep the pane's shell open afterwards for inspection.

cd "/Users/isakengdahl/Development/quantjourney-bt" || exit 1
LOG="$HOME/Library/Logs/quantjourney-bt-research-loop.log"
LOCK="$HOME/.local/state/quantjourney-bt/research-loop.lock"
CMUX=/Applications/cmux.app/Contents/Resources/bin/cmux

notify() {  # $1 = title, $2 = body
  if [[ "$RESEARCH_LOOP_IN_CMUX" == 1 ]] && "$CMUX" ping >/dev/null 2>&1; then
    "$CMUX" notify --title "$1" --body "$2" >/dev/null 2>&1
  fi
}

# Only removes the lock if it's still ours (pid match) -- safe to call
# unconditionally, including from the "another attempt is still running"
# skip path below, where the lock belongs to that OTHER process and must
# be left alone.
release_lock() {
  [[ -f "$LOCK" ]] && [[ "$(cat "$LOCK" 2>/dev/null)" == "$$" ]] && rm -f "$LOCK"
}
trap release_lock EXIT INT TERM

finish() {  # $1 = exit code
  release_lock  # must happen before exec below -- exec replaces this
                # process image without running the EXIT trap, so an
                # unreleased lock would wedge every future fire.
  # In a cmux pane, hand over to an interactive shell so the scrollback
  # stays inspectable; the workspace is the user's to close.
  if [[ "$RESEARCH_LOOP_IN_CMUX" == 1 ]]; then
    exec zsh -i
  fi
  exit "$1"
}

mkdir -p "${LOCK:h}"
if [[ -f "$LOCK" ]]; then
  existing_pid=$(cat "$LOCK" 2>/dev/null)
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "[$(date '+%F %T')] research-loop skipped: another attempt (pid $existing_pid) still running, lock $LOCK held" | tee -a "$LOG"
    notify "Research loop skipped" "Previous attempt (pid $existing_pid) still running; this fire skipped."
    finish 0
  fi
  echo "[$(date '+%F %T')] stale lock found (pid ${existing_pid:-unknown} not running); clearing" | tee -a "$LOG"
  rm -f "$LOCK"
fi
echo $$ > "$LOCK"

echo "[$(date '+%F %T')] research-loop attempt" | tee -a "$LOG"
/Users/isakengdahl/.local/bin/claude -p \
  "Run the qj-research-loop skill: execute exactly one research pipeline step, then stop." \
  --model claude-sonnet-5 \
  --permission-mode acceptEdits --verbose 2>&1 | tee -a "$LOG"
claude_status=${pipestatus[1]}

if (( claude_status == 0 )); then
  echo "[$(date '+%F %T')] research-loop success" | tee -a "$LOG"
  notify "Research loop: stage complete" \
    "Latest: $(tail -1 docs/research/loop-log.md | cut -c1-180)"
  finish 0
fi

echo "[$(date '+%F %T')] research-loop failed (exit $claude_status); next scheduled fire (~1h) will retry" | tee -a "$LOG"
notify "Research loop failed" "Exit $claude_status — see $LOG. Next scheduled fire retries in ~1h."
finish 1
