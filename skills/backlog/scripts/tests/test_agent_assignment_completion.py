"""Offline completion trust-boundary tests. All evidence here is synthetic test data."""
import importlib
import unittest
import test_agent_assignment_dispatch as dispatch_tests
from test_agent_assignment_dispatch import FakeReceiver
from test_agent_assignment_policy import m, C, I, issue
from agent_assignment.dispatch import dispatch_one

from test_agent_assignment_policy import RAW, S
DONE = '44444444-4444-4444-8444-444444444444'


class OfflinePlane:
    def __init__(self):
        self.raw = dict(RAW)
        self.calls = []
        self.patch_payload = None

    def request(self, path, method='GET', data=None):
        if path.endswith('states/'):
            self.calls.append('GET states')
            return [dict(id=S, group='unstarted', is_triage=False),
                    dict(id=DONE, group='completed', is_triage=False)]
        assert path.endswith('/issues/' + I + '/')
        if method == 'PATCH':
            self.calls.append('PATCH')
            self.patch_payload = data
            self.raw.update(data)
            return {'state': DONE}  # Never trust PATCH response as readback.
        self.calls.append('GET issue')
        return dict(self.raw)


class CompletionTests(unittest.TestCase):
    def setUp(self):
        dispatch_tests.DispatchTests.setUp(self)
        self.api = importlib.import_module('agent_assignment.completion')
        self.oid = self.db.pending()[0].outbox_id
        dispatch_one(self.db, FakeReceiver(), 2)
        self.runtime = dict(run_id='run1', session_id='session1', status='completed',
                            result={'artifact': 'offline-test-only'})
        self.criteria = {'artifact': 'Inspect the required artifact and verify its behavior'}
        self.calls = []

    def verifier(self, context):
        self.calls.append(context)
        return {'artifact': {'passed': True, 'evidence': 'independent offline test inspection'}}

    def gate(self, verifier=None):
        return self.api.CompletionGate(self.db, verifier_id='trusted-test-verifier-v1',
            verify=verifier or self.verifier, read_run=lambda run: self.runtime,
            clock=lambda: 10)

    def test_adopt_existing_delivery_preserves_provenance_without_poll_history(self):
        import hashlib
        import json
        import sqlite3
        from pathlib import Path
        envelope = json.loads(self.db.connection.execute('SELECT payload_json FROM outbox').fetchone()[0])
        source = str(Path(self.tmp.name) / 'original-bindings.sqlite')
        session = 'pa-session-' + m.digest(['test-scope', self.oid])
        body = m.canonical(dict(input=m.canonical(envelope), session_id=session, instructions='planning only'))
        binding = dict(outbox_id=self.oid, envelope_sha256=m.digest(envelope), scope='test-scope',
            identity_revision='test-receiver-v1', request_json=body,
            request_body_sha256=hashlib.sha256(body.encode()).hexdigest(),
            idempotency_key='pa-run-' + m.digest(['test-scope', self.oid, m.digest(envelope)]),
            session_id=session, created_at=2, retention_seconds=86400, state='uncertain', run_id='run1')
        from contextlib import closing
        with closing(sqlite3.connect(source, isolation_level=None)) as src:
            src.execute('CREATE TABLE hermes_binding (' + ','.join(k + ' TEXT' for k in binding) + ')')
            src.execute('INSERT INTO hermes_binding VALUES (' + ','.join('?' for k in binding) + ')', tuple(binding.values()))
        runtime = dict(self.runtime, session_id=session)
        target_path = str(Path(self.tmp.name) / 'adopted.sqlite')
        with type(self.db)(target_path) as target:
            arguments = dict(binding_path=source, outbox_id=self.oid, issue_readback=dict(RAW),
                read_run=lambda run: runtime, provenance={'audit': 'synthetic test source'}, now=10)
            self.api.adopt_existing_delivery(target, C, **arguments)
            self.api.adopt_existing_delivery(target, C, **arguments)
            self.assertEqual(target.connection.execute('SELECT count(*) FROM observation').fetchone()[0], 0)
            events = target.connection.execute('SELECT kind FROM event').fetchall()
            self.assertEqual([r[0] for r in events], ['adopted_delivery'])
            self.assertEqual(target.outbox_count(), 1)
            gate = self.api.CompletionGate(target, verifier_id='trusted-test-verifier-v1', verify=self.verifier,
                                           read_run=lambda run: runtime, clock=lambda: 10)
            gate.register(self.oid, self.criteria)
            receipt = gate.verify(self.oid)
            self.assertEqual(receipt['session_id'], session)
            evidence = target.connection.execute('SELECT evidence_json FROM completion_adoption').fetchone()[0]
            self.assertIn('synthetic test source', evidence)
            with self.assertRaises(ValueError):
                self.api.adopt_existing_delivery(target, C, **dict(arguments, issue_readback=dict(RAW, name='edited')))

    def test_tampered_delivery_binding_never_issues_pass(self):
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        self.db.connection.execute("UPDATE delivery_receipt SET request_sha256='tampered'")
        with self.assertRaisesRegex(ValueError, 'binding_mismatch'):
            gate.verify(self.oid)

    def test_runtime_mismatch_and_empty_result_do_not_call_verifier(self):
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        original = dict(self.runtime)
        for changes in [dict(run_id='other'), dict(session_id='other'), dict(status='running'),
                        dict(status='failed'), dict(result=''), dict(result={}), dict(result=None)]:
            with self.subTest(changes=changes):
                self.runtime = dict(original, **changes)
                with self.assertRaisesRegex(ValueError, 'result_invalid'):
                    gate.verify(self.oid)
        self.assertEqual(self.calls, [])

    def test_receipt_and_contract_are_immutable_and_scope_cannot_change(self):
        import sqlite3
        gate = self.gate()
        with self.assertRaisesRegex(ValueError, 'criteria_required'):
            gate.verify(self.oid)
        gate.register(self.oid, self.criteria)
        with self.assertRaisesRegex(ValueError, 'contract_mismatch'):
            gate.register(self.oid, {'other': 'Different requirement'})
        gate.verify(self.oid)
        for table in ('completion_pass', 'completion_contract'):
            for sql in ('DELETE FROM ' + table, 'UPDATE ' + table + ' SET outbox_id=outbox_id'):
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'completion_immutable'):
                    self.db.connection.execute(sql)

    def test_partial_failure_restarts_only_read_back_never_repatch(self):
        from pathlib import Path
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        gate.verify(self.oid)
        transport = OfflinePlane()
        request = transport.request
        def accepted_then_timeout(path, method='GET', data=None):
            result = request(path, method, data)
            if method == 'PATCH':
                raise TimeoutError('offline synthetic accepted then response lost')
            return result
        transport.request = accepted_then_timeout
        with self.assertRaises(TimeoutError):
            self.api.PlaneCompletionFinalizer(gate, C, transport, clock=lambda: 11).finalize(self.oid)
        self.assertNotEqual(self.db.task(I, 1)['state'], 'completed')
        self.assertEqual(gate.receipt(self.oid)['verdict'], 'PASS')
        transport.request = request
        with type(self.db)(self.path) as restarted:
            gate2 = self.api.CompletionGate(restarted, verifier_id='trusted-test-verifier-v1',
                verify=self.verifier, read_run=lambda run: self.runtime, clock=lambda: 12)
            finalizer = self.api.PlaneCompletionFinalizer(gate2, C, transport, clock=lambda: 12)
            self.assertEqual(finalizer.finalize(self.oid)['state'], DONE)
        self.assertEqual(transport.calls.count('PATCH'), 1)

    def test_failed_write_is_uncertain_and_never_automatically_retried(self):
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        gate.verify(self.oid)
        transport = OfflinePlane()
        request = transport.request
        def rejected(path, method='GET', data=None):
            if method == 'PATCH':
                transport.calls.append('PATCH')
                raise TimeoutError('offline synthetic no change')
            return request(path, method, data)
        transport.request = rejected
        finalizer = self.api.PlaneCompletionFinalizer(gate, C, transport, clock=lambda: 11)
        with self.assertRaises(TimeoutError):
            finalizer.finalize(self.oid)
        transport.request = request
        with self.assertRaisesRegex(ValueError, 'completion_readback_mismatch'):
            finalizer.finalize(self.oid)
        self.assertEqual(transport.calls.count('PATCH'), 1)
        self.assertNotEqual(self.db.task(I, 1)['state'], 'completed')

    def test_verifier_exception_never_records_pass(self):
        def broken(context):
            raise RuntimeError('synthetic independent verifier unavailable')
        gate = self.gate(verifier=broken)
        gate.register(self.oid, self.criteria)
        with self.assertRaises(RuntimeError):
            gate.verify(self.oid)
        with self.assertRaisesRegex(ValueError, 'pass_required'):
            gate.receipt(self.oid)

    def test_partial_multi_criterion_result_fails_closed(self):
        gate = self.gate()
        gate.register(self.oid, dict(self.criteria, independent_audit='Exact run independent transcript audit'))
        with self.assertRaisesRegex(ValueError, 'acceptance_failed'):
            gate.verify(self.oid)
        with self.assertRaisesRegex(ValueError, 'pass_required'):
            gate.receipt(self.oid)

    def test_post_patch_content_drift_never_records_completion(self):
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        gate.verify(self.oid)
        transport = OfflinePlane()
        request = transport.request
        def drift(path, method='GET', data=None):
            result = request(path, method, data)
            if method == 'PATCH':
                transport.raw['name'] = 'concurrent external edit'
            return result
        transport.request = drift
        with self.assertRaisesRegex(ValueError, 'completion_readback_mismatch'):
            self.api.PlaneCompletionFinalizer(gate, C, transport, clock=lambda: 11).finalize(self.oid)
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM completion_readback').fetchone()[0], 0)
        self.assertNotEqual(self.db.task(I, 1)['state'], 'completed')

    def test_finalizer_rechecks_result_digest_before_writing(self):
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        gate.verify(self.oid)
        self.runtime['result'] = {'artifact': 'changed after verification'}
        transport = OfflinePlane()
        with self.assertRaisesRegex(ValueError, 'result_mismatch'):
            self.api.PlaneCompletionFinalizer(gate, C, transport, clock=lambda: 11).finalize(self.oid)
        self.assertNotIn('PATCH', transport.calls)

    def test_finalizer_blocks_stale_mismatched_or_removed_assignment(self):
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        gate.verify(self.oid)
        cases = [({'name': 'edited'}, C, 11), ({'assignees': []}, C, 11),
                 ({'id': C.assignee_id}, C, 11), ({}, C, 1811), ({}, C, 9),
                 ({}, m.Config(C.host, C.workspace, C.project_id, I, C.repo, scope=C.scope), 11)]
        for changes, config, now in cases:
            with self.subTest(changes=changes, config=config, now=now):
                transport = OfflinePlane()
                transport.raw.update(changes)
                finalizer = self.api.PlaneCompletionFinalizer(gate, config, transport, clock=lambda: now)
                with self.assertRaises(ValueError):
                    finalizer.finalize(self.oid)
                self.assertNotIn('PATCH', transport.calls)
                self.assertNotEqual(self.db.task(I, 1)['state'], 'completed')
        self.db.connection.execute('UPDATE task SET assignment_active=0')
        with self.assertRaises(ValueError):
            self.api.PlaneCompletionFinalizer(gate, C, OfflinePlane(), clock=lambda: 11).finalize(self.oid)

    def test_finalizer_requires_pass_and_reads_exact_target_after_write(self):
        gate = self.gate()
        transport = OfflinePlane()
        finalizer = self.api.PlaneCompletionFinalizer(gate, C, transport, clock=lambda: 11)
        with self.assertRaisesRegex(ValueError, 'pass_required'):
            finalizer.finalize(self.oid)
        self.assertEqual(transport.calls, [])
        gate.register(self.oid, self.criteria)
        receipt = gate.verify(self.oid)
        result = finalizer.finalize(self.oid)
        self.assertEqual(result['state'], DONE)
        self.assertEqual(transport.calls, ['GET states', 'GET issue', 'PATCH', 'GET issue'])
        self.assertEqual(transport.patch_payload, {'state': DONE})
        self.assertEqual(finalizer.finalize(self.oid), result)
        self.assertEqual(transport.calls.count('PATCH'), 1)
        self.assertEqual(gate.receipt(self.oid), receipt)
        self.assertEqual(self.db.task(I, 1)['state'], 'completed')

    def test_self_claims_and_partial_acceptance_never_issue_pass(self):
        invalid = [True, 'PASS', {'verdict': 'PASS'}, {},
            {'artifact': {'passed': False, 'evidence': 'not done'}},
            {'artifact': {'passed': 'true', 'evidence': 'claim'}},
            {'artifact': {'passed': True, 'evidence': ''}},
            {'artifact': {'passed': True}},
            {'other': {'passed': True, 'evidence': 'wrong criterion'}}]
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        self.runtime['result'] = {'status': 'completed', 'verdict': 'PASS', 'all_done': True}
        for claim in invalid:
            with self.subTest(claim=claim):
                candidate = self.gate(verifier=lambda ctx: claim)
                with self.assertRaisesRegex(ValueError, 'acceptance_failed'):
                    candidate.verify(self.oid)
                with self.assertRaisesRegex(ValueError, 'pass_required'):
                    gate.receipt(self.oid)

    def test_pass_receipt_binds_exact_work_and_is_durable(self):
        gate = self.gate()
        gate.register(self.oid, self.criteria)
        receipt = gate.verify(self.oid)
        self.assertEqual(receipt['verdict'], 'PASS')
        for key, value in dict(issue_id=I, content_revision=issue().revision,
                               assignee_id=C.assignee_id, outbox_id=self.oid,
                               run_id='run1', session_id='session1',
                               result_sha256=m.digest(self.runtime['result'])).items():
            self.assertEqual(receipt[key], value)
        self.assertEqual(receipt['criteria'], self.criteria)
        self.assertEqual(self.calls[0]['result'], self.runtime['result'])
        self.assertEqual(gate.verify(self.oid), receipt)
        self.assertEqual(len(self.calls), 1)
        with type(self.db)(self.path) as reopened:
            restarted = self.api.CompletionGate(reopened, verifier_id='trusted-test-verifier-v1',
                verify=self.verifier, read_run=lambda run: self.runtime, clock=lambda: 11)
            self.assertEqual(restarted.receipt(self.oid), receipt)
        self.assertNotEqual(self.db.task(I, 1)['state'], 'completed')


if __name__ == '__main__':
    unittest.main()
