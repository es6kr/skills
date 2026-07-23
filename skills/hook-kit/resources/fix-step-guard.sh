#!/usr/bin/env bash
# PostToolUse:Skill — Enforce full /fix procedure after skill load
# When the fix skill is loaded, remind all Step 0–4 procedures
#
# Output channel: PostToolUse stdout is debug-log only (not model-visible).
# Surface the reminder via stderr + exit 2 per hook-kit/SKILL.md channel spec.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "Skill" ]] && exit 0

SKILL_NAME=$(echo "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null)

if [[ "$SKILL_NAME" == "fix" ]]; then
  cat >&2 <<'MSG'
⚠️ /fix procedure enforced (HARD STOP — skipping steps = procedure violation):
  Step 0: TaskCreate 4 items (fix-0~3) — first tool call MUST precede any text output
  Step 1: Why 1→2→3→4→5 analysis (no trivial exceptions)
  Step 2: Prompt fix (skill / rule / agent / memory / hook)
  Step 3: Complete original task (produce the user's requested deliverable, not just the fix itself)
  Step 4: Completion report + separate incomplete items + task cleanup
MSG
  exit 2
fi
exit 0
