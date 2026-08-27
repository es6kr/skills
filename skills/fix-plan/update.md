# Update

Mutate an **existing** fix_plan/checklist item in place — flip its marker or append a progress note — without going around `block-direct-checklist-edit.js` via a raw Edit/Write.

## Why this exists

`add.md` covers brand-new items and `move.md` covers `[x]` → `## Completed`. Neither script can touch an item that already exists and is neither new nor fully done — e.g. leaving a mid-session progress note on an open item, or flipping `[ ]` to `[BLOCKED:P1:external]` when a dependency surfaces. Before this topic, the only way to do that was a direct Edit/Write, which `block-direct-checklist-edit.js` hard-blocks (correctly — it also protects against schema corruption from hand-edits).

## Usage

```bash
python <skill-dir>/scripts/update_item.py --file <path> \
  --match "<substring of the action text>" \
  [--set-marker "[x]"] [--append-note "one-line note"] [--dry-run]
```

At least one of `--set-marker` / `--append-note` is required; both may be combined in one call (e.g. flip to `[BLOCKED:P1:external]` and leave a note explaining why in the same invocation).

## Matching (HARD STOP — exactly one item)

`--match` is a substring match against the action text (the text after the marker on the item's own line). If it matches **zero** or **two or more** items, the script errors out and lists every candidate's first 80 characters — narrow `--match` and retry rather than guessing. This mirrors `add_item.py`'s own duplicate-detection regex, applied in the opposite direction (find-one instead of prevent-duplicate).

| # | Don't | Do |
|---|-------|-----|
| 1 | Pick a short, generic `--match` fragment ("fix", "chart") hoping it lands on the right item | Use a distinctive phrase from the item's action line — the error message echoes every ambiguous candidate if the first attempt is too broad |
| 2 | Retry with a slightly different `--match` in a loop without reading the ambiguity error | The error already lists the candidates — read it and copy the exact distinguishing phrase |

## What it does NOT do

- **Does not move sections.** Flipping `--set-marker "[x]"` changes the marker in place; it does not relocate the item into `## Completed` — that stays `move.md` / `cleanup.py`'s job (which also does the completion-summary condensation `add.md`'s length budget expects).
- **Does not rewrite Why / How to apply.** Only the marker and append-only notes are mutable. If the original Why/How is wrong, that is a correctness problem in the entry itself, not a progress update — write a fresh item via `add_item.py` instead of silently rewriting history in place.
- **Does not bypass the length budget** (`add.md` "Length budget — verbose body forbidden"). `--append-note` re-checks the item's total line count against the same 10-line hard cap `add_item.py` enforces; a note that would push it over is rejected with a pointer to move the content into a research/plan artefact instead.

## Marker values

Same as `add.md`: `[ ]`, `[x]`, `[-]`, or `[BLOCKED:P<0-3>:external|selfable]`. Validated by the same `validate_marker()` `add_item.py` uses (imported, not duplicated).

## Example

```bash
# A dependency surfaced mid-session — flip the marker and leave a note in one call
python skills/fix-plan/scripts/update_item.py --file fix_plan.md \
  --match "Migrate auth middleware" \
  --set-marker "[BLOCKED:P1:external]" \
  --append-note "Blocked on legal review of session-token retention policy — see #212"
```

## See also

- [add.md](./add.md) — new item authoring schema (Action / Why / How, length budget)
- [move.md](./move.md) — how `[x]` entries get summarised into `## Completed`
- [priority.md](./priority.md) — `[BLOCKED:P0-P3:reason]` annotation semantics
