# Registry — relocated

The canonical hook inventory (`hook-registry.yaml`) and its tooling (`hook_registry.py`,
`hook_registry_verify.py`, `block-hook-registration-without-registry-read.js`, their tests)
moved to **es6kr/claude-plugins**, repo root — see that repo's `hook-registry.md`.

Why: the registry has always tracked both marketplaces (`es6kr-skills`, `es6kr-plugins`), but
lived inside this PUBLIC repo — meaning a private repo's own hook registration details were
described from inside a public one. It now lives in the private repo instead, owned by neither
marketplace exclusively.

The consult-before-registering procedure is unchanged, only the location:

1. `Read` the registry at `~/ghq/github.com/es6kr/claude-plugins/hook-registry.yaml` (or that
   repo's `~/.claude/plugins/marketplaces/es6kr-plugins/` install path).
2. Classify from its row: `owner_skill` decides the target plugin; `status` decides add
   (`dormant` → activate) / keep / tombstone; `registrations` decides whether a settings.json
   entry is a duplicate of a plugin registration.
3. Apply the registration change **and** the registry change in the same commit.
4. Verify from an es6kr/skills checkout: `uv run --with pyyaml python
   ~/ghq/github.com/es6kr/claude-plugins/scripts/hook_registry_verify.py --check --repo-root .`

The read-before-register guard (`block-hook-registration-without-registry-read.js`) now lives
and is registered in claude-plugins only — a PreToolUse:Edit|Write hook fires for edits
regardless of which repo the edited file lives in, as long as the providing marketplace is
installed, so it still protects edits made in this repo.

## See also

- [audit.md](./audit.md), [install.md](./install.md), [remove.md](./remove.md), [move.md](./move.md) — this skill's own procedures for es6kr-skills-owned hooks are unaffected by the move
