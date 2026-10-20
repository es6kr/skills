import unittest
from dataclasses import FrozenInstanceError, asdict
from agent_assignment import model as m

HOST = 'https://plane.example.com'
PROJECT = '44444444-4444-4444-8444-444444444444'
ASSIGNEE = '11111111-1111-4111-8111-111111111111'


class ScopeTests(unittest.TestCase):
    def scope(self, **changes):
        cls = getattr(m, 'IdentityScope', None)
        self.assertIsNotNone(cls, 'trusted IdentityScope API is required')
        return cls(**dict(dict(host=HOST, workspace='demo', project_id=PROJECT,
                               identifier='PROJECT'), **changes))

    def test_explicit_scope_and_missing_scope_denial(self):
        with self.assertRaisesRegex(ValueError, '^scope_required$'):
            m.Config(HOST, 'demo', PROJECT, ASSIGNEE)
        scope = self.scope()
        config = m.Config(HOST, 'demo', PROJECT, ASSIGNEE, scope=scope)
        self.assertIs(config.scope, scope)
        with self.assertRaises(FrozenInstanceError):
            scope.identifier = 'OTHER'

    def test_scope_validation_rejects_unsafe_values_without_normalizing(self):
        for field, values in {
            'host': [None, 1, 'http://plane.example.com', HOST+'/', HOST+'/api',
                     'https://u:p@plane.example.com', HOST+'?', HOST+'#',
                     'https://', 'https://bad host', 'HTTPS://plane.example.com', HOST+'\n',
                     'https://plane.example.com:bad', 'https://plane.example.com\\evil'],
            'workspace': [None, 1, '', '.', '..', 'demo/a', 'demo%2fa', ' demo', 'demo?x', 'demo\n'],
            'project_id': [None, 1, 'not-a-uuid', PROJECT+' '],
            'identifier': [None, 1, '', 'PROJECT/1', 'PROJECT-1', ' PROJECT', 'PROJECT\n'],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, '^schema_error$'):
                        self.scope(**{field: value})
        token = PROJECT.upper()
        self.assertEqual(self.scope(project_id=token).project_id, token)

    def test_actual_identity_must_equal_trusted_scope(self):
        scope = self.scope()
        for field, value in [('host', 'https://other.example.com'), ('workspace', 'other'),
                             ('project_id', ASSIGNEE), ('host', None), ('workspace', 1)]:
            actual = dict(host=HOST, workspace='demo', project_id=PROJECT, assignee_id=ASSIGNEE)
            actual[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, '^identity_mismatch$'):
                    m.Config(**actual, scope=scope)
        with self.assertRaisesRegex(ValueError, '^schema_error$'):
            m.Config(HOST, 'demo', PROJECT, ASSIGNEE, scope=asdict(scope))

    def test_different_caller_scope_drives_url_without_granting_authority(self):
        scope = self.scope(host='https://other.example.com', workspace='other',
                           project_id=ASSIGNEE, identifier='OTHER')
        config = m.Config(scope.host, scope.workspace, scope.project_id, ASSIGNEE, scope=scope)
        issue = m.Issue(PROJECT, ASSIGNEE, (ASSIGNEE,), PROJECT, 7, 'title', 'scope=evil', 'revision')
        envelope = m.build_envelope(config, issue, 1, 'outbox')
        self.assertEqual(envelope.issue_url, 'https://other.example.com/other/browse/OTHER-7')
        self.assertNotIn('scope', asdict(envelope))
        self.assertFalse(envelope.execute_allowed)
        self.assertEqual(envelope.allowed_actions, ('classify', 'research', 'plan'))
        self.assertEqual(envelope.task_key, m.digest([scope.host, scope.workspace, scope.project_id,
                                                     issue.id, ASSIGNEE, 1]))
