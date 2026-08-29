# Dev Reflect

Reflect a **local dev source repo**'s plugin/skill changes directly into the **registered Claude Code marketplace clone** (`~/.claude/plugins/marketplaces/<marketplace>/`) for local testing **before** commit/push.

## When to Use

- You develop a skill/plugin in a local source repo (e.g. `~/ghq/github.com/<org>/<repo>`) and want to test it in this Claude Code install before pushing to GitHub.
- The marketplace clone is normally synced from GitHub by Claude Code. This bypasses that round-trip for fast local iteration.
- A new skill/topic/hook is not detected because the clone (and `~/.claude/skills/`) does not yet contain it.

## Direction

```
dev source repo (SoT)                 registered marketplace clone (test target)
~/ghq/github.com/<org>/<repo>   ──►   ~/.claude/plugins/marketplaces/<marketplace>/
  .claude-plugin/marketplace.json       .claude-plugin/marketplace.json  (plugin entries upserted)
  skills/ agents/ commands/ hooks/      skills/ agents/ commands/ hooks/  (synced)
```

The source repo is the source of truth. The clone is a disposable test target — a later GitHub re-sync overwrites it.

## Precondition — the clone must not be the source repo itself (HARD STOP)

Some setups register the marketplace by **symlinking it at the source repo**:

```bash
$ ls -ld ~/.claude/plugins/marketplaces/<marketplace>
lrwxr-xr-x ... ~/.claude/plugins/marketplaces/<marketplace> -> ~/ghq/github.com/<org>/<repo>
```

When that holds, `--source` and the clone resolve to the **same repository**, and step 1's
`rsync -a --delete` overwrites the very checkout you develop in — removing every file the
checked-out branch has but `--source` does not. If that checkout sits on an unrelated feature
branch, this destroys its work.

Check before every run:

```bash
CLONE=$(cd ~/.claude/plugins/marketplaces/<marketplace> && pwd -P)
SRC=$(git -C <source> rev-parse --show-toplevel)
SRC_ROOT=$(git -C <source> rev-parse --path-format=absolute --git-common-dir | sed 's|/\.git$||')
[ "$CLONE" = "$SRC" ] || [ "$CLONE" = "$SRC_ROOT" ] && echo "SAME REPO — do not run dev-reflect"
```

A **git worktree of the same repo also counts as "same"**: its `--show-toplevel` differs from
the clone, so a naive comparison passes, yet the clone still points at the main checkout and
the `--delete` still lands on another branch's tree. Compare against the common git dir too,
as above.

**When they are the same, dev-reflect has nothing to do.** The plugin already loads from the
source repo, so the active hook/skill files are simply whatever the checked-out branch holds.
Land the change on that branch (merge the PR, or check the branch out) instead of copying.

Confirm which path is genuinely active from the plugin's own artifacts — e.g. a hook's debug-log
mtime — rather than assuming `plugins/cache/`. A cache copy can sit untouched for weeks while
the symlinked repo path is the one actually executing.

## Usage

```bash
node_or_bash="$HOME/.claude/skills/cc-plugin/scripts/dev-reflect.sh"
bash "$node_or_bash" \
  --source ~/ghq/github.com/<org>/<repo> \
  --marketplace <marketplace-name> \
  [--enable <plugin-name>] \
  [--dry-run]
```

| Flag | Meaning |
|------|---------|
| `--source` | Local dev repo (must have `.claude-plugin/marketplace.json`) |
| `--marketplace` | Clone name under `~/.claude/plugins/marketplaces/` (the registered marketplace name) |
| `--enable` | Optional. Enable `<plugin>@<marketplace>` in `settings.json` (backup written) |
| `--dry-run` | Print actions without writing |

Find the marketplace name: `jq -r '.name' ~/.claude/plugins/marketplaces/<dir>/.claude-plugin/marketplace.json`, or check `extraKnownMarketplaces` in `settings.json`.

## What It Does

1. **Sync component dirs** (`skills/ agents/ commands/ hooks/ plugins/`) source → clone (`rsync --delete` when available, else additive `cp -r`).
2. **Upsert** the source's `marketplace.json` plugin entries into the clone by name — clone-only entries are preserved, matching/new entries from source override/add.
3. **`chmod +x`** synced hook scripts.
4. **Optional enable** the plugin in `settings.json` (with `settings.json.bak-dev-reflect` backup).
5. **Print the 4-step plugin-activation verification + reload reminder.**

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Conclude "works" right after the clone is patched | Plugins load at session start. Restart / new session, then verify Skill-tool detection (step 4 stays "NEXT SESSION") |
| 2 | Treat the clone edit as durable | Clone edits are a test shortcut; a GitHub re-sync overwrites them. Commit/push the source repo to persist |
| 3 | Enable both the bundling plugin (`source: "./"`) and a sub-plugin that re-declares the same skill | Enable one. Two enabled plugins declaring the same skill name collide |
| 4 | Overwrite the clone's `marketplace.json` wholesale | Upsert by plugin name (the script does this) so a divergent clone keeps its own entries |
| 5 | Skip the backup when touching `settings.json` | `--enable` writes `settings.json.bak-dev-reflect` first; keep it until verified |
| 6 | Run dev-reflect when the marketplace entry is a symlink to the source repo | Resolve both paths first (see Precondition). Identical → the reflect is unnecessary *and* destructive: land the change on the checked-out branch instead |

## Verification (after reload)

1. **Skill detected** — the skill appears in the available-skills list, or `Skill("<name>")` resolves.
2. **SessionStart hooks** — guard/inject markers appear in the session's `additionalContext`.
3. **PreToolUse hooks** — the declared matcher fires on the target tool.

## Manual Fallback

If the script is unavailable, the same effect, done by hand:

```bash
SRC=~/ghq/github.com/<org>/<repo>
CLONE=~/.claude/plugins/marketplaces/<marketplace>
command cp -r "$SRC/skills/." "$CLONE/skills/"
RALPH=$(jq '.plugins[] | select(.name=="<plugin>")' "$SRC/.claude-plugin/marketplace.json")
jq --argjson r "$RALPH" '.plugins += [$r]' "$CLONE/.claude-plugin/marketplace.json" > /tmp/mp && command cp /tmp/mp "$CLONE/.claude-plugin/marketplace.json"
jq '.enabledPlugins["<plugin>@<marketplace>"] = true' ~/.claude/settings.json > /tmp/s && command cp /tmp/s ~/.claude/settings.json
```

## Relation to Other Topics

- `marketplace` — clone/list/update marketplace repos (GitHub → clone). dev-reflect is the reverse, local-only test path (dev repo → clone).
- `troubleshoot` — if a reflected plugin still does not load after reload (cache miss / load error), route there.
