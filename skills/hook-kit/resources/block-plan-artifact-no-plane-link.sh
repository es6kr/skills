#!/usr/bin/env bash
# PostToolUse:Write/Edit — Warn when a tracked planning artifact is written or
# edited without a Plane browse-URL link.
#
# Two surfaces are covered:
#
#   (A) Plan artifacts — */.agents/docs/generated/roadmap-*.md and plan-*.md.
#       Checked whole-file: if no Plane browse URL appears anywhere in the file
#       (frontmatter posted_to/relates_to or body), warn.
#
#   (B) Trackers — */fix_plan.md and */checklist.md.
#       Checked on the ADDED CONTENT only: if this edit introduces a new
#       top-level `- [ ]` backlog item and that added block carries no Plane
#       browse URL, warn. Whole-file grep is useless here because existing
#       items already carry URLs — the new one is what needs registering.
#
# Background: failed-attempts.md class `plane-intake-omission-on-completion`.
# Recurrences 1-6 were fix_plan.md entries / Deep Tasks items / sub-plan files
# / Plan Draft items, all recorded in prose only with no hook built despite
# status=hook-pending. The 7th built THIS script — but only for surface (A),
# and it was never registered in any settings medium, so it never fired once.
# The 8th (2026-08-25) went straight through surface (B): a new
# `- [ ]` item added to daegunsoftDev/.agents/fix_plan.md with no Plane issue.
# Hence: surface (B) added here, and registration is a required companion step
# (a script that is not registered is not a hook).
#
# `plan-agent-deliverable-lifecycle.md` §2 "Plane Issue Integration & Canonical URL
# Standard Specification (HARD STOP)": Roadmap/Parent-Plan/Sub-Plan frontmatter
# (`relates_to`, `posted_to`) must carry standard browse URLs
# (`https://<plane-host>/<workspace-slug>/browse/<ID>`).
#
# Design note: fires unconditionally regardless of the artifact's `status:`
# field (draft/review/decided) — the 6th-recurrence Why-1 explicitly names
# "excluded Draft/Blocked-status items from Plane registration" as the wrong
# behavior being corrected, so a draft-status exemption would reproduce the
# same bug this hook exists to catch.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Skip archive/backup copies — not live tracking artifacts.
case "$FILE_PATH" in
  *.bak/*|*/.bak/*|*~|*.archived|*.sync-conflict-*) exit 0 ;;
esac

PLANE_URL_RE='https://plane\.[A-Za-z0-9.-]+/[A-Za-z0-9_-]+/browse/[A-Za-z0-9-]+'

SURFACE=""
case "$FILE_PATH" in
  */.agents/docs/generated/roadmap-*.md) SURFACE="plan" ;;
  */.agents/docs/generated/plan-*.md)    SURFACE="plan" ;;
  */fix_plan.md|*/checklist.md)          SURFACE="tracker" ;;
  *) exit 0 ;;
esac

if [[ "$SURFACE" == "plan" ]]; then
  [[ -r "$FILE_PATH" ]] || exit 0

  # Signal (a): the file itself already carries a Plane browse URL.
  if grep -qE "$PLANE_URL_RE" "$FILE_PATH" 2>/dev/null; then
    exit 0
  fi

  # Signal (b): this session already dispatched a Plane issue-creation call for
  # this artifact (best-effort — transcript may lag by one turn).
  TRANSCRIPT="${CLAUDE_TRANSCRIPT_PATH:-}"
  if [[ -n "$TRANSCRIPT" && -r "$TRANSCRIPT" ]]; then
    if grep -qE 'plane_create_issue\.py|intake-issues|mcp__[a-z_]*plane[a-z_]*__' "$TRANSCRIPT" 2>/dev/null; then
      exit 0
    fi
  fi

  cat >&2 <<EOF
[block-plan-artifact-no-plane-link] $FILE_PATH

No Plane browse URL found in this artifact (frontmatter posted_to/relates_to
or body). failed-attempts.md class "plane-intake-omission-on-completion"
has recurred 8 times — this file continues that pattern unless registered now.

Required action (pick one):
  1. Register a Plane issue/intake for this artifact now (plane_create_issue.py
     or the workspace's Django-shell fallback) and add the standard browse URL
     (https://<plane-host>/<workspace-slug>/browse/<ID>) to frontmatter
     posted_to/relates_to.
  2. If this is intentionally a local-only artifact not meant to enter the
     Plane SSOT (rare — confirm with the user), state that explicitly; do not
     silently skip.

Draft/Blocked status is NOT an exemption — the 6th-recurrence root cause was
exactly "excluded Draft-status items from Plane registration".
EOF
  exit 2
fi

# --- SURFACE == tracker -------------------------------------------------------
# Inspect only what this edit ADDED. Edit -> new_string, Write -> content.
ADDED=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty' 2>/dev/null)
[[ -z "$ADDED" ]] && exit 0

# Only top-level (non-indented) unchecked items count as new backlog entries.
# Indented `- [ ]` lines are sub-steps of an existing item; `- [x]` is a state
# change, not a new entry.
NEW_ITEMS=$(printf '%s\n' "$ADDED" | grep -E '^- \[ \]' 2>/dev/null)
[[ -z "$NEW_ITEMS" ]] && exit 0

# The added block already carries a Plane browse URL -> it is an index line for
# an issue that was just created. Pass.
if printf '%s\n' "$ADDED" | grep -qE "$PLANE_URL_RE" 2>/dev/null; then
  exit 0
fi

ITEM_COUNT=$(printf '%s\n' "$NEW_ITEMS" | wc -l | tr -d ' ')
FIRST_ITEM=$(printf '%s\n' "$NEW_ITEMS" | head -1 | cut -c1-120)

cat >&2 <<EOF
[block-plan-artifact-no-plane-link] $FILE_PATH

This edit adds $ITEM_COUNT new top-level backlog item(s) with no Plane browse
URL in the added block:

  $FIRST_ITEM

If this workspace's backlog SSOT is an external tracker (see the tracker's
pinned header), a local-only entry is not a record — it is a pointer with
nothing behind it, and it disappears when the file is regenerated or
overwritten by a concurrent writer. failed-attempts.md class
"plane-intake-omission-on-completion" has recurred 8 times on exactly this.

Required action (pick one):
  1. Create the item in the external tracker first (plane_create_issue.py or
     the workspace's Django-shell fallback), then rewrite this entry as an
     index line carrying the returned URL:
       - [ ] [KEY-N] ... -> Plane (https://<plane-host>/<slug>/browse/<KEY-N>)
  2. If the user explicitly scoped this to a local-only note (rare), say so
     out loud; do not skip silently.

Note: the user naming a local medium ("defer to checklist", "add to fix_plan")
is an expression of deferral, NOT a choice of storage medium. Intake first.
EOF
exit 2
