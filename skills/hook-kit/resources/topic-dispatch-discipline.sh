#!/usr/bin/env bash
# PostToolUse:Skill — topic-dispatch-discipline.sh
#
# Root cause (failed-attempts.md "skill-topic-dispatch-returns-default-section",
# status=diagnosed): the Skill tool's tool_result always returns just
# "Launching skill: <name>" — there is no separate topic-content-serving
# mechanism in the harness. The actual SKILL.md body is injected separately,
# and "topic dispatch" is a convention written INSIDE each skill's own
# SKILL.md (a "Topic Dispatch" table instructing the assistant to manually
# Read the mapped topic .md file). When args names a topic, this hook reminds
# the assistant of the exact file to Read — skipping that follow-up Read and
# proceeding on the SKILL.md's own default section is the recurring mistake
# this hook exists to prevent (6+ recurrences in one session before this).
#
# Output channel: PostToolUse stdout is debug-log only (not model-visible).
# Deliver the reminder via stderr + exit 2 per hook-kit/SKILL.md channel spec.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "Skill" ]] && exit 0

SKILL_NAME=$(echo "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null)
ARGS=$(echo "$INPUT" | jq -r '.tool_input.args // empty' 2>/dev/null)

# No skill name, or no args at all (bare invocation — no topic requested).
[[ -z "$SKILL_NAME" || -z "$ARGS" ]] && exit 0

# Best-effort SKILL.md resolution across common roots. Skill names can carry
# a "marketplace:skill" or "plugin:skill" prefix — only the last segment
# names the actual skill directory.
BARE_NAME="${SKILL_NAME##*:}"
SKILL_MD=""
for root in ~/.claude/skills ~/.agents/skills; do
  if [[ -f "$root/$BARE_NAME/SKILL.md" ]]; then
    SKILL_MD="$root/$BARE_NAME/SKILL.md"
    break
  fi
done
if [[ -z "$SKILL_MD" ]]; then
  CANDIDATE=$(find ~/.claude/plugins/marketplaces ~/.claude/plugins/cache -maxdepth 6 -type d -iname "$BARE_NAME" 2>/dev/null | head -1)
  if [[ -n "$CANDIDATE" && -f "$CANDIDATE/SKILL.md" ]]; then
    SKILL_MD="$CANDIDATE/SKILL.md"
  fi
fi

# Could not resolve the skill directory — fail open (no reminder, no block).
[[ -z "$SKILL_MD" ]] && exit 0

# First whitespace-delimited token of the FIRST LINE of args is the candidate
# topic keyword (args after that, including any further lines, are free-text
# context for the invoked topic/procedure). Multi-line args must be truncated
# to line 1 before word-splitting — otherwise awk emits one first-field per
# line, and a later line's leading word (e.g. a bullet's topic-like noun) can
# spuriously match an unrelated Topic Dispatch row.
TOPIC_WORD=$(echo "$ARGS" | head -1 | awk '{print $1}')
[[ -z "$TOPIC_WORD" ]] && exit 0

# Topic Dispatch table row format (seen consistently across multi-topic
# skills): "| topic-word | description | [file.md](./file.md) |"
TOPIC_FILE=$(grep -iE "^\|[[:space:]]*\`?${TOPIC_WORD}\`?[[:space:]]*\|" "$SKILL_MD" 2>/dev/null \
  | grep -oE '\(\./[a-zA-Z0-9_-]+\.md\)' | head -1 | tr -d '()')

# args' first word does not match any row in this skill's Topic Dispatch
# table — nothing to remind about (bare-args skills, free-text procedures).
[[ -z "$TOPIC_FILE" ]] && exit 0

TARGET_DIR="$(dirname "$SKILL_MD")"
TARGET_PATH="$TARGET_DIR/${TOPIC_FILE#./}"

cat >&2 <<MSG
Skill("$SKILL_NAME", "$ARGS") topic dispatch reminder: the tool_result only
carries "Launching skill: $SKILL_NAME" — the injected body is the SKILL.md
router page, not topic content. Read $TARGET_PATH now before acting on the
SKILL.md's own default section (failed-attempts.md
"skill-topic-dispatch-returns-default-section", status=diagnosed — expected
harness behavior, not a bug; topic routing is the skill's own self-instruction).
MSG
exit 2
