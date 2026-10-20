PRAGMA user_version = 1;
CREATE TABLE identity (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 plane_host TEXT NOT NULL, workspace_slug TEXT NOT NULL,
 project_uuid TEXT NOT NULL, assignee_uuid TEXT NOT NULL,
 baseline_ready INTEGER NOT NULL DEFAULT 0 CHECK(baseline_ready IN (0,1)),
 last_complete_at INTEGER,
 UNIQUE(plane_host,workspace_slug,project_uuid,assignee_uuid)
);
CREATE TABLE observation (
 issue_uuid TEXT PRIMARY KEY, generation INTEGER NOT NULL CHECK(generation>=1),
 assigned INTEGER NOT NULL CHECK(assigned IN (0,1)),
 baseline INTEGER NOT NULL CHECK(baseline IN (0,1)),
 content_revision TEXT NOT NULL, last_seen_at INTEGER NOT NULL
);
CREATE TABLE task (
 task_key TEXT PRIMARY KEY, plane_host TEXT NOT NULL, workspace_slug TEXT NOT NULL,
 project_uuid TEXT NOT NULL, issue_uuid TEXT NOT NULL, assignee_uuid TEXT NOT NULL,
 assignment_generation INTEGER NOT NULL CHECK(assignment_generation>=1),
 issue_url TEXT NOT NULL, workspace_path TEXT,
 state TEXT NOT NULL CHECK(state IN
 ('observed','queued','delivered','planning','awaiting_approval','running',
 'verifying','completed','needs_context','delivery_uncertain','failed','unassigned')),
 assignment_active INTEGER NOT NULL CHECK(assignment_active IN (0,1)),
 content_revision TEXT NOT NULL, plan_revision TEXT,
 hermes_session_id TEXT, worker_runtime_id TEXT, worker_terminal_id TEXT, worker_session_id TEXT,
 approval_scope TEXT, error_code TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
 UNIQUE(plane_host,workspace_slug,project_uuid,issue_uuid,assignee_uuid,assignment_generation)
);
CREATE TABLE outbox (
 outbox_id TEXT PRIMARY KEY, task_key TEXT NOT NULL UNIQUE REFERENCES task(task_key),
 payload_json TEXT NOT NULL, request_sha256 TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','sending','delivered','delivery_uncertain','cancelled')),
 attempt_count INTEGER NOT NULL DEFAULT 0, attempt_started_at INTEGER,
 receiver_identity_revision TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, error_code TEXT
);
CREATE TABLE delivery_receipt (
 outbox_id TEXT PRIMARY KEY REFERENCES outbox(outbox_id),
 request_sha256 TEXT NOT NULL, receiver_identity_revision TEXT NOT NULL,
 run_id TEXT NOT NULL, session_id TEXT NOT NULL, status_readback TEXT NOT NULL,
 observed_at INTEGER NOT NULL, evidence_json TEXT NOT NULL
);
CREATE TABLE approval (
 approval_id TEXT PRIMARY KEY, task_key TEXT NOT NULL REFERENCES task(task_key),
 kind TEXT NOT NULL CHECK(kind IN ('execute','restart','split')),
 issue_uuid TEXT NOT NULL, plan_revision TEXT NOT NULL, workspace_path TEXT NOT NULL,
 actions_json TEXT NOT NULL, actor_id TEXT NOT NULL, issued_at INTEGER NOT NULL,
 expires_at INTEGER NOT NULL CHECK(expires_at=issued_at+1800), used_at INTEGER, revoked_at INTEGER,
 harness TEXT, model TEXT, provider TEXT
);
CREATE TABLE event (
 event_id TEXT PRIMARY KEY, task_key TEXT REFERENCES task(task_key),
 kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at INTEGER NOT NULL, external_receipt TEXT
);
