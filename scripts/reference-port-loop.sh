#!/usr/bin/env bash
# Reference-port loop: runs claude -p on a fixed cadence with state in reference-port-state.md
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROMPT_FILE="$REPO_ROOT/.claude/prompts/reference-port-loop.md"
INTERVAL="${REFERENCE_PORT_LOOP_INTERVAL:-30m}"
LOG="$REPO_ROOT/loop-run-log.md"

cd "$REPO_ROOT"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Missing prompt file: $PROMPT_FILE" >&2
  exit 1
fi

if [[ ! -f "$REPO_ROOT/docs/architecture/reference-port-state.md" ]]; then
  echo "Missing state file: docs/architecture/reference-port-state.md" >&2
  exit 1
fi

# Convert interval to seconds (supports Nm, Nh, Nd)
to_seconds() {
  local val="$1"
  if [[ "$val" =~ ^([0-9]+)s$ ]]; then echo "${BASH_REMATCH[1]}"; return; fi
  if [[ "$val" =~ ^([0-9]+)m$ ]]; then echo $((${BASH_REMATCH[1]} * 60)); return; fi
  if [[ "$val" =~ ^([0-9]+)h$ ]]; then echo $((${BASH_REMATCH[1]} * 3600)); return; fi
  if [[ "$val" =~ ^([0-9]+)d$ ]]; then echo $((${BASH_REMATCH[1]} * 86400)); return; fi
  echo "1800"
}

SLEEP_SEC="$(to_seconds "$INTERVAL")"

run_once() {
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[$ts] reference-port-loop tick (interval=$INTERVAL)"
  claude --dangerously-skip-permissions -p "$(cat "$PROMPT_FILE")"
}

echo "reference-port-loop started | repo=$REPO_ROOT | interval=$INTERVAL | prompt=$PROMPT_FILE"
echo "Attach: tmux attach -t ref-port-loop"

run_once

while true; do
  sleep "$SLEEP_SEC"
  run_once
done
