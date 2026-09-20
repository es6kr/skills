# Launch — Start a New Agent Session

Start a new coding agent inside an Orca-managed worktree.

## Supported agents

Orca's `--agent` flag accepts a closed set of known TUI agents. `claude`, `antigravity`, and
`openclaw` are all in it, alongside 30+ others (`codex`, `gemini`, `cursor`, `droid`, `aider`,
`goose`, `amp`, `cline`, `copilot`, `grok`, `devin`, `hermes`, and more). An unsupported value
is rejected with `invalid_argument` / `Unknown TUI agent "<value>"` — Orca does not guess or
fuzzy-match.

**Normalize common aliases before calling the CLI** — Orca will not do this for you:

| Alias | Canonical `--agent` value |
|---|---|
| `agy`, `gemini-antigravity` | `antigravity` |
| `cc`, `claude-code` | `claude` |
| `oc` | `openclaw` |

If the user names an agent that isn't in this alias table and isn't obviously a known agent
id, pass it through unchanged rather than guessing a correction — let the CLI's own
`Unknown TUI agent "<value>"` error surface, and report it verbatim.

## Prerequisite — the target repo must be registered with Orca

`orca worktree create` needs a repo it knows about, even with `--no-parent`. If the
invoking shell's working directory isn't inside a worktree Orca already tracks, and no
`--repo` is given, the call fails with `Missing repo selector. Pass --repo or run from
inside an Orca-managed worktree.` — this happens whenever the workspace is open in Orca as a
plain folder rather than a registered repo (`orca repo list --json` returns `"repos": []`).

Check first, and register if needed:

```bash
ORCA repo list --json
# if the target repo isn't in the list:
ORCA repo add --path <absolute-repo-path> --json
```

`repo add` returns `result.repo.id` — use that as `--repo id:<id>` below. This is a one-time,
durable registration (it doesn't need repeating for the same repo in later calls), so treat
adding a new repo as worth flagging to the user rather than doing silently — it changes what
Orca tracks beyond the current task.

**There is no CLI command to undo this.** `orca repo --help` only lists `add`, `list`,
`show`, `set-base-ref`, and `search-refs` — no `remove`/`rm`/`delete`, and the full command
schema (`orca agent-context --json`) confirms none exists anywhere else in the CLI either. If
a registration needs to be undone, say so plainly and point at the Orca app's own repo
management UI (not verified by this skill) rather than editing Orca's internal state files
directly.

## Launch Strategy: Split-First (Default / Recommended)

In interactive multi-agent workflows, prefer splitting an existing active pane over creating
uncontrolled new tabs or independent worktrees. This preserves screen layout, keeps context
visible, and avoids worktree disk bloat.

### Tier 1 (Default): Vertical Split in Active Workspace
```bash
ORCA terminal split --terminal <current-handle> --direction vertical --command "<agent>" --json
```
- Defaults to `--direction vertical` for side-by-side agent pairing.
- Pre-flight check: Always inspect `orca terminal list --json` first to identify the active pane handle. (Enforced by `block-orca-new-tab-without-split-check.sh`).

### Tier 2: New Terminal Tab in Active Worktree
```bash
ORCA terminal create --worktree active --command "<agent>" --json
```
- Use when the current window layout is already dense and an additional tab is preferred without branching out into a new git worktree.

### Tier 3: Independent Isolated Worktree
```bash
ORCA worktree create --repo id:<repoId> --name <task-name> --no-parent --agent <agent> --prompt "<task brief>" --json
```
- Use **only** when physical git worktree / branch isolation is explicitly requested by the user or strictly required for independent build artifacts/branch switches.
- Prefix with `ORCA_NEW_WORKSPACE_APPROVED=1` if running autonomously after user approval to satisfy the split-check guard.

## Post-Init Session Identity & Rename Protocol

When spawning Claude Code sessions (`--command "claude"` or `claude --model ...`):
1. **The Chicken-and-Egg Reality**: At initial launch (Welcome screen, `Ctx: 0`), Claude Code has NOT yet created its `.jsonl` transcript file on disk. The physical `sessionId` cannot be extracted before the first prompt is submitted. Never guess, fabricate, or reuse an old UUID!
2. **Step 1 — Launch & Idle Wait**:
   ```bash
   ORCA terminal split --terminal <current-handle> --direction vertical --command "claude --model <model>" --json
   ORCA terminal wait --terminal <new-handle> --for tui-idle --timeout-ms 60000 --json
   ```
3. **Step 2 — Deliver Initial Task Prompt**:
   ```bash
   ORCA terminal send --terminal <new-handle> --text "<task prompt>" --enter --json
   ```
4. **Step 3 — Collision-Free Session ID Resolution**:
   Once the prompt is delivered and Claude begins processing, resolve the deterministic session ID via payload matching:
   ```bash
   sessid=$(scripts/resolve-session-id.sh --payload "<task prompt>" --project-dir ~/.claude/projects/<key>)
   sessid8="${sessid:0:8}"
   ```
5. **Step 4 — Synchronize UI Title & Session Rename**:
   ```bash
   ORCA terminal rename --terminal <new-handle> --title "<model>-<task-slug>-<sessid8>" --json
   ```
   If renaming inside Claude Code TUI, deliver `/rename <model>-<task-slug>-<sessid8>` as a dedicated single line with `--enter`.

## Custom model / effort flags an agent's `--agent` shorthand doesn't accept

`worktree create --agent codex --prompt ...` launches Codex with its defaults; it does not
forward Codex-specific flags like `--model` or `-c model_reasoning_effort=...`. For custom
flags, use the explicit command pattern with split or create:

```bash
ORCA terminal split --terminal <handle> --direction vertical --command 'codex --model gpt-5.5 -c model_reasoning_effort="xhigh"' --json
ORCA terminal wait --terminal <new-handle> --for tui-idle --timeout-ms 60000 --json
ORCA terminal send --terminal <new-handle> --text "<task brief>" --enter --json
```

Target the returned `handle` only — if Orca restarts, omits the handle, or a later call returns
`terminal_handle_stale`, reacquire with `terminal list` before continuing.
