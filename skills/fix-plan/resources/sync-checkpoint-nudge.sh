#!/usr/bin/env bash
# Stop hook — nudge a `sync` run when a tracker referencing PR/Issue numbers
# hasn't been checked against GitHub in a while.
#
# Design (fix-plan/sync-automation.md): this hook makes ZERO network calls.
# It only compares a local checkpoint timestamp against the current time.
# The actual GitHub polling stays inside the `sync` procedure, invoked only
# when the assistant acts on this nudge.
#
# Checkpoint is keyed by a hash of the tracker's absolute path (not session
# id) — sync drift is a property of the file, shared across every session
# working in that workspace, not a per-session counter.
#
# Same block-decision envelope convention as next-trigger.sh /
# check-session-import-gap.sh.

set -uo pipefail

INPUT="$(cat)"
[ -z "$INPUT" ] && exit 0

STOP_HOOK_ACTIVE=$(printf '%s' "$INPUT" | jq -r 'if .stop_hook_active then "true" else "false" end' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0

CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""' 2>/dev/null || echo "")
[ -z "$CWD" ] && exit 0

# Locate a tracker file from cwd upward (mirrors wip/resume.md Step 0.6
# workspace-root discovery — do not assume cwd IS the workspace root).
TRACKER=""
DIR="$CWD"
for _ in 1 2 3 4 5 6; do
  if [ -f "$DIR/.ralph/fix_plan.md" ]; then TRACKER="$DIR/.ralph/fix_plan.md"; break; fi
  if [ -f "$DIR/fix_plan.md" ]; then TRACKER="$DIR/fix_plan.md"; break; fi
  if [ -f "$DIR/checklist.md" ]; then TRACKER="$DIR/checklist.md"; break; fi
  [ "$DIR" = "/" ] && break
  DIR=$(dirname "$DIR")
done
[ -z "$TRACKER" ] && exit 0

# Gate on actual PR/Issue reference presence — a tracker with none cannot
# drift relative to GitHub.
grep -qE '(PR|Issue) #[0-9]+' "$TRACKER" 2>/dev/null || exit 0

STATE_DIR="$HOME/.claude/skills/fix-plan/.state"
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0

TRACKER_HASH=$(printf '%s' "$TRACKER" | shasum -a 1 2>/dev/null | cut -d' ' -f1)
[ -z "$TRACKER_HASH" ] && exit 0
STATE_FILE="$STATE_DIR/sync-checkpoint-${TRACKER_HASH}.ts"

THRESHOLD_HOURS=24
THRESHOLD_SECONDS=$(( THRESHOLD_HOURS * 3600 ))
NOW=$(date +%s)

if [ -f "$STATE_FILE" ]; then
  LAST=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
  case "$LAST" in ''|*[!0-9]*) LAST=0 ;; esac
  ELAPSED=$(( NOW - LAST ))
  [ "$ELAPSED" -lt "$THRESHOLD_SECONDS" ] && exit 0
fi

# Update checkpoint immediately — this is a "block" envelope so the next
# response is guaranteed to see it; no retry-on-failure accounting needed.
echo "$NOW" > "$STATE_FILE"

REASON="<skill-trigger name=\"fix-plan\">Tracker $TRACKER references PR/Issue numbers and has not been sync-checked in over ${THRESHOLD_HOURS}h. Call Skill(\"fix-plan\", \"sync\") (or a role-scoped default run) to batch-verify referenced PR/Issue state against GitHub — see fix-plan/sync.md.</skill-trigger>"

jq -n --arg reason "$REASON" '{"decision":"block","reason":$reason}'
exit 0
