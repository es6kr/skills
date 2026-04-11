---
name: dotfile
description: Synchronization management with external tools. chezmoi - dotfile template management [chezmoi.md], knowledge - session knowledge → Serena memory [knowledge.md], mcp - MCP server synchronization [mcp.md], syncthing - chezmoi Syncthing sync and diagnostics [syncthing.md]. Use when "knowledge sync", "chezmoi add", "dotfile management", "syncthing", "MCP server add", "MCP sync", "external sync", "(?d)", ".stignore", "ignored files", "stignore settings", "sync incomplete", "sync status", "DB reset", "stale cache", "syncthing diagnostics", "index reset", "rescan". For ClawHub-related tasks → delegate to /clawhub skill.
depends-on: [chezmoi]
---

# Sync

Manages data synchronization with external tools (Serena, chezmoi, Syncthing, etc.).

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| chezmoi | dotfile chezmoi template management | [chezmoi.md](./chezmoi.md) |
| knowledge | Session knowledge → Serena memory sync | [knowledge.md](./knowledge.md) |
| mcp | MCP server sync (delegated to chezmoi) | [mcp.md](./mcp.md) |
| syncthing | chezmoi source Syncthing sync and diagnostics | [syncthing.md](./syncthing.md) |

## Quick Reference

### Knowledge Sync

```
"knowledge sync"        → Current project session → Serena memory
```

### Chezmoi

```
"chezmoi add"           → Add a dotfile to chezmoi
"dotfile management"    → chezmoi template operations
```

**Configurations managed by chezmoi:**
- `~/.utcp_config.json` - UTCP global config
- `~/.claude.json`, `~/.cursor/mcp.json` - MCP server config
- `~/Library/.../Syncthing/config.xml` - Syncthing default config

**MCP server sharing:**
- Single source: `.chezmoitemplates/mcp-servers.json`
- `chezmoi apply` → Automatically applied to all apps

### MCP

```
"MCP server add"        → Edit mcp-servers.json → chezmoi apply
"MCP sync"              → Apply MCP config to all apps
```

### Syncthing

```
"syncthing setup"       → chezmoi source sync configuration
".stignore"             → Ignore pattern configuration
"sync incomplete"       → Per-folder status/need item diagnostics
"DB reset"              → Stale index reset (delete index-v2)
```

**Auto-generated `.stignore`:**
- `.git`
- `(?d).DS_Store` — Prevents orphaned `.DS_Store` on remote deletion
- `*.bak`
