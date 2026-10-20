# Plane agent assignment — Phase 1 (offline only)

## Scope and source of truth

This is runtime policy source for the shared Agent Plugin v1 backlog skill. It uses only the Python 3.10+ standard library. Existing `plane_client.py` remains unchanged; only `html_to_text`, `format_browse_url`, and the GET transport port contract are reused.

**Completed offline scope: fixture → full cursor scan → SQLite baseline/generation → durable queued outbox → blocked delivery.** Automatic task-flow planning, live ACK, operational identity, production E2E, and activation are not established by synthetic tests. See the [trusted completion API companion](./scripts/agent_assignment/COMPLETION.md) for separate opt-in contracts, not an activated workflow.

- A trusted operator supplies frozen `IdentityScope(host, workspace, project_id, identifier)`. `Config(host, workspace, project_id, assignee_id, repo=None, scope=scope)` must match it.
- Offline CLI requires separate explicit `--scope-file` JSON with exactly `host`, `workspace`, `project_id`, `identifier`. No defaults, environment fallback, or fixture self-authority: snapshot config cannot authorize its own scope.
- The trusted operator must independently author and protect scope, outside issue/model/fixture control. A separate file path is neither OS authentication nor cryptographic tamper-proofness; ownership/access controls and authentic provenance remain operator responsibilities.
- `scripts/tests/fixtures/agent_assignment/scope.json` next to `snapshot.json` is test-only synthetic scope, not deployment configuration. Its synthetic assignee is not proof of any real agent account.
- No other deployment/profile, core/gateway, cron, model/worker dispatch, account/token issuance, or Plane write is activated.
- Repository source is authoritative. Do not copy implementation into agent home or link this feature worktree into a runtime plugin.

## Safe local execution

Run from worktree root. Keep DB outside Git in a fresh directory under designated scratch `TMPDIR`, not an OS-temp fallback. If absent, set TMPDIR to an approved scratch root first. This creates a new directory without overwriting an existing ledger:

```bash
: "${TMPDIR:?Set TMPDIR to an approved scratch directory}"
ASSIGNMENT_SCRATCH="$(python -c 'import os,tempfile; print(tempfile.mkdtemp(prefix="plane-assignment-offline-", dir=os.environ["TMPDIR"]))')"
PYTHONPATH=skills/backlog/scripts python -m unittest discover -s skills/backlog/scripts/tests -p 'test_agent_assignment_*.py' -v
python skills/backlog/scripts/plane_agent_poll.py --scope-file skills/backlog/scripts/tests/fixtures/agent_assignment/scope.json --fixture skills/backlog/scripts/tests/fixtures/agent_assignment/snapshot.json --db "$ASSIGNMENT_SCRATCH/ledger.sqlite3" --mode collect-only --report
```

Use fixture scope only for synthetic tests. Separately authorized integration requires independently maintained trusted scope. Without fixture or outside collect-only mode, exit is 4. Missing/invalid explicit scope fails closed. There is no live activation flag, credential input, approval/restart input command, or environment-token fallback. `--report` emits only `{mode,complete,pending,error_code}` to stderr. Default stdout is empty; never print issue body, credentials, or raw errors. Do not use stdout as Bot Chat wake data.

| exit | Meaning |
|---|---|
| 0 | Complete collect-only cycle, or cycle_busy without fetching |
| 2 | Partial cursor scan / fixture transport exhaustion |
| 3 | Schema/config/identity/content/conflict/storage error |
| 4 | Live/dispatch activation gate unsatisfied |

The same assigned fixture twice against the same DB leaves baseline_ready=1, outbox=0. Apply an empty-issues fixture first to a fresh DB, then the assigned fixture, for pending=1. This proves **durable queuing**, not receipt or model execution.

## Inputs and snapshots

- Validate UUIDs with `uuid.UUID`, preserving input strings. No display-name/email matching or automatic UUID repair.
- Assignees support UUID-string arrays or `{id: UUID}` object arrays only. Mixed forms, missing IDs, invalid UUIDs fail the cycle. This is synthetic schema; operational shapes need separate validation.
- State is UUID or `{id: UUID}`. States require id/group/an actual boolean is_triage. Reject unknown states/groups.
- Eligibility: matching project, included assignee UUID, `is_triage is False`, group `backlog/started/unstarted`. Exclude Triage/completed/cancelled; not all backlog is Triage.
- Title ≤512 characters, normalized body ≤16384; reject rather than truncate. description_html uses existing html_to_text, otherwise description_stripped.
- Revision is SHA-256 of canonical JSON title/body/state/sorted assignees; updated_at alone changes nothing.
- Public `Ledger.apply()` validates exact boolean complete, Issue UUIDs/field types/lengths/normalized assignees, and source-derived revision before transaction. Reject malformed hand-built Issues and arbitrary/stale revisions, never silently rewrite. Exact-False partial snapshots remain no-ops.
- GET states, then ordinary issues from `cursor=100:0:0`. No cache/intake/accept calls. Check pagination required keys, boolean more, nonempty cursor, repeated cursors, 1000-page limit, duplicate UUID conflicts. Legacy lists only on first page.
- Partial/malformed cycles produce `Snapshot(complete=False)` without changing observation/task/outbox/baseline. Never replace partial results with apparently valid empty snapshots.
- Complete means successful cursor scan, not server-side transactional snapshot guarantee.

## Ledger and deduplication

SQLite schema v1: identity/observation/task/outbox/delivery_receipt/approval/event. foreign_keys=ON, busy_timeout=5000, WAL, synchronous=FULL. Baseline/task/observation/outbox share one BEGIN IMMEDIATE transaction. Initial migration is serialized. No SQLite write transaction during network port calls.

One DB permits one host/workspace/project/assignee scope. repo is one trusted absolute Config path, never adopted from issue body. `repo=None` means needs_context; reevaluate the same generation after obtaining context.

- Initially assigned issues in first complete snapshot: generation=1, observed, baseline=1, outbox=0.
- Initially unassigned issues create no observation/task. First assignment is generation=1.
- Only complete-snapshot False→True reassignment increments generation, not body edits or state changes alone.
- Baseline issues do not start merely by leaving Triage/reopening. New nonbaseline assignment becoming eligible may create only one not-yet-issued outbox.
- task_key is compact canonical JSON SHA-256 of `[host,workspace,project,issue,assignee,generation]`; outbox_id is `pa-` + task_key.
- Outbox payload/request_sha256 freeze after issuance; latest task content_revision updates separately.
- Explicit assignee removal cancels pending and sets assignment_active=0. Preserve delivery/planning/execution sessions and worker handles; do not kill workers.
- Complete-snapshot absence also blocks dispatch and records `absent_from_complete_snapshot`. Reappearance may create a new generation. Before operations, define per-issue GET policy distinguishing deletion/visibility loss/Triage movement from actual unassignment.
- Completed tasks do not reissue merely by state reopen. Explicit restart approval is required.

CLI holds OS nonblocking **poll.lock** beside DB from before fetch through apply. Windows: msvcrt 1-byte LK_NBLCK; POSIX: flock LOCK_EX|LOCK_NB. Do not infer ownership from PID files or unlink lock. Contenders exit 0, stderr error_code=cycle_busy, without fetching/creating DB. OS releases lock on exit. Single-host only; Git/Syncthing DB is not a distributed lock. DBs in one directory intentionally share poll.lock.

## Delivery and receipts

Default **DisabledReceiver** returns disabled before claim, preserving pending. Separate opt-in `agent_assignment/hermes_runs.py` offers loopback-only `HermesRunsReceiver`, not wired into CLI/defaults/operational installation. HTTP tests are stdlib local mock-fixture integration, not live runtime E2E.

- pending→sending succeeds only with compare-and-set rowcount=1.
- Bind fake sender identity_revision to outbox before submit. This is offline contract, not operational identity authentication.
- Check Receipt's exact outbox ID, frozen request hash, bound receiver identity, nonempty run/session, observed_at after claim, JSON status_readback's exact run/session/status.
- Same receipt is idempotent; reject different receipt overwrite. Receipt INSERT plus outbox/task delivered is atomic. Delivered is **admission**, not planning completion.
- Timeout/ambiguous exception/invalid receipt becomes delivery_uncertain; recovery also converts interrupted sending to uncertain. Preserve pending records. Never return uncertain to pending or auto-resend due to timeout/lease expiry/lookup None.
- `HermesRunsReceiver.lookup(outbox_id, frozen_envelope_hash)` reconciles known runs only via exact GET under same auth. Unknown run returns None without resend. No CLI reconciliation/unknown-key resend API. Never claim admission without actual readback.

### Opt-in durable HTTP source contract (disabled)

- Constructor requires explicit loopback root URL (`http://127.0.0.1:<port>` or literal IPv6 loopback), dedicated bearer token, absolute SQLite binding path outside Git, identity_revision, trusted `verify_runtime` callback. No env credential fallback, profile creation/change, model/provider/harness overrides, redirects, or env HTTP proxy.
- Before auth, immediately before admission, and before receipt GET, callback freshly verifies approved listener PID/home/profile, dedicated credential scope, and **actually resolved no-tool policy including native/plugin/MCP**, returning same identity revision. Issue/model callbacks or constant lambdas are not operational verification. Source implements no host-side operational verifier; fixtures use synthetic verifier. `/v1/toolsets` may omit default MCP and alone cannot prove no-tool authority.
- Authenticated capabilities require Hermes platform, bearer required, run_submission/run_status, runs_idempotency supported/durable exactly true, positive integer retention_seconds. Block any enabled concrete tool. Initial scope is text-only planning. Prompt/Envelope.execute_allowed=False cannot replace server tool restrictions.
- Before POST, FULL synchronous commit separate SQLite `hermes_binding`: outbox ID, envelope hash, receiver identity revision, endpoint/credential scope digest, canonical HTTP body/separate body hash, fixed session_id, visible-ASCII Idempotency-Key, creation time/retention. Triggers block immutable-column UPDATE. Store no raw token. Not a security boundary against malicious local DB owner.
- Envelope hash serves Ledger Receipt, distinct from server canonical-body/session-key fingerprint. Input is envelope JSON data with only instructions/session_id alongside. No model/provider/tools/room-policy overrides.
- State is conservatively uncertain before POST. Commit POST 202 run_id immediately and separately; verify exact run/session/status GET and local body hash before returning Receipt. HTTP 200 health/202 alone is not receipt. Ledger's validated delivery_receipt transaction is authoritative, not binding state.
- Preserve fixed binding/run on failure/timeout/lost response/409/404/identity or scope change. Reinvocation/restart/retention expiry creates no new POST. Unknown run requires manual reconciliation even within retention; separately approved exact-key replay is absent. Known failed/interrupted runs remain separate from delivery and never automatically create new planning runs.
- Unittest discover includes `test_agent_assignment_hermes_runs_integration.py`. Each ThreadingHTTPServer binds ephemeral loopback only, then shuts down. Tests use scratch SQLite; no operational files/configuration/accounts/real APIs/models are changed/called.

## Approval policy and trust boundaries

Envelope fixes allowed_actions=classify/research/plan, execute_allowed=False. untrusted_body is JSON data, never instructions/argv/endpoint/env/model/provider/toolsets.

`Ledger.approve/approve_restart` are **test-only trusted in-process input contracts**. actor_id string validation is not human authentication. No model/body/CLI input path invokes them. Operations require separately authenticated human adapter. Not tamper-proof against local DB writers.

- Approval binds exact task_key/generation, current plan_revision, exact absolute workspace, actions, actor/id.
- Validity: `issued_at <= now < issued_at+1800`. Exactly +1800 seconds is rejected.
- execution_allowed is pure query, not used_at consumption/execution token/operational execution link. Reject expired/revoked/consumed/different revision/workspace/action, inactive assignment, needs_context/uncertain/running/terminal. Expiry causes neither running promotion nor renewal.
- Restart requires latest complete snapshot assigned+eligible, kind=restart, matching plan/workspace, valid unused approval. Atomically consume approval and create generation+1/task/outbox. Reject active worker, preserve handle, cancel old pending outboxes. No CLI restart.
- Restart fails closed with `previous_run_unverified` if **any historical generation of the same issue** has sending/delivery_uncertain/delivered outbox, delivered/planning/delivery_uncertain task, or Hermes session handle. Approval/generation/outbox/receipt/handles remain unchanged on rejection. Explicit human approval cannot replace prior-run termination evidence.
- Phase 1 lacks authenticated prior-run termination/readback and audit policy/adapter. Completed/failed task or fake completed readback cannot lift block. Delivered-run restart remains unavailable without separately approved termination/audit policy. Tests permit only explicit restart of undelivered pending admission. No uncertain auto-resend or SQL bypass.
- Atomic execution approval consumption, expiry events/reapproval, split workspace/harness/model/provider authentication, worker dispatch require Phase 2 design/approval. Policy calculation alone must not execute.

## Recovery and pre-activation gates

1. Stop poller, consistently preserve DB/WAL/SHM, inspect. Never manually SQL-reset uncertain to pending.
2. After separate approval, verify live dedicated assignee UUID/membership/API principal and actual response schema, not synthetic fixture.
3. Verify intended local profile/home/listener, auth scope, durable capabilities, planning-only **tool-permission restrictions**, task-flow loading/planning resume. Prompt line/CLI exit 0/generic response is not ACK.
4. Runs API requires same profile/auth scope exact GET run_id/session_id readback. Durable admission is not durable worker auto-resume. No blind POST after retention/credential rotation/404.
5. Preserve task-flow: brainstorm → plan → user review → execute → verify → delivery. Assignment replaces no implementation/deployment/split approval.
6. Actually verify user-only Windows ACLs for DB/WAL/SHM/lock. chmod 0600 is not ACL verification. Temporary-directory tests do not establish operational ACLs.
7. Operational wrapper/plugin link/cron/receiver/Plane comment readback/direct execution/other harnesses/E2E each require separate approval/integration. No activation command or active poller/model/tool dispatch is installed here.
