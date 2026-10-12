# Topic: agent-task

`agent-task.py` is the canonical standalone JSON task CLI. `claude-task.py`
remains a compatible entrypoint with shared implementation, flags, schema and exit status.
Use the repository resource directly if `agent-task` has not been installed;
this change does not install commands or alter PATH.

## Medium ownership

`agent-task` tracks current-session execution. `fix_plan.md` is the project
canonical tracker for deferred/cross-session work; Plane is the shared backlog.
Promote durable work intentionally, without copying whole session ledgers into project trackers.
Existing default and session ledgers remain accessible: no migration or automatic deletion.

## Resolution precedence

1. `--dir` (expand/resolve).
2. `CLAUDE_TASK_DIR`, then `AGENT_TASK_DIR`.
3. `--env claude`, `agent`, `auto`, or `openclaw` chooses the base;
   auto retains Claude environment detection. OpenClaw uses `.agents/tasks`.
4. `--session`, then `CLAUDE_SESSION_ID`, then `AGENT_SESSION_ID` for legacy callers.
   OpenClaw callers must pass their verified current sessionId explicitly;
   inherited Claude/agent session variables are not OpenClaw identity.
5. Without identity, legacy callers retain latest-mtime fallback with stderr warning,
   then `default` if no candidates exist. OpenClaw writes fail closed instead.

Explicit directories and directory environment overrides retain priority over session routing,
including for OpenClaw. Use verified `--dir` when inherited directory variables
must not redirect a call. Session IDs must be safe single components (letters,
digits, underscore or hyphen first; dots additionally allowed thereafter), not raw sessionKeys.
Session symlinks escaping the base and task-file symlinks are rejected.
Service markers only activate missing-ID protection; they never supply identity.
For shells without OpenClaw markers, `--env openclaw` explicitly activates it.

## OpenClaw usage

```bash
agent-task --env agent --session <verified-current-sessionId> list --json
agent-task --env agent --session <verified-current-sessionId> add -s "Implement feature X"
agent-task --env agent --session <verified-current-sessionId> update 1 --status in_progress
agent-task --env agent --session <verified-current-sessionId> show 1 --json
# Explicit OpenClaw safety even outside the Gateway environment:
agent-task --env openclaw --session <verified-current-sessionId> dir
# Deliberate access to an existing legacy default ledger:
agent-task --dir ~/.agents/tasks/default list --json
```

Flags work before or after subcommands. Task IDs are ledger-local: report subject,
not a bare numeric ID, to users. Parent and worker identities differ; use the
caller's own ID unless deliberate sharing is requested.

## Operations and safety

- `list`/`ls`, `show`/`get`, `dir` and `prune --dry-run` never create directories,
  locks or watermarks. Missing list returns `[]`; missing show exits 1.
- `add`/`create` reserves numeric IDs above `.highwatermark` and existing filenames.
- `update`/`edit` changes fields/dependencies. `--status deleted` is soft deletion.
- `delete`/`rm` unlinks the selected task only when explicitly requested.
- `prune` archives deleted and stale completed tasks (default retention 3 days);
  `--purge` deletes them. Pending/in_progress remain untouched. Do not run against
  an inherited/default namespace accidentally or register an automatic cleanup here.
- CLI writers serialize the complete transaction with an OS advisory ledger lock;
  JSON and watermark writes use same-directory temporary files and atomic replace.
  This prevents duplicate IDs, torn JSON and lost concurrent dependency updates
  between these CLI callers. External/native writers must cooperate with the lock;
  this is not a distributed filesystem or third-party writer guarantee.
- Surface the CLI confirmation after every mutation; list when the user needs
  the whole ledger. Never substitute a prose-only claim for task registration.

## Lifecycle

The ledger follows explicit current sessionId, not sessionKey. Same-ID compaction
and the installed Gateway's same-ID manual reset reuse the ledger. Daily/idle
rotation, forks or a context-engine successor ID select a different ledger;
there is no implicit carry-forward, reconciliation or deletion.

## Installation ownership and compatibility

Canonical resource: `skills/todowrite/resources/agent-task.py`.
The observed macOS `~/.local/bin/claude-task` is a symlink to the old resource;
that resource remains functional. A portable wrapper can invoke Python with
quoted arguments where symlinks are unavailable (e.g. Windows/Git Bash).
Do not claim every existing installation is a wrapper or a symlink, or register
new links/PATH/config automatically. No installer owner was found in the plan's inspection.

Git Bash can convert slash-prefixed subjects before Python sees them. Preserve
existing installation-specific argument handling and verify stored text via show;
do not globally disable path conversion as part of this rename.
