# UTCP Config Validator

Validates the UTCP config file and automatically detects common errors.

## When to Use

- An error occurs when calling `register_manual`
- `code-mode` MCP connection fails
- On requests like "validate utcp", "utcp config", or "utcp settings"

## File Priority

| Priority | Config File | Environment Variable File |
|----------|-----------|---------------|
| 1 (default) | `./.utcp_config.json` | `./.env` |
| 2 (fallback) | `~/.utcp_config.json` | `~/.utcp.env` |

## Validation Items

| Item | File | Error Type |
|------|------|----------|
| transport field | `.utcp_config.json` | Missing `"transport": "stdio"` on an MCP server |
| Variable namespace | `.env` / `~/.utcp.env` | `${VAR}` → `{manual_name}_{VAR}` format mismatch |
| dotenv path | `.utcp_config.json` | Whether the `env_file_path` file exists |
| JSON syntax | `.utcp_config.json` | Invalid JSON |

## Instructions

### Step 1: Read the config file

Check the project config first, then the global one:

```bash
cat ./.utcp_config.json 2>/dev/null || cat ~/.utcp_config.json
cat ./.env 2>/dev/null || cat ~/.utcp.env
```

### Step 2: Validate the transport field

Confirm every `mcpServers` entry has `"transport": "stdio"`:

```json
{
  "mcpServers": {
    "server-name": {
      "transport": "stdio",  // required!
      "command": "...",
      "args": [...]
    }
  }
}
```

**Error pattern**: `Unsupported MCP transport: 'undefined'`

### Step 3: Validate the environment variable namespace

See [SKILL.md's environment variable namespace rules](./SKILL.md#environment-variable-namespace-rules).

### Step 4: Report the validation results

```markdown
## UTCP Config Validation Results

### Config file locations
- Config: `./.utcp_config.json` (project)
- Environment variables: `./.env` (project)

### .utcp_config.json
- [x] Valid JSON syntax
- [ ] Missing transport: `disp-postgres` server

### .env
- [x] File exists
- [ ] Missing variable: `disp__postgres_DISP_POSTGRES_URI`

### Suggested fixes
1. Add `"transport": "stdio"` at Line 15 of .utcp_config.json
2. Add the following variable to .env:
   ```
   disp__postgres_DISP_POSTGRES_URI=postgresql://...
   ```
```

## Related Error Messages

| Error | Solution |
|------|------|
| `Unsupported MCP transport: 'undefined'` | Add the transport field |
| `Variable 'xxx' not found` | Check the .env variable name |
| `MCP error -32000: Connection closed` | Node.js 22.x LTS recommended |
