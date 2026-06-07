# Move

`[x]` entries → Completed section as one-line summaries. Subtree-move for partial completion under unfinished parents. Optional abstract RAG dispatch for callers that supply `--rag=<skill>:<topic>`.

## Summary format

Compress the verbose Progress entry to a single chronological line, then move to Completed.

```markdown
# Before (Progress)
- [x] proxy.ts basePath redirect fix → image build / deploy (2026-03-15 17:30 completed: Session xxxxxxxx, commit a1b2c3d4)
  - proxy.ts `new URL` × 5 fixed **complete**
  - callback/route.ts, logout/route.ts edited **complete**
  - Dockerfile ARG BASE_PATH added **complete**
  - app image v1.8 built **complete**
  - scp → docker load → compose up -d **complete**
  - Verification: 307 → /app/sign-in **success**

# After (Completed)
- 2026-03-15 17:30 — app image v1.8 build / deploy — proxy.ts and route handler basePath redirect fix (commit a1b2c3d4, Session xxxxxxxx)
```

## Summary rules

| Rule | Detail |
|------|--------|
| One line | Drop sub-steps; keep only the core deliverable verb + result |
| Verb + result | "X fixed", "Y deployed", "Z added" |
| Merge related | Items belonging to the same deploy cycle collapse into one line |
| Deduplicate | If a similar entry already exists in Completed, update it instead of adding a duplicate |
| Sort order | Completed is **chronological ascending**. Insert at sort position — the new entry may not be at the end |
| Timestamp | `YYYY-MM-DD HH:mm —` prefix required. **`HH:mm` mandatory** — extract from the original `[x]` line. If absent, use `git log --format=%ci` for the commit time; if still unknown, ask the user (do **not** silently use `00:00`) |
| Reference | Always include the commit hash. With a PR: `(PR #N, commit <hash>)` — PR number first, then commit. Without a PR: `(commit <hash>)` only. Append `, Session xxxxxxxx` when the entry was completed by an autonomous loop (Ralph) and the session ID is known; omit otherwise |
| No `[x]` marker | Completed uses `-` followed by a space (no checkbox) since the section already implies completion |

## PR-level item

When a top-level `[x]` PR entry carries branch / CI / code-review sub-bullets, **roll the whole thing into one line**:

```markdown
# Before
- [x] Admin re-activate loginFailCount-not-reset bug fix — PR #241 MERGED (2026-04-27 14:08, commit 0db8d76)
  - Branch: `fix/224-reset-fail-count-on-reactivate`, commit d7377d1d
  - CI SUCCESS, Test plan 1/3 checked, remaining 2 runtime-verify after deploy
  - Code review: APPROVE — 3-line change, minimal and correct

# After
- 2026-04-27 14:08 — loginFailCount-not-reset bug fix (PR #241, commit 0db8d76)
```

Rule: branch name, CI status, code-review verdict, etc., are PR metadata — they do not belong in the Completed summary. PR number and commit hash are sufficient references.

## Merge example

```markdown
# Before — three completed items in Progress
- [x] README → PDF conversion
- [x] Add account info to README
- [x] Strip internal IPs

# After — one merged Completed line
- 2026-03-15 17:30 — README polish: account info added, internal IPs stripped, PDF generated (commit a1b2c3d4)
```

## Subtree-move (partial completion)

A top-level item may stay `[ ]` while a completed sub-tree under it moves to Completed. Useful when one phase of a multi-phase initiative finishes but the parent is not yet done.

### Conditions

1. The sub-tree references a MERGED PR or CLOSED issue
2. Every checkbox under the sub-tree is `[x]`
3. The parent has other un-finished sub-items

### Example

```markdown
# Before (Progress)
- [ ] DEPS-SSO outage resolution
  - [x] PR #10 created (2026-04-24)
    - [x] Feedback applied
    - [x] Merge conflict resolved
    - [x] PR #10 MERGED (2026-04-27)
    - [x] Integration nginx config verified
  - [ ] Spring Boot SSO sample redirect bug   ← unfinished

# After
- [ ] DEPS-SSO outage resolution
  - [ ] Spring Boot SSO sample redirect bug

## Completed
- 2026-04-27 05:39 — nginx root redirect + Jinja2 template migration + integration server verified (PR #10, commit `abc1234`)
```

### Cleanup rule

- The moved sub-tree is **deleted** from the parent
- Other unfinished sub-items remain
- If the parent ends up with zero sub-items but still `[ ]` — confirm with the user via AskUserQuestion before deleting the parent

## RAG indexing (optional, vendor-agnostic)

If the caller supplies `--rag=<skill>:<topic>` dispatch, Completed entries are forwarded to the receiver for semantic indexing after the move. The receiver skill owns all storage details — endpoint, embedding model, collection naming, schema.

Caller side (example):

```text
/fix-plan move --rag=es6kr:qdrant-import
/fix-plan move --rag=anthropic:semantic-index
```

This skill makes no assumption about the backend. Common receivers might be a vector store (Qdrant, Chroma, Weaviate, Pinecone, pgvector, etc.) or a managed semantic index. The receiver picks.

| # | Don't | Do |
|---|-------|-----|
| 1 | Hard-code a specific store URL, MCP tool name, or embedding model in this skill | Declare abstract dispatch only (`--rag=<skill>:<topic>`). Caller (e.g. Ralph wrapper) implements the concrete receiver |
| 2 | Decide "qdrant is default" inside the move topic | The receiver topic decides. Without `--rag` flag, this topic operates without indexing |
| 3 | Surface receiver errors as move failures | Receiver errors are logged but do not block the move. The Completed entry already exists in the file |

Default: no `--rag` flag → move operates without any indexing dispatch.

## See also

- [format.md](./format.md) — section structure
- [add.md](./add.md) — authoring (companion before move)
- [sync.md](./sync.md) — GitHub state polling produces `[x]` entries that move then summarises
