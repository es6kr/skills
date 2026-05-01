# Session ID

Finds the session ID (UUID) of the current conversation.

## How It Works

Claude's text output is recorded in session JSONL files. By leaving a unique marker in the conversation, you can grep for that marker to identify the current session file.

## Procedure

### 0. Check Context First (Preferred — no marker needed)

Before using the marker method, check if the session ID is already visible in the current context.

**Search these path patterns in recent tool results:**

| Source | Path pattern | Example |
|--------|-------------|---------|
| Subagent | `/Users/.../{session_id}/subagents/...` | `...3b86ae4e-4aaf-4f03.../subagents/...` |
| Task output | `/private/tmp/.../tasks/{session_id}/...` | `...tasks/3b86ae4e-4aaf-4f03.../bkvaevkqo.output` |
| Tool result | `.../{session_id}/tool-results/...` | — |
| Background task | `.../{session_id}/tasks/...` | output file paths from `run_in_background` |

**Procedure:**
1. Scan all file paths in recent Bash/Read tool results for UUID pattern `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`
2. If found, return it directly — **skip Steps 1-3 entirely**
3. If not found, proceed to Step 1 (marker method)

### 1. Generate and Output Marker (only if Step 0 found nothing)

**Method A (recommended):** Generate a unique marker string directly in text output.

```
SESSION_MARKER_{random_uuid}
```

Example output:
```
Marker for finding session ID: SESSION_MARKER_a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Method B:** Let the script generate the marker automatically.

```bash
MARKER=$(bash scripts/find-session-id.sh)
echo "$MARKER"
```

When called without arguments, the script generates a unique marker (`SESSION_MARKER_{timestamp}_{pid}`) and prints it. The `echo` ensures the marker appears in text output and gets recorded in the JSONL.

### 2. Search with Marker

```bash
# Method A: pass the marker you generated
bash scripts/find-session-id.sh "SESSION_MARKER_a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# Method B: pass the script-generated marker
bash scripts/find-session-id.sh "$MARKER"
```

The script converts the CWD to a project name, then searches `~/.claude/projects/{project_name}/*.jsonl` for the marker and returns the session ID.

**Parent directory fallback**: If CWD-based project directory doesn't exist (e.g., CWD is a monorepo sub-package like `packages/vscode-extension`), the script walks up parent directories until a matching project is found.

### 3. Result

```
b5153827-a52c-4e83-b24a-8413e6aa418b
```

## Script

[find-session-id.sh](./scripts/find-session-id.sh)

- Input: `<marker>` (required), `[project_dir]` (optional, auto-derived from CWD if omitted)
- CWD → project name conversion rules:
  - Git-bash: `/c/Users/...` → `c--Users-...`
  - WSL: `/mnt/c/Users/...` → `-mnt-c-Users-...`
  - macOS: `/Users/...` → `-Users-...`
- sync-conflict files are automatically excluded

## Keyword Session Search

When called as `/session id <keyword>`, searches for sessions containing that keyword and returns the session ID.

### Search Procedure

1. Determine project JSONL directory (`~/.claude/projects/{project_name}/`)
2. Grep JSONL files for keyword — matches user messages (`"type":"user"`) + file paths
3. Sort results by modification time descending and return the most recent matching session

```bash
# Project JSONL path
PROJECT_DIR=~/.claude/projects/{project_name}

# Keyword search (matches both user messages and file paths)
grep -l "<keyword>" "$PROJECT_DIR"/*.jsonl | while read f; do
  ts=$(stat -c %Y "$f")
  sid=$(basename "$f" .jsonl)
  echo "$ts $sid"
done | sort -rn | head -5
```

### Restricting Search Scope (Skill Procedure)

These are not script flags — they are implemented by the skill at invocation time:

- `--today`: Filter results to sessions modified today (skill uses `find -newer`)
- `--project <path>`: Specify a particular project path (skill overrides CWD-based detection)

### Output Format

```
03-26 11:28 | a6aea9f3-3376-4cf3-be6f-33a7122ab283
03-25 10:02 | e972a8b7-da04-4b9f-8d26-fad0350a2e09
```

## Usage Examples

```bash
/session id                          # Look up current session ID
/session id Makefile remove          # Search sessions by keyword "Makefile remove"
/session id --today ansible/Makefile # Search only today's sessions by file path
```

