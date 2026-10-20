import unittest
from dataclasses import replace
from test_agent_assignment_policy import m, P, A, I, S, C, RAW, STATES, issue

class NormalizeTests(unittest.TestCase):
    def test_nonstring_state_group_is_schema_error_not_type_error(self):
        for group in ([], {}, None):
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, 'schema_error'):
                m.normalize_states([dict(id=S, group=group, is_triage=False)])

    def test_schema_rejects_mixed_missing_bad_uuid_project_and_limits(self):
        for changes in [dict(assignees=[A, {'id': A}]), dict(assignees=[{}]),
                        dict(assignees=['not-uuid']), dict(id='bad'), dict(state='bad'),
                        dict(project=A), dict(name='x'*513),
                        dict(description_stripped='x'*16385), dict(sequence_id=True)]:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError): issue(**changes)
        raw = dict(RAW); del raw['assignees']
        with self.assertRaises(ValueError): m.normalize_issue(raw, C)

    def test_normalized_revisions_ignore_updated_at_and_assignee_order(self):
        x = issue()
        self.assertNotEqual(x.revision, issue(description_stripped='changed').revision)
        self.assertEqual(x.revision, issue(updated_at='different').revision)
        self.assertEqual(x, issue(assignees=[{'id': A}], state={'id': S}))
        self.assertEqual(issue(description_html='<p>Hello</p>').body, 'Hello')
        raw = dict(RAW); del raw['project']
        self.assertEqual(m.normalize_issue(raw, C).project_id, P)

    def test_states_and_config_fail_closed(self):
        self.assertEqual(m.normalize_states([dict(id=S, group='unstarted', is_triage=False)]), STATES)
        for raw in [[], [dict(id=S, group='unknown', is_triage=False)],
                    [dict(id=S, group='started', is_triage=0)], [dict(id=S, group='started')]]:
            with self.assertRaises(ValueError): m.normalize_states(raw)
        for changes in [dict(host='https://evil'), dict(workspace='company'),
                        dict(project_id=A), dict(assignee_id='bad'), dict(repo='relative')]:
            with self.assertRaises(ValueError): replace(C, **changes)
