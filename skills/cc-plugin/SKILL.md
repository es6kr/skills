---
metadata:
  author: es6kr
  version: "0.1.0"
name: cc-plugin
description: >-
  Claude Code plugin lifecycle management.
  cache - clean old plugin cache versions [cache.md],
  create - plugin authoring guide (structure, plugin.json, components) [create.md],
  hud - OMC HUD statusline configuration (omcHud elements, omcLabel toggle, wrapper sed fallback) [hud.md],
  marketplace - clone/list/update marketplace repos [marketplace.md],
  troubleshoot - installation failures, cache sync, HUD diagnostics [troubleshoot.md].
  "plugin", "marketplace", "plugin cache", "plugin install", "plugin not installed",
  "marketplace clone", "marketplace update", "plugin troubleshoot",
  "HUD error", "OMC HUD", "omcHud", "omcLabel", "statusline", "[OMC#" triggers.
---

# Plugin

Claude Code plugin lifecycle management: create, install, update, cache, troubleshoot.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| cache | Clean old plugin cache versions and temp directories | [cache.md](./cache.md) |
| create | Plugin authoring guide (structure, plugin.json, components) | [create.md](./create.md) |
| hud | OMC HUD statusline configuration: omcHud elements, omcLabel toggle, wrapper sed fallback, version compatibility | [hud.md](./hud.md) |
| marketplace | Clone, list, and update marketplace repositories | [marketplace.md](./marketplace.md) |
| troubleshoot | Installation failures, cache sync, HUD diagnostics | [troubleshoot.md](./troubleshoot.md) |

## Paths

```
Marketplaces: ~/.claude/plugins/marketplaces/
Cache:        ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
```
