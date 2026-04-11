---
name: mcp-config
description: |
  MCP server configuration (.mcp.json) management. add - add server (scope selection + registration) [add.md], move - change server scope (project→local, local→user) [move.md], format - JSON format reference (differences per agent) [format.md], catalog - list of commonly used servers [catalog.md].
  Use when: "add MCP", "mcp-config", "MCP server config", "add context7", "MCP format", "MCP server list", "move MCP", "MCP scope", "scope change".
---

# MCP Server Configuration

Correctly add and manage MCP servers in the `.mcp.json` file.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| add | Add server (scope selection + registration + validation) | [add.md](./add.md) |
| move | Change server scope (project→local, local→user) | [move.md](./move.md) |
| catalog | Catalog of commonly used MCP servers | [catalog.md](./catalog.md) |
| format | JSON format reference (differences per agent) | [format.md](./format.md) |

## Quick Reference

```
"add MCP"         → add topic (scope selection → registration)
"add context7"    → add topic + refer to catalog for config
"move MCP"        → move topic (scope change: remove + re-add)
"MCP format"      → format topic (JSON differences per agent)
"MCP server list" → catalog topic
```

## Core Rules

- **New MCP server = register as a separate key** (do not put inside an existing server's `env`)
- **Scope selection AskUserQuestion required** (global vs project, agent selection)
- **Antigravity requires `transport: "stdio"`**
