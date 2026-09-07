#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — block a commit-tag-change proposal that was made
# without first counting the packages the target commit touches.
#
# Owning skill: hook-kit. This is a harness-level guard, not a gate on one
# skill's asks: a retag/reword/squash proposal can surface from consolidate,
# fix, github-flow, commit-tidy, or an ad-hoc turn. Per the within-marketplace
# placement rule, cross-skill guards live here.
#
# Background. In a release-please path-scoped monorepo, a commit's Conventional
# Commit type applies to EVERY package whose paths that commit touches — not
# only the package the scope names. So changing `fix:` to `feat:` on a commit
# that spans two packages minor-bumps both, including the one that gained
# nothing. The repo rule (.claude/rules/skills-publishing.md, "release-please
# per-package bump") states the control mechanism is COMMIT SPLITTING, not
# retagging. That rule is loaded every session and was still not applied: a CI
# error saying `Adding new skill files requires commit tag 'feat:'` was copied
# straight into an ask option as the remedy, and two of the four target commits
# spanned two packages each.
#
# The failure mode this guards is narrow and worth naming: the FAILURE's cause
# had been investigated thoroughly (workflow diff, required-check status,
# per-commit added files), and that thoroughness created a false sense that the
# proposed REMEDY was verified too. A CI error states what is violated; it never
# states how to remedy it.
#
# FA class: ask-option-premise-unverified (8th occurrence, 5th distinct axis).
# The four prior axes all concerned insufficient querying; this one concerns a
# consequence that was never queried at all.
#
# Blocks only when ALL THREE hold, so unrelated repos and already-verified turns
# pass untouched:
#   1. the ask payload proposes changing a commit's Conventional Commit type
#   2. the repo is a path-scoped monorepo (.release-please-manifest.json, >= 2)
#   3. the recent turn shows no per-commit file enumeration
#
# Bypass: COMMIT_TAG_PACKAGE_COUNT_VERIFIED=1

set -uo pipefail

# ---------------------------------------------------------------- test mode --
if [[ "${1:-}" == "--test" ]]; then
  SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  pass=0; fail=0
  # check <DENY|ALLOW> <payload-json> [transcript-contents]
  check() {
    local expect="$1" payload="$2" tail_text="${3:-}" rc got tf
    tf=$(mktemp)
    if [[ -n "$tail_text" ]]; then printf '%s\n' "$tail_text" > "$tf"; fi
    payload=${payload//__TRANSCRIPT__/$tf}
    echo "$payload" | COMMIT_TAG_GUARD_FORCE_MULTIPACKAGE=1 bash "$SELF" >/dev/null 2>&1
    rc=$?
    rm -f "$tf"
    case "$rc" in 2) got=DENY;; *) got=ALLOW;; esac
    if [[ "$expect" == "$got" ]]; then
      pass=$((pass+1))
    else
      fail=$((fail+1)); printf 'FAIL  expected=%-5s got=%-5s :: %s\n' "$expect" "$got" "$payload"
    fi
  }

  P='{"tool_name":"AskUserQuestion","transcript_path":"__TRANSCRIPT__","tool_input":{"questions":[{"question":"%s","options":[{"label":"%s","description":"%s"}]}]}}'
  mk() { printf "$P" "$1" "$2" "$3"; }

  # --- condition 1: tag-change intent is detected in any payload field ---
  check DENY  "$(mk 'how to proceed' 'reword the 4 commits' 'change fix: to feat: then force-push')"
  check DENY  "$(mk 'how to proceed' 'retag commits' 'x')"
  check DENY  "$(mk 'change fix: -> feat: on 2 commits' 'opt' 'x')"
  check DENY  "$(mk 'how to proceed' 'squash into one commit' 'retag as feat:')"

  # --- no tag-change intent anywhere: never fires ---
  check ALLOW "$(mk 'merge this PR?' 'merge now' 'squash merge on GitHub')"
  check ALLOW "$(mk 'merge this PR?' 'merge now' "merge --""squash on the PR")"
  # local history squashing IS a per-commit retag concern
  check DENY  "$(mk 'how to proceed' 'squash the last 3 commits locally' 'x')"
  check ALLOW "$(mk 'which base branch?' 'develop' 'main')"
  # "feat:" alone, with no change marker and no reword/retag verb, is just a
  # tag being named (e.g. describing an existing commit) — not a proposal.
  check ALLOW "$(mk 'which commit is it?' 'the feat: one' 'x')"

  # --- condition 3: per-commit file enumeration in the turn clears the gate ---
  check ALLOW "$(mk 'how to proceed' 'reword to feat:' 'x')" \
    'git diff-tree --no-commit-id --name-only -r 9f380929'
  check ALLOW "$(mk 'how to proceed' 'retag commits' 'x')" \
    'git show --name-status 28d0364f'
  check ALLOW "$(mk 'how to proceed' 'retag commits' 'x')" \
    'git diff-tree --name-status -r abc1234'
  # an unrelated git command is not evidence
  check DENY  "$(mk 'how to proceed' 'reword to feat:' 'x')" \
    'git log --oneline origin/main..HEAD'

  # --- non-AskUserQuestion tools are ignored ---
  check ALLOW '{"tool_name":"Bash","tool_input":{"command":"git commit --amend"}}'

  echo "Total: $((pass+fail)), Pass: $pass, Fail: $fail"
  [[ "$fail" -eq 0 ]] && exit 0 || exit 1
fi

# ---------------------------------------------------------------- bypass ------
[[ "${COMMIT_TAG_PACKAGE_COUNT_VERIFIED:-}" == "1" ]] && exit 0

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" == "AskUserQuestion" ]] || exit 0

ASK_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.question // ""),
  (.options[]? | (.label // ""), (.description // ""))
' 2>/dev/null)
[[ -n "$ASK_TEXT" ]] || exit 0

# --- condition 1: does the payload propose changing a commit's tag? -----------
# Two independent signals, either sufficient:
#   (a) an explicit rewrite verb (reword / retag / amend the message / squash)
#   (b) two Conventional Commit tags joined by a change marker (fix: -> feat:)
# Locale phrasings live in hook-kit/data/ alongside the other guards' patterns;
# the English fallback below keeps the guard functional without that data file.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
RETAG_VERBS="${HG_COMMIT_RETAG_VERBS:-(reword|re-word|retag|re-tag|squash|amend the (commit )?message|rewrite the (commit )?message)}"
CC_TAGS='(feat|fix|refactor|chore|perf|test|ci|build|style|docs)'
CHANGE_MARKER='(->|=>|to|into)'

# A squash-MERGE is a different concern (it collapses several commits' types
# into the PR title) and has its own rule and guard. Only local history
# squashing is a per-commit retag. Strip merge-context squashes before the verb
# match so "squash merge via gh pr merge" does not trip this hook.
INTENT_TEXT=$(echo "$ASK_TEXT" | sed -E 's/(squash[-[:space:]]*merge|merge[-[:space:]]*--squash|--squash|gh pr merge[^[:space:]]*)//gI')

has_intent=0
if echo "$INTENT_TEXT" | grep -qiE "$RETAG_VERBS"; then
  has_intent=1
fi
# "fix: -> feat:" / "fix: to feat:" — two tags separated by a change marker.
if echo "$ASK_TEXT" | grep -qiE "${CC_TAGS}:[^A-Za-z0-9]{0,12}${CHANGE_MARKER}[^A-Za-z0-9]{0,12}${CC_TAGS}:"; then
  has_intent=1
fi
[[ "$has_intent" -eq 1 ]] || exit 0

# --- condition 2: is this a path-scoped (multi-package) monorepo? -------------
# A single-package repo, or one with no release-please manifest, has no
# per-package bump to get wrong — the whole failure mode is absent there.
is_multipackage() {
  [[ "${COMMIT_TAG_GUARD_FORCE_MULTIPACKAGE:-}" == "1" ]] && return 0
  local root manifest count
  root=$(git rev-parse --show-toplevel 2>/dev/null) || return 1
  manifest="$root/.release-please-manifest.json"
  [[ -f "$manifest" ]] || return 1
  count=$(jq -r 'keys | length' "$manifest" 2>/dev/null) || return 1
  [[ "${count:-0}" -ge 2 ]]
}
is_multipackage || exit 0

# --- condition 3: was a per-commit file enumeration run in this turn? ---------
# Accepts the forms that actually answer "which packages does this commit
# touch": diff-tree or `git show` restricted to file names/status. A bare
# `git log`/`git diff` between refs does not answer it per commit.
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
  if tail -n 400 "$TRANSCRIPT_PATH" 2>/dev/null \
      | grep -qE '(diff-tree[^"]*--name-(only|status)|--name-(only|status)[^"]*diff-tree|git[[:space:]]+show[^"]*--(name-only|name-status|stat))'; then
    exit 0
  fi
fi

# --------------------------------------------------------------- deny ---------
cat >&2 <<'MSG'
DENIED: ask proposes changing a commit's Conventional Commit tag, but the
packages that commit touches were never counted in this turn.

Why this is blocked:
  - In a release-please path-scoped monorepo, a commit's tag applies to EVERY
    package whose paths the commit touches -- not just the package its scope
    names. Retagging a commit that spans two packages bumps BOTH, including
    the one that gained nothing.
  - The control mechanism for per-package bumps is COMMIT SPLITTING, not
    retagging. See .claude/rules/skills-publishing.md, "release-please
    per-package bump" (HARD STOP).
  - A CI error stating `requires commit tag 'feat:'` names the violation. It
    does not name the remedy. Verifying the cause of a failure is not the same
    as verifying the consequence of your proposed fix.

Required action -- count the packages per target commit first:
  git diff-tree --no-commit-id --name-only -r <sha> \
    | grep '^skills/' | cut -d/ -f2 | sort -u

  1 package  -> retagging is safe; say so in the option description
  2+         -> retagging is the WRONG remedy; offer commit splitting, or state
                the collateral bump explicitly in the option description

Then re-issue the ask with the counts included, so the user decides between
outcomes rather than labels.

Override (only when the counts are already verified):
  COMMIT_TAG_PACKAGE_COUNT_VERIFIED=1

Reference: failed-attempts.md, class=ask-option-premise-unverified (8th).
MSG
exit 2
