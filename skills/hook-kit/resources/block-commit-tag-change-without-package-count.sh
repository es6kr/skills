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

  # build_transcript <mode> <text> <out-file>
  #   mode=bash    -- <text> becomes a real Bash tool_use command in the
  #                   current turn (genuine evidence)
  #   mode=prose   -- <text> appears only as prose (user text / a tool_result
  #                   string), never as an actual Bash tool_use -- regression
  #                   probe for the self-satisfying-DENY-message bug
  #   mode=padding -- like bash, but padded to ~800KB with filler lines AFTER
  #                   the evidence entry, to reproduce the pipefail/SIGPIPE
  #                   false-DENY bug on realistically large transcripts
  #   mode=none    -- no evidence at all
  build_transcript() {
    local mode="$1" text="$2" out="$3"
    python3 - "$mode" "$text" "$out" <<'PYEOF'
import json, sys

mode, text, out = sys.argv[1], sys.argv[2], sys.argv[3]
lines = [json.dumps({"type": "user", "message": {"role": "user", "content": "turn start"}})]

if mode == "bash":
    lines.append(json.dumps({
        "type": "assistant",
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": text}}
        ]},
    }))
elif mode == "prose":
    # The evidence text is present, but only inside a tool_result string --
    # never as an actual Bash tool_use.command. A raw text scan would treat
    # this as evidence; turn-scoped tool_use parsing must not.
    lines.append(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": [
            {"type": "tool_result", "content": text}
        ]},
    }))
elif mode == "padding":
    filler = "x" * 2000
    lines.append(json.dumps({
        "type": "assistant",
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": text}}
        ]},
    }))
    for i in range(400):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": filler + str(i)}]},
        }))
elif mode == "none":
    pass

with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
PYEOF
  }

  # check <DENY|ALLOW> <payload-json> [evidence-mode] [evidence-text]
  check() {
    local expect="$1" payload="$2" mode="${3:-none}" text="${4:-}" rc got tf
    tf=$(mktemp)
    build_transcript "$mode" "$text" "$tf"
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
  # scoped Conventional Commit tags — the format this repo's own commits use
  check DENY  "$(mk 'which tag?' 'change fix(hook-kit): to feat(hook-kit):' 'x')"

  # --- no tag-change intent anywhere: never fires ---
  check ALLOW "$(mk 'merge this PR?' 'merge now' 'squash merge on GitHub')"
  check ALLOW "$(mk 'merge this PR?' 'merge now' "merge --""squash on the PR")"
  # local history squashing IS a per-commit retag concern
  check DENY  "$(mk 'how to proceed' 'squash the last 3 commits locally' 'x')"
  check ALLOW "$(mk 'which base branch?' 'develop' 'main')"
  # "feat:" alone, with no change marker and no reword/retag verb, is just a
  # tag being named (e.g. describing an existing commit) — not a proposal.
  check ALLOW "$(mk 'which commit is it?' 'the feat: one' 'x')"
  # negation: proposing the SAFE remedy must not itself trip the guard
  check ALLOW "$(mk 'how to proceed' 'do not retag; split the commits instead' 'x')"
  # "squash ... before merging" word order (not just "squash merge")
  check ALLOW "$(mk 'squash these commits before merging the PR?' 'yes' 'x')"
  # regression (issue #505): citing a guard's own filename must not trip the
  # guard even though the filename's substring happens to be a RETAG_VERBS
  # token -- both backtick-quoted and bare forms
  check ALLOW "$(mk 'how to proceed' 'x' 'see `block-squash-subject-without-pr.sh`')"
  check ALLOW "$(mk 'how to proceed' 'x' 'the guard file is block-squash-subject-without-pr.sh')"
  # regression (issue #505): citing a test-result line for an identifier that
  # contains a RETAG_VERBS token must not trip the guard either
  check ALLOW "$(mk 'how to proceed' 'x' 'bats squash-subject 19/19')"
  # regression (found live, 2026-09-21): citing a git ref whose own name
  # contains a RETAG_VERBS token. Branch names are the third identifier shape
  # (after filenames and test-result lines) that carries such a token without
  # proposing anything, and the one an ask is most likely to quote verbatim.
  check ALLOW "$(mk 'how to proceed' 'x' 'branch fix/plane-k3s-ns-and-retag-prose-fp has 5 commits')"
  check ALLOW "$(mk 'which branch?' 'origin/feat/squash-guard-tests' 'x')"
  # regression (5th recurrence, 2026-09-21): merge-STRATEGY prose that merely
  # names squash as the option NOT taken. The pre-existing merge-context
  # stripper only recognised two-word bindings ("squash merge", "--squash"),
  # so a bare `squash` token in ordinary prose fell straight through to
  # RETAG_VERBS even though the payload recommends against squashing.
  check ALLOW "$(mk 'how should this land?' 'merge commit' 'squash is discouraged for this repo')"
  check ALLOW "$(mk 'how should this land?' 'merge commit' 'use merge commit strategy, not squash')"
  check ALLOW "$(mk 'which merge strategy?' 'merge commit' 'the squash strategy collapses per-commit types')"
  check ALLOW "$(mk 'which merge strategy?' 'merge commit' 'merge commit rather than squash')"
  # ... while a bare local-history squash proposal still fires (no merge-
  # strategy context to strip), so widening the stripper must not cost
  # coverage of the case this guard exists for.
  check DENY  "$(mk 'how to proceed' 'squash the last 3 commits locally' 'retag as feat:')"

  # --- condition 3: per-commit file enumeration in the turn clears the gate ---
  check ALLOW "$(mk 'how to proceed' 'reword to feat:' 'x')" \
    bash 'git diff-tree --no-commit-id --name-only -r 9f380929'
  check ALLOW "$(mk 'how to proceed' 'retag commits' 'x')" \
    bash 'git show --name-status 28d0364f'
  check ALLOW "$(mk 'how to proceed' 'retag commits' 'x')" \
    bash 'git diff-tree --name-status -r abc1234'
  # --stat is accepted evidence too (not just --name-only/--name-status)
  check ALLOW "$(mk 'how to proceed' 'retag commits' 'x')" \
    bash 'git diff-tree --stat abc1234'
  check ALLOW "$(mk 'how to proceed' 'retag commits' 'x')" \
    bash 'git show --stat 28d0364f'
  # an unrelated git command is not evidence
  check DENY  "$(mk 'how to proceed' 'reword to feat:' 'x')" \
    bash 'git log --oneline origin/main..HEAD'
  # regression: the DENY message text (this script's own output) reappearing
  # as PROSE in the transcript must NOT count as evidence — only a genuine
  # Bash tool_use does
  check DENY  "$(mk 'how to proceed' 'reword to feat:' 'x')" \
    prose 'Required action -- count the packages per target commit first: git diff-tree --no-commit-id --name-only -r <sha>'
  # regression: genuine evidence must still ALLOW even in a large (~800KB)
  # transcript where a naive `tail | grep -q` pipeline could SIGPIPE under
  # `set -o pipefail` and report a false failure
  check ALLOW "$(mk 'how to proceed' 'reword to feat:' 'x')" \
    padding 'git diff-tree --no-commit-id --name-only -r 9f380929'

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
#   (b) two Conventional Commit tags (optionally scoped) joined by a change
#       marker (fix: -> feat:, fix(scope): to feat(scope):)
# Locale phrasings live in hook-kit/data/ alongside the other guards' patterns;
# the English fallback below keeps the guard functional without that data file.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
RETAG_VERBS="${HG_COMMIT_RETAG_VERBS:-(reword|re-word|retag|re-tag|squash|amend the (commit )?message|rewrite the (commit )?message)}"
CC_TAGS='(feat|fix|refactor|chore|perf|test|ci|build|style|docs)'
CC_SCOPE='(\([^)]*\))?'
CHANGE_MARKER='(->|=>|to|into)'
# "do not retag" / "don't squash" / "never reword" etc. propose the SAFE
# remedy (splitting), not a tag change — these must not count as intent.
NEGATION_VERBS='(do ?n.?t|do not|never|avoid|without|skip)'

# Lowercase first instead of relying on a sed case-insensitive flag: BSD sed's
# `I` flag (used here previously) is only guaranteed from macOS Big Sur
# onward and is a non-standard extension even there. Every match below is
# case-sensitive against this pre-folded copy.
ASK_TEXT_LC=$(printf '%s' "$ASK_TEXT" | tr '[:upper:]' '[:lower:]')

# A payload routinely CITES an identifier that happens to contain a
# RETAG_VERBS token as a substring -- a guard's own filename
# (block-squash-subject-without-pr.sh) or a test-result line
# (bats squash-subject 19/19) -- without proposing any tag change. Strip
# those citation shapes before verb matching so citing them does not trip the
# guard. Plain prose intent ("let's squash these commits") is untouched
# because it lacks the citation markers these patterns require.
#   1. backtick-quoted spans -- this repo's Markdown convention for citing
#      filenames/commands/test output
ASK_TEXT_LC=$(printf '%s' "$ASK_TEXT_LC" | sed -E 's/`[^`]*`//g')
#   2. filename-shaped tokens that reach the matcher without backticks --
#      hyphenated basename + a known script extension
ASK_TEXT_LC=$(printf '%s' "$ASK_TEXT_LC" | sed -E 's/[a-z0-9_]+(-[a-z0-9_]+)*\.(sh|py|js|ts)//g')
#   3. "<identifier> N/N" test-result notation (e.g. "squash-subject 19/19")
ASK_TEXT_LC=$(printf '%s' "$ASK_TEXT_LC" | sed -E 's/[a-z0-9_-]+[[:space:]]+[0-9]+\/[0-9]+//g')
#   4. git refs -- a branch named after the very thing it fixes carries the
#      token in its own name ("fix/...-retag-prose-fp"), and an ask that asks
#      where to send a branch quotes that name verbatim. Anchored on a
#      conventional branch prefix so it strips refs, not arbitrary slashes.
ASK_TEXT_LC=$(printf '%s' "$ASK_TEXT_LC" | sed -E 's#(feat|fix|hotfix|chore|refactor|perf|test|ci|build|style|docs|release|wip)/[a-z0-9._/-]+##g')

# A squash-MERGE is a different concern (it collapses several commits' types
# into the PR title) and has its own rule and guard. Only local history
# squashing is a per-commit retag. Strip merge-context squashes (including the
# "squash ... before merging" word order, not just "squash merge") before the
# verb match so a merge-strategy question does not trip this hook.
INTENT_TEXT=$(printf '%s' "$ASK_TEXT_LC" | sed -E 's/(squash[-[:space:]]*merge|merge[-[:space:]]*--squash|--squash|gh pr merge[^[:space:]]*|squash[^.]{0,40}merg(e|ing))//g')
# The bindings above only recognise squash when it is welded to a merge token.
# Ordinary merge-strategy prose names the bare word instead, and every such
# phrasing below argues about HOW TO MERGE -- several of them argue AGAINST
# squashing -- so none of them proposes rewriting local history. Each pattern
# requires its own qualifier, so a bare "squash the last 3 commits" (the case
# this guard exists for) still reaches the verb match untouched.
#   a. squash as the subject of a judgement: "squash is discouraged"
INTENT_TEXT=$(printf '%s' "$INTENT_TEXT" | sed -E 's/squash(ing)?[[:space:]]+(is|are|was|were)[[:space:]]+(not[[:space:]]+(allowed|permitted|recommended|preferred|used)|discouraged|disallowed|prohibited|forbidden|disabled|banned|unavailable)//g')
#   b. squash as the option NOT taken: "not squash", "rather than squash"
INTENT_TEXT=$(printf '%s' "$INTENT_TEXT" | sed -E 's/(not|no|never|avoid|instead[[:space:]]+of|rather[[:space:]]+than|as[[:space:]]+opposed[[:space:]]+to|versus|vs\.?)[[:space:]]+squash(ing)?//g')
#   c. squash as a merge-strategy noun: "the squash strategy", "squash option"
INTENT_TEXT=$(printf '%s' "$INTENT_TEXT" | sed -E 's/squash[-[:space:]]+(strateg(y|ies)|option|mode)//g')
# Strip negated rewrite-verb clauses ("do not retag; split the commits") so the
# guard's own recommended safe remedy does not itself trip the guard.
INTENT_TEXT=$(printf '%s' "$INTENT_TEXT" | sed -E "s/${NEGATION_VERBS}[[:space:]]+(retag|re-tag|reword|re-word|squash|amend|rewrite)[^.;]*//g")

has_intent=0
if printf '%s' "$INTENT_TEXT" | grep -qiE "$RETAG_VERBS"; then
  has_intent=1
fi
# "fix: -> feat:" / "fix(scope): to feat(scope):" — two tags, each optionally
# scoped, separated by a change marker.
if printf '%s' "$ASK_TEXT_LC" | grep -qiE "${CC_TAGS}${CC_SCOPE}:[^a-z0-9]{0,12}${CHANGE_MARKER}[^a-z0-9]{0,12}${CC_TAGS}${CC_SCOPE}:"; then
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
# touch": diff-tree or `git show` restricted to file names/status/stat. A bare
# `git log`/`git diff` between refs does not answer it per commit.
#
# Scoped to actual Bash tool_use records in the CURRENT turn only (not a raw
# text scan of the transcript) for two reasons found by direct testing:
#   1. A raw `tail | grep` over transcript text is self-satisfying — this
#      script's own DENY message (below) literally contains the enumeration
#      command as example text, so once denied, that text re-entering the
#      transcript on the next turn satisfies a naive text scan with zero real
#      command having run.
#   2. `tail -n 400 ... | grep -qE ...` under `set -o pipefail` (this script
#      uses `-uo pipefail`) can report failure even when grep matched: grep -q
#      exits on its first match and may SIGPIPE `tail` while it is still
#      writing a large transcript, and pipefail then reports the pipeline as
#      failed. Reproduced 10/10 on an ~800KB synthetic transcript with the
#      match near the start.
# Mirrors the turn-scoped parsing already used by this hook-kit skill's own
# block-agent-spawn-without-model.sh Gate C.
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
  if python3 - "$TRANSCRIPT_PATH" <<'PYEOF' 2>/dev/null
import json, re, sys

EVIDENCE_RE = re.compile(
    r'(diff-tree[^"]*--(name-only|name-status|stat)'
    r'|--(name-only|name-status|stat)[^"]*diff-tree'
    r'|git\s+show[^"]*--(name-only|name-status|stat))'
)

entries = []
with open(sys.argv[1], encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue

# Current turn starts at the most recent genuine user prompt (role=user with
# string content) — an AskUserQuestion answer comes back as a tool_result
# (list content), so it does not reset the window.
turn_start = 0
for i in range(len(entries) - 1, -1, -1):
    msg = entries[i].get("message") or {}
    content = msg.get("content")
    if msg.get("role") == "user" and isinstance(content, str):
        turn_start = i
        break

for ent in entries[turn_start:]:
    c = (ent.get("message") or {}).get("content")
    if not isinstance(c, list):
        continue
    for b in c:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
            cmd = (b.get("input") or {}).get("command", "")
            if EVIDENCE_RE.search(cmd):
                sys.exit(0)
sys.exit(1)
PYEOF
  then
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
  git diff-tree --no-commit-id --name-only -r <sha>

  Then group the file paths by this repo's package-root prefix (check
  .release-please-manifest.json's keys for the actual prefix -- "skills/" in
  this repo, but this hook is not repo-specific) and count distinct packages.

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
