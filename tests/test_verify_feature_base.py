import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/git-repo/scripts/verify_feature_base.py'

class BaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'core.hooksPath', '/dev/null')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.commit('owned.txt')
        self.base = self.git('rev-parse', 'HEAD').strip()
    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)
    def commit(self, path):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(p.read_text() + 'next\n' if p.exists() else 'initial\n')
        self.git('add', path)
        self.git('commit', '-qm', 'fixture')
    def run_guard(self, mode='deliver', count=1, paths=('owned.txt',), base=None, extra=()):
        args=['python3', str(SCRIPT), '--repo', str(self.repo), '--base', base or self.base, '--mode', mode, '--expected-commits', str(count)]
        for p in paths: args += ['--allow-path', p]
        return subprocess.run(args + list(extra), capture_output=True, text=True)
    def test_clean_start(self):
        self.assertEqual(self.run_guard('start', 0).returncode, 0)
    def test_corrected_single_commit(self):
        self.commit('owned.txt')
        self.assertEqual(self.run_guard().returncode, 0)
    def test_old_eleven_commit_range(self):
        for _ in range(11): self.commit('owned.txt')
        self.assertNotEqual(self.run_guard().returncode, 0)
    def test_unrelated_commit(self):
        self.commit('other.txt'); self.commit('owned.txt')
        self.assertNotEqual(self.run_guard().returncode, 0)
    def test_reverted_unrelated_commit_still_rejected(self):
        self.commit('other.txt')
        self.git('rm','other.txt'); self.git('commit','-qm','fix: revert unrelated')
        self.assertNotEqual(self.run_guard(count=2).returncode,0)
    def test_out_of_scope_file(self):
        self.commit('other.txt')
        self.assertNotEqual(self.run_guard().returncode, 0)
    def test_dirty_delivery(self):
        self.commit('owned.txt'); (self.repo/'owned.txt').write_text('dirty')
        self.assertNotEqual(self.run_guard().returncode, 0)
    def test_untracked_delivery(self):
        self.commit('owned.txt'); (self.repo/'untracked').write_text('dirty')
        self.assertNotEqual(self.run_guard().returncode, 0)
    def test_missing_base(self):
        self.assertNotEqual(self.run_guard(base='absent-ref').returncode, 0)
    def test_symbolic_base_rejected(self):
        self.assertNotEqual(self.run_guard(base='HEAD').returncode, 0)
        self.assertNotEqual(self.run_guard(base='main').returncode, 0)
    def test_missing_scope(self):
        self.assertNotEqual(self.run_guard(paths=()).returncode, 0)
    def test_missing_base_argument(self):
        r=subprocess.run(['python3',str(SCRIPT),'--repo',str(self.repo),'--mode','start','--expected-commits','0','--allow-path','owned.txt'],capture_output=True)
        self.assertNotEqual(r.returncode,0)
    def test_git_error(self):
        r=self.run_guard(extra=('--repo',str(self.repo/'missing')))
        self.assertNotEqual(r.returncode,0)
    def test_start_rejects_advanced_head(self):
        self.commit('owned.txt'); self.assertNotEqual(self.run_guard('start',0).returncode,0)
    def test_directory_boundary(self):
        self.commit('owned-other/file'); self.assertNotEqual(self.run_guard(paths=('owned/',)).returncode,0)
    def test_stage_allows_only_owned_dirty(self):
        (self.repo/'owned.txt').write_text('change'); self.git('add','owned.txt')
        self.assertEqual(self.run_guard('stage',0).returncode,0)
        (self.repo/'unrelated').write_text('change')
        self.assertNotEqual(self.run_guard('stage',0).returncode,0)
    def test_stage_checks_index_even_if_worktree_reverted(self):
        (self.repo/'other.txt').write_text('staged')
        self.git('add','other.txt')
        (self.repo/'other.txt').unlink()
        self.assertNotEqual(self.run_guard('stage',0).returncode,0)
    def test_stage_rejects_hidden_staged_change(self):
        self.commit('other.txt'); self.base=self.git('rev-parse','HEAD').strip()
        (self.repo/'other.txt').write_text('staged')
        self.git('add','other.txt'); (self.repo/'other.txt').write_text('initial\n')
        self.assertNotEqual(self.run_guard('stage',0).returncode,0)
    def test_merge_single_commit_rejected(self):
        self.git('checkout','-qb','side'); self.commit('side.txt')
        self.git('checkout','-q','-'); self.commit('owned.txt')
        self.git('merge','--no-ff','-qm','merge','side')
        self.assertNotEqual(self.run_guard(count=3,paths=('owned.txt','side.txt')).returncode,0)
    def test_path_with_spaces(self):
        self.commit('file with spaces'); self.assertEqual(self.run_guard(paths=('file with spaces',)).returncode,0)
    def test_rename_scope_includes_source(self):
        self.git('mv','owned.txt','other.txt'); self.git('commit','-qm','rename')
        self.assertNotEqual(self.run_guard(paths=('other.txt',)).returncode,0)
    def test_invalid_scope(self):
        for p in ('../','/',':(glob)**','.'):
            self.assertNotEqual(self.run_guard('start',0,paths=(p,)).returncode,0)

if __name__ == '__main__': unittest.main()
