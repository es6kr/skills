"""Known-run reconciliation; injected fixtures are not operational run evidence."""
from dataclasses import asdict, replace
import os
from pathlib import Path
import tempfile
import unittest
from agent_assignment.ledger import Ledger
from agent_assignment.model import Receipt, canonical, digest
from test_agent_assignment_live_read import CONFIG
from test_agent_assignment_live_cycle import ISSUE, client_for, FakeReceiver


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'ledger.sqlite3')
        from agent_assignment.live_cycle import collect_once
        collect_once(CONFIG, client_for([]), self.db, now=100)
        collect_once(CONFIG, client_for([ISSUE]), self.db, now=101)
        with Ledger(self.db) as ledger:
            self.envelope = ledger.claim(ledger.pending()[0].outbox_id, 102)
            ledger.bind_receiver(self.envelope.outbox_id, FakeReceiver.identity_revision)
        status = dict(run_id='fixture-run', session_id='fixture-session', status='running')
        self.receiver = FakeReceiver()
        self.receiver.receipt = Receipt(self.envelope.outbox_id, digest(asdict(self.envelope)),
                                       self.receiver.identity_revision, status['run_id'],
                                       status['session_id'], 104, canonical(status))

    def test_binding_accessor_returns_only_copied_frozen_fields(self):
        with Ledger(self.db) as ledger:
            before = ledger.connection.total_changes
            binding = ledger.delivery_binding(self.envelope.outbox_id)
            self.assertEqual(set(binding), {'outbox_id', 'request_sha256', 'receiver_identity_revision', 'status'})
            self.assertEqual(binding['request_sha256'], digest(asdict(self.envelope)))
            binding['status'] = 'not-a-write'
            self.assertEqual(ledger.delivery_binding(self.envelope.outbox_id)['status'], 'sending')
            self.assertIsNone(ledger.delivery_binding('pa-' + '0' * 64))
            self.assertEqual(ledger.connection.total_changes, before)

    def test_known_run_recovers_sending_and_repeat_is_receipt_noop(self):
        from agent_assignment.live_cycle import reconcile_known
        self.assertEqual(reconcile_known(self.db, self.receiver,
                         outbox_id=self.envelope.outbox_id, now=105), 'delivered')
        with Ledger(self.db) as ledger:
            before = tuple(ledger.connection.execute('SELECT * FROM delivery_receipt').fetchone())
        self.assertEqual(reconcile_known(self.db, self.receiver,
                         outbox_id=self.envelope.outbox_id, now=106), 'delivered')
        with Ledger(self.db) as ledger:
            self.assertEqual(tuple(ledger.connection.execute('SELECT * FROM delivery_receipt').fetchone()), before)
        self.assertEqual(len(self.receiver.lookups), 1)
        self.assertEqual(self.receiver.submissions, [])

    def test_unknown_lookup_keeps_uncertain_without_any_submission(self):
        from agent_assignment.live_cycle import reconcile_known
        self.receiver.receipt = None
        for now in (105, 1000000):
            self.assertEqual(reconcile_known(self.db, self.receiver,
                             outbox_id=self.envelope.outbox_id, now=now), 'unresolved')
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.delivery_binding(self.envelope.outbox_id)['status'], 'delivery_uncertain')
            self.assertEqual(ledger.outbox_count(), 1)
        self.assertEqual(self.receiver.submissions, [])

    def test_receipt_mismatches_never_modify_another_outbox(self):
        from agent_assignment.live_cycle import reconcile_known
        original = self.receiver.receipt
        for fields in (dict(outbox_id='pa-' + '0' * 64), dict(request_sha256='wrong'),
                       dict(receiver_identity_revision='wrong'), dict(session_id='wrong')):
            self.receiver.receipt = replace(original, **fields)
            with self.subTest(fields=fields):
                self.assertEqual(reconcile_known(self.db, self.receiver,
                                 outbox_id=self.envelope.outbox_id, now=105), 'unresolved')
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.connection.execute('SELECT count(*) FROM delivery_receipt').fetchone()[0], 0)
        self.assertEqual(self.receiver.submissions, [])

    def test_receiver_scope_change_blocks_before_lookup(self):
        from agent_assignment.live_cycle import reconcile_known
        self.receiver.identity_revision = 'different-scope'
        self.assertEqual(reconcile_known(self.db, self.receiver,
                         outbox_id=self.envelope.outbox_id, now=105), 'runtime_unverified')
        self.assertEqual(self.receiver.lookups, [])
        self.assertEqual(self.receiver.submissions, [])

    def test_lookup_exception_is_not_permission_to_submit(self):
        from agent_assignment.live_cycle import reconcile_known
        def unavailable(*args):
            raise TimeoutError('fixture status unavailable')
        self.receiver.lookup = unavailable
        self.assertEqual(reconcile_known(self.db, self.receiver,
                         outbox_id=self.envelope.outbox_id, now=105), 'unresolved')
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.delivery_binding(self.envelope.outbox_id)['status'], 'delivery_uncertain')
        self.assertEqual(self.receiver.submissions, [])

    def test_unknown_outbox_never_queries_receiver(self):
        from agent_assignment.live_cycle import reconcile_known
        self.assertEqual(reconcile_known(self.db, self.receiver,
                         outbox_id='pa-' + '0' * 64, now=105), 'unresolved')
        self.assertEqual(self.receiver.lookups, [])

    def http_fixture(self):
        import test_agent_assignment_hermes_runs_integration as integration
        fixture = integration.HermesRunsIntegrationTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        return fixture

    def test_http_known_run_recovers_with_only_get_after_bad_readback(self):
        from agent_assignment.dispatch import dispatch_one
        from agent_assignment.live_cycle import reconcile_known
        fixture = self.http_fixture()
        fixture.status_change = dict(session_id='wrong')
        self.assertEqual(dispatch_one(fixture.db, fixture.receiver(), 2), 'delivery_uncertain')
        before = len(fixture.requests)
        fixture.status_change = {}
        path = str(Path(fixture.tmp.name) / 'ledger.db')
        self.assertEqual(reconcile_known(path, fixture.receiver(),
                         outbox_id=fixture.envelope.outbox_id, now=4), 'delivered')
        self.assertEqual([(r[0], r[1]) for r in fixture.requests[before:]], [('GET', '/v1/runs/run-1')])
        self.assertEqual(sum(r[0] == 'POST' for r in fixture.requests), 1)

    def test_http_lost_post_response_does_not_retry_after_reopen(self):
        from agent_assignment.dispatch import dispatch_one
        from agent_assignment.live_cycle import reconcile_known
        fixture = self.http_fixture()
        fixture.drop_post = True
        self.assertEqual(dispatch_one(fixture.db, fixture.receiver(), 2), 'delivery_uncertain')
        before = len(fixture.requests)
        path = str(Path(fixture.tmp.name) / 'ledger.db')
        for now in (4, 1000000):
            self.assertEqual(reconcile_known(path, fixture.receiver(),
                             outbox_id=fixture.envelope.outbox_id, now=now), 'unresolved')
        self.assertEqual(len(fixture.requests), before)
        self.assertEqual(sum(r[0] == 'POST' for r in fixture.requests), 1)
