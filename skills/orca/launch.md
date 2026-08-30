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

## Independent new worktree (default)

```bash
ORCA worktree create --repo id:<repoId> --name <task-name> --no-parent --agent <agent> --prompt "<task brief>" --json
```

Use `--no-parent` and omit `--base-branch` for independent top-level launches unless the
user explicitly asks for stacked work, "branch from current", or a specific base — put any
current-branch context into the prompt text instead. `--repo` can be omitted only when the
calling shell's cwd is already inside an Orca-managed worktree that Orca can infer the repo
from; when in doubt, pass it explicitly.

The result's `worktree.id` is `<repoId>::<worktreePath>` — copy the whole value into any
follow-up command; a truncated `repoId` alone does not identify the worktree.

## Existing worktree, new terminal

```bash
ORCA terminal create --worktree active --command "<agent>" --json
```

Don't run this for an agent you already launched via `worktree create --agent` in the same
worktree — that agent already has its first terminal. `terminal create` is for adding an
*additional* session alongside an existing one.

## Custom model / effort flags an agent's `--agent` shorthand doesn't accept

`worktree create --agent codex --prompt ...` launches Codex with its defaults; it does not
forward Codex-specific flags like `--model` or `-c model_reasoning_effort=...`. For a request
like "gpt-5.5 xhigh", use the two-step path instead:

```bash
ORCA worktree create --name <task-name> --no-parent --json
ORCA terminal create --worktree id:<repoId>::<newWorktreePath> --title <task-name> --command 'codex --model gpt-5.5 -c model_reasoning_effort="xhigh"' --json
ORCA terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json
ORCA terminal send --terminal <handle> --text "<task brief>" --enter --json
```

Target the returned `startupTerminal.handle` (or the freshly created terminal's handle) only
— if Orca restarts, omits the handle, or a later call returns `terminal_handle_stale`,
reacquire with `terminal list` before continuing.
