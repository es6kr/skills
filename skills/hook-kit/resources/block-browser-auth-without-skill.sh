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
[[ "$TOOL_NAME" != *browser_navigate* ]] && exit 0

URL=$(printf '%s' "$INPUT" | jq -r '.tool_input.url // empty' 2>/dev/null)
[[ -z "$URL" ]] && exit 0

# Auth-sensitive domain/path patterns (grows as new cases are confirmed —
# see credential-issue.md "CDP-hostile services" for the sibling table).
if ! printf '%s' "$URL" | grep -qE 'github\.com/(login|settings/tokens|settings/personal-access-tokens)|accounts\.google\.com|dash\.cloudflare\.com.*login|/oauth/authorize'; then
  exit 0
fi

TRANSCRIPT_PATH=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]] && exit 0

# Structural match only: `"skill":"web-browser"` appears ONLY inside a real
# Skill tool_use input object — free-text mentions are JSON-escaped and
# never match this literal.
if grep -qF '"skill":"web-browser"' "$TRANSCRIPT_PATH" 2>/dev/null; then
  exit 0
fi

jq -n --arg url "$URL" '
  {
    decision: "block",
    reason: "Navigating to an auth-sensitive URL (\($url)) without a prior Skill(\"web-browser\", ...) call this session. web-browser/credential-issue.md owns this flow — it ranks Playwright LAST among backends, prefers Settings UI over gh auth refresh device-flow for scope changes, and documents a known failure mode (disabled Authorize button never enabling under automation -> do NOT force-submit via JS, it gets denied server-side). Call Skill(\"web-browser\", \"credential-issue\") first, or if you already followed its procedure manually, call it now to record the invocation."
  }'
exit 0
