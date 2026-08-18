#!/usr/bin/env bash
# PreToolUse:Bash — Block AI-bot review re-triggers when prior review evidence exists.
#
# Trigger commands:
#   - gh pr comment <N> --body "@coderabbitai review" / "@coderabbitai full review" / "/review"
#   - gh pr edit <N> --add-reviewer <copilot|coderabbit bot>
#   - gh api .../pulls/<N>/requested_reviewers -X POST (copilot/coderabbit reviewer)
#
# Policy (consolidate/pr.md Step 2.6):
#   - First review (no prior evidence from this bot on the PR) = autonomous OK -> allow
#   - Re-review (prior evidence exists) = user AskUserQuestion approval required -> deny
#   - Bypass after explicit user approval: prefix the command with BOT_RETRIGGER_APPROVED=1
#
# Evidence = formal reviews AND issue comments from the bot (CodeRabbit posts its
# review output as comments — walkthrough / summarize / zero-findings verdict).
# Fail-open on parse/query errors so unrelated commands are never blocked.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$CMD" ]]; then
  exit 0
fi

# Explicit user-approved bypass (set only after AskUserQuestion approval)
if echo "$CMD" | grep -q 'BOT_RETRIGGER_APPROVED=1'; then
  exit 0
fi

# Detect bot-trigger patterns via shlex token-adjacency (not bare substring) so
# commands that merely REFERENCE a trigger string (grep/echo of "@coderabbitai
# review", or `gh pr view --jq .comments[].body` that prints bot output) are not
# false-positived. Only a real `gh` posting/reviewer command counts as a trigger.
BOT=$(BOT_HOOK_CMD="$CMD" python3 - <<'PY' 2>/dev/null
import os, re, shlex
cmd = os.environ.get("BOT_HOOK_CMD", "")
try:
    toks = shlex.split(cmd)
except ValueError:
    print(""); raise SystemExit(0)
# Skip leading VAR=val env assignments, then require the command word to be `gh`.
i = 0
while i < len(toks) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', toks[i]):
    i += 1
argv = toks[i:]
if not argv or os.path.basename(argv[0]) != "gh":
    print(""); raise SystemExit(0)
sub = argv[1:]
def flag_value(tokens, names):
    for j, t in enumerate(tokens):
        for n in names:
            if t == n and j + 1 < len(tokens):
                return tokens[j + 1]
            if t.startswith(n + "="):
                return t[len(n) + 1:]
    return None
bot = ""
if len(sub) >= 2 and sub[0] in ("pr", "issue") and sub[1] == "comment":
    body = flag_value(sub, ["--body", "-b"]) or ""
    if re.search(r'@coderabbitai\s+(full\s+)?review', body, re.I) or re.search(r'(^|\s)/review(\s|$)', body):
        bot = "coderabbit"
elif len(sub) >= 2 and sub[0] == "pr" and sub[1] == "edit":
    rv = flag_value(sub, ["--add-reviewer"]) or ""
    if re.search(r'copilot', rv, re.I):
        bot = "copilot"
    elif re.search(r'coderabbit', rv, re.I):
        bot = "coderabbit"
elif sub and sub[0] == "api":
    joined = " ".join(sub)
    if "requested_reviewers" in joined:
        if re.search(r'copilot', joined, re.I):
            bot = "copilot"
        elif re.search(r'coderabbit', joined, re.I):
            bot = "coderabbit"
print(bot)
PY
)

if [[ -z "$BOT" ]]; then
  exit 0
fi

# Extract repo (-R / --repo flag) and PR number
REPO=$(echo "$CMD" | grep -oE -- '(-R|--repo)[= ][^ ]+' | head -1 | sed -E 's/(-R|--repo)[= ]//')
PR=$(echo "$CMD" | grep -oE 'gh (pr|issue) (comment|edit|view) [0-9]+' | grep -oE '[0-9]+' | head -1)
if [[ -z "$PR" ]]; then
  # gh api path form: .../pulls/<N>/requested_reviewers
  PR=$(echo "$CMD" | grep -oE 'pulls/[0-9]+' | grep -oE '[0-9]+' | head -1)
fi
if [[ -z "$PR" ]]; then
  # Cannot identify the PR — fail open
  exit 0
fi

REPO_FLAG=()
if [[ -n "$REPO" ]]; then
  REPO_FLAG=(-R "$REPO")
fi

# Count prior review evidence from the bot: formal reviews + review-output comments
COUNT=$(timeout 15 gh pr view "$PR" "${REPO_FLAG[@]}" --json reviews,comments --jq "
  ([.reviews[] | select(.author.login | test(\"$BOT\"; \"i\"))] | length)
  + ([.comments[] | select(.author.login | test(\"$BOT\"; \"i\"))
      | select(.body | test(\"walkthrough_start|summarize by coderabbit|No actionable comments|Action performed\"))] | length)
" 2>/dev/null)

if [[ -z "$COUNT" ]] || ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
  # Query failed — fail open
  exit 0
fi

if [[ "$COUNT" -eq 0 ]]; then
  # First review — autonomous trigger allowed
  exit 0
fi

cat >&2 <<MSG
DENIED: bot review re-trigger — prior review evidence from '$BOT' already exists on PR #$PR ($COUNT item(s)).

Why blocked (consolidate/pr.md Step 2.6):
  - "No actionable comments were generated in the recent review" = COMPLETED review, verdict 0 findings — not a missing review
  - Incremental reviewers do not re-review already reviewed commits; a re-trigger without new commits is pure noise
  - Re-review triggers require explicit user approval via AskUserQuestion

Required action (pick one):
  1. Treat the existing review as final and proceed to collect/classify (usual correct path)
  2. If new commits were pushed after the last review AND the user explicitly approved a re-review
     via AskUserQuestion, re-run prefixed with: BOT_RETRIGGER_APPROVED=1 <command>

Reference: failed-attempts.md "autonomous re-review decision" (3rd recurrence — hook enforced).
MSG
exit 2
