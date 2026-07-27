# UTCP List - Registered Tool Lookup

Look up UTCP registration status and config files.

## Usage

```
/utcp list
```

## Procedure

### 1. Select lookup targets

Ask via AskUserQuestion (multiSelect: true):

```
Select the items to look up:
1. Registered tools (mcp__code-mode__list_tools)
2. Project config (./.utcp_config.json)
3. Global config (~/.utcp_config.json)
```

### 2. Look up based on selection

#### Registered tools

```typescript
mcp__code-mode__list_tools()
```

Result format:
- No tools: "No tools are registered."
- Tools present: display the tool list as a table

#### Project config (default)

From the current working directory:

```bash
cat ./.utcp_config.json
```

- File missing: "No project config file found."
- File present: display the manual_call_templates list

#### Global config

```bash
cat ~/.utcp_config.json
```

- File missing: "No global config file found."
- File present: display the manual_call_templates list

### 3. Summarize results

| Item | Status | Count |
|------|------|------|
| Registered tools | ✅/❌ | N |
| Project config | ✅/❌ | N manuals |
| Global config | ✅/❌ | N manuals |

## Output Example

### Registered tools table

| Tool Name | Description |
|--------|------|
| disp_postgres_query | Run a PostgreSQL query |
| notion_search | Notion search |

### Config file summary

**Project (./.utcp_config.json)**:
- `project_db`: stdio transport
- `local_api`: stdio transport

**Global (~/.utcp_config.json)**:
- `disp_postgres`: stdio transport
- `notion`: stdio transport
- `openrouter`: stdio transport

## File Priority

| Priority | Config File | Environment Variable File |
|----------|-----------|---------------|
| 1 (default) | `./.utcp_config.json` | `./.env` |
| 2 (fallback) | `~/.utcp_config.json` | `~/.utcp.env` |
