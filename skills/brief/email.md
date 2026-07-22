# Email Draft Composition (email-*.md)

Rules for composing email drafts, distinct from plain-chat briefing in `compose.md`. Email clients render a subset of Markdown — the rules below prevent broken formatting in Outlook, Hanmail, and similar clients.

## Formatting constraints

| Don't | Do |
|-------|----|
| `##`, `###` headers (render as large font in mail) | Use `**bold**` for section headers |
| Code fences ` ``` ` (unsupported in mail clients) | Indentation or inline `` ` `` code |
| Image embed `![](...)` (handled as separate attachment) | Attachment notice text |
| Markdown tables (`\| col \| col \|`) — borders invisible in Outlook/Hanmail | Bullet list (`- **label**: value` + newline `· effect: ...`) or labelled paragraphs |

## Output format

- Save as `email-<topic>.md`
- Subject line as first H1 heading
- Body starts immediately after subject — no extra blank line

## When to use

Trigger: user asks for "email draft", "compose mail", "email-*.md"
