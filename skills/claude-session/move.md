# Session Move

Move specific sessions to another project directory and update internal `cwd` references.

Unlike `migrate` (bulk classify+move), `move` targets explicit session IDs.

## Quick Start

```bash
/session move <session_id> <target_project_path>
/session move <id1> <id2> <target_project_path>
/session move <session_id> <target_project_path> --cwd-mode all
```

## When to Use

- Project directory changed (repo moved, parent folder restructured)
- Sessions need to follow a `.ralph/` or config relocation
- Moving Ralph sessions from sub-repo to org-level project

## Workflow

### 1. Parse Arguments

- Last argument = target project path
- All preceding arguments = session IDs
- If `--cwd-mode` not specified, AskUserQuestion to ask

### 2. AskUserQuestion: cwd Mode

```
AskUserQuestion {
  question: "cwd를 어떻게 변경할까요?",
  options: [
    { label: "all (Recommended)", description: "파일 내 모든 cwd를 타겟 경로로 변경" },
    { label: "first", description: "첫 번째 cwd만 변경 (서브디렉토리 이동 등 특수한 경우)" }
  ]
}
```

### 3. Execute Script

```bash
python ~/.claude/skills/claude-session/scripts/move-session.py \
  <session_id> [session_id2 ...] <target_project_path> \
  --cwd-mode <first|all>
```

Add `--dry-run` for preview.

### 4. Verify

Script prints:
- Source/target project names
- Current → updated cwd values
- Replacement count
- File move confirmation

## Script Options

| Option | Default | Description |
|--------|---------|-------------|
| `--cwd-mode first` | ✓ | Only update the first cwd occurrence |
| `--cwd-mode all` | | Update all cwd occurrences |
| `--dry-run` | | Preview changes without modifying files |

## Notes

- Cross-platform: works on Windows (Git Bash, PowerShell, cmd) and macOS/Linux
- Uses `chr(92)` pattern for reliable Windows backslash handling in JSON
- `sessions-index.json` is not updated — Claude Code rebuilds it automatically
- Session content and summaries remain functional after move
- Multiple session IDs can be processed in a single invocation
