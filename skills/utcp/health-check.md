# UTCP Health Check

Tests the connection status and tool availability of registered manuals.

## When to Use

- When a DB connection issue is suspected
- When a tool call fails
- On requests like "utcp status" or "connection test"

## Instructions

### Step 1: Check registered tools

```typescript
mcp__code-mode__list_tools()
```

### Step 2: Classify tools by manual

Tool name pattern: `{manual_name}.{manual_name}_{tool_name}`

Examples:
- `disp_postgres.disp_postgres_execute_sql`
- `yd_redmine_mysql.yd_redmine_mysql_query`

### Step 3: Connection test

Run a simple query for each DB type:

**PostgreSQL**:
```typescript
mcp__code-mode__call_tool_chain({
  code: `
    const result = disp_postgres.disp_postgres_list_schemas();
    return result;
  `
})
```

**MySQL** (requires connect_db):
```typescript
mcp__code-mode__call_tool_chain({
  code: `
    yd_redmine_mysql.yd_redmine_mysql_connect_db({
      host: '<mysql-host>',
      user: 'redmine',
      password: '****',
      database: 'redmine'
    });
    const tables = yd_redmine_mysql.yd_redmine_mysql_list_tables();
    return tables;
  `
})
```

### Step 4: Report results

```markdown
## UTCP Health Check Results

| Manual | Status | Tool Count | Test |
|--------|------|---------|--------|
| disp_postgres | ✅ | 9 | list_schemas succeeded |
| disp_redmine_postgres | ✅ | 9 | list_schemas succeeded |
| yd_redmine_mysql | ✅ | 5 | list_tables succeeded |
| openrouter | ❌ | 0 | not registered |
```

## Common Issues

| Symptom | Cause | Solution |
|------|------|------|
| Empty tool list | Not registered | See register.md |
| Connection refused | DB server down | Check server status |
| Authentication failed | Invalid credentials | Check .env values |
| Database not set | MySQL connect_db not called | Run connect_db first |

## Tool Capabilities by Manual

### PostgreSQL (postgres-mcp)

| Tool | Purpose |
|------|------|
| list_schemas | List schemas |
| list_objects | List tables/views |
| execute_sql | Execute SQL |
| explain_query | Analyze query |
| analyze_db_health | Analyze DB health |

### MySQL (mcp-mysql-server)

| Tool | Purpose |
|------|------|
| connect_db | Connect (required first) |
| list_tables | List tables |
| describe_table | Describe table structure |
| query | SELECT query |
| execute | Execute DML |
