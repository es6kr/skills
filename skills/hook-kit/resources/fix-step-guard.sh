#!/usr/bin/env bash
# PostToolUse:Skill — Enforce full /fix procedure after skill load
# When the fix skill is loaded, remind all Step 0–4 procedures

INPUT=$(cat)
SKILL_NAME=$(echo "$INPUT" | grep -o '"skill"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ "$SKILL_NAME" == "fix" ]]; then
  cat <<'MSG'
⚠️ /fix procedure enforced (HARD STOP — skipping steps = procedure violation):
  Step 0: TaskCreate 4 items (fix-0~3) — first tool call MUST precede any text output
  Step 1: Why 1→2→3→4→5 analysis (no trivial exceptions)
  Step 2: Prompt fix (skill / rule / agent / memory / hook)
  Step 3: Complete original task (produce the user's requested deliverable, not just the fix itself)
  Step 4: Completion report + separate incomplete items + task cleanup
MSG
fi
