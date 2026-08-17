#!/usr/bin/env bash
# PreToolUse:Edit/Write — Block skill files from cross-referencing rule files
# or non-distributed personal-only skill data paths.
#
# Trigger: Edit or Write whose file_path is under a skills/<name>/ tree
#          (SKILL.md or a topic .md / resources file), excluding edits to a
#          file that itself lives under a skill's own data/ directory.
# Action: Deny when the content being written (new_string for Edit, content
#         for Write) contains a literal path token pointing at:
#         (a) a rule file (~/.agents/rules/... or .claude/rules/...), or
#         (b) a non-distributed personal-only skill data path
#             (failed-attempts.md, or a skills/<name>/data/ / cleanup/data/
#             path segment).
#
# Background: skill-usage.md "Skills must never cross-reference a rule file
# (all skills, HARD STOP)" / skill-kit/portability.md Rule A. Cross-reference
# direction is one-way:
# rules (always-on entry layer) may reference skills (on-demand execution
# layer) for procedure detail; skills must never point back up to a rule.
# Case (b) generalizes the same direction rule: a published/distributed skill
# file (SKILL.md, a topic .md) must not point at a skill's own data/
# directory, since data/ is typically gitignored and not shipped with the
# skill — a fresh install of the skill has no such file, so the reference is
# dead for every user but the author. This hook only stops NEW occurrences in
# the content being written — it does not retroactively scan pre-existing
# violations elsewhere in the same file.

if [[ "${1:-}" == "--test" ]]; then
  SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  pass=0; fail=0
  check() {  # check <DENY|ALLOW> <payload_json>
    local expect="$1" payload="$2" rc got
    echo "$payload" | bash "$SELF" >/dev/null 2>&1
    rc=$?
    case "$rc" in 2) got=DENY;; *) got=ALLOW;; esac
    if [[ "$expect" == "$got" ]]; then
      pass=$((pass+1))
    else
      fail=$((fail+1)); printf 'FAIL  expected=%-5s got=%-5s :: %s\n' "$expect" "$got" "$payload"
    fi
  }

  # DENY — literal rule-path tokens inside a skill file.
  check DENY '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/wip/resume.md","new_string":"See ~/.agents/rules/common.md for the general tool-error protocol."}}'
  check DENY '{"tool_name":"Write","tool_input":{"file_path":"~/.claude/skills/foo/SKILL.md","content":"Detail: see .claude/rules/git.md"}}'
  check DENY '{"tool_name":"Edit","tool_input":{"file_path":"~/ghq/repo/.claude/skills/bar/topic.md","new_string":"per <repo>/.claude/rules/branch-policy.md"}}'

  # DENY — literal non-distributed personal-data-path tokens inside a skill file.
  check DENY '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/fix-plan/move.md","new_string":"see failed-attempts.md \"some-class\" for a case where this happened"}}'
  check DENY '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/foo/topic.md","new_string":"detail is recorded in cleanup/data/failed-attempts.md"}}'
  check DENY '{"tool_name":"Write","tool_input":{"file_path":"~/.claude/skills/foo/SKILL.md","content":"see skills/foo/data/notes.md for the full history"}}'

  # ALLOW — normal-sample false-positive checks (5+).
  check ALLOW '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/wip/resume.md","new_string":"Check TaskList before proceeding."}}'
  check ALLOW '{"tool_name":"Edit","tool_input":{"file_path":"~/.agents/rules/common.md","new_string":"See ~/.agents/rules/git.md for account mapping."}}'
  check ALLOW '{"tool_name":"Write","tool_input":{"file_path":"~/.claude/skills/foo/SKILL.md","content":"This mirrors the pattern documented in the git commit rules."}}'
  check ALLOW '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/foo/data/notes.txt","new_string":"~/.agents/rules/common.md"}}'
  check ALLOW '{"tool_name":"Bash","tool_input":{"command":"grep foo ~/.agents/rules/common.md"}}'
  check ALLOW '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/foo/SKILL.md","new_string":"Rules reference skills for procedure detail, never the reverse."}}'
  check ALLOW '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/cleanup/data/failed-attempts.md","new_string":"see cleanup/data/failed-attempts.md for the prior occurrence"}}'
  check ALLOW '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/foo/SKILL.md","new_string":"Sample data files live under a per-user data directory."}}'
  check ALLOW '{"tool_name":"Edit","tool_input":{"file_path":"~/.claude/skills/foo/scripts/run.py","new_string":"Reads config from scripts/data/defaults.json"}}'

  echo "Total: $((pass+fail)), Pass: $pass, Fail: $fail"
  [[ "$fail" -eq 0 ]] && exit 0 || exit 1
fi

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Edit|Write) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Scope: .md files inside a skills/<name>/ tree only.
[[ "$FILE_PATH" == *.md ]] || exit 0
case "$FILE_PATH" in
  */skills/*/*) ;;
  *) exit 0 ;;
esac

# Exclusion: a file that itself lives under a skill's own data/ directory is
# the personal-data store, not distributed skill content — it may freely
# reference itself or sibling data/ paths.
case "$FILE_PATH" in
  */skills/*/data/*) exit 0 ;;
esac

NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty' 2>/dev/null)
[[ -z "$NEW_CONTENT" ]] && exit 0

RULE_VIOLATIONS=$(echo "$NEW_CONTENT" | grep -nE '(~|\.claude|<repo>)?/?\.agents/rules/[A-Za-z0-9_-]+\.md|(~|\.claude|<repo>)?/?\.claude/rules/[A-Za-z0-9_-]+\.md' | head -3)
DATA_VIOLATIONS=$(echo "$NEW_CONTENT" | grep -nE 'failed-attempts\.md|(~|\.claude|\.agents)?/?skills/[A-Za-z0-9_-]+/data/|cleanup/data/' | head -3)

VIOLATIONS=""
REASON=""
if [[ -n "$RULE_VIOLATIONS" ]]; then
  VIOLATIONS="$RULE_VIOLATIONS"
  REASON="cross-references a rule file"
elif [[ -n "$DATA_VIOLATIONS" ]]; then
  VIOLATIONS="$DATA_VIOLATIONS"
  REASON="references a non-distributed personal-only skill data path (e.g. failed-attempts.md, a skill's own data/ directory) — that path is typically gitignored and absent for anyone else who installs this skill"
fi

[[ -z "$VIOLATIONS" ]] && exit 0

{
  echo "DENIED: skill file $REASON."
  echo ""
  echo "Target file: $FILE_PATH"
  echo ""
  echo "Violating lines (first 3):"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    echo "  $line"
  done <<< "$VIOLATIONS"
  echo ""
  if [[ -n "$RULE_VIOLATIONS" ]]; then
    echo "Required action:"
    echo "  - Inline the needed content as self-contained prose in the skill body, OR"
    echo "  - If this is a published skill that genuinely needs the rule, bundle it in the same plugin and use an intra-plugin reference"
    echo "  - Cross-reference direction is rule -> skill only. A rule file may point at this skill; this skill must not point back at a rule file"
    echo ""
    echo "Reference: skill-usage.md 'skills must never cross-reference a rule file' / skill-kit/portability.md Rule A"
  else
    echo "Required action:"
    echo "  - Inline the case detail as self-contained prose in the skill body instead of pointing at the data path, OR"
    echo "  - Drop the pointer entirely if the case detail is not needed for the skill body to make sense"
    echo "  - A skill's own data/ directory (and failed-attempts.md specifically) is typically gitignored and not shipped when the skill is installed elsewhere"
  fi
} >&2

exit 2
