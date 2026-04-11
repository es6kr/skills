# Add MCP Server

Procedure for registering a new MCP server.

## CRITICAL: Claude Code uses `claude mcp add` CLI

**Do NOT manually edit `.mcp.json` for Claude Code.** Manually adding entries to `.mcp.json` does NOT make Claude Code recognize the server. Always use the `claude mcp add` CLI command.

```bash
# stdio server (project scope)
claude mcp add --scope project my-server -- npx my-mcp-server

# HTTP server (project scope)
claude mcp add --transport http --scope project my-server https://example.com/mcp

# stdio server with env vars
claude mcp add --scope project -e API_KEY=xxx my-server -- npx my-mcp-server
```

**Name restriction**: Only letters, numbers, hyphens, underscores. No spaces.

## Required Procedure: Scope Selection (AskUserQuestion Required)

**Before adding an MCP server, always use AskUserQuestion in 2 steps:**

### Step 1: Scope Selection

| Option | Description |
|--------|-------------|
| Global | Add to each agent's config file (proceed to step 2) |
| Project | Add only to the current project |

### Step 2: When Global is selected → Agent Selection (multiSelect)

| Agent | Method | Difference |
|-------|--------|------------|
| Claude Code | `claude mcp add --scope user` | CLI required, manual `.mcp.json` edit NOT recognized |
| Cursor | Edit `~/.cursor/mcp.json` | `transport` field not required |
| Antigravity | Edit `~/.gemini/antigravity/mcp_config.json` | `"transport": "stdio"` required |

**multiSelect: true** — can add to multiple agents simultaneously.

**Do not decide arbitrarily.** Even if `.mcp.json` exists in the project directory, the user may want to add globally, and vice versa.

### Claude Code Scope Options

| Scope | Flag | Config File | Key Path | Description |
|-------|------|-------------|----------|-------------|
| local | `--scope local` (default) | `~/.claude.json` | `projects["/path/to/project"].mcpServers` | This machine, this project only |
| user | `--scope user` | `~/.claude.json` | root `mcpServers` | This machine, all projects |
| project | `--scope project` | `./.mcp.json` | `mcpServers` | Committed to repo, shared with team |

## Core Rule: Register as Separate Server

New MCP server = register as a separate key. **Do not put it inside an existing server's `env`.**

## Validation Checklist

- [ ] Claude Code: used `claude mcp add` CLI (NOT manual `.mcp.json` edit)
- [ ] Cursor/Antigravity: JSON syntax is valid
- [ ] Each server is registered as a separate key
- [ ] Server name contains only letters, numbers, hyphens, underscores
- [ ] `claude mcp list` shows the server as Connected
