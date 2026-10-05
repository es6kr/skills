# Plugin Troubleshooting

Diagnose and fix plugin installation failures, cache sync issues, and HUD errors.

## Common Issues

### "Plugin not installed" / HUD Error

**Cause**: Cache directory missing or incomplete.

**Diagnosis**:

```bash
# Check marketplace exists (plugin lives under marketplaces/<marketplace>/plugins/<plugin-name>/)
ls ~/.claude/plugins/marketplaces/<marketplace>/plugins/<plugin-name>/

# Check cache exists
ls ~/.claude/plugins/cache/<marketplace>/<plugin-name>/

# Check for built dist (required for HUD plugins)
ls ~/.claude/plugins/cache/<marketplace>/<plugin-name>/<version>/dist/hud/index.js
```

**Fix — Sync marketplace to cache**:

```bash
MARKET=~/.claude/plugins/marketplaces/<marketplace>/plugins/<plugin-name>
CACHE=~/.claude/plugins/cache/<marketplace>/<plugin-name>/<version>

mkdir -p "$CACHE"

# Copy essential directories
for item in .claude-plugin .mcp.json agents CLAUDE.md dist hooks scripts skills; do
  [ -e "$MARKET/$item" ] && cp -r "$MARKET/$item" "$CACHE/"
done
```

After syncing: **restart Claude Code** (cache loads at session start).

### Plugin recognized but skills/commands not loading

**Cause**: `.claude-plugin/plugin.json` missing from cache.

```bash
cp -r ~/.claude/plugins/marketplaces/<marketplace>/plugins/<name>/.claude-plugin \
      ~/.claude/plugins/cache/<marketplace>/<name>/<version>/
```

### "Plugin X has conflicting manifests" — load error

**Symptom** (shown by `/plugin`, `/reload-plugins`, or `/doctor`):

```
Plugin <name> has conflicting manifests: both plugin.json and marketplace entry
specify components. Set strict: true in marketplace entry or remove component
specs from one location
```

**Cause**: The plugin's marketplace.json entry lists explicit component paths
(`skills`, `hooks`, `commands`, `agents`) while its `source` directory *also*
auto-discovers components — e.g. `source: "./"` whose root holds a `skills/`
directory. With the default `strict: false`, the explicit paths and the
auto-discovered components are two competing manifests.

**Diagnosis**:

```bash
MP=~/.claude/plugins/marketplaces/<marketplace>/.claude-plugin/marketplace.json
# 1. Does the entry specify component paths?
grep -nE '"(skills|hooks|commands|agents)"' "$MP"
# 2. Does the source root auto-discover components? (source: "./" + a skills/ dir, etc.)
ls ~/.claude/plugins/marketplaces/<marketplace>/{skills,hooks,commands,agents} 2>/dev/null
```

**Fix — set `strict: true` on the entry** (makes the entry authoritative; only its
listed components load):

```jsonc
{
  "name": "<plugin>",
  "source": "./",
  "skills": ["./skills/<one>"],
  "strict": true        // ← was false / absent
}
```

| # | Don't | Do |
|---|-------|-----|
| 1 | "Fix" it by removing the entry's `skills`/`hooks` paths | Removing them re-broadens the plugin to the whole auto-discovered collection (e.g. the entire `skills/`). Set `strict: true` to keep the narrowed set |
| 2 | Edit only the cache marketplace.json | Edit **both** the cache (loaded copy) and the source repo's marketplace.json (canonical) — otherwise the next sync reverts it (see [dev-reflect.md](./dev-reflect.md)) |

After editing run `/reload-plugins` (or restart) — the `conflicting manifests` line
disappears and the entry's hooks/skills load. Authoring rule + example:
[create.md](./create.md) "Marketplace entry: narrowing components with `strict`".

### Plugin HUD load failed — "npm install && npm run build"

**Cause**: `dist/` not built. Plugin has TypeScript source that needs compilation.

```bash
cd ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>
npm install && npm run build
```

### MCP servers not connecting after plugin install

**Cause**: `.mcp.json` not in cache.

```bash
cp ~/.claude/plugins/marketplaces/<marketplace>/plugins/<name>/.mcp.json \
   ~/.claude/plugins/cache/<marketplace>/<name>/<version>/
```

### Update succeeds but leaves orphaned `temp_git_*` directories (WSL and other slower-I/O hosts)

**Symptom**: `claude plugin marketplace update` or `claude plugin update <plugin>` reports success
(the new version downloads/clones fine), but a `temp_git_*` directory is left sitting at the top
level of `~/.claude/plugins/cache/` (a sibling of the normal `<marketplace>` directories, not
nested inside one) instead of being swapped into place as `<marketplace>`.

**Diagnosis**:

```bash
find ~/.claude/plugins/cache -maxdepth 1 -iname "temp_git_*"
```

Any hits mean a previous update's clone-then-swap step did not complete — the new version was
staged into a `temp_git_*` scratch directory, but deleting the old cache directory to make room
for it failed partway through.

**Root cause**: the swap itself happens inside the closed-source `claude` CLI binary, so it cannot
be diagnosed or patched from a plugin. It has been reported more often on WSL2 than on native
Linux/macOS; plausible contributors include WSL2's ext4-on-VHDX I/O being slower/burstier than a
native filesystem, and multiple concurrent Claude Code sessions holding the same plugin's files
open while an update tries to replace them. **Ruled out**: a cross-filesystem (`EXDEV`) rename
between a `/tmp` staging area and `~/.claude/plugins/cache` — on a single-mount WSL install both
paths resolve to the same `ext4` device (`df -T /tmp ~/.claude/plugins/cache`), so there is no
filesystem boundary to blame there. Treat this as an upstream timing issue to work around, not a
cc-plugin bug to fix at the source.

**Fix / mitigation**:

1. The `cc-plugin` plugin's own `SessionStart` hook (`resources/cache-cleanup.sh`) already deletes
   stale `temp_git_*` directories (and superseded version directories) on every session start —
   this clears the debris but does not fix the swap itself.
2. If you notice the symptom mid-session, re-run the update (`claude plugin marketplace update` /
   `claude plugin update <plugin>`) after the next session start — the retry usually succeeds once
   the stale directory is out of the way.
3. If it recurs on the same plugin repeatedly, close other Claude Code sessions/windows before
   updating (a session holding the plugin loaded is one plausible contributor), and run
   `claude doctor` to rule out an unrelated installation issue.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat the SessionStart sweep's silence as proof the problem is gone for good | The sweep hides the *debris*, not the *cause*. If `temp_git_*` keeps reappearing across sessions, that recurrence is worth reporting, not routine noise — `cache-cleanup.sh` prints a warning line with a count when it finds one, specifically so this doesn't go unnoticed |
| 2 | Assume the swap failure is an `EXDEV` cross-filesystem rename issue by default | Check first: `df -T` the staging path and the cache path. On a single-mount WSL install (one `ext4` root) there is no filesystem boundary to blame |
| 3 | Try to find the exact bug by disassembling the compiled `claude` binary | It is a closed, compiled (bun/Node SEA) binary — not practical to patch or reliably reverse-engineer from a plugin. Treat it as a black box; work around it from the plugin side only |

#### Violation case (2026-10-03)

User reported "cache download succeeds, but deleting the existing cache fails, leaving only the
temp folder" on WSL. No `temp_git_*` directories were present at diagnosis time (the SessionStart
cleanup had already swept them), `claude plugin marketplace update` / `claude plugin update` both
ran clean when retried, and `claude doctor` reported no issues — the live environment could not
reproduce the failure on demand. This section exists so the next occurrence has a ready diagnosis
command and explanation instead of restarting investigation from zero, and so the cleanup hook's
silent success is never mistaken for "this never happens."

### Symlink-Based Dual-Environment Setup — `known_marketplaces.json` Corruption

**Symptom**:

```text
Failed to refresh marketplace 'claude-plugins-official': Marketplace 'claude-plugins-official' has a
corrupted installLocation (C:\Users\<USER>\.claude\plugins\marketplaces\claude-plugins-official)
— expected a path inside /home/<user>/.claude/plugins/marketplaces.
This can happen after cross-platform path writes or manual edits to known_marketplaces.json.
Run: claude plugin marketplace remove "<name>" and re-add it.
```

Also presents as `Plugin "<name>" not found in marketplace "<marketplace>"` even when the plugin
clearly exists in the marketplace's `marketplace.json`.

**Root Cause**:

When `/home/<user>/.claude` is a **symlink to Windows `~/.claude`** (or any other dual-platform
mount), both environments share the same `known_marketplaces.json` file. Claude Code writes the
running environment's path into `installLocation`, but the other environment reads the same field
and rejects the foreign path.

This is **not** a "missing plugin" error — it is a `known_marketplaces.json` lookup failure that
masks itself as a downstream plugin-not-found error. Cache directory + manifest entry can be intact
yet the marketplace fails to resolve.

| Layer | What appears | What's actually true |
|-------|--------------|---------------------|
| `settings.json` `enabledPlugins: true` | Plugin is enabled | ✅ Enabled, but reference is bound to a broken marketplace name |
| `marketplaces/<name>/.claude-plugin/marketplace.json` plugin entry | Plugin listed | ✅ Listed correctly |
| `cache/<name>/<plugin>/<ver>/` directory | Cache exists | ✅ Cache is valid |
| `known_marketplaces.json` `installLocation` | Path string present | ❌ Path is for the **other** environment — Claude Code rejects it |

**Diagnosis**:

```bash
# 1. Check filesystem topology
readlink ~/.claude              # is it a symlink?
ls -la ~/.claude | head -3      # confirm symlink target

# 2. Read installLocation from BOTH environments
cat ~/.claude/plugins/known_marketplaces.json | grep installLocation

# 3. Compare: does the path match the current environment?
#    Windows session expects:  "C:\\Users\\<USER>\\.claude\\plugins\\marketplaces\\<name>"
#    WSL/Linux session expects: "/home/<user>/.claude/plugins/marketplaces/<name>"
```

If the file shows only one environment's path, the **other** environment will hit corruption errors.

**Fix — Separate marketplace names per environment (recommended for symlink setups)**:

Register the same marketplace twice in `known_marketplaces.json` under different names, each with
its environment's `installLocation`. Mirror the corresponding `enabledPlugins` entries.

```json
// ~/.claude/plugins/known_marketplaces.json
{
  "claude-plugins-official": {
    "source": { "source": "github", "repo": "anthropics/claude-plugins-official" },
    "installLocation": "C:\\Users\\<USER>\\.claude\\plugins\\marketplaces\\claude-plugins-official",
    "lastUpdated": "<ISO timestamp>"
  },
  "claude-plugins-official-wsl": {
    "source": { "source": "github", "repo": "anthropics/claude-plugins-official" },
    "installLocation": "/home/<user>/.claude/plugins/marketplaces/claude-plugins-official",
    "lastUpdated": "<ISO timestamp>"
  }
}
```

```json
// ~/.claude/settings.json — mirror enabledPlugins per marketplace name
"enabledPlugins": {
  "superpowers@claude-plugins-official": true,
  "superpowers@claude-plugins-official-wsl": true,
  // ... repeat for every plugin you want active in both environments
}
```

Marketplace directory under `marketplaces/<name>/` is shared via the symlink — only the
`known_marketplaces.json` entry name and `installLocation` differ. Cache directories may diverge
(`cache/claude-plugins-official/<plugin>/<ver>/` vs `cache/claude-plugins-official-wsl/<plugin>/<ver>/`)
because Claude Code keys cache by marketplace name. If the second cache is missing, restart Claude
Code in that environment so it can hydrate.

**Naming suggestions**:

- `<name>` + `<name>-wsl` (keeps the existing name as "primary" for one OS)
- `<name>-win` + `<name>-wsl` (symmetric explicit naming)
- `<name>-<hostname>` (multi-machine setups beyond Windows/WSL)

**Alternative — `claude plugin marketplace remove` + re-add**:

Works if you only ever use one environment. The error message itself suggests this. Drawback:
running it in environment A re-registers `installLocation` for A only, so environment B will hit
the same corruption again at the next invocation. Not a fix for symlink setups.

**Don't / Do**:

| # | Don't | Do |
|---|-------|-----|
| 1 | Edit `installLocation` to match the current environment only — the other environment will break next session | Register both environments under different marketplace names |
| 2 | Symlink or hard-link `known_marketplaces.json` alone while keeping the rest of `~/.claude/` shared | Either split the entire `~/.claude/` per environment or keep both entries in the single shared file |
| 3 | Assume `enabledPlugins: true` + cache existence = plugin works (indirect evidence) | Verify with an actual `Skill` tool call or `/plugin marketplace refresh <name>` — runtime invocation is the primary source |
| 4 | Trust a `grep '"name": "<plugin>"'` zero-match without trying broader patterns first (quote-escape pitfalls) | Use simpler `grep "<plugin>"` first to confirm the term exists anywhere, then narrow down |
| 5 | Conclude "plugin removed from marketplace" without reading the manifest line that actually contains the plugin | Read the `marketplace.json` section around the matching line to confirm entry shape (e.g., `source: "url"` external plugins) |

**Why naive fixes recur (failed-attempts.md "asserting without searching" pattern, 9th variant)**:

- `enabledPlugins: true` (settings flag) — represents intent, not runtime resolution
- `cache/<name>/<plugin>/<ver>/` (filesystem) — represents past download success, not current lookup validity
- SessionStart hook injecting a `<plugin>:using-<plugin>` skill — represents a one-time content load, not Skill-tool runtime invocability

These are **all indirect evidence**. The primary source is the actual Skill/CLI invocation result.
When facing a "plugin not found" error, do not assume layered evidence proves runtime health — call
the tool and read what happens.

### Primary source order (HARD STOP — diagnostic entry point)

When the user reports any plugin failure, **stop before running any diagnostic and pick the
primary source in this order**:

| Order | Source | How to read |
|-------|--------|-------------|
| 1 | The user's quoted error message | Quote the exact string back to the user — do not paraphrase |
| 2 | `/reload-plugins` output ("N errors during load") | Already in conversation if the user invoked it; do not require re-run |
| 3 | `/doctor` output | Run if no error log is visible; report each error verbatim |
| 4 | Plugin runtime invocation result | Try the failing `Skill("X")` or `/<command>` and read the error |
| 5 | `settings.json` `enabledPlugins` flag | Only proves intent, never proves runtime health |
| 6 | `~/.claude/plugins/cache/<name>/<plugin>/<ver>/` directory existence | Only proves a past download, never proves current lookup validity |

| # | Don't | Do |
|---|-------|-----|
| 1 | Iterate `enabledPlugins` × `cache/` directory existence and report "cache miss: 0 cases" | Re-read the user's quoted error + `/reload-plugins` "N errors" lines first. Filesystem checks come AFTER the primary source confirms which plugin is failing |
| 2 | Ignore "4 errors during load" already visible in the conversation | Treat any visible error count > 0 as the entry point — even if filesystem looks healthy, those errors are the actual failure |
| 3 | Conclude "no problem found" while the user still sees the symptom | If the user's symptom contradicts your finding, the finding is wrong. Run `/doctor` or reproduce the failing invocation before any conclusion |

### Violation case (2026-05-28)

User ran `/cc-plugin cache miss` after `/reload-plugins` reported `4 errors during load`. Assistant
iterated `settings.json` `enabledPlugins` against `cache/` directories, found all 7 cache
directories existed, and reported "zero cache misses" — without ever opening `/doctor`, without
re-reading the visible "4 errors during load" line, and despite this very file's table #3 listing
that exact mistake as the 9th variant of "asserting without searching". The user pointed it out
with: "the cache miss error hasn't gone away — what evidence did you use to assert otherwise?" (1st recurrence).

Recurrence after this rule → escalate to a `PreToolUse:Skill` hook that blocks `cc-plugin cache`
invocation when `/reload-plugins` or `/doctor` output in the recent conversation shows non-zero
errors, forcing routing to `troubleshoot.md`.

## Cache Structure Reference

```text
~/.claude/plugins/
├── marketplaces/          # Git clones (source of truth)
│   └── <name>/
│       ├── .claude-plugin/plugin.json
│       ├── skills/
│       └── ...
└── cache/                 # Runtime copies (loaded at session start)
    └── <marketplace>/
        └── <plugin>/
            └── <version>/
                ├── .claude-plugin/
                ├── .mcp.json
                ├── agents/
                ├── dist/
                ├── hooks/
                ├── scripts/
                └── skills/
```

## Key Rules

- **Marketplace = source of truth**, cache = runtime copy
- Cache loads at **session start** — changes need restart
- Missing files in cache → copy from marketplace
- `dist/hud/index.js` required for HUD plugins
- `temp_git_*` directories in cache are safe to delete — recurring appearance is a signal of a
  failed update swap, not routine noise (see "Update succeeds but leaves orphaned `temp_git_*`
  directories" above)
