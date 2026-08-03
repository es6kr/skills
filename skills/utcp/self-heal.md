# UTCP Self-Heal

Automatically diagnoses and recovers from `register_manual` failures or code-mode errors.

## When to Use

- An error occurs when calling `register_manual`
- npx execution fails (`ERR_DLOPEN_FAILED`, `NODE_MODULE_VERSION`, etc.)
- The `code-mode` MCP tool list is empty
- On requests like "utcp not working", "code-mode error", or "self-heal"

## Error Pattern → Diagnosis → Recovery Flow

### Step 1: Collect the error message

Analyze the error message when `register_manual` fails:

```
Error message → pattern matching → recovery action
```

### Step 2: Automatic recovery by pattern

| Error Pattern | Cause | Recovery Action |
|---|---|---|
| `NODE_MODULE_VERSION N` | npx cache was compiled for a different Node version | Clear the npx cache |
| `ERR_DLOPEN_FAILED` | Native addon version mismatch | Clear the npx cache |
| `Variable 'xxx' not found` | Missing .env variable or namespace error | Validate .env |
| `Unsupported MCP transport: 'undefined'` | Missing transport field | Fix the config |
| `MCP error -32000: Connection closed` | Node.js version issue | Check the Node version |
| `Invalid CallTemplate` | Only a string was passed | Re-register with a JSON object |
| `spawn ENOENT` | command executable not found | Verify package installation |

---

## Procedure by Recovery Action

### [A] Clear the npx cache (NODE_MODULE_VERSION mismatch)

```bash
# 1. Find the cache hash directory
ls "C:\Users\DAEGUNSOFT\AppData\Local\npm-cache\_npx\" 2>/dev/null \
  || ls ~/.npm/_npx/ 2>/dev/null

# 2. Clear the @utcp/code-mode-mcp cache
# Windows:
rm -rf "C:\Users\DAEGUNSOFT\AppData\Local\npm-cache\_npx\<hash>"
# macOS/Linux:
rm -rf ~/.npm/_npx/<hash>

# 3. Re-run the test
npx @utcp/code-mode-mcp --help 2>&1 | head -5
```

**How to identify the cache hash:**
```bash
# Extract the path from the error message
# Error: The module '...\_npx\8ebdd428a714128c\...' → 8ebdd428a714128c is the hash
```

### [B] Validate .env variables (Variable not found)

```bash
# 1. Check the .env file locations
ls ./.env 2>/dev/null && echo "PROJECT .env found" || echo "not found"
ls ~/.utcp.env 2>/dev/null && echo "GLOBAL .env found" || echo "not found"
ls ~/.utcp.local.env 2>/dev/null && echo "LOCAL .env found" || echo "not found"
```

Extract the variable name from the error message and cross-check against SKILL.md's namespace rules:

```
Error: Variable 'GITHUB_PERSONAL_ACCESS_TOKEN' not found
manual name: github
required .env key: github_GITHUB_PERSONAL_ACCESS_TOKEN
```

```bash
# Check for the variable in .env
grep "github_GITHUB_PERSONAL_ACCESS_TOKEN" ~/.utcp.env ~/.utcp.local.env ./.env 2>/dev/null
```

### [C] Fix the config (missing transport)

```bash
# Find entries missing the transport field in the config file
cat ~/.utcp_config.json | python3 -c "
import json, sys
cfg = json.load(sys.stdin)
for t in cfg.get('manual_call_templates', []):
    for k, v in t.get('config', {}).get('mcpServers', {}).items():
        if 'transport' not in v:
            print(f'missing: {t[\"name\"]} > {k}')
"
```

Fix: add `"transport": "stdio"` to the affected mcpServer entry.

### [D] Check the Node.js version (Connection closed)

```bash
node --version
# v22.x recommended. Upgrade if below v18
```

---

## Full Automatic Diagnosis Flow

When `register_manual` fails, diagnose automatically in this order:

```
1. Match the error message pattern
   ├─ NODE_MODULE_VERSION / ERR_DLOPEN_FAILED → [A] clear the cache
   ├─ Variable not found → [B] validate .env
   ├─ transport undefined → [C] fix the config
   ├─ Connection closed → [D] check the Node version
   └─ other → report the raw error message + request manual check

2. Run the recovery action

3. Retry registration
   mcp__code-mode__register_manual(...)

4. Retry succeeds → report completion
   Retry fails → request manual intervention via AskUserQuestion
```

---

## Using Inline Values on Re-registration

If `Variable not found` errors persist, register with inline values instead of loading `.env`:

```typescript
// If .env loading fails → insert the value directly
mcp__code-mode__register_manual({
  manual_call_template: {
    name: "github",
    call_template_type: "mcp",
    config: {
      mcpServers: {
        "github": {
          transport: "stdio",
          command: "npx",
          args: ["-y", "@modelcontextprotocol/server-github"],
          env: {
            GITHUB_PERSONAL_ACCESS_TOKEN: "actual-value"  // instead of ${VAR}
          }
        }
      }
    }
  }
})
```

## After Recovery

On success, run Step 3 of [health-check.md](./health-check.md) to confirm the connection status.
