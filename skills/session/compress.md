# Compress (Session Compression)

Compresses sessions to reduce file size. Removes duplicate snapshots, truncates long tool outputs, and more.

## Workflow

### 1. Check MCP Tool Availability

Check whether the `mcp__claude-sessions-mcp__compress_session` tool is directly available (`ToolSearch("select:mcp__claude-sessions-mcp__compress_session")` or an equivalent tool-list check).

- **Available**: Proceed to step 2
- **Not available**: Register `claude-sessions-mcp` in the project's MCP config (`.mcp.json` or `~/.claude/settings.json` `mcpServers`) per `mcp-config` skill conventions, then retry the availability check

### 2. Remove Profanity (Optional)

It is recommended to remove profanity from session files before compressing:

```bash
scripts/clean-profanity.py <session-file.jsonl>
```

See [profanity-cleaner.md](./profanity-cleaner.md) for details.

### 3. Determine Target Session

#### When session_id is provided
Compress only that session.

#### When session_id is not provided (batch compression)
Batch compress all sessions containing `"hookEvent":"Stop"` or `"type":"saved_hook_context"`:

1. **Confirm project path**: Generate project_name from current working directory (cwd)
   - Example: `/Users/<user>/works/.vscode` → `-Users-user-works--vscode`

2. **Find target sessions**: Search for session files containing hook-related messages
   ```bash
   grep -l -e '"hookEvent":"Stop"' -e '"type":"saved_hook_context"' ~/.claude/projects/<project_name>/*.jsonl
   ```

3. **Run compression on each session**: Compress found sessions sequentially

### 4. Backup (Required Before Compression)

Back up the original session file before compressing:

```bash
# Create backup directory
mkdir -p ~/.claude/projects/.bak

# Back up session file
cp ~/.claude/projects/<project_name>/<session_id>.jsonl ~/.claude/projects/.bak/<session_id>.jsonl
```

**Note**:
- Backup files are saved by session_id in the `.bak/` folder, regardless of project
- If a backup with the same session_id exists, it will be overwritten (only the latest backup is kept)

### 5. Call compress_session

```text
Call mcp__claude-sessions-mcp__compress_session tool:
- project_name: "<project folder name>"  // e.g. "-Users-user-works--vscode"
- session_id: "<session UUID>"
- keep_snapshots: "first_last"  // options: "first_last", "all", "none"
- max_tool_output_length: 5000  // optional: 0 means unlimited
```

## Usage

```bash
/session compress <session_id>    # compress a specific session
/session compress                 # batch compress sessions containing hook-related messages
```

## Compression Results

- Removes duplicate file-history-snapshots (keeps only first/last)
- Truncates long tool outputs
- File size reduced approximately 10-40% (varies by content)
- Displays original size → compressed size

## Example

**Single session compression:**
```
Before compression: 415 lines, 922KB
After compression: 270 lines, 816KB
```

**Batch compression:**
```
Found 13 sessions with hook-related messages
- abc123...: 922KB → 816KB (11% reduction)
- def456...: 1.2MB → 890KB (26% reduction)
- ghi789...: no change (already compressed)
...
Compression complete for 13 sessions
```

## Notes

- Compression is irreversible, so backup important sessions
- claude-sessions-mcp runs via npx, no separate installation required
