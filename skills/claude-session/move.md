# Session Move

Move specific sessions to another project directory and update internal `cwd` references.

Unlike `migrate` (bulk classify+move), `move` targets explicit session IDs.

## Quick Start

```bash
/session move <session_id> [session_id2 ...] <target_project_path>
```

## When to Use

- Project directory changed (repo moved, parent folder restructured)
- Sessions need to follow a `.ralph/` or config relocation
- Moving Ralph sessions from sub-repo to org-level project

## Workflow

### 1. Locate Session Files

```bash
find ~/.claude/projects -name "<session_id>.jsonl" 2>/dev/null
```

### 2. Identify Source and Target Projects

| Item | Example |
|------|---------|
| Source | `-Users-david-ghq-github-com-es6kr-claude-code-sessions` |
| Target | `-Users-david-ghq-github-com-es6kr` |

Target project directory is derived from the target path:
- `/Users/david/ghq/github.com/es6kr` → `-Users-david-ghq-github-com-es6kr`

### 3. Extract Current cwd Values

```bash
grep -o '"cwd":"[^"]*"' <session_file> | sort -u
```

### 4. Determine cwd Replacement

Replace the source project path with the target project path in all `cwd` values.

| Before | After |
|--------|-------|
| `"cwd":"/Users/david/ghq/.../claude-code-sessions"` | `"cwd":"/Users/david/ghq/.../es6kr"` |

**Preserve other cwd values** — only replace the exact source path. Sub-paths (e.g., `packages/web`) and unrelated paths remain unchanged.

### 5. Execute

```bash
# Create target project dir if needed
mkdir -p ~/.claude/projects/<target_project>

# Update cwd and move
sed -i '' 's|"cwd":"<old_path>"|"cwd":"<new_path>"|g' <session_file>
mv <session_file> ~/.claude/projects/<target_project>/

# Move subagent dir if exists
[ -d "<source>/<session_id>" ] && mv "<source>/<session_id>" "<target>/"
```

### 6. Verify

```bash
grep -o '"cwd":"[^"]*"' <target>/<session_id>.jsonl | sort -u
```

## Notes

- `sessions-index.json` is not updated — Claude Code rebuilds it automatically
- Session content and summaries remain functional after move
- Multiple session IDs can be processed in a single invocation
