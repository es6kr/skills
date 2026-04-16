# Session Classify

Analyzes all Claude sessions in a project and classifies them as delete/keep/extract-then-delete.

## Quick Start

```
/session classify                        # classify current project sessions (default: --depth=fast)
/session classify <project_name>         # classify sessions for a specific project
/session classify --depth=medium         # also parse Todo items for analysis
/session classify --depth=full           # apply full AI summarize to each session (slow)
/session classify --execute              # execute immediately after classification
```

## Analysis Depth Options

| Option | Method | Characteristics |
|--------|--------|----------------|
| `--depth=fast` (default) | First user message + last 3 user messages | Fast, sufficient for general classification |
| `--depth=medium` | fast + TodoWrite item parsing | Can identify actual completed task list |
| `--depth=full` | Full AI summarize applied to each session | Most accurate but slow |

> ⚠️ **Sessions scheduled for split must use `--depth=medium` or higher**
> `--depth=fast` only reads the last 3 user messages, so it may miss different topics mixed in at the end of the session.
> Always check TodoWrite items and last message flow before deciding split points.

## Instructions

### 1. Run classify-sessions.py Script

**Always use the script first** — do not inline grep/sed/jq for JSONL parsing:

```bash
python3 ~/.claude/skills/claude-session/scripts/classify-sessions.py <project-name>
```

Output: TSV with columns `ID | Lines | UserMsgs | FirstDate | LastDate | Title | LastMessages`

### 2. Immediately Classify Empty Sessions

Sessions with Lines < 10 and UserMsgs = 0 are immediately classified as **Delete Recommended**.

### 3. Analyze Each Session

#### --depth=fast (default)

Use the script output directly. The script extracts:
- Custom title (priority) or first user message (fallback)
- Last 3 user messages for completion status
- Message counts and date range
- Command tag cleanup (e.g., `<command-name>/chezmoi</command-name>` → `/chezmoi`)

#### --depth=medium

In addition to fast analysis, parse TodoWrite items:

```bash
scripts/extract-todos.py {project} {session_id}
```

Example output:
```
[completed] k3s node etcd re-join setup
[completed] ArgoCD Application YAML backup
[in_progress] Helm chart deployment validation
[pending] monitoring alert setup
```

→ Concretely understand "what was done" from actual completed/incomplete items

#### --depth=full

Apply AI summarization to each session:

```
mcp__claude-sessions-mcp__summarize_session({
  project_name: "<project>",
  session_id: "<id>"
})
```

→ Use AI summary result as the title and reason

### 4. Classification Criteria

| Category | Criteria | Action |
|----------|----------|--------|
| **A) Delete Recommended** | Empty sessions, test sessions, simple Q&A (completed), sessions terminated with errors | `delete_session` |
| **B) Keep** | Important task records, ongoing work, decisions worth referencing | Keep as-is |
| **C) Extract then Delete** | Contains knowledge/patterns but the session itself is not needed; agentify candidates | Save to Serena memory then delete |

### 5. Output Classification Results

**Title**: Show actual first message content instead of slug (`robust-leaping-crab`).
**Reason**: Write one sentence in the format `"[key content] — [task scope/status] (N messages)"`.

```markdown
## Session Classification Results: {project_name}

### A) Delete Recommended (N)
| Session ID | Title | Reason |
|------------|-------|--------|
| a1b2c3d4-e5f6-7890-abcd-ef1234567890 | npm install openclaw failure analysis | Short Q&A completed, no need to reference again (8 messages) |
| d4e5f6a7-b8c9-0123-def0-123456789abc | MCP server connection test | Test session, terminated without conclusion (3 messages) |

### B) Keep (N)
| Session ID | Title | Reason |
|------------|-------|--------|
| 12345678-abcd-ef01-2345-67890abcdef0 | session classify skill description improvement | Skill refactoring in progress, current work session (1317 messages) |
| abcdef01-2345-6789-0abc-def012345678 | k3s node re-join work | Successful infrastructure work record, worth referencing (420 messages) |

### C) Extract then Delete (N)
| Session ID | Title | Extract Target |
|------------|-------|---------------|
| 98765432-fedc-ba09-8765-432fedcba098 | Helm chart deployment workflow | Repeatable pattern → Extract as Skill |
| fedcba09-8765-4321-fedc-ba0987654321 | ArgoCD ignoreDifferences configuration | Configuration know-how → Save to Serena memory |
```

### 6. Execute (when --execute flag is provided)

#### Note on split_session behavior direction

> ⚠️ `split_session` **works counter-intuitively**:
>
> | Result | Actual Content |
> |--------|---------------|
> | **New session** | Messages **before** the split point (front portion) |
> | **Original session** | Messages **after** the split point (back portion) |
>
> So if you want to "split the latter half of a session into a new session" → the original session ID ends up with the new topic.
> Think of the split point as "up to here is the original session", not "from here is the new session".

#### A) Execute Delete
```
mcp__claude-sessions-mcp__delete_session({
  project_name: "<project>",
  session_id: "<id>"
})
```

#### C) Extract then Delete

1. Extract knowledge:
```
mcp__claude-sessions-mcp__extract_project_knowledge({
  project_name: "<project>"
})
```

2. Save to Serena memory:
```
mcp__serena__write_memory({
  memory_file_name: "session-knowledge-{session_id}.md",
  content: "<extracted-knowledge>"
})
```

3. Execute delete

### 7. Bulk Cleanup of Empty Sessions

If there are many empty sessions, clean them up in bulk:

```
mcp__claude-sessions-mcp__clear_sessions({
  project_name: "<project>",
  clear_empty: true,
  clear_invalid: true
})
```

## Classification Hints

### Reason Format

```
"[session key content] — [task scope/status] (N messages)"
```

- Good example: `"k3s etcd node re-join work — completed successfully, contains recurrence-prevention know-how (215 messages)"`
- Bad examples: `"infrastructure work"`, `"work in progress"`

### Delete Recommended Criteria

- messageCount < 10 and simple Q&A
- First message is test-like (test, check, try it, etc.)
- Terminated with error, no conclusion
- No content beyond default slug

### Keep Criteria

- messageCount > 100 and complex work
- Updated within the last 7 days
- Work in progress (last message in incomplete state)
- Important decisions or successful troubleshooting records

### Extract then Delete Criteria

- Contains repeatable workflow patterns
- Successful configuration/deployment/infrastructure work records
- Has patterns but the session itself is not needed for reference

### Agentify Candidate Identification

- **Repetitive work**: Sessions performing the same pattern 2+ times
- **Manual workflows**: Multiple steps executed sequentially
- **Tool combinations**: Grep → Read → Edit pattern repeated
- **User request patterns**: "every time ~", "always do ~", "each time ~"
- **Successful troubleshooting**: Problem-solving process + clear solution
- **Successful configuration/deployment**: Infrastructure, CI/CD, environment setup completed

**Agentify types:**
| Session Characteristic | Conversion Target |
|----------------------|-------------------|
| Repeatable workflow | Skill |
| Mistake prevention pattern | Hook (hookify) |
| Complex multi-step task | Agent |
| Domain-specific knowledge | Memory (Serena) |

## Output

After execution:
1. Classification result table (title: actual content, reason: one-sentence format)
2. Count summary per category
3. Recommended actions (if no --execute flag, ask via AskUserQuestion)

## Requirements

- claude-sessions-mcp MCP server required
- Serena MCP server (when using extraction features)
