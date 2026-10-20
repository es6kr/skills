"""Explicit trusted-host completion gate. No default verifier or network adapter.

Neither model output nor runtime `completed` authenticates acceptance. Callers must
supply an independent evidence-checking verifier, never one derived from issue or
run text. Database ownership is the local trust boundary (not a signed service).
"""
import json
import time
from .model import canonical, digest


def adopt_existing_delivery(ledger, config, *, binding_path, outbox_id, issue_readback,
                            read_run, provenance, now):
    """Trusted recovery of a real durable Hermes binding; never a polling replay.

    binding_path is read-only. The caller authenticates file ownership and supplies
    a fresh exact issue GET plus independently authenticated run reader. Provenance
    must cite the source/audit; it is retained verbatim, not treated as authority.
    Only planning-only envelopes matching the current issue can be adopted.
    """
    import hashlib
    import sqlite3
    from pathlib import Path
    from contextlib import closing
    from .model import build_envelope, normalize_issue
    from dataclasses import asdict
    if not isinstance(provenance, dict) or not provenance or type(now) is not int or not callable(read_run):
        raise ValueError('adoption_invalid')
    source_path = Path(binding_path).resolve(strict=True)
    with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source:
        source.row_factory = sqlite3.Row
        row = source.execute('SELECT * FROM hermes_binding WHERE outbox_id=?', (outbox_id,)).fetchone()
        if row is None:
            raise ValueError('binding_required')
        row = dict(row)
    body = json.loads(row['request_json'])
    envelope = json.loads(body['input'])
    issue = normalize_issue(issue_readback, config)
    expected = asdict(build_envelope(config, issue, envelope['generation'], outbox_id))
    if (type(envelope['generation']) is not int or envelope['generation'] < 1
        or canonical(envelope) != canonical(expected) or config.assignee_id not in issue.assignees
        or row['envelope_sha256'] != digest(envelope)
        or row['request_body_sha256'] != hashlib.sha256(row['request_json'].encode()).hexdigest()
        or body['session_id'] != row['session_id']
        or row['session_id'] != 'pa-session-' + digest([row['scope'], outbox_id])
        or row['idempotency_key'] != 'pa-run-' + digest([row['scope'], outbox_id, digest(envelope)])
        or not isinstance(row['identity_revision'], str) or not row['identity_revision'].strip()
        or not isinstance(row['run_id'], str) or not row['run_id'].strip()
        or now < int(row['created_at'])):
        raise ValueError('adoption_mismatch')
    runtime = read_run(row['run_id'])
    if (not isinstance(runtime, dict) or runtime.get('run_id') != row['run_id']
        or runtime.get('session_id') != row['session_id'] or runtime.get('status') != 'completed'
        or runtime.get('result') in (None, '', {}, [])):
        raise ValueError('result_invalid')
    evidence = canonical(dict(source=str(source_path), binding=row, issue_readback=issue_readback,
                              run_readback=runtime, provenance=provenance, adopted_at=now))
    key = envelope['task_key']
    with ledger.transaction():
        ledger.connection.execute('''CREATE TABLE IF NOT EXISTS completion_adoption (
            outbox_id TEXT PRIMARY KEY REFERENCES outbox(outbox_id), evidence_json TEXT NOT NULL)''')
        for operation in ('UPDATE', 'DELETE'):
            ledger.connection.execute(f'''CREATE TRIGGER IF NOT EXISTS completion_adoption_{operation.lower()}_immutable
                BEFORE {operation} ON completion_adoption BEGIN SELECT RAISE(ABORT, 'completion_immutable'); END''')
        old = ledger.connection.execute('SELECT evidence_json FROM completion_adoption WHERE outbox_id=?', (outbox_id,)).fetchone()
        if old:
            previous = json.loads(old[0])
            current = json.loads(evidence)
            # The adoption timestamp is first-write immutable; repeated fresh identical evidence is safe.
            current['adopted_at'] = previous['adopted_at']
            if canonical(previous) != canonical(current):
                raise ValueError('adoption_mismatch')
            return
        if ledger.connection.execute('SELECT 1 FROM outbox WHERE outbox_id=?', (outbox_id,)).fetchone():
            raise ValueError('adoption_conflict')
        ledger._identity(config)
        ledger.connection.execute('''INSERT INTO task (task_key,plane_host,workspace_slug,project_uuid,
            issue_uuid,assignee_uuid,assignment_generation,issue_url,workspace_path,state,
            assignment_active,content_revision,hermes_session_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,'delivered',1,?,?,?,?)''',
            (key, config.host, config.workspace, config.project_id, issue.id, config.assignee_id,
             envelope['generation'], envelope['issue_url'], envelope['workspace_path'], issue.revision,
             row['session_id'], int(row['created_at']), now))
        ledger.connection.execute('''INSERT INTO outbox (outbox_id,task_key,payload_json,request_sha256,status,
            receiver_identity_revision,created_at,updated_at) VALUES(?,?,?,?,'delivered',?,?,?)''',
            (outbox_id, key, canonical(envelope), digest(envelope), row['identity_revision'], int(row['created_at']), now))
        from .model import Receipt
        receipt = Receipt(outbox_id, digest(envelope), row['identity_revision'], row['run_id'], row['session_id'], now, canonical(runtime))
        ledger.connection.execute('INSERT INTO delivery_receipt VALUES(?,?,?,?,?,?,?,?)',
            (outbox_id, receipt.request_sha256, receipt.receiver_identity_revision, receipt.run_id,
             receipt.session_id, receipt.status_readback, now, canonical(asdict(receipt))))
        ledger.connection.execute('INSERT INTO completion_adoption VALUES(?,?)', (outbox_id, evidence))
        ledger._event('adopted_delivery', dict(source=str(source_path), source_binding_sha256=digest(row),
                      provenance=provenance), now, key)


class CompletionGate:
    def __init__(self, ledger, *, verifier_id, verify, read_run, clock=time.time):
        if not isinstance(verifier_id, str) or not verifier_id.strip() or not callable(verify) or not callable(read_run):
            raise ValueError('verifier_required')
        self.ledger = ledger
        self.verifier_id = verifier_id
        self._verify = verify
        self._read_run = read_run
        self._clock = clock
        with ledger.transaction():
            ledger.connection.execute('''CREATE TABLE IF NOT EXISTS completion_contract (
                outbox_id TEXT PRIMARY KEY REFERENCES outbox(outbox_id), contract_json TEXT NOT NULL)''')
            ledger.connection.execute('''CREATE TABLE IF NOT EXISTS completion_pass (
                outbox_id TEXT PRIMARY KEY REFERENCES completion_contract(outbox_id),
                receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL)''')
            for table in ('completion_contract', 'completion_pass'):
                for operation in ('UPDATE', 'DELETE'):
                    ledger.connection.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_{operation.lower()}_immutable
                        BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'completion_immutable'); END''')

    def _binding(self, outbox_id):
        db = self.ledger.connection
        outbox = db.execute('SELECT * FROM outbox WHERE outbox_id=?', (outbox_id,)).fetchone()
        delivery = db.execute('SELECT * FROM delivery_receipt WHERE outbox_id=?', (outbox_id,)).fetchone()
        if outbox is None or delivery is None or outbox['status'] != 'delivered':
            raise ValueError('delivery_required')
        task = db.execute('SELECT * FROM task WHERE task_key=?', (outbox['task_key'],)).fetchone()
        envelope = json.loads(outbox['payload_json'])
        if (digest(envelope) != outbox['request_sha256']
            or delivery['request_sha256'] != outbox['request_sha256']
            or delivery['receiver_identity_revision'] != outbox['receiver_identity_revision']
            or canonical({k: delivery[k] for k in delivery.keys() if k != 'evidence_json'}) != delivery['evidence_json']
            or envelope['task_key'] != task['task_key'] or envelope['issue_id'] != task['issue_uuid']
            or envelope['outbox_id'] != outbox_id or envelope['generation'] != task['assignment_generation']
            or task['hermes_session_id'] != delivery['session_id']):
            raise ValueError('binding_mismatch')
        if not task['assignment_active'] or task['error_code']:
            raise ValueError('assignment_inactive')
        if task['content_revision'] != envelope['content_revision']:
            raise ValueError('revision_mismatch')
        return dict(task_key=task['task_key'], issue_id=task['issue_uuid'],
            plane_host=task['plane_host'], workspace=task['workspace_slug'], project_id=task['project_uuid'],
            content_revision=envelope['content_revision'], assignee_id=task['assignee_uuid'],
            generation=task['assignment_generation'], outbox_id=outbox_id,
            request_sha256=outbox['request_sha256'], receiver_identity_revision=delivery['receiver_identity_revision'],
            run_id=delivery['run_id'], session_id=delivery['session_id'])

    def register(self, outbox_id, criteria):
        """Trusted caller supplies explicit, task-scoped {criterion_id: requirement}."""
        if not isinstance(criteria, dict) or not criteria or any(
                not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
                for k, v in criteria.items()):
            raise ValueError('criteria_required')
        with self.ledger.transaction():
            contract = canonical(dict(binding=self._binding(outbox_id), criteria=criteria, verifier_id=self.verifier_id))
            old = self.ledger.connection.execute('SELECT contract_json FROM completion_contract WHERE outbox_id=?', (outbox_id,)).fetchone()
            if old:
                if old[0] != contract:
                    raise ValueError('contract_mismatch')
                return
            self.ledger.connection.execute('INSERT INTO completion_contract VALUES(?,?)', (outbox_id, contract))

    def receipt(self, outbox_id):
        row = self.ledger.connection.execute('SELECT * FROM completion_pass WHERE outbox_id=?', (outbox_id,)).fetchone()
        if row is None:
            raise ValueError('pass_required')
        data = json.loads(row['receipt_json'])
        if digest(data) != row['receipt_sha256'] or data.get('verdict') != 'PASS':
            raise ValueError('receipt_mismatch')
        return data

    def verify(self, outbox_id):
        row = self.ledger.connection.execute('SELECT contract_json FROM completion_contract WHERE outbox_id=?', (outbox_id,)).fetchone()
        if row is None:
            raise ValueError('criteria_required')
        contract = json.loads(row[0])
        binding = self._binding(outbox_id)
        if contract['binding'] != binding or contract['verifier_id'] != self.verifier_id:
            raise ValueError('contract_mismatch')
        runtime = self._read_run(binding['run_id'])
        if (not isinstance(runtime, dict) or runtime.get('run_id') != binding['run_id']
            or runtime.get('session_id') != binding['session_id'] or runtime.get('status') != 'completed'
            or runtime.get('result') in (None, '', {}, [])):
            raise ValueError('result_invalid')
        result_hash = digest(runtime['result'])
        existing = self.ledger.connection.execute('SELECT 1 FROM completion_pass WHERE outbox_id=?', (outbox_id,)).fetchone()
        if existing:
            receipt = self.receipt(outbox_id)
            if receipt['result_sha256'] != result_hash:
                raise ValueError('result_mismatch')
            return receipt
        context = dict(**binding, criteria=contract['criteria'], result=runtime['result'], result_sha256=result_hash)
        checks = self._verify(json.loads(canonical(context)))
        if (not isinstance(checks, dict) or set(checks) != set(contract['criteria'])
            or any(not isinstance(check, dict) or check.get('passed') is not True
                   or not isinstance(check.get('evidence'), str) or not check['evidence'].strip()
                   for check in checks.values())):
            raise ValueError('acceptance_failed')
        receipt = dict(**binding, verdict='PASS', criteria=contract['criteria'], checks=checks,
                       verifier_id=self.verifier_id, result_sha256=result_hash, verified_at=int(self._clock()))
        with self.ledger.transaction():
            if self._binding(outbox_id) != binding:
                raise ValueError('binding_mismatch')
            self.ledger.connection.execute('INSERT INTO completion_pass VALUES(?,?,?)', (outbox_id, canonical(receipt), digest(receipt)))
        return receipt


class PlaneCompletionFinalizer:
    def __init__(self, gate, config, transport, *, clock=time.time, max_age=1800):
        self.gate, self.config, self.transport = gate, config, transport
        self._clock, self.max_age = clock, max_age
        with gate.ledger.transaction():
            gate.ledger.connection.execute('''CREATE TABLE IF NOT EXISTS completion_intent (
                outbox_id TEXT PRIMARY KEY REFERENCES completion_pass(outbox_id),
                receipt_sha256 TEXT NOT NULL, original_state TEXT NOT NULL,
                target_state TEXT NOT NULL, created_at INTEGER NOT NULL)''')
            gate.ledger.connection.execute('''CREATE TABLE IF NOT EXISTS completion_readback (
                outbox_id TEXT PRIMARY KEY REFERENCES completion_intent(outbox_id),
                evidence_json TEXT NOT NULL, observed_at INTEGER NOT NULL)''')
            for table in ('completion_intent', 'completion_readback'):
                for operation in ('UPDATE', 'DELETE'):
                    gate.ledger.connection.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_{operation.lower()}_immutable
                        BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'completion_immutable'); END''')

    def finalize(self, outbox_id):
        from .model import normalize_issue, normalize_states
        receipt = self.gate.receipt(outbox_id)
        now = int(self._clock())
        if not receipt['verified_at'] <= now < receipt['verified_at'] + self.max_age:
            raise ValueError('receipt_stale')
        if (receipt['plane_host'], receipt['workspace'], receipt['project_id'], receipt['assignee_id']) != (
                self.config.host, self.config.workspace, self.config.project_id, self.config.assignee_id):
            raise ValueError('identity_mismatch')
        binding = self.gate._binding(outbox_id)
        if any(receipt.get(k) != v for k, v in binding.items()):
            raise ValueError('binding_mismatch')
        self.gate.verify(outbox_id)  # Fresh trusted run read; immutable result digest.
        db = self.gate.ledger.connection
        prefix = f'workspaces/{self.config.workspace}/projects/{self.config.project_id}/'
        path = prefix + 'issues/' + receipt['issue_id'] + '/'
        states = normalize_states(self.transport.request(prefix + 'states/', method='GET'))
        targets = [s.id for s in states.values() if s.group == 'completed' and not s.is_triage]
        if len(targets) != 1:
            raise ValueError('completed_state_ambiguous')
        target = targets[0]
        raw = self.transport.request(path, method='GET')
        issue = normalize_issue(raw, self.config)
        with self.gate.ledger.transaction():
            intent = db.execute('SELECT * FROM completion_intent WHERE outbox_id=?', (outbox_id,)).fetchone()
            if intent is None:
                if (issue.id != receipt['issue_id'] or issue.revision != receipt['content_revision']
                    or self.config.assignee_id not in issue.assignees
                    or issue.state_id not in states or states[issue.state_id].is_triage
                    or states[issue.state_id].group not in ('backlog', 'unstarted', 'started')):
                    raise ValueError('issue_mismatch')
                if self.gate._binding(outbox_id) != binding:
                    raise ValueError('binding_mismatch')
                db.execute('INSERT INTO completion_intent VALUES(?,?,?,?,?)',
                    (outbox_id, digest(receipt), issue.state_id, target, int(self._clock())))
        original_state = issue.state_id if intent is None else intent['original_state']
        if intent is not None and (intent['receipt_sha256'] != digest(receipt) or intent['target_state'] != target):
            raise ValueError('intent_mismatch')
        if intent is None:
            self.transport.request(path, method='PATCH', data={'state': target})
            raw = self.transport.request(path, method='GET')
            issue = normalize_issue(raw, self.config)
        before = normalize_issue(dict(raw, state=original_state), self.config)
        if (issue.id != receipt['issue_id'] or issue.state_id != target
            or before.revision != receipt['content_revision'] or self.config.assignee_id not in issue.assignees):
            raise ValueError('completion_readback_mismatch')
        with self.gate.ledger.transaction():
            db.execute('INSERT OR IGNORE INTO completion_readback VALUES(?,?,?)',
                (outbox_id, canonical(raw), int(self._clock())))
            db.execute("UPDATE task SET state='completed',updated_at=? WHERE task_key=?",
                (int(self._clock()), receipt['task_key']))
        return raw
