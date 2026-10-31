"""Local callable orchestration; never real Plane, Hermes, or model traffic."""
from contextlib import redirect_stdout
from dataclasses import asdict
import copy
import io
import os
from pathlib import Path
import tempfile
import unittest
from agent_assignment.ledger import Ledger
from agent_assignment.model import Receipt, canonical, digest
from test_agent_assignment_live_read import CONFIG, PREFIX, FakeRead

STATES = [dict(id='33333333-3333-4333-8333-333333333333', group='unstarted', is_triage=False)]
ISSUE = dict(id='22222222-2222-4222-8222-222222222222', project=CONFIG.project_id,
             assignees=[CONFIG.assignee_id], state=STATES[0]['id'], sequence_id=7,
             name='Offline assigned plan', description_stripped='No live dispatch')


def client_for(issues):
    return FakeRead([STATES, dict(results=issues, next_page_results=False)])


class FakeReceiver:
    identity_revision = 'fixture-receiver-v1'
    def __init__(self, observed_at=104):
        self.submissions = []
        self.lookups = []
        self.observed_at = observed_at
        self.receipt = None

    def submit(self, envelope):
        self.submissions.append(envelope)
        status = dict(run_id='fixture-run', session_id='fixture-session', status='running')
        self.receipt = Receipt(envelope.outbox_id, digest(asdict(envelope)),
                               self.identity_revision, status['run_id'], status['session_id'],
                               self.observed_at, canonical(status))
        return self.receipt

    def lookup(self, outbox_id, request_sha256):
        self.lookups.append((outbox_id, request_sha256))
        return self.receipt


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'ledger.sqlite3')

    def test_collect_baseline_new_assignment_and_repeat_are_silent(self):
        from agent_assignment.live_cycle import collect_once
        output = io.StringIO()
        with redirect_stdout(output):
            baseline = collect_once(CONFIG, client_for([]), self.db, now=100)
            assigned = collect_once(CONFIG, client_for([ISSUE]), self.db, now=101)
            repeated = collect_once(CONFIG, client_for([ISSUE]), self.db, now=102)
        self.assertEqual(baseline, dict(complete=True, pending=0, error_code=None))
        self.assertEqual(assigned, dict(complete=True, pending=1, error_code=None))
        self.assertEqual(repeated, assigned)
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.outbox_count(), 1)
            self.assertEqual(ledger.connection.execute('SELECT count(*) FROM delivery_receipt').fetchone()[0], 0)
        self.assertEqual(output.getvalue(), '')

    def queued_id(self):
        from agent_assignment.live_cycle import collect_once
        collect_once(CONFIG, client_for([]), self.db, now=100)
        collect_once(CONFIG, client_for([ISSUE]), self.db, now=101)
        with Ledger(self.db) as ledger:
            return ledger.pending()[0].outbox_id

    def test_exact_candidate_admits_once_and_never_confuses_completion(self):
        from agent_assignment.live_cycle import admit_pending_once
        oid = self.queued_id()
        receiver = FakeReceiver()
        calls = []
        def preflight():
            calls.append('fresh')
            return receiver.identity_revision
        result = admit_pending_once(CONFIG, client_for([ISSUE]), self.db, receiver,
                                   expected_outbox_id=oid, preflight=preflight, now=103)
        self.assertEqual(result, 'delivered')
        self.assertEqual(len(receiver.submissions), 1)
        self.assertEqual(calls, ['fresh'])
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.task(ISSUE['id'], 1)['state'], 'delivered')
        self.assertEqual(admit_pending_once(CONFIG, client_for([ISSUE]), self.db, receiver,
                         expected_outbox_id=oid, preflight=preflight, now=105), 'idle')
        self.assertEqual(len(receiver.submissions), 1)

    def test_wrong_candidate_does_not_claim_any_pending(self):
        from agent_assignment.live_cycle import admit_pending_once
        oid = self.queued_id()
        receiver = FakeReceiver()
        result = admit_pending_once(CONFIG, client_for([ISSUE]), self.db, receiver,
                 expected_outbox_id='pa-' + '0' * 64,
                 preflight=lambda: receiver.identity_revision, now=103)
        self.assertEqual(result, 'candidate_mismatch')
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.pending()[0].outbox_id, oid)
            self.assertEqual(ledger.connection.execute('SELECT attempt_count FROM outbox').fetchone()[0], 0)
        self.assertEqual(receiver.submissions, [])

    def test_fresh_revision_change_blocks_frozen_envelope(self):
        from agent_assignment.live_cycle import admit_pending_once
        oid = self.queued_id()
        changed = copy.deepcopy(ISSUE)
        changed['name'] = 'Changed before admission'
        receiver = FakeReceiver()
        result = admit_pending_once(CONFIG, client_for([changed]), self.db, receiver,
                 expected_outbox_id=oid, preflight=lambda: receiver.identity_revision, now=103)
        self.assertEqual(result, 'revision_changed')
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.pending()[0].outbox_id, oid)
        self.assertEqual(receiver.submissions, [])

    def test_fresh_unassignment_prevents_submission(self):
        from agent_assignment.live_cycle import admit_pending_once
        oid = self.queued_id()
        changed = copy.deepcopy(ISSUE)
        changed['assignees'] = []
        receiver = FakeReceiver()
        self.assertEqual(admit_pending_once(CONFIG, client_for([changed]), self.db, receiver,
                         expected_outbox_id=oid, preflight=lambda: receiver.identity_revision, now=103), 'idle')
        self.assertEqual(receiver.submissions, [])

    def test_preflight_failure_is_before_claim_and_submit(self):
        from agent_assignment.live_cycle import admit_pending_once
        oid = self.queued_id()
        receiver = FakeReceiver()
        for preflight in (None, lambda: 'wrong', lambda: 1):
            result = admit_pending_once(CONFIG, client_for([ISSUE]), self.db, receiver,
                     expected_outbox_id=oid, preflight=preflight, now=103)
            self.assertIn(result, ('disabled', 'runtime_unverified'))
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.connection.execute('SELECT attempt_count FROM outbox').fetchone()[0], 0)
        self.assertEqual(receiver.submissions, [])

    def test_partial_snapshot_leaves_sending_and_all_rows_unchanged(self):
        from agent_assignment.live_cycle import collect_once, admit_pending_once
        oid = self.queued_id()
        with Ledger(self.db) as ledger:
            ledger.claim(oid, 102)
            before = tuple(ledger.connection.execute('SELECT status,attempt_count FROM outbox').fetchone())
            events = ledger.connection.execute('SELECT count(*) FROM event').fetchone()[0]
        def partial():
            return FakeRead([STATES, dict(results=[], next_page_results='not-a-bool')])
        report = collect_once(CONFIG, partial(), self.db, now=103)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['pending'])
        receiver = FakeReceiver()
        self.assertEqual(admit_pending_once(CONFIG, partial(), self.db, receiver,
                         expected_outbox_id=oid, preflight=lambda: receiver.identity_revision, now=103), 'partial_snapshot')
        with Ledger(self.db) as ledger:
            self.assertEqual(tuple(ledger.connection.execute('SELECT status,attempt_count FROM outbox').fetchone()), before)
            self.assertEqual(ledger.connection.execute('SELECT count(*) FROM event').fetchone()[0], events)
        self.assertEqual(receiver.submissions, [])

    def test_real_cycle_lock_blocks_before_fetch_or_claim(self):
        from agent_assignment.live_cycle import collect_once, admit_pending_once
        from agent_assignment.poll import cycle_lock
        oid = self.queued_id()
        client = client_for([ISSUE])
        receiver = FakeReceiver()
        with cycle_lock(str(Path(self.temp.name) / 'poll.lock')):
            report = collect_once(CONFIG, client, self.db, now=103)
            self.assertEqual(report['error_code'], 'cycle_busy')
            self.assertEqual(admit_pending_once(CONFIG, client, self.db, receiver,
                             expected_outbox_id=oid, preflight=lambda: receiver.identity_revision,
                             now=103), 'cycle_busy')
        self.assertEqual(client.calls, [])
        self.assertEqual(receiver.submissions, [])

    def test_one_selected_outbox_does_not_admit_a_second_candidate(self):
        from agent_assignment.live_cycle import collect_once, admit_pending_once
        other = copy.deepcopy(ISSUE)
        other['id'] = '88888888-8888-4888-8888-888888888888'
        other['sequence_id'] = 8
        collect_once(CONFIG, client_for([]), self.db, now=100)
        collect_once(CONFIG, client_for([ISSUE, other]), self.db, now=101)
        with Ledger(self.db) as ledger:
            oid = ledger.pending()[0].outbox_id
        receiver = FakeReceiver()
        self.assertEqual(admit_pending_once(CONFIG, client_for([ISSUE, other]), self.db, receiver,
                         expected_outbox_id=oid, preflight=lambda: receiver.identity_revision,
                         now=103), 'delivered')
        self.assertEqual(admit_pending_once(CONFIG, client_for([ISSUE, other]), self.db, receiver,
                         expected_outbox_id=oid, preflight=lambda: receiver.identity_revision,
                         now=105), 'candidate_mismatch')
        self.assertEqual(len(receiver.submissions), 1)
        with Ledger(self.db) as ledger:
            self.assertEqual(len(ledger.pending()), 1)

    def test_disabled_receiver_and_bad_host_inputs_never_read(self):
        from agent_assignment.dispatch import DisabledReceiver
        from agent_assignment.live_cycle import collect_once, admit_pending_once
        oid = self.queued_id()
        client = client_for([ISSUE])
        self.assertEqual(admit_pending_once(CONFIG, client, self.db, DisabledReceiver(),
                         expected_outbox_id=oid, preflight=lambda: 'not-authorization',
                         now=103), 'disabled')
        for path, now in (('relative.sqlite3', 100), (self.db, True), (self.db, -1)):
            with self.subTest(path=path, now=now), self.assertRaises(ValueError):
                collect_once(CONFIG, client, path, now=now)
        self.assertEqual(client.calls, [])

    def test_preflight_exception_and_identity_drift_leave_claim_unconsumed(self):
        from agent_assignment.live_cycle import admit_pending_once
        oid = self.queued_id()
        receiver = FakeReceiver()
        def failed():
            raise RuntimeError('fixture unverified host')
        def changed():
            previous = receiver.identity_revision
            receiver.identity_revision = 'new-identity'
            return previous
        for preflight in (failed, changed):
            self.assertEqual(admit_pending_once(CONFIG, client_for([ISSUE]), self.db, receiver,
                             expected_outbox_id=oid, preflight=preflight, now=103), 'runtime_unverified')
        with Ledger(self.db) as ledger:
            self.assertEqual(ledger.connection.execute('SELECT attempt_count FROM outbox').fetchone()[0], 0)
        self.assertEqual(receiver.submissions, [])
