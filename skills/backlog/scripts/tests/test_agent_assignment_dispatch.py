import unittest
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from test_agent_assignment_policy import m, C, I, STATES, issue
from agent_assignment.ledger import Ledger
from agent_assignment.dispatch import dispatch_one, DisabledReceiver, DeliveryUncertain, ReceiverUnavailable

class FakeReceiver:
    identity_revision = 'offline-fake-v1'
    def __init__(self, change=None, lost=False):
        self.calls = 0
        self.change = change or {}
        self.lost = lost
    def submit(self, envelope):
        self.calls += 1
        if self.lost: raise DeliveryUncertain('accepted_then_timeout')
        return replace(m.Receipt(envelope.outbox_id, m.digest(asdict(envelope)), self.identity_revision,
                                 'run1', 'session1', 3, m.canonical(dict(run_id='run1', session_id='session1', status='started'))), **self.change)
    def lookup(self, outbox_id, request_sha256): return None

class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name)/'db')
        self.db = Ledger(self.path)
        self.addCleanup(self.db.__exit__, None, None, None)
        self.db.apply(C, m.Snapshot((), STATES, True), 0)
        self.db.apply(C, m.Snapshot((issue(),), STATES, True), 1)

    def test_disabled_preserves_pending_and_uncertain_never_resends(self):
        with self.assertRaises(ReceiverUnavailable): DisabledReceiver().submit(self.db.pending()[0])
        self.assertIsNone(DisabledReceiver().lookup('x', 'x'))
        self.assertEqual(dispatch_one(self.db, DisabledReceiver(), 2), 'disabled')
        self.assertEqual(len(self.db.pending()), 1)
        sender = FakeReceiver(lost=True)
        self.assertEqual(dispatch_one(self.db, sender, 3), 'delivery_uncertain')
        self.db.recover(4)
        self.assertEqual(dispatch_one(self.db, sender, 5), 'idle')
        self.assertEqual(sender.calls, 1)
        self.assertEqual(self.db.task(I, 1)['state'], 'delivery_uncertain')

    def test_claim_is_compare_and_set_and_crash_recovers_uncertain(self):
        oid = self.db.pending()[0].outbox_id
        self.assertIsNotNone(self.db.claim(oid, 2))
        with Ledger(self.path) as other:
            self.assertIsNone(other.claim(oid, 3))
            other.recover(4)
            self.assertEqual(other.pending(), [])
            self.assertEqual(other.task(I, 1)['state'], 'delivery_uncertain')

    def test_exact_receipt_atomic_idempotent_and_conflict_rejected(self):
        sender = FakeReceiver()
        self.assertEqual(dispatch_one(self.db, sender, 2), 'delivered')
        row = self.db.connection.execute('SELECT evidence_json FROM delivery_receipt').fetchone()
        import json
        receipt = m.Receipt(**json.loads(row[0]))
        self.db.record_receipt(receipt)
        with self.assertRaisesRegex(ValueError, 'receipt_mismatch'):
            self.db.record_receipt(replace(receipt, session_id='other'))
        self.assertEqual(self.db.task(I, 1)['hermes_session_id'], 'session1')

    def test_receipt_cannot_predate_claim(self):
        self.assertEqual(dispatch_one(self.db, FakeReceiver(change={'observed_at': 1}), 2), 'delivery_uncertain')
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM delivery_receipt').fetchone()[0], 0)

    def test_bad_receipts_never_mark_delivered(self):
        for index, changes in enumerate([dict(outbox_id='wrong'), dict(request_sha256='wrong'),
                        dict(receiver_identity_revision='other'), dict(run_id=''), dict(session_id=''),
                        dict(status_readback='exit 0'),
                        dict(status_readback=m.canonical(dict(run_id='other', session_id='session1', status='started')))]):
            with self.subTest(changes=changes), Ledger(str(Path(self.tmp.name)/('bad'+str(index)))) as db:
                # Each subcase uses its own fresh ledger, independent of other receipt tests.
                db.apply(C, m.Snapshot((), STATES, True), 0)
                db.apply(C, m.Snapshot((issue(),), STATES, True), 1)
                self.assertEqual(dispatch_one(db, FakeReceiver(change=changes), 2), 'delivery_uncertain')
                self.assertEqual(db.connection.execute('SELECT count(*) FROM delivery_receipt').fetchone()[0], 0)
