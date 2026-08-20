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

[[ -z "$SKILL_NAME" ]] && exit 0

# Best-effort SKILL.md resolution across common roots. Skill names can carry
# a "marketplace:skill" or "plugin:skill" prefix — only the last segment
# names the actual skill directory.
BARE_NAME="${SKILL_NAME##*:}"
# The prefix is not noise — when present it names the plugin, and a plugin name
# is declared by exactly one marketplace's .claude-plugin/marketplace.json.
# Resolving it back to that marketplace lets the search below stay inside the
# right tree instead of matching same-named skills in unrelated marketplaces.
PLUGIN_PREFIX=""
[[ "$SKILL_NAME" == *:* ]] && PLUGIN_PREFIX="${SKILL_NAME%%:*}"
SKILL_MD=""
AMBIGUOUS_NOTE=""
for root in ~/.claude/skills ~/.agents/skills; do
  if [[ -f "$root/$BARE_NAME/SKILL.md" ]]; then
    SKILL_MD="$root/$BARE_NAME/SKILL.md"
    break
  fi
done
if [[ -z "$SKILL_MD" ]]; then
  # -L is required: marketplace entries are usually symlinks into a checkout,
  # and a plain `find` will not descend through them — every skill that lives
  # under a symlinked marketplace silently fails to resolve, so the hook exits
  # "fail open" and never reminds about the very skills it should cover.
  #
  # Following the symlink lands inside a working checkout, which in this
  # workspace routinely holds several git worktrees under .worktrees/ (or
  # .claude/worktrees/). Each one carries its own copy of every skill, so a
  # single skill name matches N+1 directories and `head -1` picks arbitrarily
  # among them. Observed: this hook pointed at a worktree's cleanup/run.md that
  # was two lines behind the live one, five times in one session. Worktrees are
  # in-progress branches by definition — never the installed copy — so prune
  # them rather than trying to rank the matches.
  # Pruning worktrees is necessary but not sufficient: several marketplaces can
  # each ship a skill of the same name (consolidate, github-flow, code-quality
  # …), and every one of those is a legitimate install, so no prune rule can
  # separate them. `head -1` then picks by directory-walk order — observed
  # answering Skill("es6kr:consolidate") and Skill("es6kr:github-flow") with a
  # different marketplace's copy, even though the call named its plugin.
  #
  # So when the call carries a prefix, resolve it to the one marketplace whose
  # manifest declares that plugin and search only there. Without a prefix there
  # is nothing to narrow by, and the search stays global.
  SEARCH_ROOTS=(~/.claude/plugins/marketplaces ~/.claude/plugins/cache)
  if [[ -n "$PLUGIN_PREFIX" ]] && command -v jq >/dev/null 2>&1; then
    for mf in ~/.claude/plugins/marketplaces/*/.claude-plugin/marketplace.json; do
      [[ -f "$mf" ]] || continue
      if jq -e --arg p "$PLUGIN_PREFIX" \
           '(.plugins // []) | map(.name) | index($p)' "$mf" >/dev/null 2>&1; then
        SEARCH_ROOTS=("$(dirname "$(dirname "$mf")")")
        break
      fi
    done
  fi

  # Plain string + head/grep instead of mapfile: this hook also runs where
  # `env bash` resolves to 3.2 (stock macOS), which has no mapfile.
  CANDIDATE_LIST=$(find -L "${SEARCH_ROOTS[@]}" -maxdepth 6 \
    \( -name '.worktrees' -o -name 'worktrees' -o -name '.git' \) -prune -o \
    -type d -iname "$BARE_NAME" -print 2>/dev/null)
  CANDIDATE=$(printf '%s\n' "$CANDIDATE_LIST" | head -1)
  CANDIDATE_COUNT=$(printf '%s\n' "$CANDIDATE_LIST" | grep -c . )
  if [[ -n "$CANDIDATE" && -f "$CANDIDATE/SKILL.md" ]]; then
    SKILL_MD="$CANDIDATE/SKILL.md"
  fi
  # More than one survivor means the narrowing above could not decide. Say so
  # rather than presenting an arbitrary pick as if it were the answer — a wrong
  # path here is silent, because it still resolves to a real SKILL.md.
  if [[ "$CANDIDATE_COUNT" -gt 1 ]]; then
    AMBIGUOUS_NOTE=$'\n\n'"NOTE: ${CANDIDATE_COUNT} directories match \"${BARE_NAME}\" and the call did not narrow to one. The path above is simply the first match — verify it is the installed copy before trusting it:"$'\n'"$(printf '%s\n' "$CANDIDATE_LIST" | sed 's/^/  - /')"
  fi
fi

# Could not resolve the skill directory — fail open (no reminder, no block).
[[ -z "$SKILL_MD" ]] && exit 0

TARGET_DIR="$(dirname "$SKILL_MD")"

# Bare invocation (no args at all) on a MULTI-TOPIC skill.
#
# This branch used to be an unconditional early exit, on the reasoning that no
# args means no topic was requested and therefore nothing to remind about. But
# the injected body for a multi-topic skill is only its router page — the rules
# live in the topic files. A caller who invokes bare, reads the Topics table,
# and proceeds gets the index and never the rules, with no signal that anything
# is missing. That is exactly how a HARD STOP living in one topic file went
# unread and its rule was violated in the same turn the skill was invoked.
#
# Single-topic skills (no Topics/Topic Dispatch table) are unaffected: their
# SKILL.md body IS the content, so a bare invocation is complete on its own.
if [[ -z "$ARGS" ]]; then
  TOPIC_ROWS=$(grep -cE '^\|[^|]+\|[^|]*\|[^|]*\[[a-zA-Z0-9_.-]+\.md\]\(\./[a-zA-Z0-9_.-]+\.md\)' "$SKILL_MD" 2>/dev/null)
  [[ "${TOPIC_ROWS:-0}" -lt 2 ]] && exit 0

  TOPIC_LIST=$(grep -oE '\(\./[a-zA-Z0-9_.-]+\.md\)' "$SKILL_MD" 2>/dev/null \
    | tr -d '()' | sed 's|^\./||' | sort -u | head -12 | tr '\n' ' ')

  cat >&2 <<MSG
Skill("$SKILL_NAME") was invoked with no topic argument, and this skill is
multi-topic ($TOPIC_ROWS topic rows). What got injected is the router page —
the Topics table — NOT the topic bodies. Any HARD STOP, procedure, or gate
defined in a topic file is absent from your context right now.

Topic files in $TARGET_DIR:
  $TOPIC_LIST

Read the topic(s) covering what you are about to do before acting. If the
index genuinely suffices (you only needed the topic list), proceed — but do
not treat the router page as the skill's rules.$AMBIGUOUS_NOTE
MSG
  exit 2
fi

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

TARGET_PATH="$TARGET_DIR/${TOPIC_FILE#./}"

cat >&2 <<MSG
Skill("$SKILL_NAME", "$ARGS") topic dispatch reminder: the tool_result only
carries "Launching skill: $SKILL_NAME" — the injected body is the SKILL.md
router page, not topic content. Read $TARGET_PATH now before acting on the
SKILL.md's own default section (failed-attempts.md
"skill-topic-dispatch-returns-default-section", status=diagnosed — expected
harness behavior, not a bug; topic routing is the skill's own self-instruction).$AMBIGUOUS_NOTE
MSG
exit 2
