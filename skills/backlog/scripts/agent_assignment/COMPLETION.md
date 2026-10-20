# Trusted completion API (explicit opt-in, no default network)

The receiver still only admits planning-only work; runtime `completed` is not task
acceptance. This module is not exposed to issue/model input or the offline CLI.
Only the trusted host orchestrator may construct its verifier and transport.
This is the API companion to [the agent-assignment topic](../../agent-assignment.md),
not a poller, model/tool dispatch installation, or a production E2E claim. The
default collector keeps `DisabledReceiver`; none of these opt-in calls run there.

Scope must come from a trusted operator independently of issue/model/snapshot
content. The offline CLI requires a separate explicit `--scope-file` JSON with
exactly `host`, `workspace`, `project_id`, and `identifier`, without defaults,
environment fallback, or fixture self-authority. The test-only example is
`skills/backlog/scripts/tests/fixtures/agent_assignment/scope.json`, alongside
`snapshot.json`. A separate file path is not OS authentication or cryptographic
tamper-proofness; protect its ownership/access and provenance. The example below
uses that synthetic scope, not any live project or agent identity. All undefined
names are trusted caller-supplied values/callbacks, not executable defaults.
Keep writable completion/binding DBs outside Git under designated scratch `TMPDIR`
with an independently prepared fresh directory; never fall back to OS temp or
reuse synthetic criteria as operational authorization.

```python
from agent_assignment.ledger import Ledger
from agent_assignment.model import Config, IdentityScope
from agent_assignment.completion import (
    adopt_existing_delivery, CompletionGate, PlaneCompletionFinalizer,
)

# Synthetic illustration only, not operational identity or authorization.
# A trusted operator must independently author/protect the intended scope.
scope = IdentityScope(
    host="https://plane.example.com",
    workspace="demo",
    project_id="44444444-4444-4444-8444-444444444444",
    identifier="PROJECT",
)
config = Config(
    host=scope.host, workspace=scope.workspace, project_id=scope.project_id,
    assignee_id=exact_assignee_uuid,
    repo=exact_original_envelope_workspace_path, scope=scope,
)
with Ledger(new_durable_completion_db_path) as ledger:
    # Only if original dispatch ledger was lost/in-memory. This reads the existing
    # binding DB read-only, validates hashes + exact envelope + run/session, and
    # writes an adopted_delivery event, NOT fictitious snapshot/assignment events.
    adopt_existing_delivery(
        ledger, config,
        binding_path=actual_original_binding_sqlite_path,
        outbox_id=actual_original_outbox_id,
        issue_readback=fresh_exact_plane_issue_get,
        read_run=authenticated_fresh_run_reader,
        provenance={"audit_path": independent_audit_path,
                    "audit_sha256": actual_audit_file_hash},
        now=actual_epoch_seconds,
    )
    gate = CompletionGate(
        ledger, verifier_id=trusted_verifier_revision,
        verify=independent_acceptance_verifier,
        read_run=authenticated_fresh_run_reader,
    )
    gate.register(actual_original_outbox_id, {
        "short_plan": "Output is a short text plan for this exact planning-only issue",
        "no_execution": "Independent exact-run transcript audit shows no tool calls",
    })
    receipt = gate.verify(actual_original_outbox_id)  # raises unless every check passes
    # Explicit separately authorized write. No call here implies permission to write.
    result = PlaneCompletionFinalizer(gate, config, pinned_plane_transport).finalize(
        actual_original_outbox_id)
```

Do not copy illustrative criteria to unrelated tasks. A planning-only PASS proves
only those explicit requirements, never completion of original backlog work.

## Injected contracts

* `read_run(run_id) -> dict`: freshly authenticated exact run GET, with
  `run_id`, `session_id`, `status`, `result`. Only status `completed` and a nonempty
  `result` are eligible. If the runtime calls output `output`, a trusted adapter
  must map that exact value into `result`; do not fabricate output.
* `verify(context) -> {criterion_id: {"passed": bool, "evidence": nonempty str}}`:
  exact criterion IDs, every `passed is True`. Context includes all receipt binding
  fields, explicit `criteria`, actual `result`, and `result_sha256`. Verifier must
  independently inspect relevant artifacts/transcripts; never return true because
  the model claims PASS, completion or absence of tool use. Evidence should cite
  immutable audit paths/hashes and exact run-scoped observations. A string identity
  is not authentication: caller owns this trust boundary.
* `transport.request(path, method="GET", data=None)`: PlaneClient-compatible,
  authenticated and pinned to the config host/workspace/project. Paths are relative
  `workspaces/{workspace}/projects/{project}/states/` and
  `.../issues/{issue_uuid}/`. PATCH payload is exactly `{"state": completed_uuid}`.
  A single unambiguous non-triage completed state must exist. Transport must NOT
  automatically retry PATCH. There is no network client or credential discovery
  in this module.

## Durable records and failure behavior

`completion_contract`: immutable explicit criteria + complete dispatch binding +
trusted verifier revision. `completion_pass`: immutable PASS receipt and SHA-256.
Receipt includes `task_key`, `issue_id`, `plane_host`, `workspace`, `project_id`,
`content_revision`, `assignee_id`, `generation`, `outbox_id`, `request_sha256`,
`receiver_identity_revision`, `run_id`, `session_id`, `result_sha256`, `criteria`,
`checks`, `verifier_id`, `verified_at`, `verdict`.

`completion_adoption`: original binding row, source path, actual issue/run readback,
provenance and adoption time. Source database is opened read-only. File ownership,
authenticated runtime access and evidence authenticity remain the trusted caller's
responsibility, not something a digest proves.

`completion_intent` is committed before PATCH. `completion_readback` is committed
only after an exact issue GET confirms completed state plus unchanged normalized
content/assignees. A restart or duplicate with an intent NEVER repeats PATCH. If
an uncertain write did not apply, it fails closed for manual reconciliation; if it
applied, a fresh exact GET can recover completion. PASS remains intact on failure.
Default receipt freshness is 1800 seconds; future-dated/expired receipts fail closed.

Plane REST has no documented atomic revision CAS here. The finalizer freshly GETs
and compares normalized issue revision/assignee before PATCH and exact content +
assignee after PATCH. This can detect retained content/assignee mutations, but
cannot prevent external concurrent changes. A state-only cancellation between
GET and unconditional PATCH can be overwritten by Done and remain undetectable
in the post-GET; do not claim otherwise. A plain REST transport therefore requires
a genuinely exclusive write window and must not be used for concurrent production
writers. No generic server-side atomic precondition/row-lock adapter is supplied
by this companion; an external adapter or personal live experiment is not proof
that the public REST finalizer is race-safe or production E2E-ready. SQLite
serializes local intent creation only, not external Plane writers.

Receipts are immutable against ordinary SQL UPDATE/DELETE via triggers, not signed
or tamper-proof against the owner replacing the DB/schema. Protect the ledger file
and source credentials; never give a model raw DB or verifier-construction access.
