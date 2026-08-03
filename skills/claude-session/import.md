# Session Import

Delivers session data to other agents/skills via pipeline.

## Quick Start

```
/session import --hookify          # Fetch session and deliver to hookify
/session import --analyze          # Session analysis pipeline
/session import --to <agent>       # Deliver to a specific agent
```

## Prerequisites

### 0. Verify claude-sessions-mcp tool registration

Check whether `mcp__claude-sessions-mcp__list_projects` is directly available (`ToolSearch("select:mcp__claude-sessions-mcp__list_projects")` or an equivalent tool-list check).

If not available, register `claude-sessions-mcp` in the project's MCP config per `mcp-config` skill conventions, then retry the availability check before proceeding.

### 1. Fetch Session Data

First, fetch session data using `/session summarize`.
Alternatively, you can specify the project/session ID directly in the prompt.

## Pipeline Targets

Check for the following keywords in the prompt:

| Keyword | Target | Description |
|---------|--------|-------------|
| `hookify` | hookify:conversation-analyzer | Analyze patterns and generate hooks |
| `analyze` | general-purpose | Conversation analysis insights |
| `continue` | Parent agent | Return task context |

## Pipeline Examples

### hookify Pipeline

```
Task tool:
  subagent_type: "hookify:conversation-analyzer"
  prompt: |
    Find patterns to prevent from the following conversation and generate hooks:

    <conversation>
    {fetched session conversation content}
    </conversation>
```

### Analysis Pipeline

```
Task tool:
  subagent_type: "general-purpose"
  prompt: |
    Please analyze the following conversation:

    <conversation>
    {session data}
    </conversation>
```

### Custom Pipeline

When the user specifies a particular agent/skill:

```
Task tool:
  subagent_type: "{specified agent}"
  prompt: |
    Please work based on the following session context:

    <session_context>
    {fetched session data}
    </session_context>

    Request: {user's additional request}
```

## Full Workflow

1. Select project/session (`mcp__claude-sessions-mcp__list_*`)
2. Extract conversation content (`summarize-session.py`)
3. Identify pipeline target
4. Call agent via Task tool

## Notes

- If no pipeline target is found, return summarize results only
- hookify pipeline extracts user/assistant messages only
- Sensitive information should be reviewed manually before import (API keys, tokens, etc.)
- Due to context limits, only the most recent 50 messages are delivered
