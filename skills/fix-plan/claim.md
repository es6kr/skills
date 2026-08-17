# Claim — Multi-session In-progress Lease

Prevents two contexts — two interactive sessions, or an interactive session plus an autonomous Ralph loop / background dispatch — from independently working the same tracker item. A **claim** is a lightweight, self-expiring lease stamped onto an item the moment a session starts working it, so any concurrent reader sees the item is already in flight.

## Why

`fix_plan.md` / `checklist.md` are frequently edited by more than one context at once. The `[ ]` / `[x]` / `[BLOCKED]` markers describe an item's *state*, not *who is currently acting on it*. Without a claim, two sessions can both read a `[ ]` item, both decide it is available, and both do the same work — the exact duplicate-progress hazard this topic prevents.

A claim is **not** a new checkbox state. It is a concurrency annotation (a lease) that rides alongside the existing marker, orthogonal to pending / blocked / done.

## Marker syntax

Append a `[CLAIMED:<session>:<timestamp>]` suffix tag **after** the standard checkbox marker, before the item text:

```markdown
- [ ] [CLAIMED:84f9e320:2026-08-13T11:20] Recover Plane index 84 lines
- [BLOCKED:P1:selfable] [CLAIMED:5bfda407:2026-08-13T09:05] consolidate Step 2.4 PR create
```

| Piece | Value | Notes |
|-------|-------|-------|
| `[CLAIMED]` | literal | The lease tag |
| `<session>` | first 8 chars of the session id | Same source as `format.md`'s completion convention (`.ralph/.claude_session_id` in Ralph, else the current session id) |
| `<timestamp>` | ISO `YYYY-MM-DDTHH:mm` (24h) | The moment the claim was stamped or last refreshed — doubles as the lease clock for staleness |

**Not a hybrid marker.** `format.md` forbids `- [ ] [BLOCKED...]` because `[ ]` and `[BLOCKED]` are two mutually-exclusive *state* markers. `[CLAIMED:...]` is a *lease annotation*, not a state — so `- [ ] [CLAIMED:...]` and `- [BLOCKED:P*:selfable] [CLAIMED:...]` are both valid. The checkbox marker (`[ ]` / `[BLOCKED:...]`) is unchanged; the claim tag sits after it exactly like `[TRACKED]` / `[REVIEW_FEEDBACK]`.

Claim only `[ ]` and `[BLOCKED:P*:selfable]` items (both are workable-now). Never stamp a claim on `[x]` (already done) or `[BLOCKED:*:external]` (not progressable — nothing to claim).

## Lifecycle

### 1. Claim (before starting work) — HARD STOP: re-read first

Because the tracker is often under concurrent edit, **re-read the file from disk immediately before claiming** — an in-context snapshot may be stale.

1. Re-read the tracker; grep the target item for an existing `[CLAIMED` tag
2. If unclaimed (or the existing claim is stale — see "Stale claim & takeover") → add `[CLAIMED:<your-sid>:<now>]` after the checkbox marker
3. Save (and commit, in a git-tracked tracker) the claim edit **before** beginning the actual work, so concurrent readers see it promptly

### 2. Refresh (long-running work, optional)

For work spanning longer than the stale TTL, re-stamp `<timestamp>` to the current time periodically so a live claim is not mistaken for an abandoned one.

### 3. Release

- **On completion**: the `[ ]` → `[x]` transition and the move to `## Completed` (per [move.md](./move.md)) drop the `[CLAIMED]` tag — completion supersedes the claim. Do not carry a claim tag into the Completed summary line (the Completed entry records the session id via its own convention).
- **On abandonment**: if a session stops without completing, remove the `[CLAIMED]` tag during wind-down, or leave it to expire via the stale TTL.

## Stale claim & takeover

A claim is **stale** when either:

- its `<timestamp>` is older than the **stale TTL — default 4h** (override via `--claim-ttl=<hours>`), **or**
- the claiming session is known to have ended (its session id is no longer active)

Before working an item that already carries a `[CLAIMED]` tag:

| Existing claim | Action |
|----------------|--------|
| Fresh (within TTL, different live session) | **Do not work it.** It is in flight elsewhere. Pick a different candidate; if it is the only priority, report the conflict to the user rather than racing |
| Fresh (your own session id) | Continue — it is your claim. Refresh the timestamp if long-running |
| Stale (TTL elapsed or claiming session ended) | **Take over**: replace the old tag with `[CLAIMED:<your-sid>:<now>]` in the same edit, then proceed |

## Interaction with triage & the default pipeline

- **Candidate surfacing** ([priority.md](./priority.md) triage, `impl` / `pm` `selfable`-candidate handoff): exclude items carrying a **fresh** `[CLAIMED]` tag — they are in flight, not available. Stale-claimed items stay eligible (with takeover).
- **Completion / move**: [move.md](./move.md)'s `[x]` → Completed migration drops the tag automatically.
- **Autonomous loops**: a Ralph wrapper (caller-side) should treat a fresh-claimed `[ ]` as skip, the same way it skips `[BLOCKED]`. This skill only defines the tag; loop enforcement lives in the wrapper, consistent with how the wrapper owns `[BLOCKED]` loop semantics.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Start working a `[ ]` item without checking for an existing `[CLAIMED]` tag | Re-read the tracker + grep `\[CLAIMED` on the item first; claim before starting |
| 2 | Claim from an in-context snapshot without re-reading disk | The tracker is often under concurrent edit — re-read immediately before the claim edit |
| 3 | Work a fresh claim owned by another live session | Fresh + different session = in flight. Choose another item or report the conflict |
| 4 | Introduce a new checkbox marker like `[/]` / `[WIP]` for in-progress | Forbidden by the marker contract. Use the `[CLAIMED:...]` suffix tag on the existing `[ ]` / `[BLOCKED:*:selfable]` marker |
| 5 | Carry a `[CLAIMED]` tag into the `## Completed` summary line | Completion drops the tag — the Completed entry records the session id via its own convention |
| 6 | Leave a stale claim blocking a genuinely available item forever | Stale (TTL elapsed / session ended) = takeover: re-stamp with your own session + now |

## Self-check (before claiming an item)

1. Did I re-read the tracker from disk this turn (not an in-context snapshot)?
2. Does the target item already carry a `[CLAIMED]` tag? — grep `\[CLAIMED` on the line
3. If claimed: is it mine, fresh-other, or stale? — mine → continue; fresh-other → do not work it; stale → takeover
4. Is the item `[ ]` or `[BLOCKED:*:selfable]`? — never claim `[x]` or `:external`
5. Did I save / commit the claim edit before starting the actual work?

## See also

- [format.md](./format.md) — marker syntax; `[CLAIMED]` is a suffix annotation, not a checkbox state
- [move.md](./move.md) — `[x]` → Completed migration drops the claim tag
- [priority.md](./priority.md) — triage excludes fresh-claimed items from candidate surfacing
