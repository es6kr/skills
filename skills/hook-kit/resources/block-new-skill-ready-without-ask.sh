#!/usr/bin/env bash
# PreToolUse:Bash — Block `gh pr ready` on es6kr/skills PRs that introduce a
# brand-new top-level skills/<dir>/ path not already on origin/main, unless
# explicitly approved.
#
# Trigger: `gh pr ready [<N>] [-R owner/repo]` (adjacent `gh` `pr` `ready`
# tokens per shlex) targeting an es6kr/skills PR whose changed files include
# a skills/<dir>/ path that doesn't exist under skills/ on main.
# `gh api ... ready_for_review` / GraphQL `markPullRequestReadyForReview`
# calls are pattern-matched but pass through unverified (no parseable PR
# number to check the diff against) rather than block blind.
#
# Background: es6kr/skills PR #209 (https://github.com/es6kr/skills/pull/209)
# and PR #207 (https://github.com/es6kr/skills/pull/207) both ran the
# existing 3-axis publication-readiness gate (slug/dedup, publishable
# classification, sanitize) and were STILL silently closed by the user
# because no explicit ask happened before the ready-transition. PR #209's
# ready_for_review fired 51s after creation — far too fast for CI to have
# actually completed, proving the "only after CI is green" clause in
# skills-publishing.md's Auto/Ask matrix was prose-only, not enforced.
# 2nd recurrence of failed-attempts.md class
# public-catalog-skill-publication-without-readiness-vetting.
#
# Draft PR creation + CI runs stay automatic (low-visibility, reversible).
# Only the ready-transition (the "come look, this is done" publish signal)
# is gated, and only for PRs introducing a NEW skill dir — patches to an
# already-published skill are unaffected.
#
# Bypass: NEW_SKILL_READY_APPROVED=1 prefix (explicit, auditable opt-out —
# use only after the user has explicitly approved publishing the new skill).

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$CMD" ]]; then
  exit 0
fi

# Fast pre-filter — require `gh` AND a ready-transition marker before the
# expensive parse/network calls.
if ! echo "$CMD" | grep -qE '\bgh\b'; then
  exit 0
fi
if ! echo "$CMD" | grep -qE '(pr[[:space:]]+ready|ready_for_review|markPullRequestReadyForReview)'; then
  exit 0
fi

if echo "$CMD" | grep -q 'NEW_SKILL_READY_APPROVED=1'; then
  exit 0
fi

# Resolve a working Python interpreter (same guard as block-pr-create-without-draft.sh
# — Windows python3 App Execution Alias opens the Microsoft Store instead of
# running; fail OPEN when none found rather than blocking every command).
PYBIN=""
for _cand in python3 python py; do
  _p=$(command -v "$_cand" 2>/dev/null) || continue
  case "$_p" in
    *[Ww]indows[Aa]pps*) continue ;;
  esac
  PYBIN="$_cand"; break
done
if [[ -z "$PYBIN" ]]; then
  exit 0
fi

RESULT=$(NEW_SKILL_READY_HOOK_CMD="$CMD" "$PYBIN" - <<'PY'
import os
import re
import shlex
import subprocess

cmd = os.environ.get("NEW_SKILL_READY_HOOK_CMD", "")

try:
    tokens = shlex.split(cmd)
except ValueError:
    # Unparseable (unbalanced quotes etc.) — fail open, do not block.
    print("PASS")
    raise SystemExit(0)

pr_number = None
repo = None
found_invocation = False

# `gh pr ready [<N>] [-R owner/repo]` — three adjacent bare tokens.
for i in range(len(tokens) - 2):
    if tokens[i] == "gh" and tokens[i + 1] == "pr" and tokens[i + 2] == "ready":
        found_invocation = True
        j = i + 3
        while j < len(tokens):
            t = tokens[j]
            if t in ("-R", "--repo") and j + 1 < len(tokens):
                repo = tokens[j + 1]
                j += 2
                continue
            if not t.startswith("-") and pr_number is None:
                pr_number = t
            j += 1
        break

if not found_invocation:
    # Only `gh api ... ready_for_review` / GraphQL mutation string matched
    # the pre-filter — no parseable `gh pr ready <N>` invocation. Without a
    # verifiable PR number we cannot safely fetch the diff, so fail OPEN
    # (do not block blind on a pattern we cannot check) rather than deny.
    print("PASS")
    raise SystemExit(0)

if repo is None:
    try:
        out = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True, text=True, timeout=8,
        )
        repo = out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        repo = None

if repo != "es6kr/skills":
    print("PASS")
    raise SystemExit(0)

if pr_number is None:
    # `gh pr ready` with no arg operates on the current branch's PR.
    try:
        out = subprocess.run(
            ["gh", "pr", "view", "--json", "number", "-q", ".number"],
            capture_output=True, text=True, timeout=8,
        )
        pr_number = out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        pr_number = None

if not pr_number or not pr_number.isdigit():
    print("PASS")
    raise SystemExit(0)

try:
    files_out = subprocess.run(
        ["gh", "pr", "view", pr_number, "-R", repo, "--json", "files",
         "-q", ".files[].path"],
        capture_output=True, text=True, timeout=15,
    )
except Exception:
    print("PASS")
    raise SystemExit(0)

if files_out.returncode != 0:
    print("PASS")
    raise SystemExit(0)

skill_dirs = set()
for line in files_out.stdout.splitlines():
    m = re.match(r"^skills/([^/]+)/", line.strip())
    if m:
        skill_dirs.add(m.group(1))

if not skill_dirs:
    print("PASS")
    raise SystemExit(0)

try:
    tree_out = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/skills", "-q", ".[].name"],
        capture_output=True, text=True, timeout=15,
    )
except Exception:
    print("PASS")
    raise SystemExit(0)

if tree_out.returncode != 0:
    # Can't verify main's skill list — fail open rather than block blind.
    print("PASS")
    raise SystemExit(0)

existing_dirs = set(tree_out.stdout.split())
new_dirs = sorted(d for d in skill_dirs if d not in existing_dirs)

print("DENY:" + ",".join(new_dirs) if new_dirs else "PASS")
PY
)

if [[ "$RESULT" != DENY* ]]; then
  exit 0
fi

NEW_DIRS="${RESULT#DENY:}"

cat >&2 <<MSG
[~/.agents/skills/hook-kit/resources/block-new-skill-ready-without-ask.sh]: DENIED: gh pr ready introduces new skill dir(s) without explicit approval.

Why blocked:
  - Detected new top-level skill dir(s) not on es6kr/skills main: ${NEW_DIRS}
  - The 3-axis publication-readiness gate (slug/dedup, publishable
    classification, sanitize) is necessary but not sufficient — PR #209 and
    PR #207 both passed it and were still silently closed because no
    explicit user ask happened before the ready-transition (2nd recurrence,
    failed-attempts.md class
    public-catalog-skill-publication-without-readiness-vetting).
  - draft PR creation + CI runs stay automatic; only the ready-transition
    (the "come look, this is done" signal) is gated for NEW skill
    introductions.

Required action:
  1. AskUserQuestion the user for explicit go-ahead on publishing: ${NEW_DIRS}
  2. Once approved, prefix the command: NEW_SKILL_READY_APPROVED=1 gh pr ready ...

Reference: skills-publishing.md "Publication-readiness gate before committing a new skill publicly";
  skill-kit publish-scope.md "New-skill publication-readiness gate".
MSG
exit 2
