# Composing Plain Text Chat Messages

## Core Constraints

The output of this skill must be **plain text** that can be pasted as-is into chat apps such as KakaoTalk, Slack, Teams, etc.

### Strictly Forbidden (Markdown Syntax)

| Forbidden Syntax | Replacement |
|------------------|-------------|
| `# Heading`, `## Subheading` | UPPERCASE or `[section]` brackets |
| `**bold**`, `*italic*` | Plain text as-is |
| `` `code` ``, ` ```code block``` ` | Plain text as-is |
| `- [ ]`, `- [x]` checkboxes | Numbered list or middle dot (·) |
| `- item` (hyphen list) | Numbered list or middle dot (·) |
| `[link](URL)` | Write the URL directly |
| `> quote` | None (indentation acceptable) |
| `---` horizontal rule | `━━━` or `───` unicode line |
| Emoji | Only when the user explicitly requests it |

### Allowed Formatting

| Format | Purpose | Example |
|--------|---------|---------|
| `[section name]` | Section divider | `[Status]`, `[Action items]` |
| Numbered list `1. 2. 3.` | Ordered items | `1. First item` |
| Middle dot `·` | Unordered items | `· Item A` |
| Arrow `→` | Links, results, direction | `→ Details: https://...` |
| Unicode line `━━━` `───` | Major/minor divider | Section separator |
| Line break | Paragraph break | One blank line |

## Procedure

### Step 1. Analyze the Input

Understand the situation/context the user provided.

- Who is the audience (teammate, manager, external)
- Which channel (KakaoTalk, Slack, email, etc.)
- What is the core message
- What is the tone (formal, casual, friendly, etc.)

If the user does not specify tone/channel, default to **a concise and friendly tone + general chat**.

### Step 2. Draft the Message

Write a plain text message that follows the forbidden/allowed format rules above.

Writing principles:
- The first line is the core summary (one sentence)
- Structure the details as a list
- Minimize unnecessary greetings/closings (keep it concise — it's a chat)
- Length: an amount readable in one chat message (split if too long)

### Step 3. Remove Trailing Blanks

Before output, always apply:
- Remove trailing whitespace from every line
- Remove trailing blank lines at the end of the file/message
- Collapse 2+ consecutive blank lines into 1

### Step 4. Output + Clipboard Copy

1. Print the message as plain chat text (no code block)
2. Auto-copy to clipboard:

```powershell
# Windows (PowerShell)
$message = @'
message content
'@
$message = ($message -split "`n" | ForEach-Object { $_.TrimEnd() }) -join "`n"
$message = $message.TrimEnd("`n")
Set-Clipboard -Value $message
```

```bash
# macOS
echo -n "message content" | pbcopy

# Linux (X11)
echo -n "message content" | xclip -selection clipboard
```

Environment detection: use `Set-Clipboard` on PowerShell, `pbcopy` on bash+macOS, `xclip` on bash+Linux.

### Step 5. Confirm with the User

Report copy completion and apply any edit requests.

## Examples

### Input

> "I deployed a new version of the dt app to dev-38 and need to send a test-request message to the team. It's about PR #325, map rendering improvements."

### Output

```
A new version of the dt app has been deployed to dev-38.

[Changes]
· Improved map rendering performance
· Optimized PMTiles tile loading

[Test request]
1. Connect to dev-38 and check the dashboard map
2. Feel out the tile load speed on zoom in/out
3. Let me know if anything looks off

→ PR: https://github.com/daegunsoftDev/turborepo-web/pull/325
```

### Input

> "Tomorrow 10 AM scrum — send an attendance confirmation message."

### Output

```
Scrum tomorrow (Mon) at 10 AM.
Please confirm whether you can attend.
```
