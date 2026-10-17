# OpenClaw WIP — explicit session ledger

OpenClaw does not expose Claude Code TaskCreate/TaskList by default. Route here
from runtime context before Claude tool diagnostics; a genuinely absent tool
is not a Claude disconnection/settings error. Do not attempt unavailable Claude
calls merely to satisfy the Claude-only branch.

## Identity and dispatch

Obtain the verified **current caller sessionId** from supplied context or supported
read-only session lookup. A sessionKey is a routing bucket, not a path component.
If identity is unavailable, stop ledger writes and report the missing context;
do not guess a UUID, use service markers as identity, or pick latest-mtime/default.
Use the parent ID only when intentional sharing is explicitly requested.

Use `agent-task --env openclaw --session <verified-current-sessionId>` for every
operation; `--env agent --session ...` is compatible. Directory overrides still
win: inspect inherited `CLAUDE_TASK_DIR`/`AGENT_TASK_DIR`, or pass a deliberately
verified `--dir` to guarantee the namespace. Without a command installation,
invoke `python3 <verified-repo>/skills/todowrite/resources/agent-task.py` with the
same flags. Do not install/register a command just to execute this adapter.

## Apply the shared WIP workflow

1. List this caller's ledger with `list --json` before classifying new/resume/mixed work.
2. Registration: `add -s "<subject>"` before deliverable work; then `update <id> --status in_progress`.
3. Resume: apply [resume.md](./resume.md) per-item decisions using this ledger.
   Native-tool notation in the shared workflow maps to CLI list/show/add/update/delete.
   Do not clean up a different/default ledger. Pending deletion still needs the
   shared workflow's explicit direction; do not introduce automatic pruning.
4. Completion: `update <id> --status completed`; show the actual confirmation and
   retain/remove records only as the selected workflow directs.
5. Deferred project work goes into `fix_plan.md`/`checklist.md` intentionally;
   the CLI session ledger is not the project canonical tracker.

Same current ID across compaction/manual reset reuses the same ledger; a rotated
ID starts a separate scope without migration. Never hardcode a worker's ID in
an adapter. Missing reads do not mkdir. See [agent-task](../todowrite/agent-task.md)
for aliases, precedence, safe IDs and writer locking.
