#!/usr/bin/env bash
# PreToolUse:Bash — Block `gh pr create` that omits `--draft`
#
# Trigger: Bash command that actually INVOKES `gh pr create` (three adjacent
# command tokens `gh` `pr` `create`, per shlex — NOT a string reference to
# "gh pr create" inside a grep pattern / echo / comment).
# Action: Deny unless either:
#   1. `--draft` is present (the default per github-flow/pr.md:13 HARD STOP), or
#   2. the command carries `PR_READY_APPROVED=1` (explicit, auditable opt-out
#      used ONLY when the user explicitly requested a ready PR).
#
# Background: raw `gh pr create` bypasses github-flow/register, which enforces
# "Draft is the DEFAULT". failed-attempts.md "raw gh pr create bypass / non-draft"
# (1st = PR #72 :3743, 2nd = PR #77) — line :3754 pre-authorized this Bash hook.
# Rule body: github-flow/pr.md:13 + :15 (draft default HARD STOP).

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$CMD" ]]; then
  exit 0
fi

# Fast pre-filter — both substrings must be present before the expensive parse.
if ! echo "$CMD" | grep -qE '\bgh\b'; then
  exit 0
fi
if ! echo "$CMD" | grep -q 'create'; then
  exit 0
fi

# Accurate detection via shlex: a real invocation has `gh` `pr` `create` as
# three ADJACENT bare tokens. A quoted "gh pr create" (grep pattern / echo arg)
# stays a single token, so it does not match — eliminating string-reference
# false positives. CMD is passed via env, not stdin.
RESULT=$(PR_CREATE_HOOK_CMD="$CMD" python3 - <<'PY'
import os
import shlex

cmd = os.environ.get("PR_CREATE_HOOK_CMD", "")

try:
    tokens = shlex.split(cmd)
except ValueError:
    # Unparseable (unbalanced quotes etc.) — fail open, do not block.
    print("PASS")
    raise SystemExit(0)

# Locate a real `gh pr create` invocation (three adjacent bare tokens).
invocation = False
for i in range(len(tokens) - 2):
    if tokens[i] == "gh" and tokens[i + 1] == "pr" and tokens[i + 2] == "create":
        invocation = True
        break

if not invocation:
    # Only a string reference (grep/echo/comment) — not an actual invocation.
    print("PASS")
    raise SystemExit(0)

has_draft = any(t == "--draft" or t.startswith("--draft=") for t in tokens)
has_bypass = any(t == "PR_READY_APPROVED=1" for t in tokens)

print("PASS" if (has_draft or has_bypass) else "DENY")
PY
)

if [[ "$RESULT" != "DENY" ]]; then
  exit 0
fi

cat >&2 <<'MSG'
[~/.agents/skills/hook-kit/resources/block-pr-create-without-draft.sh]: DENIED: `gh pr create` must include `--draft`.

Why blocked:
  - Draft is the DEFAULT (github-flow/pr.md:13 HARD STOP). A ready (non-draft) PR
    fires CodeRabbit/Copilot review immediately — cost grows per non-draft PR.
  - PR creation should route through `Skill("github-flow", "register")`, which
    applies the draft default + base-convention checks. Raw `gh pr create` bypasses them.

Required action (pick one):
  1. Add `--draft` to the `gh pr create` command (default), OR
  2. Prefer `Skill("github-flow", "register")` over a raw `gh pr create`, OR
  3. If the user EXPLICITLY requested a ready PR ("ready PR" / "non-draft" / "--ready"),
     prefix the command with `PR_READY_APPROVED=1 gh pr create ...` so the opt-out is auditable.

Reference: failed-attempts.md "raw gh pr create bypass / non-draft" (github-flow/pr.md:13).
MSG
exit 2
