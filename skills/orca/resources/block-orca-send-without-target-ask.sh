#!/bin/bash
# block-orca-send-without-target-ask.sh (PreToolUse:Bash)
#
# Blocks `orca terminal send` unless the handoff target was confirmed with the
# user in this turn — either by an AskUserQuestion call after the latest user
# message, or by the user naming the target handle themselves.
#
# Why: failed-attempts.md class=orca-terminal-target-ask-omission-and-handle-misrouting
# has recurred 3 times. Every recurrence shares one cause: the target terminal
# was chosen by the assistant instead of the user. The 3rd recurrence read a
# resolver result of `count: 1` as "disambiguation unnecessary, therefore ask
# unnecessary" — but one surviving candidate only means one terminal passed the
# filter, not that the user wants that terminal. send.md's Step 3 makes ask
# mandatory at 2+ candidates; this guard extends the same requirement to 0 and 1,
# because target selection is a user-decision axis at any candidate count.
#
# Escape hatches (both auditable):
#   - the latest user message names the handle passed to --terminal
#   - ORCA_SEND_TARGET_APPROVED=1 prefixed on the command

input=$(cat)

command=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
ti = d.get("tool_input") or {}
print(ti.get("command") or d.get("command") or "")
' 2>/dev/null)

[ -z "$command" ] && exit 0

# Only `terminal send` is gated. list/read/wait/split/create are handled
# elsewhere (block-orca-new-tab-without-split-check.sh) or are read-only.
printf '%s' "$command" | grep -qiE '(^|[[:space:]/])orca[[:space:]]+terminal[[:space:]]+send([[:space:]]|$)' || exit 0

# Auditable opt-out.
printf '%s' "$command" | grep -q 'ORCA_SEND_TARGET_APPROVED=1' && exit 0

transcript_path=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
print(d.get("transcript_path") or "")
' 2>/dev/null)

# Without a transcript there is nothing to verify against. Fail open rather than
# blocking every send in environments that do not pass transcript_path.
[ -f "$transcript_path" ] || exit 0

verdict=$(TRANSCRIPT="$transcript_path" COMMAND="$command" python3 <<'PY' 2>/dev/null
import json, os, re, sys

path = os.environ["TRANSCRIPT"]
command = os.environ["COMMAND"]

entries = []
with open(path, encoding="utf-8", errors="replace") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue

def is_real_user_turn(e):
    """A typed user message, not a tool_result envelope."""
    if e.get("type") != "user":
        return False
    content = (e.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") == "text" and (b.get("text") or "").strip()
            for b in content
        )
    return False

def user_text(e):
    content = (e.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text") or ""
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""

last_user = None
for i, e in enumerate(entries):
    if is_real_user_turn(e):
        last_user = i

if last_user is None:
    print("allow:no_user_turn")
    sys.exit(0)

# 1) AskUserQuestion anywhere after the latest user message.
for e in entries[last_user + 1:]:
    if e.get("type") != "assistant":
        continue
    for b in (e.get("message") or {}).get("content") or []:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
            print("allow:ask_called_this_turn")
            sys.exit(0)

# 2) The user named the target handle themselves.
m = re.search(r"--terminal[=\s]+(\S+)", command)
if m:
    handle = m.group(1).strip("'\"")
    if handle and handle in user_text(entries[last_user]):
        print("allow:handle_named_by_user")
        sys.exit(0)

print("block")
PY
)

case "$verdict" in
  allow:*) exit 0 ;;
esac

cat <<'EOF' >&2
[orca] BLOCKED: `orca terminal send` without a confirmed handoff target.

send.md Step 3 makes target selection a user-decision axis. This turn has no
AskUserQuestion call after the latest user message, and the user did not name
the --terminal handle themselves.

Do this instead:
  1. `orca terminal list --json` and resolve candidates
  2. AskUserQuestion with one option per candidate — label = title,
     description = previewTail + worktreePath + relative lastOutputAt
  3. Send only to the terminal the user picked

A resolver returning exactly one candidate is NOT a reason to skip the ask:
one surviving candidate means one terminal passed the filter, not that the user
wants that terminal. The "keep already-running sessions alive" guard is a
destruction-prevention rule, not a target-selection rule — do not use it to
auto-confirm a target.

If the user already designated this target in an earlier turn, re-state it in
the ask, or prefix ORCA_SEND_TARGET_APPROVED=1 to record the opt-out.

Background: failed-attempts.md class=orca-terminal-target-ask-omission-and-handle-misrouting (3rd recurrence)
EOF
exit 2
