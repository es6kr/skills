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
#   - Language signal, in priority order (matches
#     ~/.agents/rules/language.md's own precedence):
#       1. Explicit `language:` frontmatter field, if present — `language: ko`
#          forces permissive, `language: en` forces strict, regardless of
#          what the description field happens to say.
#       2. Hangul presence (`[가-힣]`) in the description field, when no
#          `language:` field is set. English description → zero Hangul →
#          strict mode. Korean description → 1+ Hangul → permissive (Korean
#          skills may use English technical terms).
#   - File scope = `.md` files only (data/code files skipped).
#   - Skill dir resolution = nearest ancestor directory that contains
#     `SKILL.md`.
#
# Python Unicode codepoint detection works with BSD grep and the C locale.
# A detector error must deny rather than be mistaken for English-only content.
hangul_lines() {
  python3 -c '
import sys
text = sys.stdin.buffer.read().decode("utf-8")
lines = [(i, line) for i, line in enumerate(text.splitlines(), 1)
         if any(0xAC00 <= ord(c) <= 0xD7A3 for c in line)]
for i, line in lines[:3]:
    print(f"{i}:{line}")
'
}

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

# Explicit frontmatter `language:` field — authoritative when present.
# Only read it from inside the frontmatter block (between the first two
# `---` lines) so a `language:` mention elsewhere in the body can't
# accidentally override the skill's declared language.
LANG_FIELD=$(awk '
  /^---[[:space:]]*$/ { fm++; if (fm == 2) exit; next }
  fm == 1 && /^language:[[:space:]]*/ {
    sub(/^language:[[:space:]]*/, "");
    sub(/[[:space:]]*#.*$/, "");
    sub(/[[:space:]]+$/, "");
    print;
    exit
  }
' "$SKILL_ROOT/SKILL.md")

case "$LANG_FIELD" in
  ko) exit 0 ;;   # Explicit Korean — permissive, skip the heuristic entirely.
  en) ;;          # Explicit English — fall through to strict-mode content check.
  *)
    # No explicit override — fall back to the description-Hangul heuristic.
    # Extract the description field. Handles both single-line
    # (`description: text`) and block-scalar (`description: |\n  text`) forms.
    DESC=$(awk '
      /^description:[[:space:]]*\|/ { in_block=1; next }
      in_block && /^[^[:space:]]/ { in_block=0 }
      in_block { print; next }
      /^description:/ { sub(/^description:[[:space:]]*/, ""); print; exit }
    ' "$SKILL_ROOT/SKILL.md")

    # Skill language: English when zero Hangul in description.
    DESC_HANGUL=$(printf '%s' "$DESC" | hangul_lines) || exit 2
    if [[ -n "$DESC_HANGUL" ]]; then
      # Korean skill — permissive, exit.
      exit 0
    fi
    ;;
esac

# English skill — inspect the new content for Hangul.
NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty' 2>/dev/null)
[[ -z "$NEW_CONTENT" ]] && exit 0

# Collect the first 3 violating lines; Python failure is a denial, not an allow.
VIOLATIONS=$(printf '%s' "$NEW_CONTENT" | hangul_lines) || exit 2
if [[ -z "$VIOLATIONS" ]]; then
  exit 0  # Pure English content — allow.
fi

LANG_SOURCE="description (zero Hangul, no language: override)"
[[ "$LANG_FIELD" == "en" ]] && LANG_SOURCE="explicit frontmatter language: en"

{
  echo "DENIED: Korean text in an English-described skill file."
  echo ""
  echo "Target file:     $FILE_PATH"
  echo "Skill root:      $SKILL_ROOT"
  echo "Description lang: English ($LANG_SOURCE)"
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
