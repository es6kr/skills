# Session Rename

Suggests and applies a name to a session.

## Procedure

### 0. Check Whether a Name Was Specified

- If the user specified a name directly → **skip to step 2** (skip suggestions)
- If no name was specified (e.g. `/session rename`, `/session name`, `suggest a name`) → **start from step 1**

> ⚠️ A topic alias such as the literal word `name` in `/session name` is **not** a title — treat it as "no name specified" and start from step 1.

#### Verb-phrase guard (HARD STOP)

**When the supplied "name" reads as an action verb / imperative phrase, it is NOT a title.** Invoke `AskUserQuestion` to clarify intent before calling `rename-session.sh`. The script silently appends `custom-title`/`agent-name` records, so a misroute is invisible unless caught at dispatch time.

| # | Don't | Do |
|---|-------|-----|
| 1 | Accept `remove profanity` / `remove` / `clean` / `convert` / `remove X` / `clean X` / `sanitize Y` as a title and call `rename-session.sh` | These read as actions. `AskUserQuestion`: "Did you mean (a) set title to '<text>', or (b) run <action> on the session?" |
| 2 | Match args by signature `<uuid> <text>` → rename without intent check | Several session operations take `<uuid> <param>`. Classify `<text>` as noun-phrase (title) or verb-phrase (action) first |
| 3 | "User gave 2 args, so it must be rename" | Verb-phrase trailing args → route to the matching content operation (`clean-profanity`, `repair`, etc.). When unclear, AskUserQuestion |

Verb-phrase detection cues (any one is sufficient):
- Imperative ending: `redact`, `remove`, `clean`, `sanitize`, `fix`, `convert`, `delete`
- Verb + object pattern: `remove profanity`, `clean transcripts`
- Action noun in isolation: `profanity removal` (action noun) vs `profanity removal task #42` (label about an action — title OK)

### 1. Generate Name Candidates

Analyze the conversation content and generate 2–4 name candidates.

**Naming rules:**
- **Length**: **≤30 characters**, short and simple. The name is also written as the **`agent-name`** record (the identifier shown in the session/agent list and used for multi-agent addressing, e.g. `wmux-web-browser-ui-test`) — a long or complex name makes a poor agent identifier.
- **Format**: a **single topic slug** — the one dominant theme, not a full task description (e.g. `skills-bare-worktree`, `git-repo-to-bare`). Do NOT chain multiple clauses with `+`; pick the single most representative topic.
- **Language**: English preferred; technical terms in English
- **Avoid**: dates, unnecessary words like "session"/"task", **compound multi-clause names, and `+`-chained enumerations of several tasks**

### 2. Apply the Name

**Current session** → Output as copyable list only (NO AskUserQuestion):

```
Session name suggestions:

1. `/rename Candidate 1`
2. `/rename Candidate 2`
3. `/rename Candidate 3`
```

`/rename` is a Claude Code built-in command — cannot be invoked via Bash or Skill tool.
The user copies and pastes the desired `/rename ...` line.

> **Keep candidates short (≤30 chars, single slug).** `/rename` updates BOTH the `custom-title` and the `agent-name` record — the chosen name becomes the agent identifier too, so a long compound name (`A + B + C`) is a poor fit. Suggest concise single-topic slugs.

| # | Don't | Do |
|---|-------|-----|
| 1 | Call `rename-session.sh <current-id> "title"` for the current session | Output the copyable `/rename` list and let the user apply it |
| 2 | Trust the SessionStart hint (`To rename this session: bash ...rename-session.sh`) as the current-session method | The hook hint is for **other**-session tooling. Current session = `/rename` built-in only |
| 3 | Pick and apply a title yourself for the current session | Suggest 2–4 candidates; the user chooses via `/rename` |

The script (`rename-session.sh`) appends `custom-title`/`agent-name` records, which is correct only for a **different** session's JSONL — for the live current session, the built-in `/rename` is the supported path.

**Other session** (session ID specified) → AskUserQuestion to select, then apply via script:

```
AskUserQuestion {
  question: "Select a session name",
  header: "Session Name",
  options: [
    { label: "Candidate 1" },
    { label: "Candidate 2" },
    { label: "Candidate 3" }
  ]
}
```

Then rename via script:

```bash
scripts/rename-session.sh <session_id> "<selected name>"

# Check current title
scripts/rename-session.sh --show <session_id>

# List named sessions
scripts/rename-session.sh --list
```

## Storage Format

Both records are appended together at the end of the session JSONL:

```json
{"type":"custom-title","customTitle":"<title>","sessionId":"<uuid>"}
{"type":"agent-name","agentName":"<title>","sessionId":"<uuid>"}
```

`custom-title` is displayed as the GUI title, and `agent-name` is displayed as the agent name in the session list.
