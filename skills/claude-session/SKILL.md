---
name: claude-session
description: Integrated skill for Claude Code session management. id - look up current session ID + keyword session search, import - import session, summarize - summarize session, analyze - session stats/analysis, classify - classify/organize sessions, compress - compress session, destroy - delete current session, migrate - move sessions between projects (main repo to worktree), repair - restore session structure (chain, tool_result), rename - assign custom title to session, url - generate claude-sessions web URL from session ID, Use when: "session ID", "current session", "session id", "get session", "session analysis", "session classify", "session compress", "session delete", "session repair", "chain repair", "session name", "name session", "session search", "find session", "which session", "session import", "session analyze", "session classify", "session compress", "session migrate", "session move", "worktree session", "move session", "worktree session move", "session repair", "session rename", "chain repair", "session url", "session web URL", "claude-sessions url", "session split", "split recommendations", "topic split", "session purge", "dead session", "clean dead sessions", "session cleanup"
---

# Session

Integrated skill for managing Claude Code sessions.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| analyze | Session statistics, tool usage patterns, optimization insights | [analyze.md](./analyze.md) |
| classify | Classify project sessions (delete/keep/extract) | [classify.md](./classify.md) |
| split | Analyze topic boundaries and recommend session split points | [split.md](./split.md) |
| compress | AI-compress sessions via UTCP/code-mode | [compress.md](./compress.md) |
| destroy | Delete current session and restart IDE | [destroy.md](./destroy.md) |
| id | Look up current session ID (UUID) | [id.md](./id.md) |
| import | Pipeline session data to other agents/skills | [import.md](./import.md) |
| migrate | Move sessions between projects (main repo → worktree) | [migrate.md](./migrate.md) |
| purge | Delete dead sessions (hook-only, no assistant response) permanently | [purge.md](./purge.md) |
| rename | Assign and look up custom title for session | [rename.md](./rename.md) |
| repair | Restore session structure (chain, tool_result, UUID) | [repair.md](./repair.md) |
| summarize | View and summarize conversation content from other sessions | [summarize.md](./summarize.md) |
| url | Generate claude-sessions web URL from session ID | [url.md](./url.md) |

## Quick Reference

### Summarize (View/Summarize Sessions)

```bash
/session summarize                 # select project/session then summarize
/session summarize <session_id>    # summarize a specific session
```

[Detailed guide](./summarize.md)

### Import (Pipeline Delivery)

```bash
/session import --hookify          # deliver to hookify
/session import --analyze          # analysis pipeline
/session import --to <agent>       # deliver to specific agent
```

[Detailed guide](./import.md)

### Analyze (Session Analysis)

```bash
/session analyze                   # analyze current session
/session analyze <session_id>      # analyze specific session
/session analyze --sync            # sync to Serena memory
```

[Detailed guide](./analyze.md)

### Split (Topic Split Recommendation)

```bash
/session split                     # Recommend split for current conversation
/session split <session_id>        # Recommend split for specific session
/session split --execute           # Execute recommendation immediately
```

[Detailed guide](./split.md)

### Classify (Session Classification)

```bash
/session classify                  # classify current project sessions
/session classify --depth=medium   # required when classifying sessions scheduled for split
/session classify --execute        # execute immediately after classification
```

> ⚠️ **--depth=medium or higher required before split** — fast only reads the last 3 messages, so it may miss different topics at the end of the session.

[Detailed guide](./classify.md)

### Migrate (Move Sessions Between Projects)

```bash
/session migrate                           # classify + move code sessions to worktree
/session migrate --dry-run                 # preview only
/session migrate <source> <target>         # specify source/target projects
```

Classifies sessions as CODE/INFRA/TINY/READ, then moves CODE sessions to worktree project and optionally deletes TINY sessions.

[Detailed guide](./migrate.md)

### Compress (Session Compression)

```bash
/session compress <session_id>    # compress specific session
/session compress                 # batch compress sessions containing "hookEvent":"Stop"
```

Register claude-sessions-mcp with UTCP, then call via code-mode.

[Detailed guide](./compress.md)

### ID (Session ID Lookup + Keyword Search)

```bash
/session id                          # look up current session ID
/session id Makefile remove          # search sessions by keyword
/session id --today ansible/Makefile # search only today's sessions by file path
```

Current session ID: output unique marker → search JSONL with `find-session-id.sh` → return UUID
Keyword search: grep project JSONL → sort by modification time descending → return most recent matching session

[Detailed guide](./id.md)

### Destroy (Delete Session)

```bash
scripts/destroy-session.sh
```

[Detailed guide](./destroy.md)

### Purge (Dead Session Cleanup)

```bash
/session purge                    # dry-run: list dead sessions in current project
/session purge <project_name>     # dry-run: specific project
/session purge --all              # dry-run: all projects
```

Dead session = 10 lines or fewer + no `"type":"assistant"` response.
Script: `scripts/purge-dead-sessions.sh <project_name> [--delete]`

[Detailed guide](./purge.md)

### Repair (Session Recovery)

```bash
/session repair                          # select session, then validate and repair
/session repair <session_id>             # repair specific session
/session repair --dry-run                # preview only
/session repair --check-only             # validate only (no repair)
```

Repair targets:
- Broken chain (missing parentUuid)
- Orphan tool_result (no matching tool_use)
- Duplicate UUIDs

[Detailed guide](./repair.md)

### Rename (Naming a Session)

```bash
# Assign a name to a specific session
bash scripts/rename-session.sh <session_id> "name"

# Assign a name to the latest session in the current project
bash scripts/rename-session.sh "name"

# Check current title
bash scripts/rename-session.sh --show <session_id>

# List named sessions in current project
bash scripts/rename-session.sh --list
```

[Detailed guide](./rename.md)

## Project Name Conversion Rules

| Actual Path | Project Name |
|-------------|--------------|
| `/Users/es6kr/works/.vscode` | `-Users-david-works--vscode` |
| `/Users/es6kr/Sync/AI` | `-Users-david-Sync-AI` |

Rule: `/` → `-`, remove leading `/` from path

## Requirements

- claude-sessions-mcp MCP server required
- Serena MCP server (when using analyze --sync)
