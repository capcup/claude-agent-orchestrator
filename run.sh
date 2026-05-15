#!/usr/bin/env bash
#
# Driver for orchestrator.py — runs the full loop per task:
#   plan -> (implement -> review)* -> git commit
#
# Usage:
#   ./run.sh [num_tasks] [max_rework_per_task]
#     num_tasks            how many atomic tasks to attempt (default: 1)
#     max_rework_per_task  implement/review cycles before giving up (default: 4)
#
# Environment (set in .env or exported before calling):
#   TARGET_DIR  directory where the project will be implemented (default: this repo)
#   PYTHON      interpreter to use (default: python)
#
# Note: the orchestrator has no built-in "project finished" signal. The loop
# stops after num_tasks, on a hard failure (circuit breaker / timeout / dirty
# tree), or when a task is not approved within max_rework_per_task cycles.
# APPROVED is detected by the state file being deleted — the only code path
# that removes it.

set -u

ORCH_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$ORCH_DIR/.env" ] && source "$ORCH_DIR/.env"

PYTHON="${PYTHON:-python}"
ORCH="$ORCH_DIR/orchestrator.py"
STATE="$ORCH_DIR/.agent_state.json"
TARGET_DIR="${TARGET_DIR:-$ORCH_DIR}"
export TARGET_DIR

NUM_TASKS="${1:-1}"
MAX_REWORK="${2:-4}"

die() { echo "run.sh: $*" >&2; exit 1; }

command -v claude >/dev/null 2>&1 || die "'claude' CLI not found on PATH."
[ -f "$ORCH" ]                    || die "$ORCH not found — run this from the project repo."
[ -f "$ORCH_DIR/NEW_PROJECT.md" ] || die "NEW_PROJECT.md missing — copy NEW_PROJECT_EXAMPLE.md and fill in your project spec."
git -C "$ORCH_DIR" rev-parse --git-dir >/dev/null 2>&1 || die "orchestrator is not in a git repository."

# Ensure target directory exists and is a git repo.
mkdir -p "$TARGET_DIR"
if ! git -C "$TARGET_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "run.sh: initialising git repo in $TARGET_DIR"
  git -C "$TARGET_DIR" init || die "could not init git repo in $TARGET_DIR."
fi

echo "run.sh: target directory → $TARGET_DIR"

for task in $(seq 1 "$NUM_TASKS"); do
  echo "=== Task $task/$NUM_TASKS: planning ==="
  "$PYTHON" "$ORCH" plan \
    || die "plan failed (dirty tree or planning error) — stopping."

  title="$("$PYTHON" -c "import json;print(json.load(open('$STATE'))['title'])" 2>/dev/null)"
  echo "Planned: ${title:-<unknown>}"

  approved=0
  for ((n = 1; n <= MAX_REWORK; n++)); do
    echo "--- attempt $n/$MAX_REWORK: implement ---"
    "$PYTHON" "$ORCH" implement \
      || die "implement aborted (circuit breaker / timeout) — stopping."

    echo "--- attempt $n/$MAX_REWORK: review ---"
    "$PYTHON" "$ORCH" review
    rc=$?

    if [ ! -f "$STATE" ]; then
      approved=1          # state file gone == APPROVED
      break
    fi
    [ "$rc" -ne 0 ] && echo "review exited $rc (claude timeout/no JSON?) — retrying"
    echo "Not approved yet (needs_rework), retrying..."
  done

  if [ "$approved" -ne 1 ]; then
    die "task '${title:-?}' not approved within $MAX_REWORK cycles — stopping (changes left uncommitted for inspection)."
  fi

  git -C "$TARGET_DIR" add -A
  git -C "$TARGET_DIR" commit \
    -m "${title:-orchestrator task}" \
    -m "Implemented by orchestrator.py (Claude Code CLI)." \
    -m "Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>" \
    || die "git commit failed."
  echo "=== Task $task committed ==="
done

echo "All requested tasks done ($NUM_TASKS)."
