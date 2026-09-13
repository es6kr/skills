# Registry — relocated

The canonical hook inventory (`hook-registry.yaml`) and its tooling (`hook_registry.py`,
`hook_registry_verify.py`, `block-hook-registration-without-registry-read.js`, their tests)
moved to a private companion repository's root — see that repo's own `hook-registry.md` for the
exact checkout path. This file (PUBLIC marketplace content) does not name the companion repo;
if you don't already know where it lives, you don't have access to it either.

Why: the registry has always tracked both marketplaces (`es6kr-skills`, `es6kr-plugins`), but
lived inside this PUBLIC repo — meaning a private repo's own hook registration details were
described from inside a public one. It now lives in the private repo instead, owned by neither
marketplace exclusively.

The consult-before-registering procedure is unchanged, only the location:

1. `Read` the registry at the companion repo's `hook-registry.yaml` (or its
   `~/.claude/plugins/marketplaces/es6kr-plugins/` install path).
2. Classify from its row: `owner_skill` decides the target plugin; `status` decides add
   (`dormant` → activate) / keep / tombstone; `registrations` decides whether a settings.json
   entry is a duplicate of a plugin registration.
3. Apply the registration change and the registry change. **These can no longer land in the same
   commit** — they are two different repos now. Treat them as one logical unit instead: land the
   registry-side change first, then cite its commit/PR in the settings.json-side commit message.
4. Verify from an es6kr-skills checkout, passing the companion repo's registry path explicitly —
   the verifier's own `--registry` default resolves to this repo's `skills/hook-kit/hook-registry.yaml`,
   which no longer exists here, so omitting the flag silently checks nothing:
   `uv run --with pyyaml python <companion-repo>/scripts/hook_registry_verify.py --check --repo-root . --registry <companion-repo>/hook-registry.yaml`

The read-before-register guard (`block-hook-registration-without-registry-read.js`) now lives
and is registered in the companion repo only — a PreToolUse:Edit|Write hook fires for edits
regardless of which repo the edited file lives in, as long as the providing marketplace is
installed, so it still protects edits made in this repo.

## See also

- [audit.md](./audit.md), [install.md](./install.md), [remove.md](./remove.md), [move.md](./move.md) — this skill's own procedures for es6kr-skills-owned hooks are unaffected by the move
