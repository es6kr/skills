# Secret Update

Updates UTCP tokens/API keys and automatically syncs related files.

## When to Use

- When rotating a UTCP manual's API key/token
- After editing `~/.utcp.local.env` or `~/.utcp.env`, to sync the chezmoi source
- When API validity needs to be verified after a key rotation

## File Structure

| File | Role | chezmoi-managed |
|------|------|-------------|
| `~/.utcp.local.env` | Secret tokens (not synced by syncthing) | ❌ Not managed |
| `~/.utcp.env` | Non-sensitive environment variables | ✅ Managed |
| chezmoi source `private_dot_utcp.env` | Source for `.utcp.env` | ✅ Managed |

**Principle**: Secret tokens are kept in `~/.utcp.local.env`. No chezmoi/syncthing sync.

## Procedure

### Step 1: Determine which file holds the token

```bash
# Check the current token location
grep -n "<manual_name>" ~/.utcp.local.env ~/.utcp.env 2>/dev/null
```

- If found in `~/.utcp.local.env` → **Step 2A**
- If found in `~/.utcp.env` → **Step 2B** (also edit the chezmoi source)

### Step 2A: Update the token in local.env

No chezmoi source sync needed. Edit this file only:

```bash
# Edit ~/.utcp.local.env
# Replace old_token → new_token
# Keep the old key as a comment (previous/current format)
# old: old_token_value
# current: new_token_value
manual_name_TOKEN=new_token_value
```

### Step 2B: Update the token in utcp.env (includes chezmoi sync)

1. Edit `~/.utcp.env`
2. Apply the same edit to the chezmoi source:

```bash
# Find the chezmoi source path
chezmoi source-path ~/.utcp.env
# → ~/.local/share/chezmoi/private_dot_utcp.env
```

Edit both files identically.

### Step 3: Verify API validity

Verification method per manual:

**Notion**:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer <new_token>" \
  -H "Notion-Version: <notion-api-version>" \
  https://api.notion.com/v1/users/me
# 200 means success
```

**GitHub**:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: token <new_token>" \
  https://api.github.com/user
# 200 means success
```

**OpenRouter**:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer <new_token>" \
  https://openrouter.ai/api/v1/models
# 200 means success
```

### Step 4: Report results

```markdown
## Token Update Complete

| Item | Result |
|------|------|
| manual | notion |
| File | ~/.utcp.local.env |
| chezmoi sync | not needed (local.env) |
| API validation | ✅ 200 OK |
```

## Notes

- Keep the previous key as a comment (previous/current format)
- If the token lives in `~/.utcp.env`, the chezmoi source must always be synced too
- `~/.utcp.local.env` is not covered by chezmoi/syncthing → must be configured separately on other machines

## See Also

- How to move a token to local.env: see this session
- UTCP environment variable namespace rules: see SKILL.md
