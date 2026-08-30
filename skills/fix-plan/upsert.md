# Upsert — Dup-Check Before Add

Check the tracker for an existing item covering the same work before authoring a new one; update that item in place when found, otherwise fall back to [add.md](./add.md)'s schema.

## Why

`add.md` only covers the "genuinely new item" case — it has no procedure for checking whether the work is already tracked. Without a dup-check step, the same backlog item accumulates duplicate entries across sessions (one written today, another written next week describing the same gap with different wording), or a stale entry sits underscoping the real problem while a fresh one gets written next to it instead of expanding the original. Both outcomes fragment a single piece of work across multiple tracker lines, so no one entry reflects current reality and priority triage double-counts it.

## Procedure

### 1. Dup-check (mandatory, before authoring anything)

Grep the **entire tracker** for the new item's core keywords — not just the section the new item would naturally land in. Related work often lives in a different section than expected (a `TODO` note can already cover what would otherwise become a new `Priority Tasks` entry; a `Plan Drafts` stub can already be the deferred version of what's about to be added as `[ ]`).

```bash
grep -n "<2-3 core keywords>" <tracker-path>
```

Also check the `## Completed` section — the work may already be done and the "new" item is actually stale.

### 2. Match classification

| Match result | Action |
|---------------|--------|
| No hit anywhere | Fall back to [add.md](./add.md) — author a genuinely new item with its schema |
| Hit describes the **same Action** (same target, same work), scope may be stale or narrower than reality | **Update in place** (Step 3) |
| Hit touches the same file/target but describes a **different Action** | Treat as new — author separately via `add.md`. Do not force two distinct pieces of work into one entry just because they share a file |
| Hit found only in `## Completed` | Report as already-done instead of authoring anything; if the request implies renewed scope beyond what was completed, author that renewed scope as a new item |

Matching is on **Action semantics**, not exact string — a stale item whose wording undercounts the current scope ("2 files" when the real count is now 40) is still the same item, not a new one.

### 3. Update in place

- **Preserve the original `Why`'s motivation** — add a delta, don't replace wholesale. Future sessions lose context if the original rationale for opening the item is silently erased.
- **State what changed and why**, as a one-line dated sub-bullet: what was previously recorded, what the re-check found, and why the scope/priority changed.
- **Reclassify priority explicitly when warranted** — `old → new` plus a one-line reason (see [priority.md](./priority.md)). Silent reclassification leaves no audit trail for why the marker moved.
- **Absorbed-reference note** — if other items in the tracker cite this item as a prerequisite (a dangling "see the X item" pointer that never resolved to an actual entry, or an item whose scope has now folded into this one), add a one-line note that this item now serves that role. Do not go edit those other items' bodies as part of the same upsert — that is a separate, larger blast radius than a dup-check-and-update pass should take on.
- **Length budget still applies** — an upsert absorbing prior context does not get an exemption from `add.md`'s 5-7 line cap. If the merged content would exceed it, split the overflow into a research/plan artefact per `add.md`'s deliverable separation matrix, leaving only a pointer line in the tracker item.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Skip the dup-check because the target section "already looks organized" | Grep the whole tracker (all top-level `##` sections + Completed) for the new item's core keywords before authoring anything |
| 2 | Treat differing wording as proof of a new item | Match on Action semantics — a stale item describing the same work with an outdated scope is the same item |
| 3 | Overwrite an existing item's `Why` wholesale when updating | Preserve the original motivation, append a delta describing what the re-check found and changed |
| 4 | Silently bump or lower `[BLOCKED:P*]` during an upsert | State `old → new` priority plus a one-line reason in the same edit |
| 5 | Merge two distinct pieces of work into one entry because they touch the same file | Keep them separate — same file is not the same Action |
| 6 | Edit other items' bodies to fix their dangling cross-references while upserting the item they point to | Note in the upserted item that it now serves that referenced role; leave the referencing items for a separate pass |
| 7 | Let an absorbed item's accumulated context blow past the length budget | Split overflow into a research/plan artefact, same as `add.md`'s deliverable separation matrix |

## Self-check (before finalizing an upsert)

1. Did the dup-check grep cover every top-level section, not just the item's natural target section?
2. Is the matched item the same *Action*, or only the same file/target with a different action?
3. Did the update preserve the original `Why` and add a delta, rather than replacing it wholesale?
4. If priority changed, is `old → new` + reason stated explicitly?
5. Does the updated item still fit the 5-7 line budget? If not, was the overflow split into an artefact?
6. If other items reference this one as an unresolved prerequisite, did the update note that this item now serves that role — without editing those other items?

## See also

- [add.md](./add.md) — schema and length budget for the fallback (genuinely-new-item) path
- [priority.md](./priority.md) — `[BLOCKED:P0-P3:reason]` convention referenced by Step 3's reclassification rule
- [move.md](./move.md) — how a matched-in-`## Completed` item gets reported instead of re-authored
