# Session Rewind (Direct Truncation & Soft Rewind)

Provides direct truncation and soft-rewind of conversation context (JSONL for Claude Code, SQLite DB for Antigravity) without reverting working directory source code modifications.

## Rewind Modes

| Rewind Type | Conversation Context | Local Code Files | Method / Command |
|-------------|----------------------|------------------|------------------|
| **Direct Truncation Engine** (Recommended) | Truncated to step N / line M | **Preserved 100% (Untouched)** | `python3 scripts/rewind-session.py` |
| **Git Stash Bridge** (Native UI/CLI) | Native rollback to step N | **Preserved 100% (Stash/Pop)** | `git stash` → Native Rollback → `git stash pop` |
| **Hard Rewind** (Default UI/CLI) | Rollback to step N | Reverted to step N state | Native Checkpoint Rollback / UI Rewind |

## Method 1: Direct Truncation Engine (`scripts/rewind-session.py`)

### 1. Engine Selection (`/session rewind`)

When `/session rewind` is invoked without flags, present an interactive choice for the target engine via `AskUserQuestion`:

- **1. Antigravity IDE** (`~/.gemini/antigravity-ide/conversations/*.db`)
- **2. Antigravity CLI** (`~/.gemini/antigravity-cli/conversations/*.db`)
- **3. Claude Code** (`~/.claude/projects/*/*.jsonl`)

### 2. UUID Selection (`/session rewind --<engine>`)

When invoked with an engine flag (or after engine selection), list recent session UUIDs with `mtime`, `steps/lines` count, and title, then present interactive UUID choices:

```bash
# List recent sessions for an engine
python3 scripts/rewind-session.py --list-sessions <antigravity-ide|antigravity-cli|claude-code>
```

### 3. Checkpoint & Ask Preservation Selection (`/session rewind --<engine> <uuid>`)

When a UUID is selected, fetch rewindable checkpoints (User Prompts & AskQuestions):

```bash
# List checkpoints (step index, type, summary)
python3 scripts/rewind-session.py --list-checkpoints <antigravity-ide|antigravity-cli> --uuid <uuid>
```

- **User Prompt Step**: Rewinds to right before the user prompt was sent.
- **Ask Question Step (Ask Preservation)**: Rewinds right after the `AskUserQuestion` tool call step so that the **Ask question prompt is preserved in context**, allowing the user to select a different answer without re-generating the model's Ask output.

### 4. Direct Truncation Execution

```bash
# Antigravity (IDE/CLI) SQLite DB & transcript.jsonl direct truncation
python3 scripts/rewind-session.py \
  --antigravity-ide \
  --uuid <uuid> \
  --step <cutoff_step_index> [--preserve-ask]

# Claude Code JSONL direct truncation
python3 scripts/rewind-session.py \
  --claude-code \
  --uuid <uuid> \
  --line <keep_line_count>
```

## Method 2: Git Stash Bridge (For Native UI/CLI Rewinds)

Before triggering a native UI or CLI rewind command that reverts files:

```bash
# 1. Stash all uncommitted local code changes & untracked files
git stash push -u -m "agy-soft-rewind-keep-code-$(date +%Y%m%d_%H%M%S)"

# 2. Perform native conversation rewind in agy CLI / IDE to the desired checkpoint step
# (e.g. agy --conversation=<uuid> or UI rewind)

# 3. Restore all local code changes (resolve merge conflicts if modified during native rewind)
git stash pop
```

## Method 3: Manual SQLite Step Truncation (Database-Only Fallback)

> [!NOTE]
> This manual SQL fallback truncates step rows in `SESSION_DB` and updates step counts. For full session consistency (including `transcript.jsonl` and `transcript_full.jsonl` truncation), use `Method 1: Direct Truncation Engine` (`scripts/rewind-session.py`).

```bash
SESSION_DB="$HOME/.gemini/antigravity-cli/conversations/<conversation_id>.db"
cp "$SESSION_DB" "${SESSION_DB}.bak"
sqlite3 "$SESSION_DB" "DELETE FROM steps WHERE idx > 150;"
sqlite3 "$HOME/.gemini/antigravity-cli/conversation_summaries.db" \
  "UPDATE conversation_summaries SET step_count=(SELECT COUNT(*) FROM steps WHERE conversation_id='<conversation_id>') WHERE conversation_id='<conversation_id>';"
```

## Safety & Backups

- SQLite DB files are atomically backed up as `<uuid>.db.bak`.
- Transcript logs are backed up as `transcript.jsonl.bak` and `transcript_full.jsonl.bak`.
- Local working directory source code files are **100% untouched**.

## Antigravity IDE Session Reflection (Mandatory App Restart)

- Antigravity IDE background language server (`language_server_macos_arm`) caches conversation trajectories in process memory.
- `Developer: Reload Window` (`Cmd+R`) only reloads the Electron frontend and **will NOT reload the backend language server's memory state**.
- To ensure the rewound SQLite DB and transcript are cleanly loaded without pre-invocation hook errors, **completely quit Antigravity IDE (`Cmd + Q`) and restart it**.
