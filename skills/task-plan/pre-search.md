# Pre-Search Topic (`pre-search.md`)

## 1. Overview & Core Philosophy

Before drafting any new plan, architecture document, or technical proposal, an agent MUST conduct a structured pre-search to discover prior decisions, existing codebases, and existing deliverables.

Bypassing pre-search leads to duplicate documents, conflicting architecture directions, and wasted context tokens.

---

## 2. Search-First Ordering Protocol

Always follow this sequence when researching a task:

1. **Local Generated Deliverables**: Check `.agents/docs/generated/` and `.agents/docs/` for recent plans and research (`roadmap-*.md`, `plan-*.md`, `research-*.md`).
2. **Qdrant Vector Memory & RAG**: Query semantic memory across past sessions using MCP vector search tools (e.g. `mcp__qdrant__search`) or an external workspace helper script if configured:
   ```bash
   python3 scripts/qdrant-search.py --semantic "<task-keywords>" --limit 5  # (if workspace helper exists)
   ```
3. **LLM Wiki**: Check the local wiki index (`llm-wiki/index.md` or `pages/`) for authoritative domain summaries.
4. **Codebase Grep / Symbol Search**: Verify whether the target capability or interface is already partially implemented.
5. **External / Remote Investigation**: External queries (GitHub issues, documentation, web) are consulted only after internal context is checked.

---

## 3. Canonical Medium Gate (HARD STOP)

Before writing a new plan artifact, verify whether an authoritative medium already exists for this task:

- **Check for Existing Documents**: If a plan for this initiative was already authored, do NOT create a new duplicate plan file. Update the existing document, increment `last_modified`, and record changes in the revision history.
- **External SSOT Confirmation**: If the requested information belongs in an established issue tracker (Plane issue, GitHub PR description, or wiki page), maintain that canonical medium rather than creating isolated local files.
- **Single Source of Truth (SSOT)**: Dispersed duplicate files create synchronization conflicts and cognitive bloat.
