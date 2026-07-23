# Topic: claude-task (`claude-task.md`)

Provides a standalone CLI tool (`claude-task`) under `todowrite` skill resources (`~/.agents/skills/todowrite/resources/claude-task.py`), exposed on `PATH` via `~/.local/bin/claude-task`, that allows viewing, creating, updating, and deleting Claude Code & Agent Task JSON files directly from terminal shell without depending on Claude Code API or Antigravity runtime.

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

## Windows / Git Bash

Any `-s`/`-d` value that starts with a single `/` (e.g. a slash-command reference like `/fix-plan`) gets mangled by Git Bash's MSYS path conversion — it rewrites the leading `/` into a Windows path (`C:/Program Files/Git/fix-plan`) before the argument ever reaches Python.

- Escape by doubling the leading slash: `claude-task add -s "//fix-plan follow-up"` — MSYS leaves a double-leading-slash token alone, and the CLI stores it as the intended single-slash text.
- Do NOT set `MSYS_NO_PATHCONV=1` for this — it disables path conversion for every argument on the command line, including the `$HOME`-based script path the wrapper resolves internally, and breaks the call outright.
- After any `add`/`update` whose subject/description starts with `/`, verify via `list`/`show` that the stored value still starts with a single `/` and was not silently rewritten to a drive path.

## Setup & Maintenance

- Executable path: `~/.agents/skills/todowrite/resources/claude-task.py`
- `PATH` entry: `~/.local/bin/claude-task` — a bash wrapper script (`exec uv run python <executable-path> "$@"`), **not a symlink**. Windows/Git Bash symlinks require elevated privileges or Developer Mode, so a wrapper script is the portable choice; the same pattern is used by other `~/.local/bin/` entries (e.g. `ralph`).
- Managed via `todowrite` skill resources.
