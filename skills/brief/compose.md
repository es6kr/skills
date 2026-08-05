# Composing Plain Text Chat Messages

## Core Constraints

The output of this skill must be **plain text** that can be pasted as-is into chat apps such as KakaoTalk, Slack, Teams, etc.

### Length cap — 500 characters (HARD STOP)

**A single brief message MUST NOT exceed 500 characters.** If the draft is longer, split the content **before** copying to the clipboard.

| # | Don't | Do |
|---|-------|-----|
| 1 | Copy a 564-char message to clipboard on the assumption that "a bit long, but fine" | Run length check BEFORE Set-Clipboard. >500 → split |
| 2 | Cram template file refs / branch convention / AI tool tips all into one message | Keep the core ask in message 1 (≤500); secondary info → message 2 or `.txt` file |
| 3 | Compress by removing line breaks to fit 500 | Line breaks aid readability. Split the content instead, do not collapse formatting |
| 4 | Silently drop content to fit | Tell the user "split into N messages" and copy message 1 to clipboard; offer to copy message 2 next |

**Split priorities** (when > 500):
1. **Core ask** (what's wrong + what to do) → message 1 (≤500)
2. **Reference info** (file paths, doc links, tool tips) → message 2 or omit
3. **Long examples** (sample code, full template body) → `.txt` file, attach as link or paste-after-message

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

**"Friendly" ≠ affectionate (HARD STOP — this applies across languages, not just one locale's register system).** "Team chat" specifies the *medium*, not the *register*. A workplace chat channel is not inherently casual — many workplace cultures (and most languages' honorific/politeness systems) default to a businesslike, professional-but-unpadded register for internal communication, not an affectionate or overly warm one. Do not read "concise and friendly" as license to add exclamation-heavy warmth, cutesy phrasing, or decorative emoticons — "friendly" means *approachable and unpadded*, not *cutesy*.

| # | Don't | Do |
|---|-------|-----|
| 1 | Default to affectionate/cutesy phrasing (exclamation marks, decorative emoticons, overly warm sentence-final particles where the target language has them) as the "friendly" interpretation for workplace chat | Default to a businesslike, professional register — factual and concise. Reserve an affectionate/casual register for cases the user explicitly signals (peer friends, confirmed informal team culture) |
| 2 | Match the register of a formal/honorific-addressed inquiry with a warmer, more casual reply | Mirror the inquiry's formality level in kind — formal/honorific in → businesslike register out, not the reverse |
| 3 | Treat a correction like "make it fit team chat" as "make it more casual/warm" without checking which direction is actually being requested | Ask, or infer from the inquiry's own register, which direction the correction is asking for — it can mean *less document-formal*, *less affectionate*, or both. Do not assume the softer interpretation by default |

**Structure ≠ tone.** Separately, do not mirror the inquiry's own layout (numbered bracket sections copying the question numbering) just because it maps 1:1 to the questions — flowing sentences or a light list usually read more naturally in chat, independent of which register (businesslike or casual) is chosen. This is a separate axis from the register question above; fixing structure alone does not fix a register mismatch, and vice versa.

**Self-check (before Step 2 draft)**: (1) Did the user specify tone, or only channel? (2) Default register for workplace chat is businesslike/professional, not affectionate — unless the user or the inquiry's own register clearly signals otherwise. (3) Does the inquiry being replied to use formal/honorific address? → Match that formality level, don't soften it. (4) **Language check (mandatory before writing any example or content into this file)**: this skill's `SKILL.md` description is English — any locale-specific illustration (e.g., a specific language's honorific endings or politeness markers) must be described abstractly (register/formality concepts) rather than inserted as literal non-English vocabulary. See `~/.agents/rules/opensource.md` "Skill language = SKILL.md frontmatter description language".

### Step 2. Draft the Message

Write a plain text message that follows the forbidden/allowed format rules above.

Writing principles:
- The first line is the core summary (one sentence)
- Structure the details as a list
- Minimize unnecessary greetings/closings (keep it concise — it's a chat)
- Length: an amount readable in one chat message (split if too long)

#### Follow-up "include/add" instructions — merge into the unshared draft by default (HARD STOP)

**When a later turn says "include X" / "add X" (in any language) about the same share target, the default is to merge X into the most recent draft that has not yet been confirmed as sent — not to author a new standalone message.** A fresh draft is the exception, reserved for a genuinely new share target (different recipient, different topic, or the prior draft was already sent).

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat every "include/add" instruction as a cue to write a brand-new draft file/message | Check whether the most recent draft for this share target was already confirmed sent. If not, edit that draft in place to fold in the new content |
| 2 | Keep stacking `brief-X2.txt`, `brief-X3.txt` for each follow-up instruction on the same wiki page/topic | One share target = one evolving draft until the user confirms it was sent or explicitly asks for a second, separate message |
| 3 | Treat "include" as ambiguous and default to "separate" | "include" / "add" is an explicit merge signal — it means "fold this into what's already there", not "make something new alongside it" |
| 4 | Re-decide per instruction without remembering the prior turn's correction (e.g., a prior "merge these into one" note in this same conversation) | If the user already corrected this exact pattern once this conversation, apply that same merge-by-default behavior to subsequent follow-ups without re-triggering the same correction |

**Self-check (before drafting in response to any follow-up "include/add" instruction)**:
1. Is there an existing draft for this same share target that the user has not yet confirmed as sent (posted to chat, copied and used)?
2. If yes → edit/regenerate that single draft with the new content folded in, re-run the length check (Step 3.5), and output the merged result — do not create a second file/message.
3. If no (prior draft was confirmed sent, or this is a genuinely different topic/recipient) → a new draft is correct.

### Step 3. Remove Trailing Blanks

Before output, always apply:
- Remove trailing whitespace from every line
- Remove trailing blank lines at the end of the file/message
- Collapse 2+ consecutive blank lines into 1

### Step 3.5. Length Check + Split (MANDATORY before clipboard)

Run `.Length` on the trimmed draft. If `> 500`, split per the priority list above.

```powershell
if ($message.Length -gt 500) {
  Write-Output "Draft is $($message.Length) chars (>500). Split required."
  # Manually split into $message1 + $message2 per priority list
  # Copy $message1 to clipboard; report split count + offer $message2 next
} else {
  Set-Clipboard -Value $message
}
```

Do not bypass with "only slightly over" / "just one long line" — 500 is the hard cap.

### Step 4. Output + Clipboard Copy (HARD STOP — both, in this order)

**Text output to chat is the primary medium. Clipboard is a convenience copy.** Clipboards are volatile — the user may overwrite it before pasting — so the chat-rendered text is the authoritative record.

| # | Don't | Do |
|---|-------|-----|
| 1 | Run `Set-Clipboard` and report "Copied (N chars)" without printing the message body to chat | Print the full message body to chat as plain text FIRST, then run `Set-Clipboard`, then report length |
| 2 | Wrap the printed message in a code block (` ``` ` / triple-backtick) — even for "readability" / "preserves formatting" | Plain text only — code block changes meaning for some chat apps, may collapse/scroll, and obscures intended formatting. Some chat clients (e.g., KakaoTalk, cmux preview) hide code block content from quick scroll |
| 3 | Print only the clipboard length and assume the user can paste from clipboard | Print the body even if length is short — the user needs a visible record after clipboard is overwritten |
| 4 | Skip the chat print when re-iterating in later turns (wrap-up / status / summary / final-deliverable report / session-end message), referencing the message only as "Copied to clipboard" or "N chars copied" | Every clipboard mention = re-print the copied ≤500-char chunk (the message actually on the clipboard, NOT the entire multi-message body — reprinting the full body would breach the 500-char cap again). Trigger words: "copied", "wrap-up", "status", "summary", "final", "session end" — any of these in a turn referencing the message MUST re-print the copied ≤500-char chunk |
| 5 | Assume "the user can scroll up to find the body" because it was printed once N turns ago | Clipboard outlives one turn; chat scroll buries the body after 5-10 turns. Re-print the copied ≤500-char chunk every time it is referenced |

**Procedure order**:

1. Print the message as plain chat text (no code block) — **mandatory, first**
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
