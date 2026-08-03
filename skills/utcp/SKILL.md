---
name: utcp
description: UTCP (code-mode MCP) integration management. validator - config validation [validator.md], register - bulk Manual registration [register.md], health-check - connection testing [health-check.md], list - registered tool lookup [list.md], secret-update - API key/token rotation and chezmoi sync [secret-update.md], self-heal - automatic error diagnosis/recovery [self-heal.md]. "utcp", "code-mode", "register_manual", "utcp error", "code-mode not working", "NODE_MODULE_VERSION", "API key rotation", "token update", "utcp token", "utcp register", "manual register", "MCP transport error", "manual registration failed", "utcp init" triggers
metadata:
  author: es6kr
  version: "0.1.0"
---

# UTCP Manager

Unified management skill for the UTCP (Universal Tool Calling Protocol) code-mode MCP server.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| validator | Config file validation and error correction | [validator.md](./validator.md) |
| register | Bulk Manual registration | [register.md](./register.md) |
| health-check | Connection status testing | [health-check.md](./health-check.md) |
| list | Registered tool lookup | [list.md](./list.md) |
| secret-update | API key/token rotation and chezmoi sync | [secret-update.md](./secret-update.md) |
| self-heal | Automatic error diagnosis and recovery | [self-heal.md](./self-heal.md) |

## Quick Reference

### Validator

Config file validation: detects missing transport, variable namespace errors, and dotenv path issues.

See [detailed guide](./validator.md).

### Register

Selectively registers manual_call_templates from `./.utcp_config.json`.

See [detailed guide](./register.md).

### Health Check

Checks the connection status and tool list of registered manuals.

See [detailed guide](./health-check.md).

### List

Looks up registered tools and config files. Select lookup targets via multi-select.

See [detailed guide](./list.md).

### Secret Update

Automatically syncs related files when rotating API keys/tokens:
- `~/.utcp.local.env`: secret tokens (not managed by chezmoi/syncthing) → edit this file only
- `~/.utcp.env`: chezmoi-managed file → also edit the `private_dot_utcp.env` source
- Includes curl-based API validity verification

See [detailed guide](./secret-update.md).

### Self-Heal

Automatically diagnoses and recovers from `register_manual` failures or npx errors:
- `NODE_MODULE_VERSION` mismatch → clear the npx cache
- `Variable not found` → validate the .env namespace
- `transport undefined` → automatically fix the config
- Automatically retries registration after recovery

See [detailed guide](./self-heal.md).

## File Locations

| File | Purpose | Priority |
|------|---------|----------|
| `./.utcp_config.json` | Per-project UTCP config (default) | 1 |
| `./.env` | Per-project environment variables (default) | 1 |
| `~/.utcp_config.json` | Global UTCP config (fallback) | 2 |
| `~/.utcp.env` | Global environment variables (fallback) | 2 |

**Default behavior**: Checks `.utcp_config.json` and `.env` in the project root first; if absent, falls back to the home directory.

## Environment Variable Namespace Rules

UTCP looks up variables in the `{manual_name}_{VAR_NAME}` format.

**Conversion rule**: `_` in the manual name is converted to `__`

| Manual name | config.json variable | .env variable name |
|-------------|------------------|-------------|
| `disp_postgres` | `${DISP_POSTGRES_URI}` | `disp__postgres_DISP_POSTGRES_URI` |
| `disp_redmine_postgres` | `${DISP_REDMINE_URI}` | `disp__redmine__postgres_DISP_REDMINE_URI` |
| `yd_redmine_mysql` | `${YD_REDMINE_URI}` | `yd__redmine__mysql_YD_REDMINE_URI` |
| `openrouter` | `${OPENROUTER_API_KEY}` | `openrouter_OPENROUTER_API_KEY` |
| `github` | `${GITHUB_PERSONAL_ACCESS_TOKEN}` | `github_GITHUB_PERSONAL_ACCESS_TOKEN` |
| `notion` | `${NOTION_TOKEN}` | `notion_NOTION_TOKEN` |
| `logseq` | `${LOGSEQ_API_TOKEN}` | `logseq_LOGSEQ_API_TOKEN` |
| `logseq` | `${LOGSEQ_API_URL}` | `logseq_LOGSEQ_API_URL` |

**Error pattern**: `Variable 'xxx' referenced in call template configuration not found`

## See Also

- Serena memory: `utcp-code-mode-troubleshooting`
