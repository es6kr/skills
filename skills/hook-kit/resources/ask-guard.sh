#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — consolidated guard for AskUserQuestion-stage anti-patterns.
#
# Consolidates 5 source hooks:
#   1. block-tasklist-id-in-conversation.sh    (TaskList #NN ambiguity with PR/issue numbers)
#   2. block-merge-without-review.sh           (merge option without AI Review Summary + Test Plan)
#   3. block-release-please-close-without-verification.sh (release-please/semantic-release close without verification)
#   4. block-vendor-in-generic-skill.sh        (AskUserQuestion branch: vendor names not introduced by user)
#   5. block-supervisor-loop-work-recommend.py (Ralph supervisor session recommending Ralph-loop work)
#
# Strategy:
#   - Single jq pass extracts ASK_TEXT, OPTIONS_BLOB, TRANSCRIPT path
#   - Lazy load USER_TEXT (full transcript user messages) — only for vendor / supervisor checks
#   - Lazy load CONTEXT_BLOB (last 200 transcript lines) — only for supervisor check
#   - Run checks in cost order (no-I/O first). First deny → exit 2.

set -uo pipefail

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public es6kr/skills repo never contains Korean characters. When the data
# file is missing (e.g., fresh clone in a non-Korean environment), each
# variable falls back to an English-only pattern via ${VAR:-default} below.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_ASK_ISSUE_PREFIX="${HG_ASK_ISSUE_PREFIX:-(PR|issue|pull)[[:space:]]*#[0-9]}"
HG_ASK_FINDING_PREFIX="${HG_ASK_FINDING_PREFIX:-(Finding|Item|Section|Important|Nitpick|Critical|Comment|Walkthrough)[[:space:]]*#[0-9]}"
HG_ASK_RETROSPECT_PR="${HG_ASK_RETROSPECT_PR:-(merged|MERGED|previously|prior)[^0-9]{0,20}#[0-9]}"
HG_ASK_ACTIVE_MERGE_KO="${HG_ASK_ACTIVE_MERGE_KO:-}"
HG_ASK_ACTIVE_MERGE_EN="${HG_ASK_ACTIVE_MERGE_EN:-Squash and merge|squash and merge|squash merge|Squash merge|merge it|proceed with merge|do merge|Merge this}"
HG_ASK_MERGE_KEYWORDS="${HG_ASK_MERGE_KEYWORDS:-merge|Merge|MERGE|Squash|squash}"
HG_ASK_RETROSPECT_MERGE="${HG_ASK_RETROSPECT_MERGE:-merged|MERGED|after merge|post-merge|squash type|squash subject|squash commit|merge time}"
HG_ASK_SUMMARY_ATTESTATION="${HG_ASK_SUMMARY_ATTESTATION:-AI Review Summary.*(completed|posted|✅)|github\.com/.+/pull/[0-9]+#issuecomment-[0-9]+}"
HG_ASK_TESTPLAN_ATTESTATION="${HG_ASK_TESTPLAN_ATTESTATION:-Test Plan.*(all).*\[x\]|Test Plan [0-9]+/[0-9]+ ✅|Test Plan.*✅}"
HG_ASK_CLOSE_KEYWORDS="${HG_ASK_CLOSE_KEYWORDS:-close}"
HG_ASK_VERIFICATION_ATTESTATION="${HG_ASK_VERIFICATION_ATTESTATION:-gh pr (view|diff)|base=|pinned|counter only|verified|diff URL|issuecomment}"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "AskUserQuestion" ]] && exit 0

# Extract two views of the question text:
#   ASK_TEXT     = question + option labels + descriptions, newline-separated
#   OPTIONS_BLOB = option labels + descriptions, newline-joined (excludes question text)
ASK_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.question // ""),
  (.options[]? | (.label // ""), (.description // ""))
' 2>/dev/null)

OPTIONS_BLOB=$(echo "$INPUT" | jq -r '
  [.tool_input.questions[]?.options[]? | (.label // ""), (.description // "")]
  | join("\n")
' 2>/dev/null)

[[ -z "$ASK_TEXT" ]] && exit 0

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Lazy loaders for transcript-derived blobs
USER_TEXT=""
USER_TEXT_LOADED=0
CONTEXT_BLOB=""
CONTEXT_BLOB_LOADED=0

load_user_text() {
  [[ "$USER_TEXT_LOADED" -eq 1 ]] && return 0
  USER_TEXT_LOADED=1
  if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
    return 0
  fi
  USER_TEXT=$(python3 - "$TRANSCRIPT" <<'PYEOF' 2>/dev/null
import json, sys
path = sys.argv[1]
out = []
with open(path, encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        try:
            d = json.loads(line)
        except Exception:
            continue
        msg = d.get("message") or {}
        if msg.get("role") == "user":
            c = msg.get("content")
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "text":
                        out.append(b.get("text", ""))
print(" ".join(out))
PYEOF
)
}

load_context_blob() {
  [[ "$CONTEXT_BLOB_LOADED" -eq 1 ]] && return 0
  CONTEXT_BLOB_LOADED=1
  if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
    return 0
  fi
  CONTEXT_BLOB=$(tail -n 200 "$TRANSCRIPT" 2>/dev/null)
}

# ============================================================================
# Check 1: TaskList #NN without PR/issue context
# ============================================================================
check_tasklist_id() {
  local violations=()
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    while IFS= read -r snippet; do
      [[ -z "$snippet" ]] && continue
      # PR / issue / pull #N → explicit GitHub reference, allowed
      if echo "$snippet" | grep -qiE "$HG_ASK_ISSUE_PREFIX"; then
        continue
      fi
      # GitHub URL → allowed
      if echo "$snippet" | grep -q 'github\.com'; then
        continue
      fi
      # Explicit enumeration prefix → not a TaskList ID, an ordinal reference
      # (e.g., "Finding #3", "Item #5", "Section #N", "Important #1", "Nitpick #2",
      #  "Critical #4", "Comment #1"; locale-specific variants come from data/)
      if echo "$snippet" | grep -qiE "$HG_ASK_FINDING_PREFIX"; then
        continue
      fi
      # Past-tense merge / history reference → not an active task
      # (e.g., "merged #40", "previously #57"; locale-specific variants come from data/)
      if echo "$snippet" | grep -qiE "$HG_ASK_RETROSPECT_PR"; then
        continue
      fi
      violations+=("$snippet")
    done < <(echo "$line" | grep -oE '.{0,25}#[0-9]{1,3}([^0-9]|$)')
  done <<< "$ASK_TEXT"

  [[ ${#violations[@]} -eq 0 ]] && return 0

  {
    echo "DENIED: AskUserQuestion contains TaskList ID pattern (#NN) without PR/issue context."
    echo ""
    echo "Why blocked:"
    echo "  - TaskList internal IDs and GitHub PR/issue numbers both use #NN format"
    echo "  - User cannot distinguish; previous violations recorded in failed-attempts.md"
    echo ""
    echo "Violating snippets (with preceding context):"
    for v in "${violations[@]}"; do
      echo "  - $v"
    done
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Replace TaskList ID with subject keyword (e.g., 'core clearStale task', 'Ralph improve task')"
    echo "  2. If #NN refers to a GitHub PR/issue, add an explicit prefix: 'PR #NN' or 'issue #NN'"
    echo ""
    echo "Reference: workflow.md 'TaskList ID conversation use forbidden (HARD STOP)'"
  } >&2
  exit 2
}

# ============================================================================
# Check 2: Merge option without AI Review Summary + Test Plan attestation
# ============================================================================
check_merge_without_review() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0

  # Active merge intent — explicit recommendation to merge now.
  # Locale-specific phrasing comes from data/hangul-patterns.regex; the
  # English-only fallback is sufficient when the data file is absent.
  local active_merge=0
  if [[ -n "$HG_ASK_ACTIVE_MERGE_KO" ]] && echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_ACTIVE_MERGE_KO"; then
    active_merge=1
  elif echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_ACTIVE_MERGE_EN"; then
    active_merge=1
  fi

  if [[ "$active_merge" -eq 0 ]]; then
    # Plain merge keyword — check whether all mentions are retrospective
    # (past tense / technical reference) vs forward-looking.
    # Retrospective uses ("merged already", "squash type", "squash subject")
    # describe historical or release-please cascade mechanics and are not
    # merge proposals. Skip the gate when retrospective uses dominate
    # (>= plain mentions).
    echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_MERGE_KEYWORDS" || return 0

    local retrospect_lines plain_lines
    plain_lines=$(echo "$OPTIONS_BLOB" | grep -cE "$HG_ASK_MERGE_KEYWORDS")
    retrospect_lines=$(echo "$OPTIONS_BLOB" | grep -cE "$HG_ASK_RETROSPECT_MERGE")
    if [[ "$retrospect_lines" -ge "$plain_lines" ]]; then
      return 0
    fi
  fi

  echo "$OPTIONS_BLOB" | grep -qE '#[0-9]+|PR[[:space:]]*#?[0-9]+' || return 0

  # Gate 1: AI Review Summary attestation
  # Locale variants in data/hangul-patterns.regex (HG_ASK_SUMMARY_ATTESTATION).
  if ! echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_SUMMARY_ATTESTATION"; then
    cat >&2 <<'MSG'
DENIED: AskUserQuestion has merge option for a PR without AI Review Summary attestation.

Why blocked:
  - One or more options reference merge/Squash + PR #N
  - But no option text mentions "AI Review Summary ✅/posted" or quotes an issuecomment URL

Required action (pick one before retrying):
  1. Run /consolidate pr-review <N> first to post AI Review Summary, then re-issue the question
  2. If Summary is already posted, include "AI Review Summary posted" in the option description
  3. Replace the merge option with a non-merge action (e.g., "verify only", "hold")

Reference: failed-attempts.md "AI Review Summary missing on merge recommendation" (7+ recurrences).
MSG
    exit 2
  fi

  # Gate 2: Test Plan attestation
  # Locale variants in data/hangul-patterns.regex (HG_ASK_TESTPLAN_ATTESTATION).
  if ! echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_TESTPLAN_ATTESTATION"; then
    cat >&2 <<'MSG'
DENIED: AskUserQuestion has merge option for a PR without Test Plan attestation.

Why blocked:
  - One or more options reference merge/Squash + PR #N
  - AI Review Summary attestation is present ✅
  - But no option text mentions "Test Plan N/N ✅" or "Test Plan all [x]"

Required action (pick one before retrying):
  1. Verify Test Plan items first (Playwright, curl, manual test) and check [x] on PR body
  2. Include "Test Plan N/N ✅" in the option description after all items are checked
  3. Replace the merge option with "Test Plan verification" or "hold"

Reference: failed-attempts.md "Test Plan unchecked on merge recommendation" (5+ recurrences).
MSG
    exit 2
  fi
}

# ============================================================================
# Check 3: release-please / semantic-release / changesets close without verification
# ============================================================================
check_release_please_close() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0
  echo "$OPTIONS_BLOB" | grep -qiE 'release-please|semantic-release|changesets' || return 0
  echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_CLOSE_KEYWORDS" || return 0
  echo "$OPTIONS_BLOB" | grep -qE '#[0-9]+|PR[[:space:]]*#?[0-9]+' || return 0
  echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_VERIFICATION_ATTESTATION" && return 0

  cat >&2 <<'MSG'
DENIED: AskUserQuestion recommends closing a release-please / semantic-release / changesets PR
without verification attestation.

Why blocked:
  - Options reference release-automation tool (release-please/semantic-release/changesets)
  - Options reference close action + PR number
  - But no option text shows verification attestation (gh pr view/diff result, pinned base, counter only, etc.)

Required action (pick one before retrying):
  1. Apply workflow/config fix → push → wait for next auto-generated PR
  2. Run `gh pr view <new-PR> --json title,body` or `gh pr diff <new-PR>` to verify
     intended behavior (pinned base, counter-only increment, etc.)
  3. Include verification result in the option description:
     "verified (PR #N base=0.4.9-beta.4, diff URL) → close"
  4. Then re-issue AskUserQuestion

Reference: ~/.agents/rules/release-automation.md 'auto-generated PR close recommendation prerequisites (HARD STOP)'.
failed-attempts.md: 'speculative release-please config option presentation' (3 recurrences, hook escalation).
MSG
  exit 2
}

# ============================================================================
# Check 4: Vendor name leak in question/options (not introduced by user)
# ============================================================================
check_vendor_leak() {
  local violations=""
  load_user_text

  for vendor in qdrant chroma weaviate pinecone milvus pgvector redis-search; do
    if echo "$ASK_TEXT" | grep -qiE "\b${vendor}\b|mcp__${vendor}([_-]|$)"; then
      if ! echo "$USER_TEXT" | grep -qiE "\b${vendor}\b"; then
        local hits
        hits=$(echo "$ASK_TEXT" | grep -oiE "\b${vendor}\b|mcp__${vendor}([_-]|$)" | sort -u | head -3 | tr '\n' ' ')
        violations="${violations}  - ${vendor}: ${hits}\n"
      fi
    fi
  done

  for cli in qdrant-find qdrant-store chroma-find chroma-store; do
    if echo "$ASK_TEXT" | grep -qiE "\b${cli}\b"; then
      if ! echo "$USER_TEXT" | grep -qiE "\b${cli}\b"; then
        local hits
        hits=$(echo "$ASK_TEXT" | grep -oiE "\b${cli}\b" | sort -u | head -3 | tr '\n' ' ')
        violations="${violations}  - ${cli}: ${hits}\n"
      fi
    fi
  done

  [[ -z "$violations" ]] && return 0

  {
    echo "DENIED: AskUserQuestion contains vendor-specific tool/service name not introduced by user."
    echo ""
    echo "Why blocked:"
    echo "  - skill-usage.md 'Author-facing media coverage extension'"
    echo "  - Vendor name in option label/description biases user choice before they pick a backend"
    echo "  - Recent user message did NOT introduce this vendor, so this is an assistant-side leak"
    echo ""
    echo "Vendor patterns found in question/options:"
    echo -e "$violations"
    echo "Required action (pick one before retrying):"
    echo "  1. Replace vendor name with abstract term:"
    echo "     - 'qdrant-find' / 'qdrant-store' → 'RAG semantic search' / 'RAG receiver store'"
    echo "     - 'qdrant' / 'pgvector' (backend name) → 'RAG backend' or 'vector store'"
    echo "     - 'mcp__<vendor>__*' → 'RAG store MCP tool'"
    echo "  2. If user explicitly asked about this vendor (e.g., 'pgvector vs qdrant comparison'),"
    echo "     rephrase user input to include the vendor name first, then retry."
    echo ""
    echo "Reference: ~/.agents/rules/skill-usage.md 'Author-facing media coverage extension'"
  } >&2
  exit 2
}

# ============================================================================
# Check 5: Supervisor session recommending Ralph-loop work
# ============================================================================
check_supervisor_loop_recommend() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0

  # Quick trigger pattern check before loading transcript
  if ! python3 -c "
import re, sys
blob = sys.argv[1]
pat = re.compile(r'(?<![A-Za-z0-9_-])(consolidate|pr-review|/consolidate|/github-flow\s+merge|code-reviewer)(?![A-Za-z0-9_-])', re.IGNORECASE)
sys.exit(0 if pat.search(blob) else 1)
" "$OPTIONS_BLOB" 2>/dev/null; then
    return 0
  fi

  load_context_blob
  [[ -z "$CONTEXT_BLOB" ]] && return 0

  if ! python3 -c "
import re, sys
blob = sys.argv[1]
pat = re.compile(
    r'\"name\"\s*:\s*\"Skill\"[\s\S]{0,500}?\"skill\"\s*:\s*\"ralph\"[\s\S]{0,200}?supervise'
    r'|\"ralph\",\s*\"supervise\"'
    r'|/ralph\s+supervise'
    r'|ralph\s+supervise',
    re.IGNORECASE,
)
sys.exit(0 if pat.search(blob) else 1)
" "$CONTEXT_BLOB" 2>/dev/null; then
    return 0
  fi

  cat >&2 <<'MSG'
DENIED: AskUserQuestion in Ralph supervisor session recommends Ralph-loop work.

Why blocked:
  - Supervisor context detected (recent `Skill("ralph", "supervise")` invocation)
  - Option label/description contains Ralph-loop trigger keyword
    (consolidate / pr-review / /consolidate / /github-flow merge / code-reviewer)

Per agent-coord.md "supervise vs Ralph loop separation (HARD STOP)":
  - Supervisor session = report / analysis / user-decision support only
  - Ralph loop owns: consolidate, merge, code-review execution

Required action (pick one before retrying):
  1. Remove the trigger-keyword option(s); report the same content as TEXT instead
     (e.g., "PR #N has no AI Review Summary -- the next Ralph loop can run consolidate")
  2. Replace with supervisor-allowed options:
     BLOCKED triage / fix_plan.md cleanup / improvements.md update / start next Ralph loop
  3. Only if the user explicitly typed an override such as "handle this in the supervise session directly"
     earlier may you bypass this hook -- and you should still re-confirm via AskUserQuestion
     without the trigger keyword in the option.

Reference: failed-attempts.md "supervise vs Ralph loop" entries (4+ recurrences as of 2026-06-12)
MSG
  exit 2
}

# Execute checks in cost order
check_tasklist_id
check_merge_without_review
check_release_please_close
check_vendor_leak
check_supervisor_loop_recommend

exit 0
