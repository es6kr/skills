#!/usr/bin/env bash
# PreToolUse — Playwright/browser MCP navigation to an auth-sensitive domain
# (GitHub login/settings/device-flow, Google accounts, Cloudflare dash login)
# without a prior Skill("web-browser", ...) call this session.
#
# web-browser/credential-issue.md already documents the full procedure for
# these flows (backend selection, "Settings UI first" for scope refresh, the
# device-code disabled-button/access_denied failure mode) — but nothing
# forced that skill to actually be invoked before driving raw browser tool
# calls at one of these domains. This closes that gap (skill-invoke-bypass
# class, see failed-attempts.md).
#
# Detection is intentionally coarse: "was web-browser skill invoked ANYWHERE
# in this session's transcript" — not windowed/anchored to this specific
# navigate call. False positives (skill invoked once, then an unrelated
# later navigate to the same domain) are acceptable; the cost of missing a
# real bypass (repeating today's incident) is higher than an occasional
# unnecessary reminder.

INPUT=$(cat)

TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

# Auth-sensitive domain/path patterns (grows as new cases are confirmed —
# see credential-issue.md "CDP-hostile services" for the sibling table).
AUTH_URL_RE='github\.com/(login|settings/tokens|settings/personal-access-tokens)|accounts\.google\.com|dash\.cloudflare\.com.*login|/oauth/authorize'

TRANSCRIPT_PATH=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

case "$TOOL_NAME" in
  *browser_navigate*)
    # Navigating TO an auth-sensitive URL.
    URL=$(printf '%s' "$INPUT" | jq -r '.tool_input.url // empty' 2>/dev/null)
    [[ -z "$URL" ]] && exit 0
    printf '%s' "$URL" | grep -qE "$AUTH_URL_RE" || exit 0
    ;;
  *browser_click*|*browser_type*|*browser_fill_form*|*browser_press_key*|\
  *browser_select_option*|*browser_file_upload*|*browser_handle_dialog*|\
  *browser_drag*|*browser_drop*)
    # Driving a credential flow on an ALREADY-OPEN auth page never calls
    # browser_navigate, so gating on navigate alone covered 1 of the 10 tools
    # the matcher delivers. Treat an interaction as auth-sensitive when this
    # session already navigated to such a URL.
    [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]] && exit 0
    grep -qE "$AUTH_URL_RE" "$TRANSCRIPT_PATH" 2>/dev/null || exit 0
    URL="(already-open auth page)"
    ;;
  *)
    exit 0
    ;;
esac

[[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]] && exit 0

# Structural match only: `"skill":"web-browser"` appears ONLY inside a real
# Skill tool_use input object — free-text mentions are JSON-escaped and
# never match this literal.
if grep -qF '"skill":"web-browser"' "$TRANSCRIPT_PATH" 2>/dev/null; then
  exit 0
fi

# exit 2 + stderr is the contract every sibling guard in this plugin uses and
# the one this harness demonstrably honours. The previous top-level
# {"decision":"block"} on stdout with exit 0 is the deprecated form -- if it is
# not honoured the block is silently swallowed, which is indistinguishable from
# the guard passing.
cat >&2 <<EOF
BLOCKED: browser auth flow without the web-browser skill

Target: $URL
Tool:   $TOOL_NAME

No Skill("web-browser", ...) call is recorded in this session. web-browser/credential-issue.md
owns this flow — it ranks Playwright LAST among backends, prefers the Settings UI over
\`gh auth refresh\` device-flow for scope changes, and documents a known failure mode
(a disabled Authorize button never enabling under automation -> do NOT force-submit via JS,
it gets denied server-side).

Call Skill("web-browser", "credential-issue") first, or — if you already followed its
procedure manually — call it now to record the invocation.
EOF
exit 2
