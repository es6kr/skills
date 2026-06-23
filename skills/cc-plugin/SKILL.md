---
metadata:
  author: es6kr
  version: "0.1.0"
name: cc-plugin
description: |
  Claude Code plugin lifecycle management.
  cache - clean old cache versions (cleanup only — NOT for cache miss diagnosis) [cache.md],
  clustering - skill affinity scoring (coupling/dep/hook-ownership) → plugin bundle membership [clustering.md],
  create - plugin authoring guide (structure, plugin.json, components) [create.md],
  dev-reflect - reflect local dev repo into marketplace clone for pre-push testing [dev-reflect.md],
  hud - OMC HUD statusline (omcHud elements, omcLabel, wrapper sed fallback) [hud.md],
  marketplace - clone/list/update marketplace repos [marketplace.md],
  troubleshoot - cache miss/error, install fail, cache sync, HUD diagnostics — ALL plugin errors route here [troubleshoot.md].
  "plugin", "marketplace", "plugin install", "plugin not installed",
  "cache miss", "cache error", "plugin error", "load error", "reload errors",
  "dev reflect", "plugin clustering", "bundle skills", "skill affinity",
  "OMC HUD", "omcHud", "omcLabel", "statusline", "[OMC#" triggers.
---

# Plugin

Claude Code plugin lifecycle management: create, install, update, cache, troubleshoot.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| cache | **Cleanup only** — clean old plugin cache versions and temp directories. **NOT for "cache miss" or load errors** — use troubleshoot instead | [cache.md](./cache.md) |
| clustering | Score skill-to-skill affinity (coupling / shared external dep / hook-ownership gate) and recommend plugin bundle membership. Feeds into `create` | [clustering.md](./clustering.md) |
| create | Plugin authoring guide (structure, plugin.json, components) | [create.md](./create.md) |
| dev-reflect | Reflect a local dev source repo's plugin/skill changes into the registered marketplace clone for local testing before commit/push (helper: `scripts/dev-reflect.sh`) | [dev-reflect.md](./dev-reflect.md) |
| hud | OMC HUD statusline configuration: omcHud elements, omcLabel toggle, wrapper sed fallback, version compatibility | [hud.md](./hud.md) |
| marketplace | Clone, list, and update marketplace repositories | [marketplace.md](./marketplace.md) |
| troubleshoot | **All plugin errors** — cache miss, load errors, `/reload-plugins` errors, `/doctor` failures, installation failures, cache sync, HUD diagnostics | [troubleshoot.md](./troubleshoot.md) |

## Routing rule (HARD STOP)

| User says | Topic |
|-----------|-------|
| "cache miss", "cache error", "load error", "reload errors", "plugin not loading", "plugin not installed" | **troubleshoot** (NOT cache) |
| "cache cleanup", "old versions", "disk space", "remove temp_git_*" | cache |

`cache.md` only owns deletion of stale versions. Any diagnostic of "why isn't this plugin working" — including the literal phrase "cache miss" — routes to `troubleshoot.md`.

## Paths

```
Marketplaces: ~/.claude/plugins/marketplaces/
Cache:        ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
```

