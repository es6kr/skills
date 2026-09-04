#!/usr/bin/env bash
# artifact-corpus-prelookup-guard.sh — PostToolUse:Write|Edit guard
# When a research-*.md / plan-*.md artifact is written, check that this session
# actually performed the corpus pre-lookup that steps.md Step 1 marks HARD STOP
# ("Mandatory Corpus & RAG Pre-Lookup"), and warn when no trace of one exists.
#
# Why a separate guard: the existing session-end RAG check compares store/find
# counts when the session wraps up — by then the artifact is already written and
# may have been reported to the user. This guard fires at write time instead.
#
# Responsible skill: code-workflow (resources holds the source). Install: ~/.claude/hooks/
# Recurrence target: failed-attempts.md "code-workflow-research-rag-presearch-omission"
#
# Warning only — the artifact write already happened and is not reverted.

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Target the research/plan artifact family in its established directories only.
# The tracker family (fix_plan.md, checklist.md) is a different artifact class
# owned by another skill and is deliberately excluded — same scoping rationale
# as the sibling plan-undecided-guard.
case "$FILE_PATH" in
  *docs/generated/research-*.md|*docs/generated/plan-*.md|*.omc/plans/*.md) ;;
  *) exit 0 ;;
esac

# The transcript path arrives in the hook payload. Do NOT read it from an
# environment variable — CLAUDE_TRANSCRIPT_PATH is not populated in every
# harness build, and a guard that silently depends on it degrades into
# "never fires" (or, worse, into an unsatisfiable block) without warning.
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -z "$TRANSCRIPT" ] && exit 0        # no transcript to inspect — fail open
[ -r "$TRANSCRIPT" ] || exit 0        # unreadable — fail open

# Evidence that a corpus pre-lookup happened in this session. Two independent
# families count, because the mandate is "consult the knowledge stores", not
# "call one specific tool":
#
#   (a) semantic/RAG retrieval — a vendor find-style MCP tool, or the search
#       script invoked from a shell. Skill/tool names may carry a plugin
#       prefix, so never anchor on a bare unprefixed literal.
#   (b) wiki corpus access — reading the index or touching the raw/ source
#       layer where primary documents live.
#
# A store/write call is deliberately NOT evidence: writing findings back is the
# opposite direction from checking what is already known.
RAG_RE='qdrant-search|--semantic|mcp__[A-Za-z0-9_]+__[A-Za-z0-9_-]*find|"name":"[A-Za-z0-9_.:-]*-find"'
WIKI_RE='llm-wiki/index\.md|llm-wiki/raw/|/raw/(articles|specs|meetings)/|wiki[^"]*/index\.md'

if grep -qE "$RAG_RE" "$TRANSCRIPT" 2>/dev/null; then exit 0; fi
if grep -qE "$WIKI_RE" "$TRANSCRIPT" 2>/dev/null; then exit 0; fi

{
  echo "⚠️ [artifact-corpus-prelookup-guard] no corpus pre-lookup trace this session"
  echo "  artifact: $FILE_PATH"
  echo ""
  echo "  code-workflow steps.md Step 1 marks 'Mandatory Corpus & RAG Pre-Lookup' a HARD STOP:"
  echo "  check the knowledge stores BEFORE writing, so the artifact rests on primary"
  echo "  sources rather than on a secondhand summary in an upstream document."
  echo ""
  echo "  Neither family of evidence appears in this session's transcript:"
  echo "    (a) semantic/RAG retrieval — a vendor find-style tool, or the search script"
  echo "    (b) wiki corpus access — reading the index, or the raw/ primary-source layer"
  echo ""
  echo "  → Do this now, then correct the artifact if the lookup changes anything:"
  echo "     1. Run the semantic search for this artifact's subject"
  echo "     2. Grep the wiki index / raw layer for the sources the artifact cites"
  echo "     3. Any claim of the form 'X was produced from source Y' must rest on Y"
  echo "        itself when Y is already in the corpus — not on a summary of Y"
  echo ""
  echo "  Reading an upstream research/plan document is NOT this check: that confirms a"
  echo "  downstream artifact exists, which is a different axis from confirming the"
  echo "  primary sources it cites are in the corpus."
  echo ""
  echo "  See failed-attempts.md 'code-workflow-research-rag-presearch-omission'."
} >&2

exit 2
