#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — block an Orca session-launch/handoff question whose
# options never offer splitting the current tab.
#
# Why this exists separately from block-orca-new-tab-without-split-check.sh:
#   That guard watches Bash and fires on `orca terminal create` / `orca worktree
#   create`. But the recurring failure happens one step earlier, while the
#   options are being authored: the question lists "register the repo and launch
#   a new session", "reuse another session", "skip" — and never "split the
#   current tab". The user then has no way to pick the default path, and whatever
#   they choose, no create command is ever issued for the Bash guard to catch.
#   failed-attempts.md class=orca-terminal-split-pane-parameter-omission reached
#   14 occurrences that way, with the Bash guard installed and registered the
#   whole time. The user's own words: the split option is never there.
#
# Spec:
#   If the payload is about launching or handing off an Orca session (an
#   orca-specific token: `orca`, `ORCA_`, `terminal create`, `worktree create`,
#   `terminal split`), then at least one option must mention the split path
#   (split / vertical / horizontal / pane). Otherwise block.
#
#   Three documented exceptions pass without a split option, because splitting
#   genuinely does not apply: the tab already holds 4 panes, the user explicitly
#   asked for a new tab/worktree, or both sessions must edit the same files. The
#   payload has to say so — naming the exception is what makes it auditable.
#
# Self-test:
#   bash <this-script> --test
#   4 positive (block) + 8 negative (allow) fixtures.

set -uo pipefail

# ----- Locale data (Korean keyword set, git-ignored; absent => English only) --
HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_ORCA_HANDOFF_KO="${HG_ORCA_HANDOFF_KO:-}"
HG_ORCA_SPLIT_KO="${HG_ORCA_SPLIT_KO:-}"
HG_ORCA_EXCEPTION_KO="${HG_ORCA_EXCEPTION_KO:-}"

# An orca-specific token is required, so ordinary words like "session" or
# "handoff" in an unrelated question cannot trigger this guard.
ORCA_CTX_EN='\borca\b|orca-ide|orca-dev|ORCA_|terminal create|terminal split|worktree create'
SPLIT_EN='\bsplit\b|vertical|horizontal|\bpane\b|\bpanes\b'
EXCEPTION_EN='pane limit|4 panes|four panes|ORCA_PANE_LIMIT_REACHED|ORCA_NEW_WORKSPACE_APPROVED|ORCA_FILE_CONFLICT|file conflict|same files|user explicitly asked|user asked for a new tab'

join_alt() { # join_alt <english> <korean-or-empty>
  if [[ -n "$2" ]]; then printf '(%s|%s)' "$1" "$2"; else printf '(%s)' "$1"; fi
}

ORCA_CTX=$(join_alt "$ORCA_CTX_EN" "$HG_ORCA_HANDOFF_KO")
SPLIT_PATTERN=$(join_alt "$SPLIT_EN" "$HG_ORCA_SPLIT_KO")
EXCEPTION_PATTERN=$(join_alt "$EXCEPTION_EN" "$HG_ORCA_EXCEPTION_KO")

evaluate() { # evaluate <payload-json>  -> 0 allow, 2 block
  # Evaluate each question independently: neither an option nor an exception
  # in a different question can authorize this launch/handoff.
  printf '%s' "$1" | python3 -c '
import json, re, sys
ctx, split, exception = (re.compile(p, re.I) for p in sys.argv[1:4])

def offers_split(option):
    # Negation applies within a clause, not to affirmative alternatives after
    # a comma/semicolon or contrast. A trailing "not a new tab" is not a denial
    # of a preceding split, while "split unavailable" is.
    for clause in re.split(r"[;,\n]|\b(?:but|instead)\b", option, flags=re.I):
        for match in split.finditer(clause):
            before, after = clause[:match.start()], clause[match.end():]
            denied = re.search(r"\b(?:no|not|never|without|avoid|skip|cannot|cant|dont|disable)\b|don\x27t|can\x27t", before, re.I)
            unavailable = re.match(r"\s*(?:(?:is|are)\s+)?(?:unavailable|unsupported|disabled|not\s+(?:available|possible|allowed))\b", after, re.I)
            if not denied and not unavailable:
                return True
    return False
try:
    payload = json.load(sys.stdin)
except (ValueError, TypeError):
    sys.exit(0)
for q in (payload.get("tool_input") or {}).get("questions") or []:
    options = [" ".join((o.get("label") or "", o.get("description") or ""))
               for o in q.get("options") or []]
    text = "\n".join([q.get("question") or "", q.get("header") or ""] + options)
    # A product/project name alone is not a session-launch decision.
    action = re.search(r"\b(?:launch\w*|start\w*|delegat\w*|hand.?off)\b|session.{0,30}\brun\b|\brun\b.{0,30}session|terminal\s+(?:create|split)|worktree\s+create|repo\s+add", text, re.I)
    # Preserve externally supplied locale handoff triggers when present.
    locale_action = sys.argv[4] and re.search(sys.argv[4], text, re.I)
    if ctx.search(text) and (action or locale_action) and not exception.search(text):
        if not any(offers_split(option) for option in options):
            sys.exit(2)
' "$ORCA_CTX" "$SPLIT_PATTERN" "$EXCEPTION_PATTERN" "$HG_ORCA_HANDOFF_KO"
}

if [[ "${1:-}" == "--test" ]]; then
  pass=0
  fail=0
  test_case() {
    local name=$1 expected=$2 payload=$3 rc=0
    evaluate "$payload" || rc=$?
    if [[ "$rc" -eq "$expected" ]]; then
      pass=$((pass + 1))
      printf '  PASS: %s\n' "$name"
    else
      fail=$((fail + 1))
      printf '  FAIL: %s (expected %s, got %s)\n' "$name" "$expected" "$rc" >&2
    fi
  }

  echo "=== Positive fixtures (should block, rc 2) ==="
  test_case "handoff options omit split" 2 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"How should the es6kr work be handed off? orca has no registered repo.","options":[{"label":"Register repo, new session","description":"orca repo add then worktree create"},{"label":"SendMessage to an existing session","description":"reuse another running session"},{"label":"Hold","description":"defer"}]}]}}'
  test_case "terminal create option without split alternative" 2 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Start the follow-up session?","options":[{"label":"New tab","description":"orca terminal create --worktree active --command claude"},{"label":"Hold","description":"defer"}]}]}}'
  test_case "worktree create framed as the only launch path" 2 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Launch the audit session where?","options":[{"label":"Independent worktree","description":"orca worktree create --no-parent --agent claude"},{"label":"Skip","description":"not now"}]}]}}'
  test_case "orca token in option only, still gated" 2 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Who runs the push?","options":[{"label":"Delegate","description":"hand it to a new orca-ide session"},{"label":"Hold","description":"defer"}]}]}}'

  echo ""
  echo "=== Negative fixtures (should allow, rc 0) ==="
  test_case "split offered as an option" 0 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"How should the work be handed off?","options":[{"label":"Split the current tab","description":"orca terminal split --terminal <handle> --direction vertical"},{"label":"Register repo, new session","description":"orca repo add then worktree create"}]}]}}'
  test_case "pane limit reached is a named exception" 0 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"The tab already holds 4 panes — where should the new session go?","options":[{"label":"New tab","description":"orca terminal create --command claude"},{"label":"Hold","description":"defer"}]}]}}'
  test_case "file conflict is a named exception" 0 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Both sessions must edit the same files — separate worktree?","options":[{"label":"Separate worktree","description":"orca worktree create --no-parent"},{"label":"Hold","description":"defer"}]}]}}'
  test_case "unrelated question mentioning sessions" 0 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Should the session summary go to the wiki or the tracker?","options":[{"label":"Wiki","description":"publish under pages/ops"},{"label":"Tracker","description":"attach to the backlog item"}]}]}}'
  test_case "unrelated handoff of a tracker item" 0 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Hand off the backlog item to whom?","options":[{"label":"Assign to reviewer","description":"set assignee and move to in-progress"},{"label":"Hold","description":"leave unassigned"}]}]}}'
  test_case "PR merge question, no orca token" 0 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Ready the draft PR?","options":[{"label":"Ready it","description":"CI is green on every check"},{"label":"Keep draft","description":"wait for review"}]}]}}'
  test_case "pane word in option satisfies the requirement" 0 \
    '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"Where should the orca session run?","options":[{"label":"Same tab","description":"add a pane next to this one"},{"label":"Hold","description":"defer"}]}]}}'
  test_case "empty payload" 0 '{"tool_name":"AskUserQuestion","tool_input":{}}'

  echo ""
  printf 'PASS=%d FAIL=%d\n' "$pass" "$fail"
  [[ "$fail" -eq 0 ]]
  exit $?
fi

input=$(cat)
rc=0
evaluate "$input" || rc=$?
[[ "$rc" -eq 0 ]] && exit 0

cat >&2 <<'EOF'
============================================================
⛔ [Safety Hook] BLOCKED: Orca session-launch question with no split option.

Why blocked:
  - failed-attempts.md class=orca-terminal-split-pane-parameter-omission has
    recurred 14 times. The Bash-side guard only sees `orca terminal create` /
    `orca worktree create`; this failure happens earlier, while the options are
    written. If "split the current tab" is never offered, the user cannot pick
    the default path and no create command ever reaches the other guard.
  - Below the 4-pane limit, splitting the current tab is the default. A new tab
    or worktree is the exception, not the baseline.

Required action (pick one):
  1. Add the split option. Check the pane budget first — `orca terminal list
     --json` reports a `tabId` per terminal and panes in one tab share it. Under
     4, offer:
       orca terminal split --terminal <handle> --direction vertical --command "<cmd>"
     A split takes only the handle, so it also works when the workspace is open
     as a plain folder with no git worktree registered.
  2. If splitting genuinely does not apply, say which exception holds in the
     question text: the tab already holds 4 panes, the user explicitly asked for
     a new tab/worktree, or both sessions must edit the same files.

Reference: failed-attempts.md class=orca-terminal-split-pane-parameter-omission.
============================================================
EOF
exit 2
