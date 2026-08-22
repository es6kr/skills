#!/usr/bin/env bash
# Stop hook — detect manual web-task handoff: assistant text asking the user
# to personally visit/check a web console or page and report back, when the
# assistant could have used the web-browser skill (or WebFetch) directly.
#
# Trigger: last assistant text contains a handoff-delegation phrase
#          AND co-occurs with a web-context reference (URL or console/dashboard word)
#          AND the same response has NO web-browser-capable tool_use
#          (Skill call naming web-browser, WebFetch, or a wmux/playwright
#          browser tool).
# Action: emit {"decision":"block","reason":"..."} — Stop event schema does
#         NOT support hookSpecificOutput.additionalContext; decision:"block"+
#         reason mirrors check-ask-bypass-keywords.sh and trigger-Stop.sh.
#
# Background: failed-attempts.md "manual-handoff" class (9th occurrence,
# 2026-07-30) — a Tailscale ACL policy check was handed to the user as
# "check this console and tell me" instead of using web-browser. The class
# had been mis-recorded as status=hook-active for 8 prior occurrences with a
# hook file (block-manual-delegation-without-automation-check.sh) that never
# actually existed on disk or in settings.json — a ghost hook. This script is
# the first real implementation, scoped to plain-text handoff (not just
# AskUserQuestion options, which HG_MD_* patterns in hangul-patterns.regex
# were designed for but never wired to a consuming script either).
#
# Cannot block the response itself (Stop hook fires after the response ends).
# Reminder is injected so the NEXT turn does the web-browser check directly.

HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_HANDOFF_DELEGATE_PHRASES="${HG_HANDOFF_DELEGATE_PHRASES:-__NEVER_MATCH__}"
HG_HANDOFF_WEB_CONTEXT="${HG_HANDOFF_WEB_CONTEXT:-__NEVER_MATCH__}"

INPUT=$(cat)

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -f "$TRANSCRIPT" ] || exit 0

# Last assistant message (whole JSON entry)
LAST_MSG=$(jq -s 'map(select(.type == "assistant")) | last // empty' "$TRANSCRIPT" 2>/dev/null)
if [ -z "$LAST_MSG" ] || [ "$LAST_MSG" = "null" ]; then
  exit 0
fi

# Concatenate all text-content from the assistant message
LAST_TEXT=$(echo "$LAST_MSG" | jq -r '.message.content // [] | map(select(.type == "text") | .text) | join("\n")' 2>/dev/null)
[ -z "$LAST_TEXT" ] && exit 0

# Skip if a web-browser-capable tool was used recently: Skill call naming
# web-browser, WebFetch, or any wmux/playwright browser tool. Scanned across
# the last 5 assistant messages (not just the very last one) — a genuine
# multi-turn automation attempt (navigate, discover no session, open the real
# browser) that concludes with a plain-text status report should not be
# treated as a zero-attempt bare handoff just because the reporting turn
# itself made no tool call.
RECENT_MSGS=$(jq -s 'map(select(.type == "assistant")) | .[-5:]' "$TRANSCRIPT" 2>/dev/null)
BROWSER_TOOL_COUNT=$(echo "$RECENT_MSGS" | jq -r '
  map(.message.content // [] | map(select(.type == "tool_use")) | map(
    (.name // "") as $n |
    ((.input // {} | tostring)) as $i |
    if $n == "WebFetch" then 1
    elif $n == "Skill" and ($i | test("web-browser")) then 1
    elif ($n | test("browser|playwright")) then 1
    elif $n == "PowerShell" and ($i | test("Start-Process")) then 1
    else 0
    end
  ) | add) | add // 0
' 2>/dev/null)
if [ -n "$BROWSER_TOOL_COUNT" ] && [ "$BROWSER_TOOL_COUNT" != "0" ]; then
  exit 0
fi

# Gate 1: delegation phrase present
echo "$LAST_TEXT" | grep -qE "$HG_HANDOFF_DELEGATE_PHRASES" || exit 0

# Gate 2: co-occurs with a URL or console/dashboard word (scopes to web-reachable tasks)
if ! echo "$LAST_TEXT" | grep -qE 'https?://'; then
  echo "$LAST_TEXT" | grep -qE "$HG_HANDOFF_WEB_CONTEXT" || exit 0
fi

REMINDER="[hook:block-manual-handoff-web-task] Manual web-task handoff phrase detected (delegation phrase + URL/console context) with no web-browser-capable tool_use in the same response.

feedback_no_manual_handoff_after_diagnosis.md applies — this is not limited to credential issuance. If the task is reachable via API or the web-browser skill (chrome-devtools real-session reuse, wmux/cmux browser), do it directly instead of asking the user to check and report back.

Self-check (at the start of the next turn):
1. Was the handed-off task actually reachable via web-browser skill (real logged-in session) or an API?
2. If yes, call it directly this turn instead of waiting on the user
3. If genuinely unreachable (no session, no API, physical-access-only), state that explicitly rather than a bare handoff

Details: cleanup/data/failed-attempts.md \"manual-handoff\" class, feedback_no_manual_handoff_after_diagnosis.md"

jq -n --arg msg "$REMINDER" '{
  decision: "block",
  reason: $msg
}'
exit 0
