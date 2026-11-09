"""Doctor must expose absent semantic enforcement, not report wiring as coverage."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

DOCTOR = Path(__file__).resolve().parents[1] / 'scripts/git-repo-doctor.sh'


class CommitPolicyDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        subprocess.run(['git', 'init', '-q', str(self.root)], env=self.env, check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'core.hooksPath', '.githooks'], env=self.env, check=True)
        self.put('skills/check/SKILL.md', 'instruction\n')
        subprocess.run(['git', '-C', str(self.root), 'add', 'skills/check/SKILL.md'], env=self.env, check=True)
        self.put('.githooks/pre-commit', '#!/bin/sh\nexit 0\n', executable=True)

    def put(self, name, text, executable=False):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        if executable:
            p.chmod(0o755)
        return p

    def rows(self):
        r = subprocess.run(['bash', str(DOCTOR), str(self.root), '--json'], env=self.env,
                           capture_output=True, text=True, timeout=30)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return {x['id']: x for x in json.loads(r.stdout)['results']}

    def test_missing_commit_msg_and_policy_are_not_pass(self):
        rows = self.rows()
        self.assertIn('COND-COMMIT-TAG', rows)
        self.assertEqual(rows['COND-COMMIT-TAG']['status'], 'FAIL')

    def test_comments_do_not_establish_wiring(self):
        self.put('.githooks/commit-msg', '#!/bin/sh\n# commit-tag-policy-hook.sh --staged\nexit 0\n', True)
        self.put('.githooks/pre-push', '#!/bin/sh\n# commit-tag-policy-hook.sh --pre-push\nexit 0\n', True)
        self.put('scripts/check_commit_tags.py', 'raise SystemExit(0)\n')
        self.assertEqual(self.rows()['COND-COMMIT-TAG']['status'], 'FAIL')

    def test_data_files_are_not_hook_executable_failures(self):
        self.put('.githooks/private-refs.regex', '# local data\n')
        rows = self.rows()
        self.assertFalse(any(x['id'] == 'BASE-2' and x['status'] == 'FAIL'
                             for x in rows.values()))

    def test_global_commit_msg_shadow_is_detected(self):
        global_dir = self.root / 'global-hooks'
        global_dir.mkdir()
        p = global_dir / 'commit-msg'
        p.write_text('#!/bin/sh\nexit 1\n')
        p.chmod(0o755)
        config = self.root / 'global-config'
        config.write_text('[core]\n hooksPath = ' + str(global_dir) + '\n')
        self.env['GIT_CONFIG_GLOBAL'] = str(config)
        rows = self.rows()
        self.assertIn('BASE-8', rows)
        self.assertEqual(rows['BASE-8']['status'], 'FAIL')

    def test_non_executable_post_index_change_is_detected(self):
        self.put('.githooks/post-index-change', '#!/bin/sh\nexit 0\n')
        self.assertEqual(self.rows()['BASE-2']['status'], 'FAIL')

    def test_relative_global_hook_is_resolved_from_target(self):
        self.put('.relative-global/commit-msg', '#!/bin/sh\nexit 1\n', True)
        config = self.root / 'global-config'
        config.write_text('[core]\n hooksPath = .relative-global\n')
        self.env['GIT_CONFIG_GLOBAL'] = str(config)
        helper = DOCTOR.parent / 'check-commit-policy-wiring.py'
        r = subprocess.run(['python3', str(helper), str(self.root)], cwd=self.root.parent,
                           env=self.env, capture_output=True, text=True, check=True)
        rows = {line.split('|', 1)[0]: line.split('|')[3] for line in r.stdout.splitlines()}
        self.assertEqual(rows['BASE-8'], 'FAIL')

    def test_noop_runner_is_rejected_with_functional_checker(self):
        self.put('.githooks/commit-msg', '#!/bin/sh\nsh scripts/commit-tag-policy-hook.sh --staged --message-file "$1"\n', True)
        self.put('.githooks/pre-push', '#!/bin/sh\nsh scripts/commit-tag-policy-hook.sh --pre-push\n', True)
        self.put('scripts/commit-tag-policy-hook.sh', '#!/bin/sh\nexit 0\n', True)
        # Diagnostic fixture: the checker rejects docs, while the runner bypasses it.
        self.put('scripts/check_commit_tags.py', 'import sys\nfrom pathlib import Path\np=Path(sys.argv[sys.argv.index("--message-file")+1])\nraise SystemExit(1 if p.read_text().startswith("docs") else 0)\n')
        self.put('.github/workflows/policy.yml', 'jobs:\n  check:\n    steps:\n      - run: python3 scripts/check_commit_tags.py --base "$BASE" --head "$HEAD"\n')
        self.assertEqual(self.rows()['COND-COMMIT-TAG']['status'], 'FAIL')

    def test_bash_runner_wiring_and_native_probe_pass(self):
        self.put('.githooks/commit-msg', '#!/bin/sh\nbash scripts/commit-tag-policy-hook.sh --staged --message-file "$1"\n', True)
        self.put('.githooks/pre-push', '#!/bin/sh\nbash scripts/commit-tag-policy-hook.sh --pre-push\n', True)
        self.put('scripts/commit-tag-policy-hook.sh', '#!/bin/sh\nexec python3 scripts/check_commit_tags.py "$@"\n', True)
        # Small diagnostic fixture, not the production policy: enough to exercise
        # both actual hook processes and the doctor's explicit bounded probes.
        self.put('scripts/check_commit_tags.py', 'import sys,subprocess\nfrom pathlib import Path\nif "--pre-push" in sys.argv:\n print("skill behavior fixture rejection")\n raise SystemExit(1)\nmessage=Path(sys.argv[sys.argv.index("--message-file")+1]).read_text()\npaths=subprocess.check_output(["git","diff","--cached","--name-only"],text=True)\nbad="skills/" in paths and message.startswith("docs")\nif bad: print("skill behavior fixture rejection")\nraise SystemExit(1 if bad else 0)\n')
        self.put('.github/workflows/policy.yml', 'jobs:\n  check:\n    steps:\n      - run: python3 scripts/check_commit_tags.py --base "$BASE" --head "$HEAD"\n')
        before = (self.root / '.git/index').read_bytes()
        self.assertEqual(self.rows()['COND-COMMIT-TAG']['status'], 'PASS')
        self.assertEqual((self.root / '.git/index').read_bytes(), before)

    def test_noop_checker_is_rejected_even_with_declared_calls(self):
        self.put('.githooks/commit-msg', '#!/bin/sh\nsh scripts/commit-tag-policy-hook.sh --staged --message-file "$1"\n', True)
        self.put('.githooks/pre-push', '#!/bin/sh\nsh scripts/commit-tag-policy-hook.sh --pre-push\n', True)
        self.put('scripts/commit-tag-policy-hook.sh', '#!/bin/sh\nexit 0\n', True)
        self.put('scripts/check_commit_tags.py', 'raise SystemExit(0)\n')
        self.put('.github/workflows/policy.yml', 'jobs:\n  check:\n    steps:\n      - run: python3 scripts/check_commit_tags.py --base "$BASE" --head "$HEAD"\n')
        self.assertEqual(self.rows()['COND-COMMIT-TAG']['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
