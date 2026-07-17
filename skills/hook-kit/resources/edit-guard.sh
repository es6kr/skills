#!/usr/bin/env bash
# PreToolUse:Edit + PreToolUse:Write — consolidated guard for Edit/Write anti-patterns.
#
# Consolidates 5 source hooks (all registered on both Edit and Write matchers):
#   1. block-date-in-skill-rule.sh           (YYYY-MM-DD date stamps in skill/rule bodies)
#   2. block-skill-language-mismatch.sh      (Korean in English-described skill files)
#   3. block-vendor-in-generic-skill.sh      (Edit/Write branch: vendor refs in generic skills)
#   4. block-stub-file-substantive-edit.sh   (substantive content into a stub-pointer file)
#   5. block-fa-edit-without-rag-search.sh   (new failed-attempts section without RAG search)
#
# Strategy:
#   - Single jq pass extracts TOOL_NAME, FILE_PATH, NEW_CONTENT
#   - Resolve SKILL_ROOT lazily (used by skill-language + vendor-in-generic checks)
#   - Checks run in cost order (no-I/O → file I/O → transcript I/O). First deny → exit 2.

set -uo pipefail

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public repo never sees Korean characters. When absent, the variables
# fall back to ASCII-only regex via ${VAR:-default} below — Korean detection
# is disabled but the rest of the guard still functions.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
# When the locale data is missing, set the Hangul range to a pattern that
# never matches (so the language-mismatch check no-ops gracefully).
HG_EDIT_HANGUL_RANGE="${HG_EDIT_HANGUL_RANGE:-[!-~]_NEVER_MATCH}"
HG_EDIT_STUB_MARKERS="${HG_EDIT_STUB_MARKERS:-location pointer|Use .* instead|^type: *stub$|^stub: *true$|^pointer: *true$}"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Edit|Write) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty' 2>/dev/null)

# Lazy SKILL_ROOT resolution (only when a skill scope check runs)
SKILL_ROOT=""
SKILL_ROOT_RESOLVED=0
resolve_skill_root() {
  [[ "$SKILL_ROOT_RESOLVED" -eq 1 ]] && return 0
  SKILL_ROOT_RESOLVED=1
  local d
  d="$(dirname "$FILE_PATH")"
  while [[ "$d" != "/" && "$d" != "." ]]; do
    if [[ -f "$d/SKILL.md" ]]; then
      SKILL_ROOT="$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
}

# ============================================================================
# Check 1: YYYY-MM-DD date stamps in skill/rule body
# ============================================================================
check_date_in_skill_rule() {
  case "$FILE_PATH" in
    */.claude/skills/*/*.md|*/.agents/skills/*/*.md|*/.agents/rules/*.md|*/.claude/rules/*.md) ;;
    *) return 0 ;;
  esac

  case "$FILE_PATH" in
    */cleanup/data/failed-attempts.md|*/cleanup/data/archive/*.md|*/cleanup/data/failed-hooks.md)
      return 0
      ;;
  esac

  [[ -z "$NEW_CONTENT" ]] && return 0

  local matches
  matches=$(echo "$NEW_CONTENT" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort -u)
  [[ -z "$matches" ]] && return 0

  local count
  count=$(echo "$matches" | wc -l | tr -d ' ')

  cat >&2 <<MSG
DENIED: skill/rule Edit/Write contains literal YYYY-MM-DD date stamp(s).

Target file: $FILE_PATH
Date matches ($count unique):
$(echo "$matches" | sed 's/^/  - /')

Reference: fix.md Don't #8 -- skill/rule body must not contain date stamps.
Case history lives only in:
  ~/.claude/skills/cleanup/data/failed-attempts.md (HOT)

Required action:
  1. STRIP every date stamp from the Edit's new_string / Write's content
     (remove section-header annotations like '(HARD STOP -- added DATE)',
      parenthetical '(DATE Nth recurrence)', code comments '// observed DATE')
  2. If the date stamp accompanied case-history content, move that content
     to failed-attempts.md HOT via a separate write
  3. Use date-free pointers when a case reference is essential:
       (see failed-attempts.md "<keyword>")
  4. Retry the Edit/Write with the cleaned text
MSG
  exit 2
}

# ============================================================================
# Check 2: Korean text in English-described skill file
# ============================================================================
check_skill_language_mismatch() {
  [[ "$FILE_PATH" == *.md ]] || return 0
  case "$FILE_PATH" in
    */skills/*/*) ;;
    *) return 0 ;;
  esac

  # Path-based exemption: case-history data files are locale logs, not skill
  # procedural body -- same exemption as check 1 (date stamps) and check 3
  # (vendor refs) above. Missing here caused a false DENY on Korean-only
  # failed-attempts.md entries (2026-07-16).
  case "$FILE_PATH" in
    */data/failed-attempts*.md|*/data/failed-hooks*.md|*/data/archive/*.md|*/data/case-studies/*.md)
      return 0
      ;;
  esac

  resolve_skill_root
  [[ -z "$SKILL_ROOT" ]] && return 0
  [[ -f "$SKILL_ROOT/SKILL.md" ]] || return 0

  local desc
  desc=$(awk '
    /^description:[[:space:]]*\|/ { in_block=1; next }
    in_block && /^[^[:space:]]/ { in_block=0 }
    in_block { print; next }
    /^description:/ { sub(/^description:[[:space:]]*/, ""); print; exit }
  ' "$SKILL_ROOT/SKILL.md")

  # Korean skill → permissive
  echo "$desc" | grep -qE "$HG_EDIT_HANGUL_RANGE" && return 0

  # English skill: inspect content for Hangul
  [[ -z "$NEW_CONTENT" ]] && return 0
  echo "$NEW_CONTENT" | grep -qE "$HG_EDIT_HANGUL_RANGE" || return 0

  local violations
  violations=$(echo "$NEW_CONTENT" | grep -nE "$HG_EDIT_HANGUL_RANGE" | head -3)

  {
    echo "DENIED: Korean text in an English-described skill file."
    echo ""
    echo "Target file:     $FILE_PATH"
    echo "Skill root:      $SKILL_ROOT"
    echo "Description lang: English (zero Hangul in SKILL.md description)"
    echo ""
    echo "Violating lines (first 3):"
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      echo "  $line"
    done <<< "$violations"
    echo ""
    echo "Required action:"
    echo "  - Rewrite the Korean text in English."
    echo "  - User quotes must be paraphrased, not pasted verbatim."
    echo "  - Technical terms (Vault, ArgoCD, etc.) are allowed only in Korean skills."
    echo ""
    echo "Reference: opensource.md 'Skill language = SKILL.md frontmatter description language (HARD STOP)'"
  } >&2
  exit 2
}

# ============================================================================
# Check 3: Vendor refs in generic skill files (Edit/Write branch)
# ============================================================================
check_vendor_in_generic_skill() {
  [[ "$FILE_PATH" == *.md ]] || return 0
  case "$FILE_PATH" in
    */skills/*/*) ;;
    *) return 0 ;;
  esac

  # Path-based exemption: case-history files preserve vendor names
  case "$FILE_PATH" in
    */data/failed-attempts*.md|*/data/failed-hooks*.md|*/data/archive/*.md|*/data/case-studies/*.md)
      return 0
      ;;
  esac

  resolve_skill_root
  [[ -z "$SKILL_ROOT" ]] && return 0
  [[ -f "$SKILL_ROOT/SKILL.md" ]] || return 0

  local skill_name
  skill_name="$(basename "$SKILL_ROOT")"

  # Skip vendor / infra-host skills (they ARE the receivers)
  case "$skill_name" in
    es6kr|dgs|daegun|semaphore|argocd|hook|deps-project|deps-wbs-sync|k3s|gitops-expert|cert-reflector-setup|hedgedoc|oci-resource|rclone|launchd-manager|win|macos|asdf-dev-env|package-manager)
      return 0
      ;;
    omc-*|deps-*)
      return 0
      ;;
  esac

  [[ -z "$NEW_CONTENT" ]] && return 0

  local violations=""

  # Pattern 1: Vendor Skill() invocation
  local p1
  p1=$(echo "$NEW_CONTENT" | grep -nE 'Skill\("(es6kr|dgs|daegun|semaphore|argocd|omc-[^"]+|deps-[^"]+)"' | head -3)
  [[ -n "$p1" ]] && violations="${violations}[vendor Skill() invocation]\n${p1}\n"

  # Pattern 2: Private network IPs (RFC1918)
  local p2
  p2=$(echo "$NEW_CONTENT" | grep -nE '\b(192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})(:[0-9]+)?\b' | head -3)
  [[ -n "$p2" ]] && violations="${violations}[private network IP]\n${p2}\n"

  # Pattern 3: Internal domains
  local p3
  p3=$(echo "$NEW_CONTENT" | grep -nE '\b(es6\.kr|EMC-WAS|EMC-WEB|deps-emc|deps-dts|gitea\.es6|daegunsoft\.com)\b' | head -3)
  [[ -n "$p3" ]] && violations="${violations}[internal domain]\n${p3}\n"

  # Pattern 4: Vendor MCP servers
  local p4
  p4=$(echo "$NEW_CONTENT" | grep -nE 'mcp__(qdrant|chroma|weaviate|pinecone|milvus)([_-]|$)' | head -3)
  [[ -n "$p4" ]] && violations="${violations}[vendor MCP server]\n${p4}\n"

  # Pattern 5: Agent-specific slash commands without agent label
  local p5
  # Preceding char must be a command position (SOL / whitespace / quote / paren /
  # pipe / bracket) so REST path segments like commits/{sha}/status (preceded by
  # '}') or api/v2/status (preceded by a digit) do not false-positive.
  p5=$(echo "$NEW_CONTENT" | grep -nE '(^|[[:space:]"`(|[])/(reload-plugins|mcp|doctor|clear|compact|cost|model|status|theme|memory)([^A-Za-z0-9_-]|$)' | head -3)
  if [[ -n "$p5" ]]; then
    if ! echo "$NEW_CONTENT" | grep -qiE '\b(Claude[-[:space:]]?Code|Cursor|Antigravity|Codex|Gemini[-[:space:]]?CLI)\b'; then
      violations="${violations}[agent-specific slash command without agent label]\n${p5}\n"
    fi
  fi

  [[ -z "$violations" ]] && return 0

  {
    echo "DENIED: Vendor-specific reference in a generic skill file."
    echo ""
    echo "Target file:     $FILE_PATH"
    echo "Generic skill:   $skill_name"
    echo "Skill root:      $SKILL_ROOT"
    echo ""
    echo "Violating patterns (first matches per category):"
    echo -e "$violations"
    echo "Required action:"
    echo "  - Replace vendor Skill() invocations with abstract dispatch:"
    echo "      --rag=<skill>:<topic> flag (caller supplies vendor)"
    echo "  - Replace private network IPs / internal domains with env-var"
    echo "    contract (e.g., RAG_TARGET_URL)"
    echo "  - Replace mcp__<vendor>__* tool names with abstract receiver"
    echo "    contract; receiver skill picks its own MCP/HTTP backend"
    echo ""
    echo "Reference:"
    echo "  ~/.agents/rules/skill-usage.md"
    echo "    section: 'Vendor-specific references forbidden in shared skills'"
  } >&2
  exit 2
}

# ============================================================================
# Check 4: Substantive edit to a stub file
# ============================================================================
check_stub_file_substantive_edit() {
  [[ ! -f "$FILE_PATH" ]] && return 0

  local file_size
  file_size=$(stat -f "%z" "$FILE_PATH" 2>/dev/null || stat -c "%s" "$FILE_PATH" 2>/dev/null || echo "0")
  [[ "$file_size" -gt 5120 ]] && return 0

  # Stub identification: 2-axis (either axis matches → consider stub)
  #   AXIS A (strict): frontmatter `type: stub` / `pointer: true` / `stub: true`
  #                    declared in the first 10 lines. Explicit author intent.
  #   AXIS B (loose):  body pointer phrase + size < 2KB + `## section count <= 1`.
  #                    True stubs are small pointer files with at most one ##
  #                    section ("Location pointer" or equivalent). Topic files that
  #                    happen to contain a body phrase like "Use X instead"
  #                    typically carry 2+ ## sections (Method, Example, etc.)
  #                    — the section-count gate filters those out.
  local frontmatter_stub=0
  if head -10 "$FILE_PATH" 2>/dev/null | grep -qE "^(type: *stub|pointer: *true|stub: *true)$"; then
    frontmatter_stub=1
  fi

  local body_marker_stub=0
  local stub_match=0
  local section_count=0
  if [[ "$file_size" -lt 2048 ]]; then
    stub_match=$(grep -cE "$HG_EDIT_STUB_MARKERS" "$FILE_PATH" 2>/dev/null | head -1)
    stub_match=${stub_match:-0}
    section_count=$(grep -cE '^## [^#]' "$FILE_PATH" 2>/dev/null)
    section_count=${section_count:-0}
    if [[ "$stub_match" =~ ^[0-9]+$ ]] && [[ "$stub_match" -ge 1 ]] \
       && [[ "$section_count" =~ ^[0-9]+$ ]] && [[ "$section_count" -le 1 ]]; then
      body_marker_stub=1
    fi
  fi

  [[ "$frontmatter_stub" -eq 0 && "$body_marker_stub" -eq 0 ]] && return 0

  [[ -z "$NEW_CONTENT" ]] && return 0

  # Override keyword
  echo "$NEW_CONTENT" | grep -q "intentional-stub-edit" && return 0

  # Substantive = new level-2 section
  echo "$NEW_CONTENT" | grep -qE '^## [^#]' || return 0

  local axis_label
  if [[ "$frontmatter_stub" -eq 1 ]]; then
    axis_label="frontmatter declares stub (type: stub / pointer: true / stub: true)"
  else
    axis_label="body marker + size < 2KB + ## section count <= 1 (loose: ${stub_match} marker matches, ${section_count} sections, ${file_size} bytes)"
  fi

  {
    echo "DENIED: substantive edit to a stub file."
    echo ""
    echo "Why blocked:"
    echo "  - Target file is a small stub that points to canonical content elsewhere"
    echo "  - Substantive edits (new ## sections) belong in the canonical HOT location, not the stub"
    echo ""
    echo "Target file:  $FILE_PATH"
    echo "File size:    $file_size bytes (< 5KB threshold)"
    echo "Stub signal:  $axis_label"
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Open the stub file and find the canonical HOT path in its body. Apply your edit there."
    echo "  2. If you genuinely intend to edit the stub itself, include the literal token 'intentional-stub-edit' in the new_string body."
    echo "  3. If this is a new topic file mistakenly classified (body grep FP on 2-5KB file), add frontmatter to declare it is NOT a stub or grow past 5KB before adding the section."
  } >&2
  exit 2
}

# ============================================================================
# Check 5: failed-attempts.md new section without RAG search
# ============================================================================
check_fa_edit_without_rag_search() {
  case "$FILE_PATH" in
    */data/failed-attempts*.md|*/data/archive/*.md) ;;
    *) return 0 ;;
  esac

  [[ -z "$NEW_CONTENT" ]] && return 0
  echo "$NEW_CONTENT" | grep -qE '^## [^#]' || return 0

  local transcript
  transcript=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
  [[ -z "$transcript" ]] && return 0
  [[ ! -f "$transcript" ]] && return 0

  local rag_calls
  rag_calls=$(python3 - "$transcript" <<'PYEOF' 2>/dev/null
import json, re, sys
path = sys.argv[1]
# Medium 1: MCP find tool (mcp__<vendor>__*-find)
pat = re.compile(r"^mcp__[A-Za-z0-9_-]+__.*-find$")
# Medium 2: vendor script fallback when MCP is unavailable (e.g. qdrant-search.py, qdrant-import.py)
vendor_pat = re.compile(r"qdrant-(search|import)\.py")
count = 0
with open(path, encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        try:
            ent = json.loads(line)
        except Exception:
            continue
        msg = ent.get("message") or {}
        c = msg.get("content")
        if isinstance(c, list):
            for b in c:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name = b.get("name", "")
                if pat.match(name):
                    count += 1
                elif name == "Bash":
                    cmd = (b.get("input") or {}).get("command", "")
                    if vendor_pat.search(cmd):
                        count += 1
print(count)
PYEOF
)
  rag_calls="${rag_calls:-0}"
  [[ "$rag_calls" -gt 0 ]] && return 0

  {
    echo "DENIED: failed-attempts.md new section added without preceding RAG semantic search."
    echo ""
    echo "Why blocked:"
    echo "  - fix.md Step 1 'Recurrence pre-check — MANDATORY 2-stage' (Stage 0)"
    echo "  - Exact-match grep misses paraphrased recurrences; RAG semantic search is required first"
    echo "  - Without RAG, an Nth recurrence may be mislabeled as 1st, invalidating the escalation rule"
    echo ""
    echo "Target file:  $FILE_PATH"
    echo "RAG calls in this session: $rag_calls (need >= 1)"
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Run a RAG semantic search via the registered MCP find tool"
    echo "     (e.g., mcp__<vendor>__qdrant-find / chroma-find / etc.)"
    echo "     with the recurrence pattern's core keywords. Then retry the Edit."
    echo "  1b. MCP unavailable? Run the vendor script fallback instead"
    echo "     (e.g., qdrant-search.py / qdrant-import.py) — also counts as RAG search."
    echo "  2. If you have verified via grep that the pattern is genuinely new,"
    echo "     include 'fix-rag-search-skipped' in the new section body."
    echo ""
    echo "Reference: ~/.claude/skills/fix/SKILL.md Step 1 'Recurrence pre-check'"
  } >&2
  exit 2
}

# Execute checks in cost order (no-I/O → file I/O → transcript I/O)
check_date_in_skill_rule
check_skill_language_mismatch
check_vendor_in_generic_skill
check_stub_file_substantive_edit
check_fa_edit_without_rag_search

exit 0
