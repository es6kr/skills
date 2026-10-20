import unittest
from test_agent_assignment_policy import m, C, S, RAW
from agent_assignment.poll import fetch_snapshot

class Client:
    def __init__(self, pages, states=None):
        self.pages = iter(pages)
        self.paths = []
        self.states = states if states is not None else [dict(id=S, group='unstarted', is_triage=False)]
    def request(self, path, method='GET', data=None):
        assert method == 'GET' and data is None
        self.paths.append(path)
        if path.endswith('states/'): return self.states
        page = next(self.pages)
        if isinstance(page, Exception): raise page
        return page

def page(items=None, more=False, cursor=None):
    return dict(results=items or [], next_page_results=more, next_cursor=cursor)

class SnapshotTests(unittest.TestCase):
    def test_all_pages_no_intake_deduplicate(self):
        c = Client([page([RAW], True, '100:1:0'), page([RAW])])
        s = fetch_snapshot(c, C)
        self.assertTrue(s.complete)
        self.assertEqual(len(s.issues), 1)
        paths = [x for x in c.paths if 'issues/?' in x]
        self.assertEqual(len(paths), 2)
        self.assertIn('cursor=100:0:0', paths[0])
        self.assertIn('cursor=100:1:0', paths[1])
        self.assertFalse(any('intake' in p or 'cache' in p for p in c.paths))

    def test_partial_malformed_transport_and_unknown_state_fail_closed(self):
        for pages in [[page([], True, 'next'), RuntimeError('HTTP 401 secret')],
                      [{'next_page_results': False}], [page([], 1)],
                      [page([], True, '')], [page([], True, 'next'), []],
                      [page([dict(RAW, state=C.assignee_id)])],
                      [TimeoutError()], [RuntimeError('HTTP 403')], [RuntimeError('HTTP 429')]]:
            with self.subTest(pages=repr(pages)):
                s = fetch_snapshot(Client(pages), C)
                self.assertFalse(s.complete)
                self.assertEqual(s.issues, ())
                self.assertNotIn('secret', s.error_code)

    def test_cursor_cycle_conflict_page_limit_legacy_list(self):
        for pages, code in [([page([], True, '100:0:0')], 'cursor_cycle'),
                            ([page([RAW], True, 'next'), page([dict(RAW, name='changed')])], 'snapshot_conflict'),
                            ([page([], True, str(n)) for n in range(1001)], 'page_limit')]:
            self.assertEqual(fetch_snapshot(Client(pages), C).error_code, code)
        self.assertTrue(fetch_snapshot(Client([[RAW]]), C).complete)
        self.assertFalse(fetch_snapshot(Client([page()], states=[dict(id=S, group='unknown', is_triage=False)]), C).complete)
