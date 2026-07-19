# RAG Store — Session-End Persistence Obligation

Persist key findings, decisions, and artifacts to a RAG store medium at session wrap-up + sync `fix_plan.md` completed items. Auto-runs at cleanup `run` Step 5 or `next` wrap-up.

## Scope

This topic covers **personal-environment RAG store procedure**. Deploy-target skills (cleanup/next) must not register vendor-specific RAG receivers, so this content is isolated here. The body uses abstract names (`mcp__<vendor>__*-store`, "RAG receiver", "RAG store") rather than vendor-specific names — actual tool calls go through whichever vendor tool is available.

## Trigger Conditions (all must hold)

1. **RAG store tool is available** — confirm `mcp__<vendor>__*-store` or equivalent receiver skill via ToolSearch / system reminder
2. **Session wrap-up signal is present** — any one of:
   - `next` skill wrap-up entry (next invocation or next-action ask)
   - `cleanup run` invocation
   - User says "wrap up", "cleanup", "finish", or similar wrap-up keywords
   - User accumulates 3+ turns of housekeeping (task/fix_plan cleanup) with no further work intent
   - `/fix` Step 4 Completion Report stage
3. **Session has discoveries worth storing** (skip pure-query sessions)

## Storage Targets

| Category | Example |
|----------|---------|
| **Infrastructure finding** | "a1-1 flannel subnet.env not created", "instance1 split brain", "firewalld stale config" |
| **New constraint / best practice** | "ArgoCD client-side rendering does not support helm chart lookup" |
| **Decision + rationale** | "Qdrant apiKey disabled + VPN/firewall protection" decision + reason |
| **Deployment artifact** | "Service X deployed + commit SHA" |
| **Troubleshooting procedure** | "Recreate svclb after firewall-cmd reload" |

## Storage Format

```text
mcp__<vendor>__*-store(
  information="<key finding 1-3 sentences + context>",
  metadata={
    "type": "deployment|discovery|decision|troubleshooting|infra-finding",
    "project": "<repo/domain>",
    "date": "YYYY-MM-DD",
    "category": "infrastructure|security|networking|build|..."
  }
)
```

**Storage unit**: one call per item. Multiple findings → separate stores. Metadata enables semantic search + filtering.

## Don't / Do — Session-End RAG Store

| # | Don't | Do |
|---|-------|-----|
| 1 | End session immediately after picking the `next` wrap-up "end session" option | Call RAG store (≥1) before executing the end option. Store all available findings |
| 2 | "Already recorded in fix_plan/failed-attempts → RAG is duplicate" reasoning | fix_plan/failed-attempts = record medium. RAG store = semantic-search medium. **Different purposes** — duplication is fine |
| 3 | Adding vendor-specific RAG mapping to deploy-target skills (cleanup/next/skill-kit) | Isolate in this topic or in personal rules. Deploy-target skills stay generic |
| 4 | Store without metadata | Mandatory 4 metadata keys (type/project/date/category). Both semantic search and filtering need them |
| 5 | "1 store is enough" wrap-up | Store all category findings from this session. Even if only 1 discovery, store that |
| 6 | Forcing the rule when RAG is unavailable (MCP disconnected) | If `mcp__<vendor>__*-store` schema is unavailable, the rule does not apply. Fall back to fix_plan/failed-attempts |

## Self-Check (every time before session end)

1. Is `mcp__<vendor>__*-store` available? — check system reminder / recent store/find call traces
2. **For 3-C.1 whole-session import specifically**: before using the generic MCP tool, run the "Purpose-fit priority for 3-C.1" detection procedure below (Medium Matrix section) — a purpose-built session-importer script outranks the generic MCP tool even when the MCP tool is available
3. If yes, is there any discovery worth storing? — extract from TaskList completed + fix_plan changes + commits + new rules
4. Did you extract ≥1 per category? (infra finding / decision / best practice / troubleshooting)
5. Does each store call include the 4 metadata keys?
6. Does the wrap-up report state "RAG store N completed"?

## Medium Matrix (HARD STOP — Definition of "tool available")

RAG store is not a single tool but a **multi-medium fallback chain** — one medium's failure ≠ "unavailable". Mark unavailable only after all media fail.

| Medium | Availability check | Fallback |
|--------|-------------------|----------|
| (1) `mcp__<vendor>__*-store` MCP tool | system reminder deferred tools / recent call traces | Try medium (2) |
| (2) vendor skill script (e.g., vendor-provided import script) | script file exists + RAG server readyz passes | Try medium (3) |
| (3) RAG server REST API direct call | RAG server readyz passes + own embedding capability (or pre-embedded data) | Try medium (4) |
| (4) **local durable pending-import queue** (always available) | filesystem writable (always true) | — terminal medium, never fails |

**"Tool unavailable" definition**: media (1)-(3) (the RAG-server-dependent media) are unusable. Transient failures in one medium (e.g., embedding cache missing, MCP disconnect) ≠ unavailable — must try next medium.

### Purpose-fit priority for 3-C.1 session-chunk import (HARD STOP — not a plain availability fallback)

**The (1)→(2)→(3)→(4) order above is an availability fallback chain, not a purpose-fit ranking.** For **3-C.1 whole-session import specifically**, a purpose-built session-importer script (medium 2) is the correct tool **even when medium (1) is available** — check for it FIRST, not as a fallback (see [run.md](file:///Users/david/.agents/skills/cleanup/run.md#L418) for the 3-C.1 "Availability check" HARD STOP).

A generic `mcp__<vendor>__*-store` MCP call (medium 1) writes one arbitrary text blob with whatever metadata schema the caller supplies. It has no per-turn structure (no `session_id`/`turn_id`/`message_uuid`/`parent_uuid`/`timestamp` fields), no idempotent re-import (re-running upserts a fresh blob instead of skipping already-stored turns), and no dedupe against prior partial imports (e.g., a hook that already imported most of the session mid-conversation). Calling it for 3-C.1 produces a shallow, non-idempotent, hand-summarized substitute — not an actual session import.

**Detection procedure (before any 3-C.1 store call)**:
1. Search locally installed skills' Topics tables for a topic whose description matches "session JSONL → (vector store) import" / "session chunk import" (e.g. a topic literally named `qdrant-import`, `session-import`, or similarly described)
2. If found → that script/topic is the medium (2) receiver for 3-C.1. Use it, even though medium (1) MCP is also available
3. If not found → medium (1) generic MCP store is an acceptable substitute for 3-C.1, but the resulting chunk should be reported as a single ad-hoc summary, not as "session imported"
4. This detection is separate from — and precedes — the (1)→(4) availability fallback chain, which only governs what to do when the chosen medium fails

| # | Don't | Do |
|---|-------|-----|
| 1 | See a generic MCP `*-store` tool listed as available (ToolSearch / ambient reminder) and call it directly for 3-C.1 because it's the first thing found | Run the detection procedure above first — a purpose-built session-importer script outranks the generic MCP tool for whole-session import, regardless of which is discovered first |
| 2 | Treat "1 MCP store call succeeded" as equivalent to "session imported" in the wrap-up report | If a purpose-built importer exists but wasn't used, report the MCP call honestly as a single ad-hoc summary chunk — not as session-level import coverage |
| 3 | Assume no prior import exists because this is "the first RAG store this session" | A purpose-built importer is typically idempotent and hook-driven — it may have already imported most of the session incrementally. Run its dry-run/check mode before assuming 0 existing chunks |

**Self-check (immediately before any 3-C.1 call)**:
1. Does any locally installed skill declare a session-JSONL-import topic? (grep Topics tables / skill descriptions for "session" + "import"/"qdrant"/"vector" keywords)
2. If yes, use that script, not the generic MCP store tool, even if the MCP tool is readily available
3. If yes, and the script supports dry-run/check mode, run it first to check coverage before assuming 0 existing chunks

### Medium (4) — local durable pending-import queue (HARD STOP — server-down ≠ info lost)

**When all RAG-server media (1)-(3) fail (server unreachable / network down), the info is NOT preserved by "register BLOCKED + retry next session".** Next session may never run; the semantic index is then permanently lost. Medium (4) is the **terminal, always-available** fallback: write the import payload to a durable local queue file **this session**, so a future cleanup deterministically drains it when the server returns.

**Queue location** (central — drained by any future cleanup, workspace-independent):

```
~/.claude/skills/cleanup/data/rag-pending/<session-uuid>.md
```

**Queue file content** (everything needed for a later import):
- Session UUID + date
- Artifact paths (plan/research/analysis `.md`) to import
- Distilled facts (decisions, infra findings) with metadata `{type, project, date, topic}`
- One-line reason the server was unreachable (e.g., `Qdrant readyz http_code=000`)

**Drain step (next cleanup 3-C.1)**: before/after the session import, `ls ~/.claude/skills/cleanup/data/rag-pending/*.md`. For each queued file, if RAG server now reachable → import its payload → delete the queue file. If still unreachable → leave queued.

| # | Don't | Do |
|---|-------|-----|
| 10 | All server media fail → "register BLOCKED in fix_plan + retry next session" and stop (punt) | Write medium (4) local queue file **this session** — durable, deterministic drain. fix_plan BLOCKED note is supplementary, not the preservation mechanism |
| 11 | "RAG server down = info preservation impossible this session" | Server down ≠ can't preserve. Durable text (memory/fix_plan/skill) already holds the knowledge; medium (4) queue holds the import payload. Both are on-disk this session |
| 12 | Treat "next session task" as the preservation guarantee | A task is a reminder, not durable content. The queue **file** is the guarantee — it survives even if no future session reads the task |

### Don't / Do — Fallback Across Media

| # | Don't | Do |
|---|-------|-----|
| 7 | "One medium failed (script dep missing) → tool unavailable, skip" | Try next medium (vendor script → REST API). Only mark unavailable when the full matrix fails |
| 8 | RAG server readyz OK but client-side failure classified as "unavailable" | Separate server availability from client: server up + client broken = must try REST API direct call |
| 9 | `/fix` Step 4 or cleanup `run` Step 4.5 final report says "RAG storage BLOCKED" then proceeds to `next` Step 5 | RAG BLOCKED is an unresolved trigger. Forbid `next` entry + retry medium matrix |

### Self-Check (every time RAG store fails)

1. Medium (1) MCP failed → did you try medium (2) vendor script?
2. Medium (2) script failed → identify cause (cache miss / dependency / network) → did you try medium (3) REST API direct call?
3. Medium (3) failed → check "RAG server readyz" (server up?). Only mark RAG-server media unusable when the server itself is down
4. **All server media (1)-(3) fail → write medium (4) local pending-import queue file THIS session** (`~/.claude/skills/cleanup/data/rag-pending/<session-uuid>.md`). Do NOT punt to "next session retry" — that abandons preservation. The queue file is the durable guarantee
5. Only after medium (4) queue is written: register a BLOCKED note in `fix_plan` as a supplementary reminder (the queue file, not the note, is the preservation)

## fix_plan.md Completed Item RAG Sync + Delete Obligation (HARD STOP)

**When `fix_plan.md` contains completed (`- [x]`) items or Merged/Closed PR info, immediately upsert to the RAG workspace collection (`fix-plan-{workspace}`) via sync script, then delete the items from the file.**

### Trigger Conditions

1. `## Completed` section or other sections of `fix_plan.md` contain completed (`- [x]`) items
2. `fix_plan.md` contains Merged / Closed PR info left in merged state
3. MCP RAG server + sync script are available
4. **A `[BLOCKED]` / `[ ]` item is changed to `[x]` + the body is compressed/merged/removed (e.g., multiple sub-bullets → single line)** — when the lost body content (option candidates, verification medium, primary-source references, user-decision + commit SHA, hold work, related plan refs) has RAG storage value. **The sync script parses the Completed section only**, so other-section compression is not handled by the script → **manual RAG store obligation**
5. **A completed (`- [x]`) top-level item living OUTSIDE `## Completed` (e.g., in "Priority Work"/TODO sections) has grown oversized** (roughly > 10 lines of inline detail) — sessions tend to *append* a new phase/session log to an already-`[x]` item instead of condensing it, so the item silently bloats across sessions. Neither the sync script (Completed-section only) nor the `fix-plan` agent (on-demand only) sees this case automatically. A `PostToolUse:Edit|Write` hook (`~/.agents/skills/hook-kit/resources/block-fixplan-completed-bloat.sh`) surfaces an advisory when this threshold is crossed — treat that advisory the same as a manual trigger: RAG-store the full detail, move durable lessons to the relevant skill, then condense to a 1-line summary + pointers

### Procedure

1. **Bulk-sync Completed section (script)**: run vendor-provided fix_plan → RAG sync script
2. After sync success, delete `## Completed` body (keep empty header)
3. **Other-section body compression (manual RAG store)**: if compression would lose body content, call `mcp__<vendor>__*-store` first. Include 4-6 metadata keys: `{type: troubleshooting|decision|infra-finding, project: <repo/domain>, date: YYYY-MM-DD, category: <area>, source: fix_plan-L<line-num>, status: archived}`. Only after store success, run Edit to compress

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 10 | Leave `[x]` items in `fix_plan.md` indefinitely | Run RAG sync script then delete to clean up |
| 11 | Delete completed list without running the sync script | Always run script and confirm success before deleting |
| 12 | Batch RAG sync at session end | Run sync immediately when completed items are detected |
| 13 | Compress `[BLOCKED]`/`[ ]` items with sub-bullets without RAG store (options/verification/primary source/user-decision commit/related plan are permanently lost) | Identify RAG storage value before Edit → call `mcp__<vendor>__*-store` manually → only after store success, run Edit to compress |
| 14 | Report "RAG obligation done" after 1 script sync then compress other-section `[x]` items | Script parses **Completed section only**. Other-section `[x]` handling + body-loss cases require separate manual RAG store. Report both "script: N + manual: M" counts |
| 15 | "If user concludes 'no further action needed', the body can be cleaned up too" reasoning | Conclusion and body preservation are separate. User conclusion = **state decision**; body = **troubleshooting steps / primary source / commit history** with future value. Conclusion = `[x]` processing; body = RAG store then compress |
| 16 | Treat oversized `[x]` items as safe to ignore because they're "not in `## Completed`" | The sync script's Completed-only scope is a tooling gap, not a signal that inline `[x]` bloat is fine. At wrap-up, also scan top-level `- [x]` items outside `## Completed` for size — condense the same way |

### Self-Check (every session start / end + every time before fix_plan Edit)

1. Does `fix_plan.md` contain `- [x]` items? — if yes, run sync script
2. If yes, was the sync executed?
3. After sync success, were the items removed from `fix_plan.md`?
4. **Are you about to Edit fix_plan to compress/merge/remove items?** — if yes, run self-checks 5-7
5. Does the body to be compressed contain sub-bullets (options / verification medium / primary source / user-decision commit SHA / hold work / related plan refs) that would be lost?
6. If yes, did you call `mcp__<vendor>__*-store` **before** the Edit? Include source location (fix_plan-L<num>) + type/project/date/category metadata?
7. Only after RAG store success, run Edit (script does not handle other sections — manual obligation)
8. **At wrap-up, scan for oversized inline `- [x]` items outside `## Completed`** (rough heuristic: > 10 lines of body under one top-level item) — the `block-fixplan-completed-bloat.sh` hook advisory is one signal, but also check proactively since the hook only fires on the Edit/Write that touches the file
9. For each oversized item found, RAG-store the full detail (with pointer to any artifact file already holding it), then condense to a 1-line summary + pointers — same procedure as trigger condition 4

## Exceptions

- All three media unavailable (RAG server down + all client media failed) — rule does not apply
- User explicitly says "do not store to RAG" / "do not store to vendor"
- Pure-query session (zero discoveries worth storing)

## Violation Case References

See `~/.claude/skills/cleanup/data/failed-attempts.md` entries under "Session-end RAG persistence" and "fix_plan.md completed item Qdrant sync" for details.

## Generic Skill Artifact — Immediate Store on Write (HARD STOP)

**Generic skill-generated research/plan artifacts (`research-*.md`, `plan-*.md`, etc.) must be stored to the RAG receiver immediately after writing.** "Just before archive" is not the only trigger — **write complete = store trigger**, regardless of decision pending or active status.

### Trigger timing

| Moment | RAG store required? |
|--------|---------------------|
| Immediately after write (Write/Edit complete) | ✅ |
| Decision pending / user review waiting | ✅ |
| User changes option → plan updated (re-store, same id upsert) | ✅ |
| Just before archive or deletion | ✅ |
| When composing artifact handling ask options | ✅ store is the default action (not an option) |

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | Skip store when archiving immediately after writing | Call RAG store MCP immediately after writing — store body + metadata |
| 2 | "User instructed archive so store is unnecessary" assumption | Archive and RAG store are separate responsibilities (local cleanup vs external index preservation) |
| 3 | "Decision pending = store unnecessary" inference | Store immediately even in pending state. Pending ≠ changing the default |
| 4 | "MCP was disconnected in the previous turn, assume same this turn" | Re-confirm availability every turn (system reminder deferred tool list) |
| 5 | "Already stored once, sufficient" when plan is updated | Updated version also upserts with same id (idempotent) |
| 6 | 3-way option ("store" / "keep" / "delete") in artifact handling ask | Store is default. Options are only for local handling after store (keep/archive/delete) |

**Self-check (after every research/plan file Write/Edit)**: File path matches `**/.ralph/docs/generated/{research,plan}-*.md` or `**/.omc/plans/*.md`? → RAG store MCP available? → Any store call trace for this file this session? → If none, store immediately.

## RAG Store Report Format (HARD STOP)

When calling RAG receiver store, **state the number of chunks added quantitatively at the end of the response**. Status-only reporting ("store complete") is forbidden.

### Format

```text
RAG store summary: N chunks added (receiver: <skill>:<topic>)
  - <chunk-id-1>: <one-line summary>
  ...
```

Place as the **last element** of the response (after other report text).

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | "RAG store complete" status-only report | "RAG store summary: N chunks added" quantitative statement |
| 2 | Chunk info only mid-response + missing at end | Place summary block as last element of response |
| 3 | Report responsibility unclear in cross-topic calls → omission | Caller skill is responsible for reporting (state cross-topic cumulative total) |
| 4 | Store count mismatch (intended N ≠ store calls ≠ reported count) | Verify intended = store = reported all match |
| 5 | Per-medium totals not separated | Separate quantitative totals per medium (RAG / memory / file record) |
| 6 | Report only current call + ignore session cumulative | Report full session cumulative total |

**Self-check (before every response end)**: RAG store call traces in this response / this session → mandatory: summary block as last element.

