# Fast (zero-modal staging record)

Append an observation straight to the workspace's `.agents/improvements.md` staging inbox and
return within the same turn — no 5-Why, no recurrence pre-check, no `AskUserQuestion`. The
mistake/finding is *staged*, not yet classified; a later `fa-inbox-triage.py` pass (Phase 3,
not implemented in this revision) is what promotes staged entries into `retrospect`'s full FA
record, or drains them as no-ops.

This exists for the case `retrospect.md`'s full procedure does not fit: a quick note made
mid-task that should not interrupt the current flow with a modal, but also should not be lost
by staying only in the transcript.

## Trigger

- Explicit flag: `/fa fast <note>`
- Bare note-only intent phrases (Axis 2, user-confirmed 2026-10-11, alongside the explicit flag
  — not instead of it): a request that explicitly asks for a note-only / non-interrupting
  record ("just note this", "don't interrupt, just log it", "record it quietly") routes here
  instead of the full retrospect ceremony
- **Disambiguation against `ask-gates.md` recording-skip rules**: a bare "record this" /
  "log this mistake" with no "fast" / "just note" / "quietly" qualifier still routes to
  `retrospect.md` (the full procedure) — `fast` requires an explicit flag or one of the
  note-only phrases above, not any generic recording request

## Procedure

1. Resolve the session id if available (`source="interactive"` default; Ralph callers pass
   `source="ralph"`).
2. Call `scripts/fa-fast-record.py`'s `fast_record(note, session_id, source)` directly — or the
   CLI form `python3 scripts/fa-fast-record.py '<note>'` from the workspace root.
3. Report the one-line `[OK]`/`[FAIL]` result and continue the interrupted task immediately.
   Do **not** chain into Step 1 (mistake detection) or Step 1.5 (recurrence pre-check) of
   `retrospect.md` — that classification work is deferred to the Phase 3 triage pass.

## Out of scope (Phase 3 — not implemented here)

- `fa-inbox-triage.py`'s promotion logic: emitting a classification header on each staged entry
  and moving it into this skill's canonical mistake record once triaged, or draining it as a
  resolved no-op.
- Any periodic scan of the inbox for un-triaged entries.

## Failure modes

`fa-fast-record.py` fails loudly (non-zero exit, `[FAIL]` to stderr) rather than silently
degrading in two cases — do not add a fallback around either:

- **No workspace root** — no ancestor owning `.agents/` found from the caller's cwd (searched strictly below the `ghq` parent, so a global `~/.agents` is never picked up). There is no global
  fallback inbox; this is intentional (see the script's module docstring for the Fable-audit
  rationale against the plan's original `~/.agents/improvements.md` fallback).
- **`.agents/` directory missing** — the script does not auto-create it.
