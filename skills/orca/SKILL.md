---
name: orca
description: |
  Launch and coordinate agent sessions inside the Orca IDE runtime (stablyai/orca). Topics:
  send - find a running Orca terminal by title/preview/worktree and deliver a prompt to it,
  always disambiguating with a question when more than one candidate matches and never
  targeting the caller's own pane [send.md]. launch - start a new agent session (claude,
  antigravity, openclaw, codex, and 30+ other supported agents) in a fresh or existing
  worktree [launch.md]. install - install the stablyai/orca skill bundle into Claude Code,
  OpenClaw, or Antigravity, asking whether to ghq-clone + symlink or use a plain marketplace
  install [install.md].
  Use when: "send this to the claude session working on X", "hand this off to another agent
  in Orca", "spawn a new codex/antigravity worktree", "which Orca terminal is running Y",
  "install the orca skills into openclaw/antigravity", "Orca worktree", "Orca terminal send".
metadata:
  author: es6kr
  version: "0.1.0"
---

# Orca Session Management

Coordinates agent sessions running inside the Orca IDE (`stablyai/orca`) — finding a
specific running session and delivering work to it, launching new sessions, and installing
Orca's own bundled skills into other harnesses.

## Topic Dispatch

**When this skill is invoked with a topic specifier (e.g., `/orca send` or `Skill("orca", "send")`), load and follow only the matching topic file (`send.md`). Do not echo the Topics table or summarize other topics in the response.** The Topics table below is an index for invocations without a topic specifier — it is not user-facing output when a topic is named.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| send | Deliver work to a running Orca terminal, disambiguating candidates | [send.md](./send.md) |
| launch | Start a new agent session in a worktree | [launch.md](./launch.md) |
| install | Install the Orca skill bundle into another harness | [install.md](./install.md) |

## Resolve the CLI (all topics)

Every topic in this skill needs the Orca CLI executable. Resolve it once per session and
reuse it:

1. If `ORCA_CLI_COMMAND` is set, use its value (Orca exports this for managed WSL sessions).
2. Otherwise, in a dev checkout exposing `ORCA_DEV_REPO_ROOT`, use `orca-dev`.
3. Otherwise, on Linux outside an Orca-managed terminal, use `orca-ide`. **Never run bare
   `orca` there** — it normally resolves to the GNOME Orca screen reader and starts speech on
   the user's machine.
4. Otherwise, use `orca`.

Below, `ORCA` is a placeholder for the resolved executable. Substitute it before running
anything — do not create a shell variable or run `ORCA` literally.

If the resolved executable fails, report the exact error and stop. Do not fall through to
another executable — that could silently target a different Orca build.

Confirm the app is reachable before anything else:

```bash
ORCA status --json
```

If `result.app.running` is false, start it with `ORCA open --json` first. Prefer `--json` for
every agent-driven call.

## Command source of truth

**Do not hardcode Orca CLI flags in this skill or memorize them from a prior session.** Orca
releases change subcommands and flags; a cached copy drifts from the binary that will
actually run the command. Before running an unfamiliar command, confirm its current shape
with:

```bash
ORCA skills get orca-cli
ORCA skills get orchestration
```

These print the complete, version-matched guide for the exact binary in this session. This
skill's topic files hold the parts that don't change across releases (the disambiguation
policy, the self-targeting guard, the harness install matrix) — not a copy of Orca's flag
reference.

## Self-identification

Every command in this skill that talks to another terminal must first know which terminal it
is itself, to avoid ever targeting its own pane. Orca exports `ORCA_PANE_KEY` as
`<tabId>:<leafId>` inside every managed terminal. If it is unset, this session is not running
inside an Orca-managed terminal and `send` must refuse to run (see [send.md](./send.md)).

## Topic Dependencies

```text
orca
  ├─→ send: uses the CLI-resolution + self-identification rules above
  ├─→ launch: uses the CLI-resolution rules above
  └─→ install: independent — only needs the CLI resolved when verifying a Claude/OpenClaw install
```

- `send` and `launch` both call into the running Orca app; `install` mostly edits files on
  disk and only touches the CLI to confirm an install landed.
- For task DAGs, ask/reply flows, or coordinator loops between agents, use Orca's own
  `orchestration` skill directly (`ORCA skills get orchestration`) — this skill does not
  reimplement it. `send` covers the simpler case: "deliver this prompt to that terminal."
