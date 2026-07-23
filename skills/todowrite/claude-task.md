# Topic: claude-task (`claude-task.md`)

Provides a standalone CLI tool (`claude-task`) under `todowrite` skill resources (`~/.agents/skills/todowrite/resources/claude-task.py`) symlinked to `~/.local/bin/claude-task` that allows viewing, creating, updating, and deleting Claude Code & Agent Task JSON files directly from terminal shell without depending on Claude Code API or Antigravity runtime.

## When to Use

- When Claude Code Task tool encounters internal errors or is unavailable.
- When working in non-Claude Code environments (Antigravity, standalone terminal shell, OpenClaw, cron scripts).
- When third-party tools need to follow the exact same Task JSON schema.

## Features

- **Dual Storage Auto-Detection**:
  - Detects active Claude Code session in `~/.claude/tasks/<session-id>/` automatically when `--env claude` or active session is detected.
  - Falls back to `~/.agents/tasks/default/` when `--env agent` or operating outside Claude Code.
  - Supports custom directory via `--dir <path>`.
- **Concurrency & Highwatermark**: Auto-maintains `.highwatermark` for auto-incrementing numeric Task IDs (`#131`, `#132`, etc.).
- **Subcommands**:
  - `list` (or `ls`): List tasks in table format with ID, subject, activeForm, and status.
  - `show` (or `get`): View detailed JSON content for a specific task.
  - `add` (or `create`): Create a new task with auto-assigned numeric ID.
  - `update` (or `edit`): Update task status (`in_progress`, `completed`, `deleted`) or subject.
  - `delete` (or `rm`): Mark task status as `deleted`.
  - `dir`: Print resolved Task directory path.

## CLI Usage Examples

```bash
# List tasks for current Claude session
claude-task list --session 2f13089c-5113-4cc9-9a79-cc4deacee1d6

# List tasks in default agent directory
claude-task --env agent list

# Create a new task in agent directory
claude-task --env agent add -s "Implement feature X" -d "Detailed description"

# Update task status
claude-task --env agent update 1 --status completed
```

## Usage Discipline

`add`/`update`/`delete` write to disk silently — the caller must surface the result:

- After any `add`/`update`/`delete` call, include the command's own confirmation line (e.g. `Created Agent Tasks #3: ...`) in the visible response. Do not let registration remain an invisible side effect.
- When the caller needs the user to see the current ledger (not just the one changed row), follow up with `list` and show its output too.
- Skipping this is a violation even when the caller's own task-tracking convention (e.g. `/next` Step 0-0, `/fix` Step 0) treats the call as internal bookkeeping — the CLI's output is the only thing that makes the registration visible to the user.

## Setup & Maintenance

- Executable path: `python3 ~/.agents/skills/todowrite/resources/claude-task.py`
- Symlink path: `~/.local/bin/claude-task`
- Managed via `todowrite` skill resources. Symlink setup can be verified via `Skill("todowrite", "doctor")` or skill setup workflows.
