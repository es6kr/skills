# Registry — canonical hook inventory (`hook-registry.yaml`)

`skills/hook-kit/hook-registry.yaml` is the single canonical inventory of every hook this
marketplace knows about: its logical identity (`id` = filename stem), `owner_skill`,
`marketplace` (`es6kr-skills` | `es6kr-plugins` | `user-settings` | `antigravity`),
`status` (`active` | `dormant` | `orphan` | `removed`), `implementations` (sh/py/js
variants), `registrations` (which surface/event/matcher/command), and — for removed hooks —
a `tombstone`. The schema and its rules are defined in the plan
`plan-hook-registry-schema.md` (workspace `llm-wiki/outputs/`); this topic is the operating
procedure that hook-kit's other topics and any hook-registration change must go through.

## When to consult it (HARD STOP — before the change, not after)

Any of these is a registry-first task:

| Situation | Registry answers |
|-----------|------------------|
| Adding, removing, or re-pointing a hook entry in `~/.claude/settings.json` `hooks` | Is the hook already registered on a plugin surface (dual registration)? Who owns it? |
| Editing any `hooks/hooks.json` / `.claude-plugin/hooks.json` | Does the `registrations` list already cover this event/matcher? Is the id `removed` (re-introduction)? |
| A hook errors with "No such file" (phantom / ghost path) | Which `marketplace` and `implementations.file` is the live copy? Was it moved or tombstoned? |
| Deciding whether a hook may be deleted | `runtime_copies.expected_roots` — deletion is complete only when every copy is gone |
| Auditing dual-marketplace duplicates | Same `id` active in two marketplaces is a violation; `.sh` + `.js` with the same id is a migration, not a duplicate |

"A plugin `hooks.json` also lists it" is **not** the ownership criterion — the registry row is.
Hooks that exist on disk but have no registry entry are backfill candidates (report them), not
free-floating files to re-point by guesswork.

## Procedure

1. `Read skills/hook-kit/hook-registry.yaml` (the marketplace checkout under
   `~/.claude/plugins/marketplaces/es6kr-skills/` is the installed copy). The guard below checks
   the session transcript for exactly this read.
2. For each hook touched, classify from its row: `owner_skill` decides the target plugin;
   `status` decides add (`dormant` → activate) / keep / tombstone; `registrations` decides
   whether a settings.json entry is a duplicate of a plugin registration.
3. Apply the registration change **and** the registry change in the same commit
   (new `registrations` entry, `status` flip, or `tombstone` block — never delete a row).
4. Verify: `uv run --with pyyaml python skills/hook-kit/scripts/hook_registry_verify.py --check`
   (add `--check-copies` when the change deletes or moves files).
5. Report registry-absent hooks encountered on the way as Phase 2 backfill candidates.

## Enforcement

`resources/block-hook-registration-without-registry-read.js` (PreToolUse `Edit` + `Write`,
registered in `hooks/hooks.json`) blocks edits to `*/.claude/settings*.json` hook content and to
any `hooks/hooks.json` when the session transcript contains no `hook-registry.yaml` read. Explicit,
audited override: put the literal token `hook-registry-consulted` in the edited content.

| # | Don't | Do |
|---|-------|-----|
| 1 | Triage settings.json hook entries by grepping plugin `hooks.json` for the same filename | Look the id up in the registry: `owner_skill` + `marketplace` + `status` decide |
| 2 | Re-point a phantom path to whichever copy `find` locates first | Use the `implementations.file` of the owning marketplace; other copies are drift to report |
| 3 | Delete a hook file and call it removed | `status: removed` needs a tombstone and every `expected_roots` copy gone; Syncthing checkouts restore working-tree deletions unless committed |
| 4 | Register a hook on a plugin surface without a registry row | Add the row (or `registrations` entry) in the same change; CI's registry verification reports the gap otherwise |
| 5 | Consult the registry only when `/fix` step 2 tells you to | The consult-first rule applies on every entry path — cleanup hook review, phantom-hook repair, settings edits, plugin moves |

## See also

- [audit.md](./audit.md) — reference/permission/orphan checks (registry diff is the ground truth for orphan vs dormant)
- [install.md](./install.md), [remove.md](./remove.md), [move.md](./move.md) — each registration change ends with the registry update in step 3 above
- `scripts/hook_registry_verify.py` — bootstrap (`--bootstrap`) and 3-way check (`--check`, `--check-copies`)
