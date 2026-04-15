# MCP Server Connection Diagnostics

Diagnose and resolve MCP server connection issues.

## Diagnostic Steps

### 1. Quick Status Check (Start Here)

```bash
# List all MCP servers and their connection status
claude mcp list
```

If the server appears as **Disconnected** or is missing entirely, proceed to Step 2.

### 2. Verify Configuration Files (Check ALL in order)

| Priority | File | Description |
|----------|------|-------------|
| 1 | `~/.claude.json` | **Claude Code global MCP config** (mcpServers section) |
| 2 | `~/.claude/settings.json` | Claude Code settings mcpServers |
| 3 | `~/.claude/settings.local.json` | Local overrides |
| 4 | `.mcp.json` (project root) | Project-level MCP config |
| 5 | `~/.config/claude/mcp.json` | User-level (legacy) |
| 6 | `~/.utcp_config.json` | UTCP-specific config |
| 7 | Plugin cache (`~/.claude/plugins/cache/`) | MCP servers provided by plugins |

**Always check `~/.claude.json` first** — this is the primary file where Claude Code stores MCP server configurations.

### 3. Common Errors and Solutions

#### "Connection closed" / "MCP error -32000"

**Cause**: Server process exits immediately after starting.

**Check**:
- Command path is correct (`which npx`, `which node`)
- Environment variables are set
- Native module build failures

#### "Failed to reconnect to [server-name]"

**Cause**: Previously connected server is no longer responding.

**Resolution**:
1. Check server status with `/mcp` command
2. Restart server or verify configuration

#### UTCP code-mode Specific Issues

**isolated-vm build failure**:
- Node.js version compatibility (LTS 22.x recommended)
- No prebuilt binaries for arm64 macOS
- Fix: `asdf local nodejs 22.14.0` then reinstall

**Empty config file**:
- If `~/.utcp_config.json` is `{}`, initialization failed
- Minimum required config:
```json
{
  "load_variables_from": [],
  "manual_call_templates": [],
  "tool_repository": {
    "tool_repository_type": "in_memory"
  },
  "tool_search_strategy": {
    "tool_search_strategy_type": "tag_and_description_word_match"
  },
  "post_processing": []
}
```

### 4. Check Logs

```bash
# Latest MCP debug logs (UUID-based filenames)
ls -lt ~/.claude/debug/ | head -5

# Read a specific log
cat ~/.claude/debug/<uuid>.txt
```

### 5. Manual Server Test

Run the server command directly outside Claude Code to see raw errors:

```bash
# npx-based server
npx -y @utcp/code-mode-mcp

# npx with environment variables
UTCP_CONFIG_FILE=~/.utcp_config.json npx -y @utcp/code-mode-mcp

# uvx-based server (e.g., serena, postgres)
uvx --from "git+https://github.com/oraios/serena" serena start-mcp-server --context claude-code
```

**Key**: Copy the exact `command` + `args` from `~/.claude.json` and run it in your terminal. The error output will reveal the root cause (missing dependency, wrong argument, auth failure, etc.).
