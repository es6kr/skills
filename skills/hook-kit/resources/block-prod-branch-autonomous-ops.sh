#!/usr/bin/env bash
# PreToolUse hook: Block autonomous assistant operations on production-like release-trigger branches
#
# Applied policy (HARD STOP):
#
# - Assistant MUST NOT create, push, protect, delete, or otherwise modify branches
#   whose name is `production`, `master`, `release`, `prod`, or `stable` without
#   explicit user instruction. This also covers workflow_dispatch runs targeting
#   one of these branches as the ref (`gh workflow run --ref production`, or the
#   equivalent raw `gh api .../dispatches` call) — a dispatched run can reproduce
#   or trigger real release-path behavior on the branch, same blast-radius class
#   as a direct git mutation. When validating a fix, dispatch against a feature/fix
#   branch (or `beta`, the intended pre-release testing ground) first.
#
# - These branches are release triggers for semantic-release / release-please / GitOps ArgoCD sync.
#   A single push to `production` can immediately trigger stable publish to npm / Marketplace / GHCR
#   with no user review, no dry-run, no rollback path.
#
# - `main` is intentionally NOT covered here — main is the default working branch,
#   and CLAUDE.md's existing "push requires explicit user confirmation" rule already gates it.
#
# Bypass mechanism (explicit user override):
#
#   ALLOW_PROD_BRANCH_OPS=1 <command>
#
# Only prefix with this env var when the operation is user-approved for the specific command.
# Do NOT set it session-wide.
#
# Reference:
# - fix.md — production branch autonomous operation prevention
# - branch-source-matrix.md — release trigger branch policy
# - publishing.md — release-please/semantic-release dry-run HARD STOP

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Explicit user override
if [[ "$ALLOW_PROD_BRANCH_OPS" == "1" ]]; then
  exit 0
fi
if echo "$COMMAND" | grep -qE 'ALLOW_PROD_BRANCH_OPS=1'; then
  exit 0
fi

# Branch names covered — release-trigger branches only. `main` deliberately excluded.
BRANCHES='(production|master|release|prod|stable)'

# Patterns to block. Each targets a distinct autonomous-operation surface.
BLOCKED_REASON=""

# 1. git push origin production / git push origin main:production / git push -u origin production
if echo "$COMMAND" | grep -qE "git[[:space:]]+push[[:space:]]+.*($BRANCHES)(\$|[[:space:]]|:)"; then
  BLOCKED_REASON="git push targeting protected branch"
fi

# 2. git push origin :production  (branch deletion)
if echo "$COMMAND" | grep -qE "git[[:space:]]+push[[:space:]]+.*:$BRANCHES(\$|[[:space:]])"; then
  BLOCKED_REASON="git push deleting protected branch"
fi

# 3. git branch production / git branch -f production / git branch --force production
if echo "$COMMAND" | grep -qE "git[[:space:]]+branch[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*$BRANCHES(\$|[[:space:]])"; then
  BLOCKED_REASON="git branch create/force on protected branch"
fi

# 4. git checkout -b production / git switch -c production
if echo "$COMMAND" | grep -qE "git[[:space:]]+(checkout|switch)[[:space:]]+-[bBcC][[:space:]]+$BRANCHES(\$|[[:space:]])"; then
  BLOCKED_REASON="git branch create via checkout/switch on protected branch"
fi

# 5. gh api ... branches/production (protection rules, deletions, etc.)
if echo "$COMMAND" | grep -qE "gh[[:space:]]+api[[:space:]].*branches/$BRANCHES"; then
  BLOCKED_REASON="gh api mutation on protected branch"
fi

# 6. git worktree add ... production
if echo "$COMMAND" | grep -qE "git[[:space:]]+worktree[[:space:]]+add[[:space:]]+.*$BRANCHES(\$|[[:space:]])"; then
  BLOCKED_REASON="git worktree add on protected branch"
fi

# 7. git update-ref refs/heads/production
if echo "$COMMAND" | grep -qE "git[[:space:]]+update-ref[[:space:]]+refs/heads/$BRANCHES"; then
  BLOCKED_REASON="git update-ref on protected branch"
fi

# 8. gh workflow run <workflow> --ref production / -r production
#    (workflow_dispatch runs are not git mutations, but a run against a protected branch's
#    ref can reproduce/trigger real release-path behavior on that branch — same blast radius
#    class as the git-level patterns above)
if echo "$COMMAND" | grep -qE "gh[[:space:]]+workflow[[:space:]]+run[[:space:]].*(--ref|-r)[[:space:]]+$BRANCHES(\$|[[:space:]])"; then
  BLOCKED_REASON="gh workflow run (workflow_dispatch) targeting protected branch"
fi

# 9. gh api .../actions/workflows/.../dispatches with ref=production (raw API workflow_dispatch)
if echo "$COMMAND" | grep -qE "gh[[:space:]]+api[[:space:]].*actions/workflows/.*dispatches" \
  && echo "$COMMAND" | grep -qE "(-f|-F|--field|--raw-field)[[:space:]]+ref=$BRANCHES(\$|[[:space:]])"; then
  BLOCKED_REASON="gh api workflow_dispatch targeting protected branch"
fi

if [[ -n "$BLOCKED_REASON" ]]; then
  cat >&2 <<EOF
[block-prod-branch-autonomous-ops] DENIED: $BLOCKED_REASON

Reason: Branches matching /(production|master|release|prod|stable)/ are release triggers.
A single autonomous operation on them can trigger real-user-facing publishes (semantic-release,
Marketplace stable, npm dist-tag latest, GitOps ArgoCD sync) with no dry-run and no rollback.

Attempted command:
  $COMMAND

To proceed with a genuinely user-approved operation, prefix the command with
ALLOW_PROD_BRANCH_OPS=1:

  ALLOW_PROD_BRANCH_OPS=1 $COMMAND

Do NOT set the env var session-wide. Prefix per-command only after explicit user instruction.

Reference:
  ~/.agents/rules/git.md — protected branch policy
  ~/.claude/rules/branch-source-matrix.md — release trigger discipline (per-project overlay)
  ~/.claude/rules/publishing.md — new release-trigger branch dry-run HARD STOP
EOF
  exit 2
fi

exit 0
