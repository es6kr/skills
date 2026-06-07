# Move

`[x]` → Completed section summary rules + subtree partial completion + optional abstract RAG dispatch.

> **Scaffold placeholder** — Content migration from `ralph/fix-plan.md` (sections L191-263, L326-368) in progress. See plan `~/.agents/docs/generated/plan-fix-plan-migration.md` §4 for migration matrix.

## Planned Content

### Summary format

```markdown
# Before (Progress)
- [x] {detailed multi-line item} (completed: Session xxxx, commit hash)
  - sub-step 1 **complete**
  - sub-step 2 **complete**

# After (Completed)
- YYYY-MM-DD HH:mm — {one-line summary} (commit hash, Session xxxx)
```

### Summary rules

| Rule | Description |
|------|-------------|
| One line | Strip sub-steps; keep core deliverable only |
| Verb + result | "X modified", "Y deployed", "Z added" |
| Merge related | Same deploy cycle items collapse into one |
| Sort order | Completed list is **chronological ascending** — insert at correct position |
| Timestamp | `YYYY-MM-DD HH:mm —` format required (`HH:mm` mandatory) |
| Reference | Merged: `(PR #N, Session xxxx)`. Unmerged: `(commit hash, PR #N, Session xxxx)`. No PR: `(commit hash, Session xxxx)` |
| Drop `[x]` marker | Completed section uses `- ` not `- [x]` (already implicitly complete) |

### Subtree partial completion

Top-level item may stay `[ ]` while a completed sub-tree (e.g., a finished PR within a larger initiative) moves to Completed.

```markdown
# Before
- [ ] {Parent}
  - [x] PR #N MERGED (sub-tree complete)
  - [ ] {Other sub-step}

# After (top-level stays in Progress, completed sub-tree moved)
- [ ] {Parent}
  - [ ] {Other sub-step}

## Completed
- YYYY-MM-DD HH:mm — {Sub-tree summary} (PR #N, Session xxxx)
```

### RAG indexing (optional)

If a RAG receiver is configured via `--rag=<skill>:<topic>` dispatch flag (caller-supplied), Completed entries are forwarded to the receiver for semantic indexing after the move. The generic skill makes no assumption about the backend (vector store, embedding model, collection naming) — receiver implementation handles all storage details.

| # | Don't | Do |
|---|-------|-----|
| 1 | Hard-code a specific vector-store URL or MCP tool name into this skill | Declare abstract dispatch only (`--rag=<skill>:<topic>`). Caller (e.g., ralph wrapper) implements the receiver |
| 2 | Reference a specific embedding model / collection name | Receiver skill owns those decisions |

No `--rag` flag supplied → move topic operates without indexing.
