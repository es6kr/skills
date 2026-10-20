import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_agent_assignment_policy import C, RAW, S
from contextlib import closing
from dataclasses import asdict

SCRIPTS = Path(__file__).resolve().parents[1]
CLI = SCRIPTS / 'plane_agent_poll.py'

class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'ledger.db'
        self.fixture = self.root / 'fixture.json'
        self.scope_file = self.root / 'scope.json'
        self.scope_file.write_text(json.dumps(asdict(C.scope)), encoding='utf-8')
        self.env = dict(os.environ, PYTHONPATH=str(self.root)+os.pathsep+str(SCRIPTS),
                        PLANE_API_KEY='synthetic-secret-never-read', PLANE_TOKEN='synthetic-secret-never-read')
        (self.root/'sitecustomize.py').write_text('''import socket, urllib.request
from pathlib import Path
import os
def blocked(*args, **kwargs):
    Path(os.environ['NETWORK_MARKER']).write_text('attempted')
    raise AssertionError('network forbidden')
socket.socket.connect = blocked
socket.create_connection = blocked
urllib.request.urlopen = blocked
''', encoding='utf-8')
        self.env['NETWORK_MARKER'] = str(self.root/'network-attempt')
        self.write_fixture([RAW])

    def write_fixture(self, issues):
        config = asdict(C)
        config.pop('scope')
        self.fixture.write_text(json.dumps(dict(config=config, states=[dict(id=S, group='unstarted', is_triage=False)], issues=issues)), encoding='utf-8')

    def run_cli(self, extra=(), scope=True):
        scope_args = ['--scope-file', str(self.scope_file)] if scope else []
        p = subprocess.run([sys.executable, str(CLI), '--db', str(self.db), '--mode', 'collect-only', '--report', *scope_args, *extra], env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(p.stdout, '')
        self.assertNotIn('synthetic-secret', p.stderr)
        self.assertFalse((self.root/'network-attempt').exists())
        return p

    def test_live_missing_fixture_and_dispatch_modes_are_blocked(self):
        p = self.run_cli()
        self.assertEqual(p.returncode, 4)
        self.assertEqual(json.loads(p.stderr)['error_code'], 'activation_required')
        self.assertFalse(self.db.exists())
        p = self.run_cli(['--fixture', str(self.fixture), '--mode', 'dispatch'])
        self.assertEqual(p.returncode, 4)
        self.assertFalse(self.db.exists())

    def test_missing_scope_denies_fixture_and_environment_self_scope_before_storage(self):
        data = json.loads(self.fixture.read_text(encoding='utf-8'))
        data['scope'] = asdict(C.scope)
        data['config']['scope'] = asdict(C.scope)
        self.fixture.write_text(json.dumps(data), encoding='utf-8')
        self.env['PLANE_AGENT_SCOPE'] = json.dumps(asdict(C.scope))
        p = self.run_cli(['--fixture', str(self.fixture)], scope=False)
        self.assertEqual(p.returncode, 4)
        self.assertEqual(json.loads(p.stderr)['error_code'], 'scope_required')
        self.assertFalse(self.db.exists())
        self.assertFalse((self.root/'poll.lock').exists())

    def test_baseline_repeat_and_new_assignment_have_silent_stdout(self):
        for _ in range(2):
            p = self.run_cli(['--fixture', str(self.fixture)])
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stderr), dict(mode='collect-only', complete=True, pending=0, error_code=None))
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT baseline_ready FROM identity').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM outbox').fetchone()[0], 0)
        self.db = self.root/'new.db'
        self.write_fixture([])
        self.assertEqual(self.run_cli(['--fixture', str(self.fixture)]).returncode, 0)
        self.write_fixture([RAW])
        p = self.run_cli(['--fixture', str(self.fixture)])
        self.assertEqual(json.loads(p.stderr)['pending'], 1)

    def test_explicit_scope_identity_mismatch_denied_without_db(self):
        original = json.loads(self.fixture.read_text(encoding='utf-8'))
        for field, value in [('host', 'https://other.example.com'), ('workspace', 'other'),
                             ('project_id', RAW['id'])]:
            with self.subTest(field=field):
                data = json.loads(json.dumps(original))
                data['config'][field] = value
                data['scope'] = dict(asdict(C.scope), **{field: value})
                self.fixture.write_text(json.dumps(data), encoding='utf-8')
                p = self.run_cli(['--fixture', str(self.fixture)])
                self.assertEqual(p.returncode, 3)
                self.assertEqual(json.loads(p.stderr)['error_code'], 'identity_mismatch')
                self.assertFalse(self.db.exists())

    def test_scope_file_duplicate_keys_are_rejected_before_storage(self):
        raw = json.dumps(asdict(C.scope))
        self.scope_file.write_text('{"host":"https://evil.example.com",'+raw[1:], encoding='utf-8')
        p = self.run_cli(['--fixture', str(self.fixture)])
        self.assertEqual(p.returncode, 3)
        self.assertEqual(json.loads(p.stderr)['error_code'], 'schema_error')
        self.assertFalse(self.db.exists())
        self.assertFalse((self.root/'poll.lock').exists())

    def test_scope_file_exact_schema_and_no_credential_fallback(self):
        scope = asdict(C.scope)
        invalid = [[], None, {}, dict(scope, token='synthetic-secret'),
                   dict(scope, host=123), dict(scope, workspace='../demo'),
                   dict(scope, project_id='invalid'), dict(scope, identifier='PROJECT/7')]
        invalid.extend({k: v for k, v in scope.items() if k != field} for field in scope)
        for value in invalid:
            with self.subTest(value=value):
                self.scope_file.write_text(json.dumps(value), encoding='utf-8')
                p = self.run_cli(['--fixture', str(self.fixture)])
                self.assertEqual(p.returncode, 3)
                self.assertEqual(json.loads(p.stderr)['error_code'], 'schema_error')
                self.assertFalse(self.db.exists())
                self.assertFalse((self.root/'poll.lock').exists())
        self.scope_file.write_text('{', encoding='utf-8')
        p = self.run_cli(['--fixture', str(self.fixture)])
        self.assertEqual((p.returncode, json.loads(p.stderr)['error_code']), (3, 'schema_error'))
        self.scope_file = self.root/'missing-scope.json'
        p = self.run_cli(['--fixture', str(self.fixture)])
        self.assertEqual((p.returncode, json.loads(p.stderr)['error_code']), (3, 'storage_error'))
        self.assertFalse(self.db.exists())

    def test_fixture_config_cannot_supply_scope_even_with_explicit_scope_file(self):
        data = json.loads(self.fixture.read_text(encoding='utf-8'))
        data['config']['scope'] = asdict(C.scope)
        self.fixture.write_text(json.dumps(data), encoding='utf-8')
        p = self.run_cli(['--fixture', str(self.fixture)])
        self.assertEqual((p.returncode, json.loads(p.stderr)['error_code']), (3, 'schema_error'))
        self.assertFalse(self.db.exists())

    def test_different_trusted_scope_and_matching_untrusted_snapshot_work(self):
        scope = dict(asdict(C.scope), host='https://other.example.com', workspace='other',
                     project_id=RAW['id'], identifier='OTHER')
        self.scope_file.write_text(json.dumps(scope), encoding='utf-8')
        data = json.loads(self.fixture.read_text(encoding='utf-8'))
        data['config'].update({k: scope[k] for k in ('host', 'workspace', 'project_id')})
        data['issues'][0]['project'] = scope['project_id']
        self.fixture.write_text(json.dumps(data), encoding='utf-8')
        p = self.run_cli(['--fixture', str(self.fixture)])
        self.assertEqual(p.returncode, 0, p.stderr)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT issue_url FROM task').fetchone()[0],
                             'https://other.example.com/other/browse/OTHER-7')
            self.assertEqual(db.execute('SELECT count(*) FROM outbox').fetchone()[0], 0)

    def test_checked_in_offline_fixture_has_separate_scope_file(self):
        root = SCRIPTS/'tests'/'fixtures'/'agent_assignment'
        p = self.run_cli(['--fixture', str(root/'snapshot.json'), '--scope-file', str(root/'scope.json')])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stderr)['complete'])

    def test_schema_mismatch_and_partial_never_modify_baseline(self):
        self.fixture.write_text('{}', encoding='utf-8')
        self.assertEqual(self.run_cli(['--fixture', str(self.fixture)]).returncode, 3)
        self.write_fixture([])
        data = json.loads(self.fixture.read_text(encoding='utf-8'))
        data['pages'] = [dict(results=[], next_page_results=True, next_cursor='next')]
        self.fixture.write_text(json.dumps(data), encoding='utf-8')
        p = self.run_cli(['--fixture', str(self.fixture)])
        self.assertEqual(p.returncode, 2)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM identity').fetchone()[0], 0)

    def test_os_cycle_lock_competing_process_skips_fixture_fetch_and_releases_on_exit(self):
        code = '''from agent_assignment.poll import cycle_lock
import sys
with cycle_lock(sys.argv[1]):
    print('locked', flush=True)
    sys.stdin.readline()
'''
        child = subprocess.Popen([sys.executable, '-u', '-c', code, str(self.root/'poll.lock')], env=self.env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'locked')
            # Missing file must never be opened while another process owns cycle lock.
            p = self.run_cli(['--fixture', str(self.root/'does-not-exist')])
            self.assertEqual(p.returncode, 0)
            self.assertEqual(json.loads(p.stderr)['error_code'], 'cycle_busy')
            self.assertFalse(self.db.exists())
            competing = '''import plane_agent_poll as cli
from pathlib import Path
import sys
def request(*args, **kwargs):
    Path(sys.argv[1]).write_text('requested')
    raise AssertionError('must not fetch while cycle busy')
cli.FixtureClient.request = request
raise SystemExit(cli.main(sys.argv[2:]))
'''
            marker = self.root/'request-attempt'
            other = subprocess.run([sys.executable, '-c', competing, str(marker), '--fixture', str(self.fixture),
                                    '--scope-file', str(self.scope_file), '--db', str(self.db), '--report'], env=self.env, capture_output=True, text=True, timeout=10)
            self.assertEqual(other.returncode, 0)
            self.assertEqual(other.stdout, '')
            self.assertEqual(json.loads(other.stderr)['error_code'], 'cycle_busy')
            self.assertFalse(marker.exists(), 'competing child request count must be zero')
        finally:
            child.communicate('\n', timeout=10)
        self.assertEqual(child.returncode, 0)
        self.assertTrue((self.root/'poll.lock').exists())
        self.assertEqual(self.run_cli(['--fixture', str(self.fixture)]).returncode, 0)
