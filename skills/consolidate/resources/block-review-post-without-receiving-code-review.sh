#!/usr/bin/env bash
# PreToolUse hook (cross-platform: Claude Code + Antigravity):
# Block a review-flavored PR/issue comment or review POST unless this session has
# actually invoked `Skill("superpowers:receiving-code-review")` beforehand.
#
# Rationale:
#   consolidate/collect.md Step 3.6 is MANDATORY: before classifying any AI review
#   feedback (CodeRabbit/Copilot/internal), the caller must invoke
#   `Skill("superpowers:receiving-code-review")` to load the verify->evaluate->respond
#   protocol. This has already recurred twice (FA class
#   receiving-code-review-superpowers-invocation-omission) because the sibling guard
#   `block-noncompliant-review-comment.sh` only checks whether the POSTED BODY
#   contains the literal "receiving-code-review" link text — a template can carry
#   that link in its title (e.g. "## AI Review Summary — [receiving-code-review](...)")
#   even when the skill was never actually invoked this session. This hook closes
#   that gap by checking the session TRANSCRIPT for a real Skill-tool invocation,
#   not the text of the body being posted.
#
# Cross-platform I/O contract:
#   - Claude Code:  stdin {tool_name, tool_input.command, transcript_path};
#                   block = exit 2 + stderr.
#   - Antigravity:  stdin {toolCall.name, toolCall.args...}; block = stdout
#                   {"decision":"deny","reason":...} (+ exit 0). Antigravity has no
#                   discoverable transcript_path equivalent at this hook's I/O layer,
#                   so on Antigravity this hook fails open (cannot verify -> exit 0)
#                   until that gap is confirmed in a real Antigravity session.
#
# Bypass (explicit user override, per-command only — never session-wide):
#   ALLOW_REVIEW_POST_WITHOUT_RECEIVING_CODE_REVIEW=1 <command>

INPUT=$(cat)

CLAUDE_TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
AG_TOOL=$(echo "$INPUT" | jq -r '.toolCall.name // empty' 2>/dev/null)

RUNTIME=""
COMMAND=""
TRANSCRIPT_PATH=""
if [[ -n "$CLAUDE_TOOL" ]]; then
  RUNTIME="claude"
  [[ "$CLAUDE_TOOL" != "Bash" ]] && exit 0
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
  TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
elif [[ -n "$AG_TOOL" ]]; then
  RUNTIME="antigravity"
  [[ "$AG_TOOL" != "run_command" ]] && exit 0
  COMMAND=$(echo "$INPUT" | jq -r '.toolCall.args.command // .toolCall.args.CommandLine // (.toolCall.args | tostring) // empty' 2>/dev/null)
else
  exit 0
fi
[[ -z "$COMMAND" ]] && exit 0

# --- explicit override ---
if [[ "$ALLOW_REVIEW_POST_WITHOUT_RECEIVING_CODE_REVIEW" == "1" ]] || echo "$COMMAND" | grep -qE 'ALLOW_REVIEW_POST_WITHOUT_RECEIVING_CODE_REVIEW=1'; then
  exit 0
fi

# --- only act on a PR/issue comment or review POST (same detection as the sibling guard) ---
IS_POST=""
echo "$COMMAND" | grep -qE 'gh[[:space:]]+(pr|issue)[[:space:]]+comment' && IS_POST=1
echo "$COMMAND" | grep -qE 'gh[[:space:]]+pr[[:space:]]+review' && IS_POST=1
echo "$COMMAND" | grep -qE 'gh[[:space:]]+api[[:space:]].*(issues/[0-9]+/comments|pulls/[0-9]+/(comments|reviews))' && IS_POST=1
echo "$COMMAND" | grep -qE 'curl[[:space:]].*(issues/[0-9]+/comments|pulls/[0-9]+/(comments|reviews))' && IS_POST=1
[[ -z "$IS_POST" ]] && exit 0

# --- extract the body text (inline --body / --body-file / gh api body=@file / --input) ---
BODY=""
BODY="$(echo "$COMMAND" | grep -oE -- '(--body|-b)[[:space:]]+.*' | head -1)"
BF="$(echo "$COMMAND" | grep -oE -- '--body-file[[:space:]]+[^[:space:]]+' | awk '{print $2}')"
[[ -n "$BF" && -f "$BF" ]] && BODY="$BODY $(cat "$BF" 2>/dev/null)"
AF="$(echo "$COMMAND" | grep -oE -- '(--input[[:space:]]+[^[:space:]]+|body=@[^[:space:]]+)' | sed -E 's/^--input[[:space:]]+//; s/^body=@//')"
[[ -n "$AF" && -f "$AF" ]] && BODY="$BODY $(cat "$AF" 2>/dev/null)"
# Can't inspect the body (heredoc / env var / stdin) -> do NOT block (avoid false positive).
[[ -z "$BODY" ]] && exit 0

# --- is this a review-flavored comment? (same keyword cluster as the sibling guard) ---
REVIEW_FLAVORED=""
if echo "$BODY" | grep -qiE 'coderabbit|copilot|code[ -]?review|review summary' \
   && echo "$BODY" | grep -qiE 'finding|verif|nitpick|actionable|inline comment|(^|[^a-z])(major|minor|critical)([^a-z]|$)'; then
  REVIEW_FLAVORED=1
fi
[[ -z "$REVIEW_FLAVORED" ]] && exit 0

# --- Antigravity: no transcript to check here yet -> fail open ---
if [[ "$RUNTIME" == "antigravity" ]]; then
  exit 0
fi

# --- Claude Code: check the TRANSCRIPT (not the body) for an actual Skill invocation ---
if [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]]; then
  # Can't verify -> fail open rather than wedge the session on an env mismatch.
  exit 0
fi

if grep -F '"name":"Skill"' "$TRANSCRIPT_PATH" 2>/dev/null | grep -qF 'receiving-code-review'; then
  exit 0   # the skill was actually invoked this session — compliant
fi

# --- DENY ---
cat >&2 <<EOF
[block-review-post-without-receiving-code-review] DENIED: this review-flavored PR/issue
POST has no record of Skill("superpowers:receiving-code-review") being invoked in this
session's transcript. consolidate/collect.md Step 3.6 requires that call BEFORE
classifying/posting any AI review feedback — a template containing the literal
"receiving-code-review" link text in its title is NOT the same as the skill actually
having been invoked (that gap is what let this recur; see FA class
receiving-code-review-superpowers-invocation-omission).

Attempted command:
  $COMMAND

Call the Skill tool once this session (skill="superpowers:receiving-code-review"), then
retry. If a subagent will do the actual posting, invoke the skill yourself in the
orchestrating session before dispatching it, or include the call explicitly in the
subagent's instructions.

If this is a genuinely user-approved exception, prefix per-command with:
  ALLOW_REVIEW_POST_WITHOUT_RECEIVING_CODE_REVIEW=1 <command>
EOF
exit 2
