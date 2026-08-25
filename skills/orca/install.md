# Install — Add Orca's Bundled Skills to Another Harness

`stablyai/orca` ships 8 skills under its own `skills/` directory (`orca-cli`, `orchestration`,
`computer-use`, `orca-emulator`, `orca-emulator-android`, `orca-linear`, `linear-tickets`,
`orca-per-workspace-env`). This topic installs *that* bundle into a harness — Claude Code,
OpenClaw, or Antigravity — so an agent running there can use Orca's own skills, not this
`orca` skill's `send`/`launch` topics.

## Step 1 — Ask how to source the repo (mandatory)

Before installing anything, ask the user which of these two they want:

| Option | Trade-off |
|---|---|
| **ghq-clone + symlink/junction** | Repo updates (`git pull`) are reflected immediately in every installed harness. The clone accumulates local, untracked install-manifest files (see Step 2) that can confuse later work in that clone if not tracked. |
| **Plain marketplace/package install** | Installer copies into its own cache; the source clone stays untouched. Updates require an explicit `plugin update`/`plugins update` per harness. |

Do not default to one silently — this is a durable choice about how future updates
propagate, not a one-off preference.

## Step 2 — Per-harness procedure

### Claude Code

Requires `.claude-plugin/marketplace.json` at the repo root (Orca does not ship one).

```bash
# Write .claude-plugin/marketplace.json with at least one plugin entry pointing at "./"
claude plugin marketplace add <path-to-orca-clone-or-manifest-dir>
claude plugin install orca@<marketplace-name>
```

Verify: `claude plugin list` shows the plugin `enabled`.

### OpenClaw

No manifest file is required. OpenClaw's bundle detector recognizes the **manifestless
Claude layout** (a `skills/` directory with no `.claude-plugin/plugin.json`) directly, so a
plain link is enough:

```bash
openclaw plugins install --link <path-to-orca-clone>
# or, reusing the marketplace.json created for Claude Code above:
openclaw plugins install <plugin-name> --marketplace <source>
```

Verify: `openclaw plugins list` shows it with `Format: bundle`, subtype `claude`. Restart the
gateway (`openclaw gateway restart`) for skills to load into the next session.

**Symlink hygiene**: if `~/.openclaw/skills/` already has skill-name symlinks pointing at a
different, now-missing source (this has been observed for `orca-cli` and `orchestration`
pointing at a stale `~/.agents/skills/` path), remove the dangling links before installing —
a dangling symlink doesn't error loudly, it just silently fails to load.

### Antigravity

Two things are required, neither of which Orca ships:

1. A `plugin.json` at the plugin's root. The minimal working form is just:
   ```json
   { "name": "orca" }
   ```
   (observed as sufficient on working local plugins — extra fields like `description`,
   `version`, `$schema` are optional decoration, not requirements.)
2. Placement under `~/.gemini/config/plugins/orca/` (global) or the workspace's
   `.agents/plugins/orca/` / `_agents/plugins/orca/` (project-scoped), with the `skills/`
   directory from the Orca clone copied or symlinked in alongside `plugin.json`.

```bash
mkdir -p ~/.gemini/config/plugins/orca
echo '{"name":"orca"}' > ~/.gemini/config/plugins/orca/plugin.json
# then symlink or copy <orca-clone>/skills into ~/.gemini/config/plugins/orca/skills
```

Then register it in `~/.gemini/config/config.json` under the top-level `plugins` key:

```json
{ "plugins": { "orca": { "enabled": true } } }
```

**Caveat — verify, don't assume**: whether this `config.json` registration step is strictly
required, or whether directory placement + `plugin.json` alone is sufficient, has **not been
confirmed** — a plugin was observed present on disk with a valid `plugin.json` but no
corresponding `config.json` entry, and whether it is actually active was not checked live.
Register it anyway (it is the pattern every confirmed-working plugin follows) and confirm
with the user by restarting Antigravity and checking whether `orca-cli`/`orchestration` (or
whichever Orca skills were copied in) actually appear in the next session's available-skills
list — don't report the install as complete on file placement alone.

## Step 3 — Report, don't assume

After any install, report what was actually verified (config file written, harness's own
`list`/`inspect` command output) rather than declaring success from the copy/link step alone.
A harness's plugin loader can silently skip a malformed manifest.
