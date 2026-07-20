#!/bin/zsh
# Hourly qj-research-loop runner. SOURCE OF TRUTH lives here in the repo,
# but the LaunchAgent (com.quantjourney.research-loop) runs the INSTALLED
# COPY at ~/.local/bin/quantjourney-bt-research-loop-daily.sh -- mirrors
# IMQuantFund's own research-loop automation (scripts/research_loop_daily.sh
# in that repo), which hardened this exact pattern against a real macOS TCC
# wall (launchd-spawned processes can be denied read access to some
# user folders even when an interactive shell isn't) and an auth failure
# (a bare `claude -p` launchd invocation couldn't authenticate outside an
# interactive/cmux session). Reusing the proven shape rather than
# re-discovering the same failure modes for this repo.
#
# After editing this file, reinstall with:
#   cp tools/research_loop_daily.sh ~/.local/bin/quantjourney-bt-research-loop-daily.sh
#
# Runs the day's pipeline stage VISIBLY in a cmux workspace (launching the
# cmux app if needed); the retry/lock logic lives in
# research_loop_attempts.sh, executed INSIDE the cmux pane. The headless
# fallback below is best-effort only -- it costs nothing and logs the
# attempt, but may hit the same wall a bare launchd process hits.

REPO="/Users/isakengdahl/Development/quantjourney-bt"
LOG="$HOME/Library/Logs/quantjourney-bt-research-loop.log"
CMUX=/Applications/cmux.app/Contents/Resources/bin/cmux
ATTEMPTS="$REPO/tools/research_loop_attempts.sh"

# cmux's socket rejects non-cmux-descendant clients unless
# socketControlMode=password AND the client presents the password. This is
# a machine-level cmux secret, not owned by this repo -- same file
# IMQuantFund's own research-loop automation reads
# (~/.local/state/imqf/cmux-socket-password), since there is one cmux app
# instance on this machine, not one per project.
export CMUX_SOCKET_PASSWORD="$(cat "$HOME/.local/state/imqf/cmux-socket-password" 2>/dev/null)"

# Self-heal: the cmux app rewrites cmux.json at startup and can strip the
# socketPassword field, which locks external clients out again. The app
# live-watches the file, so re-adding the password here takes effect
# immediately -- no restart needed.
if [[ -n "$CMUX_SOCKET_PASSWORD" ]] && ! grep -q socketPassword "$HOME/.config/cmux/cmux.json" 2>/dev/null; then
  echo "[$(date '+%F %T')] re-adding stripped socketPassword to cmux.json" >> "$LOG"
  /usr/bin/python3 - "$CMUX_SOCKET_PASSWORD" <<'PYEOF' >> "$LOG" 2>&1
import json, sys, pathlib
p = pathlib.Path.home() / ".config/cmux/cmux.json"
data = json.loads(p.read_text())
auto = data.setdefault("automation", {})
auto["socketControlMode"] = "password"
auto["socketPassword"] = sys.argv[1]
p.write_text(json.dumps(data, indent=2) + "\n")
PYEOF
  sleep 3  # give the app's file watcher a moment
fi

cd "$REPO" || exit 1

if ! "$CMUX" ping >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] cmux not running; launching app" >> "$LOG"
  open -a cmux
  for _ in {1..12}; do
    sleep 5
    "$CMUX" ping >/dev/null 2>&1 && break
  done
fi

if "$CMUX" ping >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] spawning research-loop workspace in cmux" >> "$LOG"
  if "$CMUX" new-workspace \
    --name "qj-research-loop $(date '+%F %H%M')" \
    --cwd "$REPO" \
    --focus false \
    --command "zsh -lc 'RESEARCH_LOOP_IN_CMUX=1 exec $ATTEMPTS'" >> "$LOG" 2>&1; then
    exit 0
  fi
  echo "[$(date '+%F %T')] cmux new-workspace failed; falling back to headless" >> "$LOG"
else
  echo "[$(date '+%F %T')] cmux unreachable after 60s; falling back to headless" >> "$LOG"
fi

exec "$ATTEMPTS"
