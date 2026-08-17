#!/usr/bin/env bash
# PreToolUse hook: Block manual-delegation phrases in gh pr/issue body content
#
# Applied policy (HARD STOP):
#
# - When the assistant runs `gh pr create/edit/comment` or `gh issue create/edit/comment`
#   with a body (via --body, --body-file, or -b), the body must not delegate work to the
#   user that assistant automation could handle instead.
#
# - Delegation phrases target the same pattern the existing AskUserQuestion delegation
#   hook catches, extended to GitHub body content medium.
#
# - This complements block-manual-delegation-without-automation-check.sh, which only
#   scans AskUserQuestion option label/description.
#
# Bypass mechanism (explicit user override):
#
#   ALLOW_GH_BODY_DELEGATION=1 <gh command>
#
# Only prefix when the user has explicitly instructed the assistant that a genuine
# manual step must remain in the body (e.g. a hardware operation only the user can
# perform).
#
# Reference:
# - block-manual-delegation-without-automation-check.sh (AskUserQuestion scope)
# - fix.md — manual delegation without automation check (recurring pattern)

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Only inspect gh pr / gh issue commands that carry a body
if ! echo "$COMMAND" | grep -qE 'gh[[:space:]]+(pr|issue)[[:space:]]+(create|edit|comment)'; then
  exit 0
fi

# Explicit user override
if [[ "$ALLOW_GH_BODY_DELEGATION" == "1" ]]; then
  exit 0
fi
if echo "$COMMAND" | grep -qE 'ALLOW_GH_BODY_DELEGATION=1'; then
  exit 0
fi

# Extract body content — three sources: --body-file <path>, --body "<inline>", -b "<inline>"
BODY=""

# --body-file path
BODY_FILE=$(echo "$COMMAND" | grep -oE -- '--body-file[=[:space:]]+[^[:space:]]+' | sed -E 's/^--body-file[=[:space:]]+//')
if [[ -n "$BODY_FILE" ]]; then
  # Resolve tilde expansion
  BODY_FILE_RESOLVED="${BODY_FILE/#\~/$HOME}"
  if [[ -f "$BODY_FILE_RESOLVED" ]]; then
    BODY=$(cat "$BODY_FILE_RESOLVED" 2>/dev/null)
  fi
fi

# --body "..." (naive extraction — captures quoted content)
if [[ -z "$BODY" ]]; then
  INLINE_BODY=$(echo "$COMMAND" | perl -ne 'if (/--body(?:=|\s+)("([^"\\]|\\.)*"|'"'"'[^'"'"']*'"'"')/) { my $b = $1; $b =~ s/^["'"'"']|["'"'"']$//g; print $b; }' 2>/dev/null)
  if [[ -n "$INLINE_BODY" ]]; then
    BODY="$INLINE_BODY"
  fi
fi

if [[ -z "$BODY" ]]; then
  # No body extractable — skip check
  exit 0
fi

# Delegation phrases (case-insensitive)
BLOCKED_PHRASE=""

# English patterns
if echo "$BODY" | grep -qiE 'manual,?[[:space:]]+one[- ]time|manual[[:space:]]+(step|action|operation|task)|please[[:space:]]+(create|add|set[[:space:]]*up|configure)[[:space:]]+.*(environment|secret|reviewer|scope)[[:space:]]+(in|via)[[:space:]]+.*settings'; then
  BLOCKED_PHRASE=$(echo "$BODY" | grep -iEo 'manual,?[[:space:]]+one[- ]time|manual[[:space:]]+(step|action|operation|task)|please[[:space:]]+(create|add|set[[:space:]]*up|configure)[[:space:]]+.*(environment|secret|reviewer|scope)' | head -1)
fi

# GitHub UI directives — "Settings → X → Y" pattern common in delegation
if [[ -z "$BLOCKED_PHRASE" ]] && echo "$BODY" | grep -qE 'Settings[[:space:]]*(→|->|>)[[:space:]]*(Environments|Secrets|Actions|Branches|Collaborators|Webhooks)'; then
  BLOCKED_PHRASE=$(echo "$BODY" | grep -Eo 'Settings[[:space:]]*(→|->|>)[[:space:]]*(Environments|Secrets|Actions|Branches|Collaborators|Webhooks)' | head -1)
fi

# Korean patterns (hex-encoded for ASCII source compliance)
KO_DELEGATION_PAT=$(printf '\xec\x82\xac\xec\x9a\xa9\xec\x9e\x90[[:space:]]+(\xec\x9e\x91\xec\x97\x85|\xec\xb2\x98\xeb\xa6\xac|\xec\x8b\xa0\xec\x84\xa4|\xec\x83\x9d\xec\x84\xb1|\xec\x84\xa4\xec\xa0\x95|\xec\xb6\x94\xea\xb0\x80)|\xec\x88\x98\xeb\x8f\x99[[:space:]]+(\xec\x9e\x91\xec\x97\x85|\xec\xb2\x98\xeb\xa6\xac|1\xed\x9a\x8c|1 \xed\x9a\x8c|\xec\x83\x9d\xec\x84\xb1|\xec\x8b\xa0\xec\x84\xa4|\xec\x84\xa4\xec\xa0\x95)|GitHub[[:space:]]+UI(\xec\x97\x90\xec\x84\x9c|\xeb\xa5\xbc)[[:space:]]+(\xec\x8b\xa0\xec\x84\xa4|\xec\x83\x9d\xec\x84\xb1|\xec\x84\xa4\xec\xa0\x95|\xec\xb6\x94\xea\xb0\x80)')
if [[ -z "$BLOCKED_PHRASE" ]] && echo "$BODY" | grep -qE "$KO_DELEGATION_PAT"; then
  BLOCKED_PHRASE=$(echo "$BODY" | grep -Eo "$KO_DELEGATION_PAT" | head -1)
fi

if [[ -n "$BLOCKED_PHRASE" ]]; then
  cat >&2 <<EOF
[block-delegation-in-github-body] DENIED: manual-delegation phrase detected in gh body content

Matched phrase: "$BLOCKED_PHRASE"

Reason: The body delegates work to the user that assistant automation could handle:
  - GitHub Environments: gh api --method PUT /repos/{o}/{r}/environments/{name}
  - Secrets: gh secret set (repo/env scope)
  - Branch protection: gh api /repos/{o}/{r}/branches/{b}/protection
  - Reviewers: gh api /repos/{o}/{r}/environments/{name} with reviewers[]
  - UI interactions requiring session: web-browser skill (Playwright/CDP)

Before posting: run the automation, then describe the outcome in the body.
"manual, one-time follow-up" phrasing implies delegation — replace with either:
  (a) "already applied via gh api" — post-automation description, or
  (b) "user override required (reason)" — genuine manual step needed.

To bypass for a genuinely manual step (rare):
  ALLOW_GH_BODY_DELEGATION=1 <gh command>

Reference:
  ~/.agents/skills/hook-kit/resources/block-manual-delegation-without-automation-check.sh
    (AskUserQuestion scope — this hook extends the coverage to gh pr/issue body)
  ~/.claude/skills/cleanup/data/failed-attempts.md "manual delegation"
EOF
  exit 2
fi

exit 0
