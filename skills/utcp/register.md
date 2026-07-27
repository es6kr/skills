# UTCP Manual Registration

Selectively registers manual_call_templates from `./.utcp_config.json`.

## When to Use

- To initialize UTCP tools after starting a new session
- When `list_tools` returns an empty array
- On requests like "register manual" or "register utcp"

## Prerequisites

1. `manual_call_templates` is defined in `./.utcp_config.json` or `~/.utcp_config.json`
2. Each template includes `"transport": "stdio"`
3. If using environment variables, `./.env` or `~/.utcp.env` is prepared

## File Priority

| Priority | Config File | Environment Variable File |
|----------|-----------|---------------|
| 1 (default) | `./.utcp_config.json` | `./.env` |
| 2 (fallback) | `~/.utcp_config.json` | `~/.utcp.env` |

## Instructions

### Step 1: Check the config file

Check the project config first, then the global one:

```bash
cat ./.utcp_config.json 2>/dev/null || cat ~/.utcp_config.json
```

### Step 2: Select registration targets

Select which manuals to register via AskUserQuestion (multiSelect: true):

**Option composition:**
1. **Register all** - Bulk-register all manual_call_templates
2. **1-3 recommendations** - Recommend manuals matching the current work context
   - If the project has `.mcp.json`, recommend manuals related to that server
   - If working on a DB task, recommend postgres/mysql manuals
   - If working on API integration, recommend openrouter/notion, etc.

**Recommendation logic examples:**
- `disp` project → recommend `disp_postgres`, `disp_redmine_postgres`
- `yd` project → recommend `yd_redmine_mysql`
- AI/LLM work → recommend `openrouter`

### Step 3: Register the selected manuals

Register each template via `register_manual`:

```typescript
mcp__code-mode__register_manual({
  manual_call_template: {
    name: "template_name",
    call_template_type: "mcp",
    config: {
      mcpServers: {
        "server-name": {
          transport: "stdio",
          command: "uvx",
          args: ["package-name"],
          env: {
            VAR_NAME: "inline-value"  // actual value instead of ${VAR}
          }
        }
      }
    }
  }
})
```

### Step 4: Confirm registration results

```typescript
mcp__code-mode__list_tools()
```

## AskUserQuestion Example

```json
{
  "question": "Select the UTCP manual(s) to register",
  "header": "UTCP Registration",
  "options": [
    {"label": "Register all (4)", "description": "Bulk-register all manual_call_templates"},
    {"label": "disp_postgres (recommended)", "description": "DISP PostgreSQL database"},
    {"label": "disp_redmine_postgres", "description": "DISP Redmine PostgreSQL"},
    {"label": "yd_redmine_mysql", "description": "YD Redmine MySQL"}
  ],
  "multiSelect": true
}
```

**When "Register all" is selected**: registers all manual_call_templates
**When selecting individually**: registers only the selected manuals

## Notes

| Issue | Cause | Solution |
|------|------|------|
| `Invalid CallTemplate` | Only a string was passed | Pass the full JSON object |
| `Variable not found` | .env not loaded | Use an inline value or restart MCP |
| `transport undefined` | transport missing | Add `"transport": "stdio"` |

## Example

### Successful registration

```
| Manual | Status | Tools |
|--------|--------|-------|
| disp_postgres | ✅ SUCCESS | 9 |
| disp_redmine_postgres | ✅ SUCCESS | 9 |
| yd_redmine_mysql | ✅ SUCCESS | 5 |
```

### Failure case

```
| Manual | Status | Reason |
|--------|--------|--------|
| openrouter | ❌ FAILED | API key missing |
```

## In-Memory Storage Caveat

When using `tool_repository: in_memory`:
- Registration info is lost on MCP restart
- Must re-register every session
- Persistent storage requires a custom implementation
