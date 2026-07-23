# Move

`[x]` entries → Completed section as one-line summaries. Subtree-move for partial completion under unfinished parents. Optional abstract RAG dispatch for callers that supply `--rag=<skill>:<topic>`.

## Summary format

Move = **two artifacts from one `[x]` entry**:

1. **Body → RAG receiver** (vendor-agnostic dispatch — see "RAG dispatch" section below). Full Progress entry body (sub-bullets, commit hashes, session IDs, model name, verification logs) is stored externally for semantic recall.
2. **Summary → Completed section**. One-line chronological summary (verb + result) replaces the moved entry in the file.

Keep the Completed file minimal — detailed steps, commit hashes, session IDs, and model name **belong in RAG, not in the file**. The Completed line is a pointer; the body lives in RAG.

**Completed Lifecycle Rule (HARD STOP)**: The `## Completed` section in the active tracker file is a **temporary holding area** only. It does not accumulate indefinitely.
- **Cycle**: Completed item added → Archived to `.bak/` partition file (and index to RAG) at the end of the current period (weekly/monthly) → **Deleted permanently from the active tracker file**.
- **Result**: The active `fix_plan.md` always stays compact. Leaving months of completed history in the active file is forbidden.
- **Atomic Move Obligation (HARD STOP)**: When moving an entry to `## Completed` (or marking `[x]`), the original line in the active section (`## Priority Work`, `## Progress`, etc.) **MUST be deleted atomically in the same edit turn**. Marking `[x]` while leaving the original line in place is strictly forbidden — it creates visual confusion and stale state.
- **Forbidden**: Do **not** manually insert one-line summaries at random locations (such as above `## REPEAT` or in active lists) to keep track of them. Once mapped to RAG or archived, they must be **deleted** from the active file.



```markdown
# Before (Progress)
- [x] proxy.ts basePath redirect fix → image build / deploy (2026-03-15 17:30 completed: Session xxxxxxxx, model claude-sonnet-4-6, commit a1b2c3d4)
  - proxy.ts `new URL` × 5 fixed **complete**
  - callback/route.ts, logout/route.ts edited **complete**
  - Dockerfile ARG BASE_PATH added **complete**
  - app image v1.8 built **complete**
  - scp → docker load → compose up -d **complete**
  - Verification: 307 → /app/sign-in **success**

# After (Completed)
- 2026-03-15 17:30 — app image v1.8 build and deploy
```

## Summary rules

| Rule | Detail |
|------|--------|
| One line | Keep it minimal. Drop sub-steps and detailed changes. Use a simple high-level title. |
| Verb + result | "X fixed", "Y deployed", "Z added" |
| Merge related | Collapsed related tasks into a single high-level headline |
| Deduplicate | If a similar entry already exists in Completed, update it instead of adding a duplicate |
| Sort order | Completed is **chronological ascending**. Insert at sort position |
| Timestamp | `YYYY-MM-DD HH:mm —` prefix required. **`HH:mm` mandatory** |
| Reference | Do NOT include commit hashes, session IDs, or model name. These are cataloged in RAG. If applicable, keep only the PR or Issue number (e.g. `(PR #N)`). |
| No `[x]` marker | Completed uses `-` followed by a space (no checkbox) |

## PR-level item

When a top-level `[x]` PR entry carries branch / CI / code-review sub-bullets, **roll the whole thing into one simple line**:

```markdown
# Before
- [x] Admin re-activate loginFailCount-not-reset bug fix — PR #241 MERGED (2026-04-27 14:08, commit 0db8d76)
  - Branch: `fix/224-reset-fail-count-on-reactivate`, commit d7377d1d
  - CI SUCCESS, Test plan 1/3 checked, remaining 2 runtime-verify after deploy
  - Code review: APPROVE — 3-line change, minimal and correct

# After
- 2026-04-27 14:08 — loginFailCount-not-reset bug fix (PR #241)
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
- YYYY-MM-DD HH:mm — nginx root redirect + Jinja2 template migration + integration server verified (PR #10)
```

### Cleanup rule

- The moved sub-tree is **deleted** from the parent
- Other unfinished sub-items remain
- If the parent ends up with zero sub-items but still `[ ]` — confirm with the user via AskUserQuestion before deleting the parent

## Completed-section size management (periodic archive)

`move` only adds *into* `## Completed`; without periodic archiving the section
grows unbounded and the tracker file bloats. Archive older Completed entries to a
**local, receiver-independent** partition file on a period boundary. This is the
default lifecycle for a plain `checklist.md` / `fix_plan.md` with no registered
archive-receiver.

### Period (config `completed-archive-period`)

| Value | Partition file | Cadence |
|-------|----------------|---------|
| `monthly` (default) | `<tracker-dir>/.bak/<tracker-stem>-completed-YYYY-MM.md` | at month boundary |
| `weekly` | `<tracker-dir>/.bak/<tracker-stem>-completed-YYYY-Www.md` (ISO week) | at ISO-week boundary |

- `<tracker-stem>` = tracker basename without extension (`checklist`, `fix_plan`).
- Set per tracker via `--completed-archive-period=weekly|monthly` (default `monthly`).
- **Receiver-independent**: unlike the SKILL.md default-invocation archive-receiver
  dispatch (which needs a registered `<skill>:<topic>` receiver and targets external
  reports — weekly report / postmortem / RAG), this archives to a local `.bak/` file
  with zero dependencies. Local archiving is mandatory for size-control on period
  boundaries, and is run independently of (and in addition to) any registered external
  receivers.

### What moves vs stays

- **Move**: every Completed entry whose `YYYY-MM-DD` timestamp is **before the current
  period** (before this month / this ISO week). Appended (chronological ascending) to
  the matching partition file and **removed** from the tracker's `## Completed`.
- **Stay**: Completed entries within the current period remain in the tracker.
- Result: the live tracker holds only the current period's Completed history; older
  history lives in dated partition files under `.bak/`.

### Procedure

1. Determine the cutoff = start of the current period (month or ISO week) from a
   **caller-supplied date** (this skill does not read the clock — pass the date in;
   the automated script defaults to the start of the current month via system clock if omitted).
2. Partition `## Completed` entries by their `YYYY-MM-DD` prefix: `< cutoff` → archive.
3. `mkdir -p <tracker-dir>/.bak` if absent.
4. Group archived entries by their respective periods (e.g. YYYY-MM or YYYY-Www based on
   their timestamp prefix) and route them to their respective partition files under `.bak/`.
5. Append archived entries (preserving chronological order) to their matching period partition
   file; create it with an `# Archived Completed — <period>` header if new. Implement an
   idempotency check (only append if the entry's unique text is not already present in the
   partition file) to make the append retry-safe.
6. Remove the archived lines from the tracker's `## Completed` after the append is confirmed.
7. Report: `N entries archived to matching partition files; tracker Completed now M entries`.

### Automated Script

To automate the checklist parsing, subtree-move, and size archiving procedure, run the Python utility script included in the skill:

```bash
python3 ~/.claude/skills/fix-plan/scripts/cleanup.py [--file <path>] [--cutoff <YYYY-MM-DD>] [--period monthly|weekly] [--dry-run]
```

This script:
1. Detects UTF-8 BOM encoding automatically.
2. Extracts completed `[x]` items (including subtrees under active parents) and removes them from progress sections.
3. Sorts completed entries chronologically descending under `## Completed`.
4. Archives entries older than the cutoff date (defaults to the start of the current month) into `.bak/` partition files (`<tracker>-completed-YYYY-MM.md`).

**Wholesale move, not semantic summary (HARD STOP)**: the script moves a completed subtree **verbatim** (parent + every child line, checkbox markers stripped) — it does NOT synthesize the "one merged headline" shown in the Summary format / Merge example sections above. Merging N child bullets into one coherent sentence requires semantic judgment a parser/tree-walker cannot safely perform; an earlier version tried to fake this by keeping only the parent's original text and silently dropping every child line (real completion detail lost). If a condensed one-liner is wanted, hand-author it (Summary rules above) either instead of running the script on that entry, or as a follow-up edit after the script's wholesale move has landed the full detail safely.

| # | Don't | Do |
|---|-------|-----|
| 1 | Assume the script produces move.md's "one merged headline" format | The script preserves the full subtree verbatim (checkbox-stripped); manual condensing is a separate, optional step |
| 2 | Trust a single-node-text summary function to represent a subtree with children | Verify the entries mover recurses into children (see `node_to_completed_block` in `cleanup.py`) before relying on it for a multi-line subtree |

### Trigger

- **Period boundary** is the primary trigger — the first `move` / cleanup of a new
  month (or ISO week) archives the *previous* period's Completed entries.
- **Size safety net**: if `## Completed` exceeds ~40 entries or the tracker file exceeds
  ~20 KB before a boundary, archive the previous period early.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Let `## Completed` grow unbounded across months | Archive prior-period entries to `.bak/` partition files on the period boundary |
| 2 | Delete old Completed entries to shrink the file | **Move** (never delete) — the `.bak/` partition preserves the full history |
| 3 | Require a registered archive-receiver for local size management | This `.bak/` path is receiver-independent; the receiver dispatch is a separate optional external-report path |
| 4 | Dump the whole Completed history into one ever-growing partition | One partition file **per period** (`YYYY-MM` / `YYYY-Www`) |
| 5 | Only change status to `[x]` and defer moving to `## Completed` to the next turn | Move completed `[x]` items to the `## Completed` section immediately in the same turn with a one-line summary |
| 6 | Keep detailed history (sub-steps, commit hashes, logs) in `fix_plan.md` | Preserve the detailed body in RAG (body-preservation) and keep only a high-level one-liner in the Completed section |

## RAG dispatch (vendor-agnostic, body preservation)

Move's **body-preservation step**. The Progress entry's body (sub-bullets, commit hashes, session IDs, verification details) is forwarded to the RAG receiver supplied via `--rag=<skill>:<topic>` dispatch. The receiver skill owns all storage details — endpoint, embedding model, collection naming, schema.

Caller side (example):

```text
/fix-plan move --rag=es6kr:qdrant-import
/fix-plan move --rag=anthropic:semantic-index
```

This skill makes no assumption about the backend. Common receivers might be a vector store (Qdrant, Chroma, Weaviate, Pinecone, pgvector, etc.) or a managed semantic index. The receiver picks.

### Behavior matrix

| `--rag` supplied? | Body | Summary |
|-------------------|------|---------|
| ✅ supplied | Stored in receiver (full body + metadata) | Inserted into Completed |
| ❌ omitted | **Lost** (body discarded permanently) | Inserted into Completed |

| # | Don't | Do |
|---|-------|-----|
| 1 | Hard-code a specific store URL, MCP tool name, or embedding model in this skill | Declare abstract dispatch only (`--rag=<skill>:<topic>`). Caller (e.g. Ralph wrapper) implements the concrete receiver |
| 2 | Decide "qdrant is default" inside the move topic | The receiver topic decides. Caller (Ralph wrapper, project skill, etc.) is responsible for supplying `--rag` per the local environment's available receiver |
| 3 | Surface receiver errors as move failures | Receiver errors are logged but do not block the move. The Completed summary entry already exists in the file |
| 4 | Run move without `--rag` when body preservation matters | Caller must supply `--rag` to preserve the body. Without it, the Completed one-liner is the only surviving record |

**Caller responsibility (Ralph wrapper, project skill, etc.)**: detect the local environment's available RAG receiver and supply `--rag=<skill>:<topic>` automatically when invoking move. The fix-plan skill itself stays vendor-agnostic; the caller routes.

## See also

- [format.md](./format.md) — section structure
- [add.md](./add.md) — authoring (companion before move)
- [sync.md](./sync.md) — GitHub state polling produces `[x]` entries that move then summarises
