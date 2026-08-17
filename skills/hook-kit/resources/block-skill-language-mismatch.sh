#!/usr/bin/env bash
# PreToolUse:Edit/Write — Block Korean text inside English-described skill files.
#
# Trigger: Edit or Write on a `.md` file inside `skills/<name>/`.
# Action: Deny when the same-dir SKILL.md `description:` field contains zero
#         Hangul characters but the new content contains 1+ Hangul characters.
#
# Background: opensource.md "Skill language = SKILL.md frontmatter description
# language (HARD STOP)" has recurred 3 times despite rule strengthening
# (2026-05-19 / 2026-05-21 / 2026-05-25). Per fix.md escalation, 3rd recurrence
# requires hook implementation in the same fix's Step 2 — this script.
#
# Detection details:
#   - Language signal = Hangul presence (`[가-힣]`) in the description field.
#     English description → zero Hangul → strict mode.
#     Korean description  → 1+ Hangul → permissive (Korean skills may use
#                                      English technical terms).
#   - File scope = `.md` files only (data/code files skipped).
#   - Skill dir resolution = nearest ancestor directory that contains
#     `SKILL.md`.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Edit|Write) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Only enforce on .md files inside a skills/<name>/ tree, excluding data/
# subdirectories (local-only, git-ignored, locale content is expected there —
# see opensource.md "PUBLIC repo locale-specific patterns — externalize via
# skill data/ folder"). Header comment above already documents this scope;
# this case statement is where it's actually implemented.
[[ "$FILE_PATH" == *.md ]] || exit 0
case "$FILE_PATH" in
  */skills/*/data/*) exit 0 ;;
  */skills/*/*) ;;
  *) exit 0 ;;
esac

# Resolve the skill root: walk up until we find SKILL.md.
SKILL_ROOT="$(dirname "$FILE_PATH")"
while [[ "$SKILL_ROOT" != "/" && "$SKILL_ROOT" != "." ]]; do
  if [[ -f "$SKILL_ROOT/SKILL.md" ]]; then
    break
  fi
  SKILL_ROOT="$(dirname "$SKILL_ROOT")"
done

[[ -f "$SKILL_ROOT/SKILL.md" ]] || exit 0

# Extract the description field. Handles both single-line
# (`description: text`) and block-scalar (`description: |\n  text`) forms.
DESC=$(awk '
  /^description:[[:space:]]*\|/ { in_block=1; next }
  in_block && /^[^[:space:]]/ { in_block=0 }
  in_block { print; next }
  /^description:/ { sub(/^description:[[:space:]]*/, ""); print; exit }
' "$SKILL_ROOT/SKILL.md")

# Skill language: English when zero Hangul in description.
if echo "$DESC" | grep -qE '[가-힣]'; then
  # Korean skill — permissive, exit.
  exit 0
fi

# English skill — inspect the new content for Hangul.
NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty' 2>/dev/null)
[[ -z "$NEW_CONTENT" ]] && exit 0

if ! echo "$NEW_CONTENT" | grep -qE '[가-힣]'; then
  # Pure English content — allow.
  exit 0
fi

# Collect the first 3 violating lines for the error message.
VIOLATIONS=$(echo "$NEW_CONTENT" | grep -nE '[가-힣]' | head -3)

{
  echo "DENIED: Korean text in an English-described skill file."
  echo ""
  echo "Target file:     $FILE_PATH"
  echo "Skill root:      $SKILL_ROOT"
  echo "Description lang: English (zero Hangul in SKILL.md description)"
  echo ""
  echo "Violating lines (first 3):"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    echo "  $line"
  done <<< "$VIOLATIONS"
  echo ""
  echo "Required action:"
  echo "  - Rewrite the Korean text in English."
  echo "  - User quotes must be paraphrased, not pasted verbatim."
  echo "  - Technical terms (Vault, ArgoCD, etc.) are allowed only in Korean skills."
  echo ""
  echo "Reference: opensource.md 'Skill language = SKILL.md frontmatter description language (HARD STOP)'"
  echo "Failure history: 2026-05-19 / 2026-05-21 / 2026-05-25 (this trigger)"
} >&2

exit 2
