# add — write a new hook into this marketplace

The end-to-end path for a hook that does not exist yet: from "a failure class
needs a guard" to a committed, registered, empirically-verified script.

This is distinct from the neighbouring topics. [install.md](./install.md) moves
an existing script into `hooks/` and registers it; [edit.md](./edit.md) changes
one that already runs; [registry.md](./registry.md) owns the inventory file this
topic writes one row into. Only this topic covers authoring.

## When a hook is the right answer

A hook is worth writing when the failure has a **mechanically checkable
signature**. If detecting the failure requires understanding intent, a rule or a
skill instruction is the correct medium and a hook will only produce noise.

| Signal | Medium |
|--------|--------|
| The mistake shows up as a specific tool call shape (a flag, a path, a missing companion call) | hook |
| The mistake shows up in the response text alongside checkable evidence in the same turn | hook (Stop event) |
| The mistake is a judgment call with no observable trace | rule / skill topic, not a hook |
| The class has recurred 4+ times and `failed-attempts.md` marks it `status=hook-mandatory` | hook, and it is overdue |

## Step 1 — Read the registry before writing anything

`skills/hook-kit/hook-registry.yaml` is the canonical inventory. Consult it
first, every time:

```bash
grep -n "id: " skills/hook-kit/hook-registry.yaml | wc -l
grep -n -B2 -A10 "<the-name-you-are-considering>" skills/hook-kit/hook-registry.yaml
```

Two things you are looking for:

- **An existing hook that already covers this.** Extending one is almost always
  better than adding a second that fires on overlapping input — two hooks
  disagreeing about the same tool call is its own failure class.
- **A tombstone** (`status: removed`). A hook that was deliberately removed
  carries the reason it was removed. Re-adding it without reading that row
  repeats whatever caused the removal.

This step is enforced: `block-hook-registration-without-registry-read.js` blocks
registration edits that were not preceded by a read of this file.

## Step 2 — Pick the sibling to mirror

Do not design the file layout from scratch. Find the closest existing hook by
**event**, and copy its shape — where the file lives, how it reads stdin, how it
emits its verdict, how it degrades when its inputs are missing.

```bash
# what already runs on the event you are targeting
jq -r '.hooks.Stop[]?.hooks[]?.command' hooks/hooks.json
jq -r '.hooks.PreToolUse[]? | "\(.matcher): \(.hooks[]?.command)"' hooks/hooks.json
```

Placement follows the owner: a hook that gates one skill's behaviour lives in
**that skill's** `resources/`, not in `hook-kit/`. `hook-kit` holds the
harness-level guards that are not tied to a single skill.

## Step 3 — Know what your event can and cannot emit

The events do not share an output schema, and getting this wrong fails silently.

| Event | Block by | Feeds text back via |
|-------|----------|---------------------|
| `PreToolUse` | `exit 2` | stderr |
| `Stop` | `{"decision":"block","reason":"…"}` on stdout | the `reason` string |
| `PostToolUse` / `UserPromptSubmit` | — | `hookSpecificOutput.additionalContext` |

`Stop` does **not** accept `hookSpecificOutput.additionalContext` — schema
validation rejects it. `decision` + `reason` is the only channel there. A Stop
hook also fires *after* the response is written, so it cannot suppress that
response; it can only shape the next turn.

An exit code of 127 (script not on disk) reads to the harness as "the guard had
no objection". A registered-but-missing hook is therefore worse than no hook: it
looks present and never fires. `hook_registry_verify.py --check` reports these
as `ORPHAN_REGISTRATION`.

## Step 4 — Keep it English-only and locale-degradable

This repository is PUBLIC and CI enforces English in every tracked `.md` and
`.sh`. Non-English detection patterns belong in the git-ignored
`skills/hook-kit/data/` file, sourced with a never-match fallback:

```bash
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
[ -f "$HG_DATA_FILE" ] && . "$HG_DATA_FILE"
MY_PATTERN="${HG_MY_PATTERN:-__NEVER_MATCH__}"
```

The fallback matters: when the data file is absent the hook must become a no-op
for that language, not crash and not match everything.

## Step 5 — Ship a `--test` harness, weighted toward negatives

A guard whose false positives outnumber its catches makes the class worse than
leaving it unguarded — the reminder gets tuned out, and the real catch arrives
inside noise nobody reads any more. So the negative set is the load-bearing
half.

```bash
if [ "${1:-}" = "--test" ]; then
  test_case "<name>" <expected> '<stdin fixture>'
  # PreToolUse: expected is the exit code (2 = block, 0 = allow)
  # Stop:       assert on whether stdout carries "decision"
fi
```

Minimum bar before commit:

- **5+ negative fixtures** drawn from phrasing that legitimately occurs in this
  workspace. Not invented near-misses — text a real turn would produce.
- Every branch exercised. A fixture set that only covers one input shape leaves
  the other branches dead, and dead branches are where the bugs sit. A real
  example: a hook whose non-`Bash` tool path was never fixtured shipped with a
  NUL byte in its case pattern; the Bash-only fixtures all passed anyway. Adding
  two fixtures for that path surfaced it immediately.
- Run it: `bash <hook>.sh --test`.

## Step 6 — Register in both surfaces

Registration is two files, and missing either one produces a hook that is
invisible in a different way.

```bash
# 1. hooks/hooks.json — what the harness actually executes
#    Insert next to the sibling from Step 2 so related guards stay adjacent.

# 2. skills/hook-kit/hook-registry.yaml — the canonical inventory
#    id / owner_skill / marketplace / status / implementations / registrations
```

Then verify, and read the output against the base rather than in isolation:

```bash
uv run --with pyyaml python skills/hook-kit/scripts/hook_registry_verify.py --check
```

Findings that already exist on the base ref are not yours. Confirm that rather
than assuming it:

```bash
git show origin/develop:skills/hook-kit/hook-registry.yaml | grep -c "id: <finding-id>"
```

## Step 7 — Pre-commit gates

```bash
bash -n <hook>.sh                              # syntax
bash <hook>.sh --test                          # own fixtures
python3 scripts/check-hangul.py skills         # English-only
uv run --with pytest python -m pytest tests/ -q
bats tests/                                    # includes "every hooks.json command path exists on disk"
```

Then the PUBLIC-repo secret scan on the staged diff (see
`commit-tidy/security-scan`), and stage explicitly — never `git add -A`.

Commit type: a new file under `skills/<name>/resources/` is a new capability, so
it is `feat(<skill>)`, which is also what `bash-guard.py`'s own feat-tag
integrity check requires. Modifying an existing hook is `fix(<skill>)`.

## Self-check before commit

1. Did you read `hook-registry.yaml` — including tombstones — before writing?
2. Is the placement decided by the owner (skill-specific → that skill's
   `resources/`; harness-level → `hook-kit`)?
3. Does the emit shape match the event's schema, and does the script exit 0 on
   every path where it has no objection?
4. Does it degrade to a no-op when its data file or its input is absent?
5. Are there 5+ negative fixtures, and is every branch covered by at least one?
6. Are both `hooks.json` and `hook-registry.yaml` updated, and does
   `hook_registry_verify.py --check` report only findings that already exist on
   the base ref?
7. Does the commit tag match the change class (`feat` for a new script)?
