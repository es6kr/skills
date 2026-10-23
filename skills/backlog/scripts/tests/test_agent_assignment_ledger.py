import unittest
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from test_agent_assignment_policy import m, C, I, S, STATES, issue, snap
from agent_assignment.ledger import Ledger

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'ledger.db')
        self.db = Ledger(self.path)
        self.addCleanup(self.db.__exit__, None, None, None)

    def test_public_snapshot_unknown_state_schema_is_rejected_atomically(self):
        invalid = {S: m.State(S, 'unknown', False)}
        with self.assertRaisesRegex(ValueError, 'schema_error'):
            self.db.apply(C, m.Snapshot((issue(),), invalid, True), 0)
        self.assertIsNone(self.db.task(I, 1))
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM identity').fetchone()[0], 0)

    def test_public_snapshot_rejects_invalid_issue_without_mutation(self):
        self.db.apply(C, m.Snapshot((), STATES, True), 0)
        before = '\n'.join(self.db.connection.iterdump())
        cases = [
            (dict(id='bad'), 'schema_error'),
            (dict(state_id='bad'), 'schema_error'),
            (dict(project_id=I), 'identity_mismatch'),
            (dict(assignees=('bad',)), 'schema_error'),
            (dict(assignees=list(issue().assignees)), 'schema_error'),
            (dict(sequence_id=True), 'schema_error'),
            (dict(sequence_id=0), 'schema_error'),
            (dict(title=123), 'schema_error'),
            (dict(title='x' * 513), 'content_limit'),
            (dict(body='x' * 16385), 'content_limit'),
            (dict(body=None), 'schema_error'),
            (dict(revision='arbitrary'), 'schema_error'),
            (dict(body='changed without revision'), 'schema_error'),
        ]
        for changes, code in cases:
            with self.subTest(fields=tuple(changes), code=code):
                with self.assertRaisesRegex(ValueError, code):
                    self.db.apply(C, m.Snapshot((replace(issue(), **changes),), STATES, True), 1)
                self.assertEqual('\n'.join(self.db.connection.iterdump()), before)

    def test_public_snapshot_requires_exact_boolean_completeness(self):
        before = '\n'.join(self.db.connection.iterdump())
        for complete in (1, 0, 'true', '', None):
            with self.subTest(complete=complete):
                with self.assertRaisesRegex(ValueError, 'schema_error'):
                    self.db.apply(C, m.Snapshot((issue(),), STATES, complete), 0)
                self.assertEqual('\n'.join(self.db.connection.iterdump()), before)

    def test_partial_first_then_baseline_never_dispatches_existing(self):
        self.db.apply(C, snap(complete=False), 0)
        self.assertIsNone(self.db.task(I, 1))
        self.db.apply(C, snap(), 1)
        self.db.apply(C, snap(False, False), 2)
        self.assertEqual(self.db.task(I, 1)['assignment_active'], 1)
        self.assertEqual(self.db.task(I, 1)['state'], 'observed')
        self.assertEqual(self.db.outbox_count(), 0)

    def test_reassignment_edits_frozen_outbox_and_reopen(self):
        self.db.apply(C, snap(False), 0)
        self.db.apply(C, snap(), 1)
        before = self.db.pending()[0]
        self.db.apply(C, m.Snapshot((issue(name='edited'),), STATES, True), 2)
        self.assertEqual(self.db.pending()[0], before)
        self.assertNotEqual(self.db.task(I, 1)['content_revision'], before.content_revision)
        self.db.apply(C, snap(False), 3)
        self.assertEqual(self.db.pending(), [])
        self.db.apply(C, snap(), 4)
        self.assertIsNotNone(self.db.task(I, 2))
        with Ledger(self.path) as other:
            other.recover(5)
            other.apply(C, snap(), 6)
            self.assertEqual(other.outbox_count(), 2)

    def test_needs_context_eligibility_baseline_and_absence(self):
        no_repo = replace(C, repo=None)
        self.db.apply(no_repo, snap(False), 0)
        self.db.apply(no_repo, snap(), 1)
        self.assertEqual(self.db.task(I, 1)['state'], 'needs_context')
        self.db.apply(C, snap(), 2)
        self.assertEqual(len(self.db.pending()), 1)
        self.db.apply(C, m.Snapshot((), STATES, True), 3)
        self.assertEqual(self.db.pending(), [])
        self.assertEqual(self.db.task(I, 1)['error_code'], 'absent_from_complete_snapshot')

    def test_triage_new_generation_can_queue_but_baseline_cannot(self):
        triage = {S: m.State(S, 'backlog', True)}
        self.db.apply(C, m.Snapshot((), STATES, True), 0)
        self.db.apply(C, m.Snapshot((issue(),), triage, True), 1)
        self.assertEqual(self.db.outbox_count(), 0)
        self.db.apply(C, snap(), 2)
        self.assertEqual(self.db.outbox_count(), 1)
        with Ledger(str(Path(self.tmp.name)/'baseline.db')) as b:
            b.apply(C, m.Snapshot((issue(),), triage, True), 0)
            b.apply(C, snap(), 1)
            self.assertEqual(b.outbox_count(), 0)

    def test_independent_connections_are_atomic_and_identity_scoped(self):
        self.db.apply(C, snap(False), 0)
        errors = []
        barrier = threading.Barrier(2)
        def apply():
            try:
                with Ledger(self.path) as db:
                    barrier.wait(timeout=5)
                    db.apply(C, snap(), 1)
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=apply) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join(10)
        self.assertFalse(errors)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(self.db.outbox_count(), 1)
        with self.assertRaisesRegex(ValueError, 'identity_mismatch'):
            self.db.apply(replace(C, assignee_id=I), snap(), 2)
        self.assertEqual(self.db.connection.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
        self.assertEqual(self.db.connection.execute('PRAGMA synchronous').fetchone()[0], 2)
        self.assertEqual(self.db.connection.execute('PRAGMA foreign_keys').fetchone()[0], 1)
