# Update

Mutate an **existing** fix_plan/checklist item in place — flip its marker, append a progress note, or set a trailing attribute — without going around `block-direct-checklist-edit.js` via a raw Edit/Write.

## Why this exists

`add.md` covers brand-new items and `move.md` covers `[x]` → `## Completed`. Neither script can touch an item that already exists and is neither new nor fully done — e.g. leaving a mid-session progress note on an open item, or flipping `[ ]` to `[BLOCKED:P1:external]` when a dependency surfaces. Before this topic, the only way to do that was a direct Edit/Write, which `block-direct-checklist-edit.js` hard-blocks (correctly — it also protects against schema corruption from hand-edits).

## Usage

```bash
python <skill-dir>/scripts/update_item.py --file <path> \
  --match "<substring of the action text>" \
  [--set-marker "[x]"] [--append-note "one-line note"] \
  [--set-attr ICE=I2,C0.8,E4] [--dry-run]
```

At least one of `--set-marker` / `--append-note` / `--set-attr` is required; they may be combined in one call (e.g. flip to `[BLOCKED:P1:external]`, leave a note explaining why, and record the channel in the same invocation).

## Matching (HARD STOP — exactly one item)

`--match` is a substring match against the action text (the text after the marker on the item's own line). If it matches **zero** or **two or more** items, the script errors out and lists every candidate's first 80 characters — narrow `--match` and retry rather than guessing. This mirrors `add_item.py`'s own duplicate-detection regex, applied in the opposite direction (find-one instead of prevent-duplicate).

| # | Don't | Do |
|---|-------|-----|
| 1 | Pick a short, generic `--match` fragment ("fix", "chart") hoping it lands on the right item | Use a distinctive phrase from the item's action line — the error message echoes every ambiguous candidate if the first attempt is too broad |
| 2 | Retry with a slightly different `--match` in a loop without reading the ambiguity error | The error already lists the candidates — read it and copy the exact distinguishing phrase |

## What it does NOT do

- **Does not move sections.** Flipping `--set-marker "[x]"` changes the marker in place; it does not relocate the item into `## Completed` — that stays `move.md` / `cleanup.py`'s job (which also does the completion-summary condensation `add.md`'s length budget expects). `format.md`'s "Completion Migration Rule (HARD STOP)" requires the marker flip and the `## Completed` migration to happen in the **same edit/turn** — after `--set-marker "[x]"`, chain straight into `move.md` / `cleanup.py` before ending the turn; do not leave a bare `[x]` sitting in `## Progress` across turns.
- **Does not rewrite Why / How to apply.** Only the marker and append-only notes are mutable. If the original Why/How is wrong, that is a correctness problem in the entry itself, not a progress update — write a fresh item via `add_item.py` instead of silently rewriting history in place.
- **Does not bypass the length budget** (`add.md` "Length budget — verbose body forbidden"). `--append-note` re-checks the item's total line count against the same 10-line hard cap `add_item.py` enforces; a note that would push it over is rejected with a pointer to move the content into a research/plan artefact instead.

## The two bracket slots

An item line carries two bracket slots, and they are not interchangeable:

```
- [BLOCKED:P2:selfable] Migrate auth middleware [ICE:I4,C0.8,E2] [ch:orca]
  ^-- checkbox marker (leading)                 ^-- attributes (trailing)
```

| Slot | Position | Written by | Values |
|------|----------|-----------|--------|
| Checkbox marker | leading, one per item | `--set-marker`, validated by `validate_marker()` imported from `add_item.py` | `[ ]`, `[x]`, `[-]`, `[BLOCKED:P<0-3>:external\|selfable]` |
| Attributes | trailing, any number, one per key | `--set-attr`, validated against `ATTR_VOCAB` | see the vocabulary table below |

`BLOCKED` is a checkbox-marker value and is deliberately **not** registered as an attribute key, so a trailing `[BLOCKED:...]` can never be emitted beside a real one.

## Attribute slot (`--set-attr KEY=VALUE`)

Per-item attributes that queries and scoring need as fields rather than prose. Writing one through this flag, instead of by hand, is what makes it machine-readable: the key must be registered, the value must match that key's grammar, and a repeated write **replaces that key in place** rather than appending a second marker for it.

### Registered vocabulary

| Key | Grammar | Meaning | Example |
|-----|---------|---------|---------|
| `ICE` | `I<num>,C<num>,E<num>` | Impact / Confidence / Ease scoring inputs. Reach is deliberately absent — ICE, not RICE, because internal tooling items have no natural reach denominator | `[ICE:I4,C0.8,E2]` |
| `ch` | one of `orca`, `clawo`, `deep-tasks`, `in-session`, `user-decision` | Which execution channel the item is allocated to | `[ch:orca]` |
| `RAID` | non-empty subset of `R`,`A`,`I`,`D`, comma-separated | Which RAID axes are registered for the item (risk / assumption / issue / dependency) | `[RAID:R,D]` |

An unregistered key is **refused, not written** — otherwise the tracker accumulates private vocabularies no reader parses. The rejection names the registered keys, and a bad value names the grammar it failed:

```
error: argument --set-attr: unregistered attribute key 'NOPE'. Registered: ICE, RAID, ch.
error: argument --set-attr: value 'telepathy' does not match the grammar registered for 'ch'
```

### Adding a key

Add the row to `ATTR_VOCAB` in `update_item.py` together with its value grammar, add the row to the table above, and add a self-test case. A key that exists in only one of those three places is a key some reader cannot parse.

| # | Don't | Do |
|---|-------|-----|
| 1 | Hand-type a trailing marker with Edit/Write because the key is not registered yet | Register the key first. Hand-typed markers are what left `ch` and `RAID` at zero coverage while tool-written vocabularies reached 265 items |
| 2 | Write a second `[ICE:...]` when re-scoring an item | `--set-attr` replaces the key in place; a duplicate key makes the item's score ambiguous to every reader |
| 3 | Invent a value outside the registered grammar ("[ch:slack]") | Extend the grammar deliberately, in `ATTR_VOCAB` and the table, so the new value is parseable everywhere |

## Example

```bash
# A dependency surfaced mid-session — flip the marker and leave a note in one call
python <skill-dir>/scripts/update_item.py --file fix_plan.md \
  --match "Migrate auth middleware" \
  --set-marker "[BLOCKED:P1:external]" \
  --append-note "Blocked on legal review of session-token retention policy — see #212"

# Record the scoring inputs and the execution channel on an existing item
python <skill-dir>/scripts/update_item.py --file fix_plan.md \
  --match "Migrate auth middleware" \
  --set-attr "ICE=I4,C0.8,E2"
python <skill-dir>/scripts/update_item.py --file fix_plan.md \
  --match "Migrate auth middleware" \
  --set-attr "ch=orca"
```

## See also

- [add.md](./add.md) — new item authoring schema (Action / Why / How, length budget)
- [move.md](./move.md) — how `[x]` entries get summarised into `## Completed`
- [priority.md](./priority.md) — `[BLOCKED:P0-P3:reason]` annotation semantics
