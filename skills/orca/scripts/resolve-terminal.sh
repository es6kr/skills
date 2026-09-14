#!/usr/bin/env bash
# Resolve candidate Orca terminals matching a title/preview filter. Never selects a
# terminal on its own — it only prints candidates as JSON for the caller (an
# AskUserQuestion when count > 1) to choose from. Reads `orca terminal list --json`
# from stdin if piped, otherwise calls the CLI itself.
#
# Usage: resolve-terminal.sh <title-regex> <preview-regex>
#   Both regexes default to "." (match anything) when omitted.
#   ORCA_PANE_KEY must be set (Orca sets it inside every managed terminal) — the
#   terminal whose tabId:leafId matches is always excluded from the results.
#   ORCA_TERMINAL_LIST_JSON, if set, is used instead of calling the CLI (test fixtures
#   inject it this way). Tty-detection ("was stdin piped?") is not reliable across
#   harnesses, so this is an explicit override rather than an auto-detected one.
set -euo pipefail

ORCA_BIN="${ORCA_CLI_COMMAND:-orca}"
TITLE_RE="${1:-.}"
PREVIEW_RE="${2:-.}"

if [ -z "${ORCA_PANE_KEY:-}" ]; then
  echo '{"ok":false,"error":"ORCA_PANE_KEY is unset — not running inside an Orca-managed terminal; refusing to resolve send targets"}' >&2
  exit 2
fi
SELF_TAB="${ORCA_PANE_KEY%%:*}"
SELF_LEAF="${ORCA_PANE_KEY##*:}"

if [ -n "${ORCA_TERMINAL_LIST_JSON:-}" ]; then
  LIST_JSON="$ORCA_TERMINAL_LIST_JSON"
else
  LIST_JSON=$("$ORCA_BIN" terminal list --json)
fi

printf '%s' "$LIST_JSON" \
| SELF_TAB="$SELF_TAB" SELF_LEAF="$SELF_LEAF" TITLE_RE="$TITLE_RE" PREVIEW_RE="$PREVIEW_RE" node -e '
let s = "";
process.stdin.on("data", d => s += d);
process.stdin.on("end", () => {
  const res = JSON.parse(s);
  if (!res.ok) {
    console.log(JSON.stringify(res));
    process.exit(1);
  }
  const { SELF_TAB, SELF_LEAF, TITLE_RE, PREVIEW_RE } = process.env;
  const titleRe = new RegExp(TITLE_RE, "i");
  const previewRe = new RegExp(PREVIEW_RE, "i");
  // Leading status glyphs (e.g. a filled/half circle, a dot) are UI decoration,
  // not part of the title the user gave the session — strip them before matching.
  const stripGlyphs = t => (t || "").replace(/^[^\p{L}\p{N}]+/u, "").trim();

  const candidates = res.result.terminals
    .filter(t => !(t.tabId === SELF_TAB && t.leafId === SELF_LEAF))
    .filter(t => t.connected && t.writable && !t.orphaned)
    .filter(t => titleRe.test(stripGlyphs(t.title)) && previewRe.test(t.preview || ""))
    .map(t => ({
      handle: t.handle,
      title: stripGlyphs(t.title),
      worktreePath: t.worktreePath,
      branch: t.branch,
      lastOutputAt: t.lastOutputAt,
      previewTail: (t.preview || "").slice(-160)
    }));

  console.log(JSON.stringify({ ok: true, count: candidates.length, candidates }, null, 1));
});'
