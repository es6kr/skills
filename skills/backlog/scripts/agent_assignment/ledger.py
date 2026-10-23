"""Single-host SQLite ledger. No network, worker execution, or credentials."""
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import json
import sqlite3
import uuid
from .model import (Envelope, canonical, digest, task_key, build_envelope, eligible)


class Ledger:
    def __init__(self, path: str):
        self._connection = sqlite3.connect(path, timeout=5, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute('PRAGMA foreign_keys=ON')
        self._connection.execute('PRAGMA busy_timeout=5000')
        self._connection.execute('PRAGMA journal_mode=WAL')
        self._connection.execute('PRAGMA synchronous=FULL')
        version = self._connection.execute('PRAGMA user_version').fetchone()[0]
        if version == 0:
            # Serialize migration, including the version recheck, across fresh connections.
            with self.transaction():
                if self._connection.execute('PRAGMA user_version').fetchone()[0] == 0:
                    for sql in Path(__file__).with_name('schema.sql').read_text(encoding='utf-8').split(';'):
                        if sql.strip():
                            self._connection.execute(sql)
        elif version != 1:
            self._connection.close()
            raise ValueError('schema_version')

    @property
    def connection(self):
        """Test setup/inspection only; no approval input adapter is exposed."""
        return self._connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._connection.close()

    @contextmanager
    def transaction(self):
        self._connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            raise

    def _event(self, kind, payload, now, key=None):
        self._connection.execute('INSERT INTO event(event_id,task_key,kind,payload_json,created_at) VALUES(?,?,?,?,?)',
                                 (str(uuid.uuid4()), key, kind, canonical(payload), now))

    def _identity(self, config):
        identity = (config.host, config.workspace, config.project_id, config.assignee_id)
        row = self._connection.execute('SELECT * FROM identity WHERE singleton=1').fetchone()
        if row is None:
            self._connection.execute('INSERT INTO identity(singleton,plane_host,workspace_slug,project_uuid,assignee_uuid) VALUES(1,?,?,?,?)', identity)
            return False
        if tuple(row[k] for k in ('plane_host','workspace_slug','project_uuid','assignee_uuid')) != identity:
            raise ValueError('identity_mismatch')
        return bool(row['baseline_ready'])

    def task(self, issue_id, generation):
        row = self._connection.execute('SELECT * FROM task WHERE issue_uuid=? AND assignment_generation=?', (issue_id, generation)).fetchone()
        return dict(row) if row else None

    def outbox_count(self):
        return self._connection.execute('SELECT count(*) FROM outbox').fetchone()[0]

    def _create_task(self, config, issue, generation, baseline, now):
        key = task_key(config, issue.id, generation)
        envelope = build_envelope(config, issue, generation, 'pa-' + key)
        state = 'observed' if baseline or config.repo else 'needs_context'
        self._connection.execute('''INSERT INTO task(task_key,plane_host,workspace_slug,project_uuid,issue_uuid,
            assignee_uuid,assignment_generation,issue_url,workspace_path,state,assignment_active,content_revision,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?,?)''',
            (key, config.host, config.workspace, config.project_id, issue.id, config.assignee_id,
             generation, envelope.issue_url, config.repo, state, issue.revision, now, now))
        return key

    def _queue(self, config, issue, generation, now):
        key = task_key(config, issue.id, generation)
        task = self.task(issue.id, generation)
        if task['state'] not in ('observed', 'needs_context') or not config.repo or not eligible(issue, config, self._states):
            return
        envelope = build_envelope(config, issue, generation, 'pa-' + key)
        payload = asdict(envelope)
        self._connection.execute('''INSERT OR IGNORE INTO outbox(outbox_id,task_key,payload_json,request_sha256,status,created_at,updated_at)
                                    VALUES(?,?,?,?,'pending',?,?)''',
                                 (envelope.outbox_id, key, canonical(payload), digest(payload), now, now))
        self._connection.execute("UPDATE task SET state='queued',workspace_path=?,updated_at=? WHERE task_key=?", (config.repo, now, key))

    def apply(self, config, snapshot, now):
        if type(snapshot.complete) is not bool:
            raise ValueError('schema_error')
        if not snapshot.complete:
            return
        # Validate, do not repair, public normalized input before any ledger mutation.
        from .model import Issue, normalize_issue, normalize_states
        for issue in snapshot.issues:
            if not isinstance(issue, Issue) or not isinstance(issue.assignees, tuple):
                raise ValueError('schema_error')
            normalized = normalize_issue(dict(
                id=issue.id, project=issue.project_id, assignees=list(issue.assignees),
                state=issue.state_id, sequence_id=issue.sequence_id, name=issue.title,
                description_stripped=issue.body), config)
            if normalized != issue:
                raise ValueError('schema_error')
        normalize_states([asdict(state) for state in snapshot.states.values()])
        if any(key != state.id for key, state in snapshot.states.items()):
            raise ValueError('schema_error')
        if not snapshot.states or any(x.state_id not in snapshot.states or x.project_id != config.project_id for x in snapshot.issues):
            raise ValueError('schema_error')
        if len({x.id for x in snapshot.issues}) != len(snapshot.issues):
            raise ValueError('snapshot_conflict')
        with self.transaction():
            ready = self._identity(config)
            self._states = snapshot.states
            seen = set()
            for issue in snapshot.issues:
                seen.add(issue.id)
                assigned = config.assignee_id in issue.assignees
                prev = self._connection.execute('SELECT * FROM observation WHERE issue_uuid=?', (issue.id,)).fetchone()
                if prev is None and not assigned:
                    continue
                generation = prev['generation'] if prev else 1
                baseline = prev['baseline'] if prev else int(not ready)
                if assigned and (prev is None or not prev['assigned']):
                    if prev:
                        generation += 1
                        baseline = 0
                    self._create_task(config, issue, generation, baseline, now)
                self._connection.execute('''INSERT INTO observation VALUES(?,?,?,?,?,?) ON CONFLICT(issue_uuid) DO UPDATE SET
                    generation=excluded.generation,assigned=excluded.assigned,baseline=excluded.baseline,
                    content_revision=excluded.content_revision,last_seen_at=excluded.last_seen_at''',
                    (issue.id, generation, int(assigned), baseline, issue.revision, now))
                key = task_key(config, issue.id, generation)
                if not assigned:
                    self._unassign(key, now, 'assignee_removed')
                    continue
                self._connection.execute('UPDATE task SET assignment_active=1,content_revision=?,updated_at=?,error_code=? WHERE task_key=?',
                                         (issue.revision, now, None if eligible(issue, config, snapshot.states) else 'ineligible', key))
                if not baseline:
                    self._queue(config, issue, generation, now)
            for prev in self._connection.execute('SELECT * FROM observation WHERE assigned=1').fetchall():
                if prev['issue_uuid'] not in seen:
                    self._connection.execute('UPDATE observation SET assigned=0 WHERE issue_uuid=?', (prev['issue_uuid'],))
                    self._unassign(task_key(config, prev['issue_uuid'], prev['generation']), now, 'absent_from_complete_snapshot')
            self._connection.execute('UPDATE identity SET baseline_ready=1,last_complete_at=? WHERE singleton=1', (now,))
            self._event('complete_snapshot', dict(issues=[asdict(x) for x in snapshot.issues], states={k:asdict(v) for k,v in snapshot.states.items()}), now)

    def _unassign(self, key, now, code):
        self._connection.execute("UPDATE outbox SET status='cancelled',error_code=?,updated_at=? WHERE task_key=? AND status='pending'", (code, now, key))
        self._connection.execute("""UPDATE task SET assignment_active=0,error_code=?,updated_at=?,
            state=CASE WHEN state IN ('observed','queued','needs_context') THEN 'unassigned' ELSE state END WHERE task_key=?""", (code, now, key))

    @staticmethod
    def _envelope(row):
        data = json.loads(row['payload_json'])
        data['allowed_actions'] = tuple(data['allowed_actions'])
        return Envelope(**data)

    def pending(self):
        return [self._envelope(row) for row in self._connection.execute('''SELECT o.* FROM outbox o JOIN task t USING(task_key)
            WHERE o.status='pending' AND t.assignment_active=1 AND t.error_code IS NULL AND t.state='queued' ORDER BY o.created_at,o.outbox_id''')]

    def claim(self, outbox_id, now):
        with self.transaction():
            row = self._connection.execute('''SELECT o.* FROM outbox o JOIN task t USING(task_key)
                WHERE o.outbox_id=? AND o.status='pending' AND t.assignment_active=1
                AND t.state='queued' AND t.error_code IS NULL''', (outbox_id,)).fetchone()
            if row is None:
                return None
            changed = self._connection.execute("""UPDATE outbox SET status='sending',attempt_count=attempt_count+1,
                attempt_started_at=?,updated_at=? WHERE outbox_id=? AND status='pending'""", (now, now, outbox_id)).rowcount
            return self._envelope(row) if changed == 1 else None

    def bind_receiver(self, outbox_id, identity_revision):
        if not isinstance(identity_revision, str) or not identity_revision.strip():
            raise ValueError('receipt_mismatch')
        with self.transaction():
            changed = self._connection.execute("""UPDATE outbox SET receiver_identity_revision=?
                WHERE outbox_id=? AND status='sending' AND receiver_identity_revision IS NULL""",
                (identity_revision, outbox_id)).rowcount
            if changed != 1:
                raise ValueError('receipt_mismatch')

    def record_receipt(self, receipt):
        from .model import Receipt
        if not isinstance(receipt, Receipt):
            raise ValueError('receipt_mismatch')
        evidence = canonical(asdict(receipt))
        with self.transaction():
            old = self._connection.execute('SELECT evidence_json FROM delivery_receipt WHERE outbox_id=?', (receipt.outbox_id,)).fetchone()
            if old:
                if old[0] != evidence:
                    raise ValueError('receipt_mismatch')
                return
            row = self._connection.execute('SELECT * FROM outbox WHERE outbox_id=?', (receipt.outbox_id,)).fetchone()
            try:
                status = json.loads(receipt.status_readback)
            except (ValueError, TypeError):
                raise ValueError('receipt_mismatch') from None
            if (row is None or row['status'] not in ('sending', 'delivery_uncertain')
                or row['request_sha256'] != receipt.request_sha256
                or not row['receiver_identity_revision']
                or row['receiver_identity_revision'] != receipt.receiver_identity_revision
                or not isinstance(receipt.run_id, str) or not receipt.run_id.strip()
                or not isinstance(receipt.session_id, str) or not receipt.session_id.strip()
                or type(receipt.observed_at) is not int
                or row['attempt_started_at'] is None or receipt.observed_at < row['attempt_started_at']
                or not isinstance(status, dict) or status.get('run_id') != receipt.run_id
                or status.get('session_id') != receipt.session_id
                or status.get('status') not in ('started','queued','running','completed','failed','interrupted','cancelled')):
                raise ValueError('receipt_mismatch')
            self._connection.execute('INSERT INTO delivery_receipt VALUES(?,?,?,?,?,?,?,?)',
                (receipt.outbox_id, receipt.request_sha256, receipt.receiver_identity_revision,
                 receipt.run_id, receipt.session_id, receipt.status_readback, receipt.observed_at, evidence))
            self._connection.execute("UPDATE outbox SET status='delivered',updated_at=?,error_code=NULL WHERE outbox_id=?", (receipt.observed_at, receipt.outbox_id))
            self._connection.execute("UPDATE task SET state='delivered',hermes_session_id=?,updated_at=?,error_code=NULL WHERE task_key=?",
                                     (receipt.session_id, receipt.observed_at, row['task_key']))

    def approve(self, task_key, plan_revision, workspace_path, actions, approval_id, actor_id, now):
        self._approve('execute', task_key, plan_revision, workspace_path, actions, approval_id, actor_id, now)

    def approve_restart(self, task_key, plan_revision, workspace_path, approval_id, actor_id, now):
        self._approve('restart', task_key, plan_revision, workspace_path, ('restart',), approval_id, actor_id, now)

    def _approve(self, kind, key, revision, workspace, actions, approval_id, actor_id, now):
        # GUARD: Test-only trusted-call boundary; strings are NOT human authentication.
        # No CLI/model/issue-input path may call this without a future authenticated adapter.
        from .model import absolute_workspace
        if (not all(isinstance(x, str) and x.strip() for x in (key, revision, workspace, approval_id, actor_id))
            or not absolute_workspace(workspace) or type(now) is not int
            or not isinstance(actions, tuple) or not actions
            or any(not isinstance(x, str) for x in actions)
            or len(set(actions)) != len(actions)
            or not set(actions) <= ({'restart'} if kind == 'restart' else {'implement','verify','test','deploy'})):
            raise ValueError('approval_invalid')
        with self.transaction():
            task = self._connection.execute('SELECT * FROM task WHERE task_key=?', (key,)).fetchone()
            if (task is None or not task['assignment_active'] or task['plan_revision'] != revision
                or task['workspace_path'] != workspace
                or (kind == 'execute' and task['state'] != 'awaiting_approval')):
                raise ValueError('approval_invalid')
            try:
                self._connection.execute('''INSERT INTO approval(approval_id,task_key,kind,issue_uuid,plan_revision,
                    workspace_path,actions_json,actor_id,issued_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (approval_id, key, kind, task['issue_uuid'], revision, workspace, canonical(actions), actor_id, now, now+1800))
            except sqlite3.IntegrityError:
                raise ValueError('approval_invalid') from None

    @staticmethod
    def _approval_matches(approval, task, revision, workspace, action, now):
        return bool(approval and task and task['assignment_active']
                    and task['plan_revision'] == revision and task['workspace_path'] == workspace
                    and approval['plan_revision'] == revision and approval['workspace_path'] == workspace
                    and action in json.loads(approval['actions_json'])
                    and approval['used_at'] is None and approval['revoked_at'] is None
                    and approval['issued_at'] <= now < approval['expires_at'])

    def execution_allowed(self, task_key, plan_revision, workspace_path, action, now):
        """Pure policy check, NOT an execution token or atomic approval consumer."""
        if type(now) is not int:
            return False
        task = self._connection.execute('SELECT * FROM task WHERE task_key=?', (task_key,)).fetchone()
        if task is None or task['state'] != 'awaiting_approval' or task['error_code']:
            return False
        approvals = self._connection.execute("SELECT * FROM approval WHERE task_key=? AND kind='execute'", (task_key,)).fetchall()
        return any(self._approval_matches(a, task, plan_revision, workspace_path, action, now) for a in approvals)

    def restart(self, config, issue_id, approval_id, now):
        from .model import Issue, State
        if type(now) is not int:
            raise ValueError('approval_invalid')
        with self.transaction():
            self._identity(config)
            observation = self._connection.execute('SELECT * FROM observation WHERE issue_uuid=?', (issue_id,)).fetchone()
            if not observation or not observation['assigned']:
                raise ValueError('assignment_inactive')
            task = self.task(issue_id, observation['generation'])
            active = self._connection.execute("""SELECT 1 FROM task WHERE issue_uuid=? AND
                (state IN ('running','verifying') OR
                ((worker_runtime_id IS NOT NULL OR worker_terminal_id IS NOT NULL OR worker_session_id IS NOT NULL)
                 AND state NOT IN ('completed','failed')))""", (issue_id,)).fetchone()
            if active:
                raise ValueError('active_worker')
            # No authenticated previous-run termination/audit adapter exists in Phase 1.
            # Approval alone cannot resolve a claimed, uncertain, or accepted admission.
            previous_run = self._connection.execute("""SELECT 1 FROM task t
                LEFT JOIN outbox o USING(task_key) WHERE t.issue_uuid=? AND
                (o.status IN ('sending','delivery_uncertain','delivered') OR
                 t.state IN ('delivered','planning','delivery_uncertain') OR
                 t.hermes_session_id IS NOT NULL) LIMIT 1""", (issue_id,)).fetchone()
            if previous_run:
                raise ValueError('previous_run_unverified')
            approval = self._connection.execute("SELECT * FROM approval WHERE approval_id=? AND task_key=? AND kind='restart'", (approval_id, task['task_key'])).fetchone()
            if not self._approval_matches(approval, task, task['plan_revision'], config.repo, 'restart', now):
                raise ValueError('approval_invalid')
            latest = self._connection.execute("SELECT payload_json FROM event WHERE kind='complete_snapshot' ORDER BY rowid DESC LIMIT 1").fetchone()
            data = json.loads(latest[0]) if latest else {}
            raw = next((x for x in data.get('issues', []) if x['id'] == issue_id), None)
            if raw is None:
                raise ValueError('assignment_inactive')
            raw['assignees'] = tuple(raw['assignees'])
            issue = Issue(**raw)
            self._states = {k: State(**v) for k,v in data['states'].items()}
            if not eligible(issue, config, self._states):
                raise ValueError('assignment_ineligible')
            changed = self._connection.execute('UPDATE approval SET used_at=? WHERE approval_id=? AND used_at IS NULL AND revoked_at IS NULL', (now, approval_id)).rowcount
            if changed != 1:
                raise ValueError('approval_invalid')
            # Cancel old pending admission; retain all prior sessions/receipts.
            self._connection.execute("UPDATE outbox SET status='cancelled',error_code='explicit_restart',updated_at=? WHERE task_key=? AND status='pending'", (now, task['task_key']))
            self._connection.execute('UPDATE task SET assignment_active=0,updated_at=? WHERE task_key=?', (now, task['task_key']))
            generation = observation['generation'] + 1
            self._create_task(config, issue, generation, False, now)
            self._queue(config, issue, generation, now)
            self._connection.execute('UPDATE observation SET generation=?,baseline=0 WHERE issue_uuid=?', (generation, issue_id))
            self._event('restart', {'approval_id': approval_id}, now, task['task_key'])
            return generation

    def recover(self, now):
        with self.transaction():
            rows = self._connection.execute("SELECT outbox_id FROM outbox WHERE status='sending'").fetchall()
            for row in rows:
                self._uncertain(row['outbox_id'], now, 'recovered_sending')

    def _uncertain(self, outbox_id, now, code):
        self._connection.execute("UPDATE outbox SET status='delivery_uncertain',error_code=?,updated_at=? WHERE outbox_id=? AND status='sending'", (code, now, outbox_id))
        self._connection.execute("""UPDATE task SET state='delivery_uncertain',error_code=?,updated_at=? WHERE task_key IN
            (SELECT task_key FROM outbox WHERE outbox_id=? AND status='delivery_uncertain')""", (code, now, outbox_id))
