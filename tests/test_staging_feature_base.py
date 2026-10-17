import subprocess
import tempfile
import unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'skills/git-repo/scripts/local-to-staging-pr.sh'
class StagingGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'source';self.repo.mkdir()
        self.git('init','-q');self.git('config','core.hooksPath','/dev/null');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid')
        (self.repo/'owned.txt').write_text('base');self.git('add','owned.txt');self.git('commit','-qm','chore: base');self.git('branch','develop')
        subprocess.run(['git','clone','--bare','-q',str(self.repo),str(self.root/'remote.git')],check=True)
        self.git('remote','add','origin',str(self.root/'remote.git'))
        (self.repo/'owned.txt').write_text('feature');self.git('add','owned.txt');self.git('commit','-qm','fix: feature');self.sha=self.git('rev-parse','HEAD').strip()
    def git(self,*args):return subprocess.check_output(['git','-C',str(self.repo),*args],text=True)
    def run_script(self,*args):return subprocess.run(['bash',str(SCRIPT),str(self.repo),self.sha,'--branch','fix/fixture','--base','develop',*args],capture_output=True,text=True)
    def test_missing_scope_rejected_before_creation(self):
        r=self.run_script();self.assertNotEqual(r.returncode,0);self.assertFalse((self.repo/'.claude/worktrees/fix-fixture').exists())
    def test_scoped_transfer_passes_and_exact_count(self):
        r=self.run_script('--allow-path','owned.txt');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        w=self.repo/'.claude/worktrees/fix-fixture';count=subprocess.check_output(['git','-C',str(w),'rev-list','--count','origin/develop..HEAD'],text=True).strip();self.assertEqual(count,'1');self.assertIn('"valid": true',r.stdout)
    def test_unrelated_scope_blocks_delivery_without_deleting_payload(self):
        r=self.run_script('--allow-path','other.txt');self.assertNotEqual(r.returncode,0)
        self.assertTrue((self.repo/'.claude/worktrees/fix-fixture/owned.txt').exists())
if __name__=='__main__':unittest.main()
