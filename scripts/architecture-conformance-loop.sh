#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROMPT_FILE="$REPO_ROOT/.claude/prompts/architecture-conformance-loop.md"
INTERVAL="${ARCH_CONFORMANCE_LOOP_INTERVAL:-45m}"

cd "$REPO_ROOT"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Missing prompt file: $PROMPT_FILE" >&2
  exit 1
fi

if [[ ! -f "$REPO_ROOT/docs/architecture/conformance-state.md" ]]; then
  echo "Missing state file: docs/architecture/conformance-state.md" >&2
  exit 1
fi

to_seconds() {
  local val="$1"
  if [[ "$val" =~ ^([0-9]+)s$ ]]; then echo "${BASH_REMATCH[1]}"; return; fi
  if [[ "$val" =~ ^([0-9]+)m$ ]]; then echo $((${BASH_REMATCH[1]} * 60)); return; fi
  if [[ "$val" =~ ^([0-9]+)h$ ]]; then echo $((${BASH_REMATCH[1]} * 3600)); return; fi
  if [[ "$val" =~ ^([0-9]+)d$ ]]; then echo $((${BASH_REMATCH[1]} * 86400)); return; fi
  echo "2700"
}

SLEEP_SEC="$(to_seconds "$INTERVAL")"

run_once() {
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[$ts] architecture-conformance-loop tick (interval=$INTERVAL)"
  claude --dangerously-skip-permissions -p "$(cat "$PROMPT_FILE")"
}

echo "architecture-conformance-loop started | repo=$REPO_ROOT | interval=$INTERVAL | prompt=$PROMPT_FILE"
echo "Attach: tmux attach -t arch-conformance-loop"

run_once

while true; do
  sleep "$SLEEP_SEC"
  run_once
done
