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
# English-only defaults, per this data file's own convention ("guards fall back
# to the English-only defaults built into each guard"). They were previously
# __NEVER_MATCH__, which made Gate 1 below exit 0 unconditionally — the hook was
# registered, syntactically valid, and structurally incapable of ever firing.
# A guard that cannot fire is worse than an absent one: the docs cite it as the
# backstop, so nobody looks.
# The locale file must AUGMENT these, not replace them. It is sourced above, so
# a plain `${VAR:-default}` would silently drop the English patterns the moment a
# localized copy exists — the guard would then only ever catch handoffs phrased in
# that one language. Compose instead: English always, plus the locale alternation
# when present.
HG_HANDOFF_DELEGATE_EN='(please[[:space:]]+(go[[:space:]]+to|open|visit|click|sign[[:space:]]+in|log[[:space:]]+in|navigate|add|grant|enable|set|toggle|check)|you[[:space:]]+(need[[:space:]]+to|will[[:space:]]+need[[:space:]]+to|must|should|have[[:space:]]+to)[[:space:]]+(go|open|click|visit|sign[[:space:]]+in|log[[:space:]]+in|add|grant|enable|do)|do[[:space:]]+(it|this)[[:space:]]+(yourself|manually|on[[:space:]]+your[[:space:]]+end)|handle[[:space:]]+(it|this)[[:space:]]+(yourself|manually)|(is|are)[[:space:]]+a[[:space:]]+(UI|manual)[[:space:]]+(task|step|action))'
HG_HANDOFF_WEB_EN='(console|dashboard|settings[[:space:]]+(page|screen|tab)|admin[[:space:]]+(panel|ui|console)|portal|web[[:space:]]?ui|browser)'
HG_HANDOFF_DELEGATE_PHRASES="${HG_HANDOFF_DELEGATE_EN}${HG_HANDOFF_DELEGATE_PHRASES:+|${HG_HANDOFF_DELEGATE_PHRASES}}"
HG_HANDOFF_WEB_CONTEXT="${HG_HANDOFF_WEB_EN}${HG_HANDOFF_WEB_CONTEXT:+|${HG_HANDOFF_WEB_CONTEXT}}"

INPUT=$(cat)

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -f "$TRANSCRIPT" ] || exit 0

# Last assistant message (whole JSON entry)
LAST_MSG=$(jq -s 'map(select(.type == "assistant")) | last // empty' "$TRANSCRIPT" 2>/dev/null)
if [ -z "$LAST_MSG" ] || [ "$LAST_MSG" = "null" ]; then
  exit 0
fi

# Concatenate the assistant message's text content AND the text it puts inside
# an AskUserQuestion payload.
#
# Scanning only `type == "text"` blocks misses the most natural way to hand work
# to a user: not a sentence in prose, but an option in a question. A handoff
# written as `question`/`options[].description` never appears in a text block,
# so both gates below were structurally blind to it — the delegation phrase and
# the console URL can sit in the payload and this hook sees an empty string.
LAST_TEXT=$(echo "$LAST_MSG" | jq -r '
  (.message.content // []) as $c
  | (($c | map(select(.type == "text") | .text)) +
     ($c | map(select(.type == "tool_use" and (.name == "AskUserQuestion"))
              | (.input // {}) | tostring)))
  | join("\n")' 2>/dev/null)
[ -z "$LAST_TEXT" ] && exit 0

# Skip if a web-browser-capable tool was used recently: Skill call naming
# web-browser, WebFetch, or any wmux/playwright browser tool. Scanned across
# the last 5 assistant messages (not just the very last one) — a genuine
# multi-turn automation attempt (navigate, discover no session, open the real
# browser) that concludes with a plain-text status report should not be
# treated as a zero-attempt bare handoff just because the reporting turn
# itself made no tool call.
# Immunity requires an attempt on a backend the user can actually act in.
# Playwright MCP alone no longer grants it: its window is invisible by design,
# so a flow that stalls on a login/consent screen there learns nothing the user
# can resolve — and counting it as "already tried" turns a wrong-backend attempt
# into an alibi for the handoff that follows. That is the exact path a prior
# recurrence took. Visible/controllable backends (cmux, wmux, chrome-devtools,
# an OS-level window) and an explicit web-browser Skill dispatch still count.
RECENT_MSGS=$(jq -s 'map(select(.type == "assistant")) | .[-5:]' "$TRANSCRIPT" 2>/dev/null)
BROWSER_TOOL_COUNT=$(echo "$RECENT_MSGS" | jq -r '
  map(.message.content // [] | map(select(.type == "tool_use")) | map(
    (.name // "") as $n |
    ((.input // {} | tostring)) as $i |
    if $n == "WebFetch" then 1
    elif $n == "Skill" and ($i | test("web-browser")) then 1
    elif ($n | test("cmux|wmux|chrome-devtools")) then 1
    elif ($n == "Bash" and ($i | test("cmux browser|wmux browser|remote-debugging-port"))) then 1
    elif $n == "PowerShell" and ($i | test("Start-Process")) then 1
    else 0
    end
  ) | add) | add // 0
' 2>/dev/null)
if [ -n "$BROWSER_TOOL_COUNT" ] && [ "$BROWSER_TOOL_COUNT" != "0" ]; then
  exit 0
fi

# Gate 1: delegation phrase present.
# Case-insensitive: the English patterns are written lowercase but a handoff
# sentence normally starts one ("Please go to..."), so a case-sensitive match
# silently skipped every English phrasing. Harmless for the caseless locale side.
echo "$LAST_TEXT" | grep -qiE "$HG_HANDOFF_DELEGATE_PHRASES" || exit 0

# Gate 2: co-occurs with a URL or console/dashboard word (scopes to web-reachable tasks)
if ! echo "$LAST_TEXT" | grep -qE 'https?://'; then
  echo "$LAST_TEXT" | grep -qiE "$HG_HANDOFF_WEB_CONTEXT" || exit 0
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
