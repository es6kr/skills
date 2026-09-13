#!/usr/bin/env bash
# artifact-sibling-existence-guard.sh — PostToolUse:Write guard
# When a NEW research-*.md / plan-*.md artifact is written into a generated-docs
# directory, list the sibling artifacts in that same directory whose filename
# shares topic tokens with it, and warn when any exist.
#
# Why: the canonical-first rule ("when a canonical document on the same topic
# already exists, update it in place instead of creating a new file") lived only
# as prose. Nothing mechanically surfaced the siblings at write time, so a new
# parallel document could be created in a directory that already tracked the
# same subject — fragmenting the corpus and leaving several documents to go
# stale independently.
#
# Why a separate guard rather than extending artifact-corpus-prelookup-guard.sh:
# that guard exits 0 as soon as it finds RAG/wiki evidence in the session. A
# corpus lookup having happened says nothing about whether a same-topic sibling
# was considered — the two axes are independent, and folding this check into
# that one would silently skip it in exactly the sessions that did search.
#
# Performance note: the scan runs as a single awk pass over the directory
# listing. A per-file shell loop is not viable — these directories reach several
# hundred artifacts, and spawning processes per file makes the hook slower than
# the write it guards (measured: minutes, on a 690-file directory).
#
# Responsible skill: code-workflow (resources holds the source). Install: ~/.claude/hooks/
# Recurrence target: failed-attempts.md "duplicate-artifact-creation-instead-of-canonical-update"
#
# Warning only — the artifact write already happened and is not reverted.

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
# Write only. Edit means an in-place update of an existing file, which is the
# behaviour this guard wants to encourage — never something to warn about.
[ "$TOOL_NAME" = "Write" ] || exit 0

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Normalize a native Windows path — a backslash path never matches the
# slash-only case patterns below. Same normalization as the sibling guards.
FILE_PATH=${FILE_PATH//\\//}

# Same artifact family and directories as artifact-corpus-prelookup-guard.sh.
case "$FILE_PATH" in
  *docs/generated/research-*.md|*docs/generated/plan-*.md|*.omc/plans/*.md) ;;
  *) exit 0 ;;
esac

ART_DIR=$(dirname "$FILE_PATH")
[ -d "$ART_DIR" ] || exit 0

SELF_BASE=$(basename "$FILE_PATH" .md)

# --- already-diligent exemption --------------------------------------------
# If this session already enumerated the artifact directory (listing, globbing
# or grepping it), the author had the siblings in front of them and this guard
# would only add noise.
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
if [ -n "$TRANSCRIPT" ] && [ -r "$TRANSCRIPT" ]; then
  # Restrict evidence to real tool invocations, not prose or command output.
  TOOL_USE_RECORDS=$(jq -c 'select(.message.content != null) | .message.content[]? | select(.type == "tool_use")' "$TRANSCRIPT" 2>/dev/null)
  DIR_TAIL=${ART_DIR##*/}
  PARENT_TAIL=$(basename "$(dirname "$ART_DIR")")
  # Two independent conditions, deliberately NOT one adjacency regex: a single
  # pattern spanning tool name → path cannot cross the JSON quotes that sit
  # between them, so it silently never matches. Instead narrow to listing/search
  # tool records first, then look for this directory inside those records.
  ENUM_RECORDS=$(printf '%s' "$TOOL_USE_RECORDS" | grep -E '"name":"(Glob|Grep|LS|Bash|Read)"')
  # Require the parent/dir pair rather than the bare tail: a lone "generated"
  # would exempt far too eagerly, and a false exemption silently disables this
  # guard — the failure mode that is strictly worse than a false warning.
  if printf '%s' "$ENUM_RECORDS" | grep -qF "${PARENT_TAIL}/${DIR_TAIL}"; then exit 0; fi
fi

# --- sibling scan (single awk pass) ----------------------------------------
# Tokenization, shared-token scoring and match formatting all happen inside awk
# so the directory is walked once with no per-file process spawns.
SCAN=$(ls -1 "$ART_DIR" 2>/dev/null | awk -v self="$SELF_BASE" '
function strip_class(b) {
  sub(/^(plan|research|progress|walkthrough|analysis|handoff)-/, "", b)
  return b
}
function is_stop(t) {
  return (" and the for with into from not via per new old fix all out off up " \
          "to of on in is are be by at as its this that " ) ~ (" " t " ")
}
# Fill arr with the significant subject tokens of a basename.
function tokenize(b, arr,   stem, n, i, parts, t) {
  delete arr
  stem = tolower(strip_class(b))
  gsub(/[^a-z0-9]+/, " ", stem)
  n = split(stem, parts, " ")
  for (i = 1; i <= n; i++) {
    t = parts[i]
    if (length(t) < 3) continue
    if (is_stop(t)) continue
    # A bare 8-char hex token is a session-id instance marker, not a subject.
    if (t ~ /^[0-9a-f]{8}$/) continue
    arr[t] = 1
  }
}
BEGIN {
  tokenize(self, selftok)
  for (t in selftok) nself++
  if (nself == 0) exit 0
  count = 0
}
{
  base = $0
  if (base !~ /\.md$/) next
  sub(/\.md$/, "", base)
  if (base == self) next

  tokenize(base, sibtok)
  shared = ""; ns = 0
  for (t in sibtok) if (t in selftok) { shared = shared (ns ? " " : "") t; ns++ }

  # Two shared subject tokens is the point where "same subject" beats
  # coincidence; one token alone matches far too broadly.
  if (ns >= 2) {
    count++
    printf "    - %s.md  (shared: %s)\n", base, shared
  }
}
END { printf "COUNT=%d\n", count }
')

MATCH_COUNT=$(printf '%s' "$SCAN" | sed -n 's/^COUNT=//p')
MATCHES=$(printf '%s' "$SCAN" | grep -v '^COUNT=')

[ "${MATCH_COUNT:-0}" -eq 0 ] && exit 0

{
  echo "⚠️ [artifact-sibling-existence-guard] ${MATCH_COUNT} same-topic artifact(s) already in this directory"
  echo "  new artifact: $(basename "$FILE_PATH")"
  echo "  directory:    $ART_DIR"
  echo ""
  echo "  Existing siblings sharing subject tokens with the new file:"
  printf '%s\n' "$MATCHES"
  echo ""
  echo "  The canonical-first rule: when a document on the same subject already exists,"
  echo "  update it in place rather than adding a parallel one. Several documents on one"
  echo "  subject each go stale on their own, and the next session cannot tell which is"
  echo "  authoritative."
  echo ""
  echo "  → Decide explicitly, now:"
  echo "     1. Read the siblings above and identify which (if any) is canonical for this subject"
  echo "     2. If one is — fold this content into it and remove the new file"
  echo "     3. If none is — keep the new file, and cross-link it from the closest sibling"
  echo "        so the relationship is discoverable"
  echo ""
  echo "  A progress log or handoff note counts as canonical for its subject: appending an"
  echo "  entry there is usually the cheaper and more durable choice than a new document."
  echo ""
  echo "  See failed-attempts.md 'duplicate-artifact-creation-instead-of-canonical-update'."
} >&2

exit 2
