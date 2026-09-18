# Artifact Rules Topic (`artifact-rules.md`)

## 1. Volatile Staging vs Persistent Deliverables

- **Volatile Staging**: Session scratchpad and temporary task lists reside in the session artifact directory (`<appDataDir>/brain/<session-id>/`). These are session-scoped and volatile.
- **Persistent Deliverables**: Permanent architectural plans (`plan-*.md`), research records (`research-*.md`), and macro roadmaps (`roadmap-*.md`) MUST be authored in the workspace's designated output directory (default: `.agents/docs/generated/`).

---

## 2. Document Metadata Banner & Revision Discipline

When revising an existing deliverable:
1. Preserve the original `created: YYYY-MM-DD` date.
2. Update `last_modified: YYYY-MM-DD`.
3. Prepend a visible document metadata banner immediately below the title:
   ```markdown
   > **Document Metadata**: Initial created date: YYYY-MM-DD / Last modified date: YYYY-MM-DD / Status: review
   ```

---

## 3. Ambiguous Destination Multi-Copy Prohibition (HARD STOP)

When the target destination path for an artifact or export is ambiguous:
- Never speculatively copy or write to multiple candidate paths simultaneously.
- Unilateral multi-copying pollutes git trees and violates the Single Source of Truth (SSOT).
- Always enumerate candidate destination paths and invoke `AskUserQuestion` / `ask_question` to obtain explicit confirmation before executing file operations.

---

## 4. Artifact Sibling Existence Guard (PostToolUse:Write)

When creating a new plan, research, or roadmap artifact via Write:
- `artifact-sibling-existence-guard.sh` scans the target directory for sibling artifacts sharing 2 or more subject tokens (ignoring stopwords and 8-character hex session IDs).
- **Canonical-First Discipline**: When a document on the same topic already exists, update it in place (`replace_file_content` / `Edit`) rather than adding a parallel fragmented artifact.
- **Directory Enumeration Exemption**: If the session transcript confirms that the author already inspected the target directory (via glob, listing, or grep) prior to writing, the warning is suppressed.
- **Warning-Only Semantics**: This guard emits an advisory warning upon write completion to encourage canonical document consolidation and prevent corpus fragmentation.

