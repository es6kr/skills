"""Hermetic GET-port contracts; no real clients, credentials, or services."""
import copy
import unittest
from agent_assignment.model import Config, IdentityScope

SCOPE = IdentityScope('https://plane.example.com', 'demo',
                      '44444444-4444-4444-8444-444444444444', 'PROJECT')
CONFIG = Config(SCOPE.host, SCOPE.workspace, SCOPE.project_id,
                '55555555-5555-4555-8555-555555555555',
                repo='C:/approved/repo', scope=SCOPE)
PREFIX = 'workspaces/demo/projects/' + SCOPE.project_id + '/'


class FakeRead:
    def __init__(self, responses=()):
        self.profile = dict(plane_host=SCOPE.host, workspace_slug=SCOPE.workspace)
        self.responses = iter(responses)
        self.calls = []

    def request(self, path, method='GET', data=None):
        self.calls.append((path, method, data))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


class LiveReadTests(unittest.TestCase):
    def test_writes_rejected_before_upstream(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        client = FakeRead()
        port = ReadOnlyPlanePort(client, CONFIG)
        for method, data in [('POST', {}), ('PATCH', {}), ('DELETE', None), ('GET', {})]:
            with self.subTest(method=method, data=data), self.assertRaises(ValueError):
                port.request(PREFIX + 'issues/?cursor=100:0:0', method=method, data=data)
        self.assertEqual(client.calls, [])

    def test_profile_mismatch_and_mutation_fail_closed(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        for field in ('plane_host', 'workspace_slug'):
            client = FakeRead()
            client.profile[field] = 'wrong'
            with self.subTest(field=field), self.assertRaises(ValueError):
                ReadOnlyPlanePort(client, CONFIG)
            self.assertEqual(client.calls, [])
        client = FakeRead()
        port = ReadOnlyPlanePort(client, CONFIG)
        client.profile['plane_host'] = 'https://other.example.com'
        with self.assertRaises(ValueError):
            port.request(PREFIX + 'issues/?cursor=100:0:0')
        self.assertEqual(client.calls, [])

    def test_only_exact_project_collection_paths_are_allowed(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        client = FakeRead()
        port = ReadOnlyPlanePort(client, CONFIG)
        for path in (None, '/api/v1/' + PREFIX + 'states/',
                     'https://plane.example.com/' + PREFIX + 'states/',
                     PREFIX + 'intake-issues/', PREFIX + 'issues/',
                     PREFIX + 'issues/?cursor=x&extra=1',
                     PREFIX + 'issues/?cursor=x&cursor=y',
                     PREFIX + 'issues/?cursor=', PREFIX + 'issues/?cursor=x#other',
                     PREFIX.replace('/demo/', '/other/') + 'states/'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                port.request(path)
        self.assertEqual(client.calls, [])

    def test_issue_page_is_forwarded_without_flattening(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        page = {'results': [], 'next_page_results': False}
        client = FakeRead([page])
        path = PREFIX + 'issues/?cursor=100:0:0'
        self.assertEqual(ReadOnlyPlanePort(client, CONFIG).request(path), page)
        self.assertEqual(client.calls, [(path, 'GET', None)])

    def test_states_paginated_envelope_requires_full_scan(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        first = dict(id='66666666-6666-4666-8666-666666666666', group='backlog', is_triage=False)
        second = dict(id='77777777-7777-4777-8777-777777777777', group='backlog', is_triage=True)
        client = FakeRead([
            dict(results=[first], next_page_results=True, next_cursor='100:1:0'),
            dict(results=[second], next_page_results=False)])
        self.assertEqual(ReadOnlyPlanePort(client, CONFIG).request(PREFIX + 'states/'), [first, second])
        self.assertEqual(client.calls[-1], (PREFIX + 'states/?cursor=100:1:0', 'GET', None))

    def test_invalid_states_never_invent_non_triage(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        sid = '66666666-6666-4666-8666-666666666666'
        for response in ([], [dict(id=sid, group='backlog')],
                         dict(results=[], next_page_results=0),
                         dict(results=[], next_page_results=True),
                         [dict(id=sid, group='unknown', is_triage=False)]):
            with self.subTest(response=response), self.assertRaises(ValueError):
                ReadOnlyPlanePort(FakeRead([response]), CONFIG).request(PREFIX + 'states/')

    def test_repeated_states_cursor_is_rejected(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        page = dict(results=[], next_page_results=True, next_cursor='100:1:0')
        client = FakeRead([page, page])
        with self.assertRaises(ValueError):
            ReadOnlyPlanePort(client, CONFIG).request(PREFIX + 'states/')
        self.assertEqual(len(client.calls), 2)

    def test_transport_error_is_not_replaced_by_empty_success(self):
        from agent_assignment.live_read import ReadOnlyPlanePort
        from plane_client import PlaneError
        for error in (PlaneError('synthetic 401'), TimeoutError('synthetic timeout')):
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)) as caught:
                ReadOnlyPlanePort(FakeRead([error]), CONFIG).request(PREFIX + 'states/')
            self.assertIs(caught.exception, error)
