"""Integration with a real stdlib loopback HTTP fixture; NOT live Hermes E2E."""
import json
from contextlib import closing
import sqlite3
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dataclasses import asdict, replace
from test_agent_assignment_policy import m, C, STATES, issue
from agent_assignment.dispatch import dispatch_one
from agent_assignment.ledger import Ledger


class HermesRunsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.binding_path = str(Path(self.tmp.name) / 'bindings.db')
        self.requests = []
        self.capabilities = {'object': 'hermes.api_server.capabilities', 'platform': 'hermes-agent',
                             'auth': {'type': 'bearer', 'required': True},
                             'features': {'run_submission': True, 'run_status': True,
                                          'runs_idempotency': {'supported': True, 'durable': True, 'retention_seconds': 86400}}}
        self.toolsets = {'object': 'list', 'platform': 'api_server', 'data': []}
        self.status_change = {}
        self.drop_post = False
        self.delay_post = False
        self.release_post = threading.Event()
        self.redirect = False
        self.candidate = {'run_id': 'run-1', 'status': 'started', 'replayed': False}
        self.post_code = 202
        self.get_code = 200
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def respond(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                try: self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
            def do_GET(self):
                owner.requests.append(('GET', self.path, self.headers.get('Authorization'), None))
                if self.path == '/v1/capabilities' and owner.redirect:
                    self.send_response(302)
                    self.send_header('Location', owner.url + '/redirect-target')
                    self.end_headers()
                elif self.path == '/v1/capabilities': self.respond(200, owner.capabilities)
                elif self.path == '/v1/toolsets': self.respond(200, owner.toolsets)
                elif self.path == '/v1/runs/run-1':
                    self.respond(owner.get_code, dict(run_id='run-1', session_id=owner.session, status='started') | owner.status_change)
                else: self.respond(404, {})
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length'])).decode()
                owner.requests.append(('POST', self.path, self.headers.get('Authorization'), body))
                # A separate connection proves binding committed BEFORE any POST.
                with closing(sqlite3.connect(owner.binding_path)) as db:
                    db.row_factory = sqlite3.Row
                    owner.persisted_at_post = dict(db.execute('SELECT * FROM hermes_binding').fetchone())
                owner.assertEqual(owner.persisted_at_post['request_json'], body)
                owner.assertEqual(owner.persisted_at_post['idempotency_key'], self.headers['Idempotency-Key'])
                owner.session = json.loads(body)['session_id']
                if owner.delay_post:
                    owner.release_post.wait(1)
                if owner.drop_post:
                    self.close_connection = True
                    return
                self.respond(owner.post_code, owner.candidate)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        def stop():
            self.release_post.set()
            self.server.shutdown(); self.server.server_close(); thread.join()
        self.addCleanup(stop)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.db = Ledger(str(Path(self.tmp.name) / 'ledger.db'))
        self.addCleanup(self.db.__exit__, None, None, None)
        self.db.apply(C, m.Snapshot((), STATES, True), 0)
        self.db.apply(C, m.Snapshot((issue(),), STATES, True), 1)
        self.envelope = self.db.pending()[0]

    def test_invalid_capabilities_or_dangerous_tools_never_post(self):
        from agent_assignment.dispatch import ReceiverUnavailable
        cases = [('supported', False), ('durable', False), ('retention_seconds', 0),
                 ('retention_seconds', True)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                old = self.capabilities['features']['runs_idempotency'][field]
                self.capabilities['features']['runs_idempotency'][field] = value
                with self.assertRaises(ReceiverUnavailable): self.receiver().submit(self.envelope)
                self.capabilities['features']['runs_idempotency'][field] = old
        self.toolsets['data'] = [{'name': 'terminal', 'enabled': True, 'tools': ['terminal']}]
        with self.assertRaises(ReceiverUnavailable): self.receiver().submit(self.envelope)
        self.assertFalse(any(r[0] == 'POST' for r in self.requests))

    def test_wrong_exact_run_session_or_status_never_returns_receipt(self):
        from agent_assignment.dispatch import DeliveryUncertain
        receiver = self.receiver()
        receipt = receiver.submit(self.envelope)
        for change in [{'run_id': 'wrong'}, {'session_id': 'wrong'}, {'status': 'healthy'}, {'status': None}]:
            self.status_change = change
            with self.subTest(change=change), self.assertRaises(DeliveryUncertain):
                receiver.lookup(receipt.outbox_id, receipt.request_sha256)
        self.status_change = {'status': 'failed'}
        self.assertEqual(json.loads(receiver.lookup(receipt.outbox_id, receipt.request_sha256).status_readback)['status'], 'failed')
        self.assertEqual(sum(r[0] == 'POST' for r in self.requests), 1)

    def test_unsafe_endpoint_or_missing_runtime_verifier_is_rejected_before_network(self):
        from agent_assignment.hermes_runs import HermesRunsReceiver
        for url in ['https://remote.invalid', 'http://localhost:8642', 'http://127.0.0.1:8642/evil',
                    'http://user:password@127.0.0.1:8642', 'http://127.0.0.1:8642?x=1']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                HermesRunsReceiver(url, 'fixture-only-token', self.binding_path,
                                   identity_revision='fixture-runtime-v1', verify_runtime=lambda: 'fixture-runtime-v1')
        with self.assertRaises(ValueError):
            HermesRunsReceiver(self.url, '', self.binding_path,
                               identity_revision='fixture-runtime-v1', verify_runtime=None)
        self.assertEqual(self.requests, [])

    def test_redirect_is_not_followed_with_dedicated_auth(self):
        from agent_assignment.dispatch import DeliveryUncertain
        self.redirect = True
        with self.assertRaises(DeliveryUncertain): self.receiver().submit(self.envelope)
        self.assertEqual([r[1] for r in self.requests], ['/v1/capabilities'])

    def test_response_loss_binding_is_immutable_and_never_fresh_retried_after_reopen(self):
        from agent_assignment.dispatch import DeliveryUncertain
        self.drop_post = True
        self.assertEqual(dispatch_one(self.db, self.receiver(), 2), 'delivery_uncertain')
        with closing(sqlite3.connect(self.binding_path)) as db:
            before = db.execute('SELECT request_json,idempotency_key,session_id,state,run_id FROM hermes_binding').fetchone()
            self.assertEqual(before[3:], ('uncertain', None))
            for column in ['request_json', 'idempotency_key', 'session_id', 'scope', 'envelope_sha256', 'request_body_sha256', 'retention_seconds', 'created_at']:
                with self.subTest(column=column), self.assertRaises(sqlite3.IntegrityError):
                    db.execute('UPDATE hermes_binding SET ' + column + "='changed'")
            db.rollback()
        reopened = self.receiver()
        reopened._clock = lambda: 999999
        with self.assertRaises(DeliveryUncertain): reopened.submit(self.envelope)
        self.assertIsNone(reopened.lookup(self.envelope.outbox_id, m.digest(asdict(self.envelope))))
        self.assertEqual(dispatch_one(self.db, reopened, 999999), 'idle')
        self.assertEqual(sum(r[0] == 'POST' for r in self.requests), 1)
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM delivery_receipt').fetchone()[0], 0)
        with closing(sqlite3.connect(self.binding_path)) as db:
            self.assertEqual(db.execute('SELECT request_json,idempotency_key,session_id,state,run_id FROM hermes_binding').fetchone(), before)

    def test_known_run_survives_bad_readback_and_runtime_change_without_post_retry(self):
        from agent_assignment.dispatch import DeliveryUncertain, ReceiverUnavailable
        self.status_change = {'session_id': 'wrong'}
        self.assertEqual(dispatch_one(self.db, self.receiver(), 2), 'delivery_uncertain')
        with closing(sqlite3.connect(self.binding_path)) as db:
            self.assertEqual(db.execute('SELECT run_id FROM hermes_binding').fetchone()[0], 'run-1')
        reopened = self.receiver()
        self.status_change = {}
        reopened._verify_runtime = lambda: 'different-runtime'
        with self.assertRaises(ReceiverUnavailable):
            reopened.lookup(self.envelope.outbox_id, m.digest(asdict(self.envelope)))
        reopened._verify_runtime = lambda: 'fixture-runtime-v1'
        receipt = reopened.lookup(self.envelope.outbox_id, m.digest(asdict(self.envelope)))
        self.db.record_receipt(receipt)
        self.assertEqual(self.db.task(issue().id, 1)['state'], 'delivered')
        self.assertEqual(sum(r[0] == 'POST' for r in self.requests), 1)

    def test_execution_envelope_and_nondurable_storage_are_rejected_without_post(self):
        from agent_assignment.dispatch import ReceiverUnavailable
        for envelope in [replace(self.envelope, execute_allowed=True),
                         replace(self.envelope, allowed_actions=('implement',))]:
            with self.subTest(envelope=envelope), self.assertRaises(ReceiverUnavailable):
                self.receiver().submit(envelope)
        from agent_assignment.hermes_runs import HermesRunsReceiver
        for path in ['', ':memory:', 'file:binding?mode=memory']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                HermesRunsReceiver(self.url, 'fixture-only-token', path,
                                   identity_revision='fixture-runtime-v1', verify_runtime=lambda: 'fixture-runtime-v1')
        self.assertEqual(self.requests, [])

    def test_candidate_run_identifier_is_encoded_as_exact_single_path_segment(self):
        from agent_assignment.dispatch import DeliveryUncertain
        self.candidate['run_id'] = 'run/other?secret=1'
        with self.assertRaises(DeliveryUncertain): self.receiver().submit(self.envelope)
        self.assertEqual(self.requests[-1][1], '/v1/runs/run%2Fother%3Fsecret%3D1')
        with closing(sqlite3.connect(self.binding_path)) as db:
            self.assertEqual(db.execute('SELECT run_id FROM hermes_binding').fetchone()[0], 'run/other?secret=1')

    def test_local_canonical_body_integrity_is_checked_before_readback(self):
        from agent_assignment.dispatch import DeliveryUncertain
        receipt = self.receiver().submit(self.envelope)
        with closing(sqlite3.connect(self.binding_path)) as db:
            # DB owner can drop triggers: not tamper-proof, but digest mismatch must fail closed.
            db.execute('DROP TRIGGER hermes_binding_immutable')
            db.execute("UPDATE hermes_binding SET request_json='{}'")
            db.commit()
        count = len(self.requests)
        with self.assertRaises(DeliveryUncertain):
            self.receiver().lookup(receipt.outbox_id, receipt.request_sha256)
        self.assertEqual(len(self.requests), count)

    def test_http_conflict_preserves_unknown_admission_and_does_not_retry(self):
        from agent_assignment.dispatch import DeliveryUncertain
        self.post_code = 409
        self.assertEqual(dispatch_one(self.db, self.receiver(), 2), 'delivery_uncertain')
        with self.assertRaises(DeliveryUncertain): self.receiver().submit(self.envelope)
        self.assertEqual(sum(r[0] == 'POST' for r in self.requests), 1)
        with closing(sqlite3.connect(self.binding_path)) as db:
            self.assertEqual(db.execute('SELECT state,run_id FROM hermes_binding').fetchone(), ('uncertain', None))

    def test_exact_get_404_preserves_candidate_without_new_post(self):
        from agent_assignment.dispatch import DeliveryUncertain
        self.get_code = 404
        receiver = self.receiver()
        with self.assertRaises(DeliveryUncertain): receiver.submit(self.envelope)
        with self.assertRaises(DeliveryUncertain): self.receiver().submit(self.envelope)
        with closing(sqlite3.connect(self.binding_path)) as db:
            self.assertEqual(db.execute('SELECT run_id FROM hermes_binding').fetchone()[0], 'run-1')
        self.assertEqual(sum(r[0] == 'POST' for r in self.requests), 1)

    def test_changed_payload_or_credential_scope_cannot_replace_binding(self):
        from agent_assignment.dispatch import DeliveryUncertain
        from agent_assignment.hermes_runs import HermesRunsReceiver
        receipt = self.receiver().submit(self.envelope)
        with self.assertRaises(DeliveryUncertain): self.receiver().submit(replace(self.envelope, untrusted_body='changed'))
        other = HermesRunsReceiver(self.url, 'rotated-fixture-token', self.binding_path,
                                   identity_revision='fixture-runtime-v1', verify_runtime=lambda: 'fixture-runtime-v1')
        count = len(self.requests)
        with self.assertRaises(DeliveryUncertain): other.lookup(receipt.outbox_id, receipt.request_sha256)
        with self.assertRaises(DeliveryUncertain): self.receiver().lookup(receipt.outbox_id, 'wrong-hash')
        self.assertEqual(len(self.requests), count)
        self.assertEqual(sum(r[0] == 'POST' for r in self.requests), 1)

    def test_runtime_identity_is_checked_before_disclosing_auth_to_listener(self):
        from agent_assignment.dispatch import ReceiverUnavailable
        receiver = self.receiver()
        receiver._verify_runtime = lambda: 'wrong-home-profile'
        with self.assertRaises(ReceiverUnavailable): receiver.submit(self.envelope)
        self.assertEqual(self.requests, [])

    def test_post_timeout_keeps_fixed_request_without_automatic_retry(self):
        from agent_assignment.dispatch import DeliveryUncertain
        self.delay_post = True
        receiver = self.receiver(timeout=0.03)
        self.assertEqual(dispatch_one(self.db, receiver, 2), 'delivery_uncertain')
        self.release_post.set()
        with self.assertRaises(DeliveryUncertain): self.receiver().submit(self.envelope)
        self.assertEqual(sum(r[0] == 'POST' for r in self.requests), 1)
        with closing(sqlite3.connect(self.binding_path)) as db:
            self.assertEqual(db.execute('SELECT state,run_id FROM hermes_binding').fetchone(), ('uncertain', None))

    def receiver(self, **kwargs):
        from agent_assignment.hermes_runs import HermesRunsReceiver
        return HermesRunsReceiver(self.url, 'fixture-only-token', self.binding_path,
                                  identity_revision='fixture-runtime-v1',
                                  verify_runtime=lambda: 'fixture-runtime-v1', clock=lambda: 3, **kwargs)

    def test_admission_is_durable_before_post_and_exact_same_auth_readback_before_receipt(self):
        receiver = self.receiver()
        self.assertEqual(dispatch_one(self.db, receiver, 2), 'delivered')
        self.assertEqual([(r[0], r[1]) for r in self.requests],
                         [('GET', '/v1/capabilities'), ('GET', '/v1/toolsets'), ('POST', '/v1/runs'), ('GET', '/v1/runs/run-1')])
        self.assertTrue(all(r[2] == 'Bearer fixture-only-token' for r in self.requests))
        body = json.loads(self.persisted_at_post['request_json'])
        self.assertEqual(set(body), {'input', 'instructions', 'session_id'})
        self.assertEqual(json.loads(body['input']), asdict(self.envelope) | {'allowed_actions': list(self.envelope.allowed_actions)})
        self.assertEqual(self.persisted_at_post['state'], 'uncertain')
        self.assertEqual(self.persisted_at_post['identity_revision'], receiver.identity_revision)
        receipt = receiver.lookup(self.envelope.outbox_id, m.digest(asdict(self.envelope)))
        self.assertEqual(receipt.run_id, 'run-1')
        self.assertEqual(receipt.session_id, body['session_id'])
        self.assertEqual(receipt.request_sha256, m.digest(asdict(self.envelope)))
