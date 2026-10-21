"""Executable regressions for still-live PR572 residual behavior."""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'skills/hook-kit/resources'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Residual572Tests(unittest.TestCase):
    def test_poll_guard_observes_non_bash_calls(self):
        data = json.loads((ROOT / 'hooks/hooks.json').read_text())
        groups = [g for g in data['hooks']['PreToolUse'] if any('check-excessive-ci-polling.sh' in h.get('command', '') for h in g['hooks'])]
        self.assertEqual([g.get('matcher') for g in groups], ['*'])

    def test_pm_budget_observes_skill_and_non_bash_calls(self):
        data = json.loads((ROOT / 'hooks/hooks.json').read_text())
        groups = [g for g in data['hooks']['PostToolUse'] if any('check-pm-turn-budget.sh' in h.get('command', '') for h in g['hooks'])]
        self.assertEqual([g.get('matcher') for g in groups], ['*'])

    def test_pm_skill_call_activates_without_bash_mention(self):
        mod = load(RES / 'check-pm-turn-budget.py', 'budget')
        with tempfile.TemporaryDirectory() as d:
            mod.STATE_DIR = d
            mod.STATE_FILE = str(Path(d) / 'state.json')
            mod.track_pm_budget('Skill', {'skill': 'es6kr:fix-plan', 'args': '--pm'}, 's')
            self.assertTrue(mod.get_state().get('s', {}).get('is_pm'))

    def test_polled_streak_resets_on_read(self):
        mod = load(RES / 'check-excessive-ci-polling.py', 'poll')
        with tempfile.TemporaryDirectory() as d:
            mod.STATE_DIR = d
            mod.STATE_FILE = str(Path(d) / 'state.json')
            for _ in range(7):
                self.assertIsNone(mod.check_polling('Bash', {'command': 'gh pr checks'}, 's'))
            mod.check_polling('Read', {'path': 'source.py'}, 's')
            self.assertIsNone(mod.check_polling('Bash', {'command': 'gh pr checks'}, 's'))

    def concurrent_state(self, filename, expression):
        with tempfile.TemporaryDirectory() as d:
            code = ("import importlib.util,time; from pathlib import Path; "
                    "s=importlib.util.spec_from_file_location('guard',%r);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                    "m.STATE_DIR=%r;m.STATE_FILE=%r; original=m.get_state; "
                    "exec('def delayed():\\n value=original()\\n time.sleep(0.08)\\n return value');m.get_state=delayed;" %
                    (str(RES / filename), d, str(Path(d) / 'state.json')))
            def call(i):
                p = subprocess.run([sys.executable, '-c', code + expression.replace('SESSION', repr(str(i)))], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(call, range(8)))
            return json.loads((Path(d) / 'state.json').read_text())

    def test_polling_transactions_preserve_concurrent_sessions(self):
        state = self.concurrent_state('check-excessive-ci-polling.py', "m.check_polling('Bash',{'command':'gh pr checks'},SESSION)")
        self.assertEqual(len(state), 8)

    def test_budget_transactions_preserve_concurrent_sessions(self):
        state = self.concurrent_state('check-pm-turn-budget.py', "m.track_pm_budget('Bash',{'command':'fix-plan --pm'},SESSION)")
        self.assertEqual(len(state), 8)

    def test_fenced_example_does_not_create_fa_section(self):
        path = ROOT / 'skills/fa/scripts/fa-classify.py'
        text = '# Log\n\n## Actual\nDetails\n```markdown\n## Example only\n```\n\n## Second\nBody\n'
        # This CLI owns/reconfigures stdout at import time; isolate that side
        # effect instead of closing pytest's capture stream in the parent.
        code = ("import importlib.util,json; s=importlib.util.spec_from_file_location('classifier',%r);"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                "print(json.dumps([m.section_title(s) for s in m.split_sections(%r)]))" % (str(path), text))
        p = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), ['Actual', 'Second'])

    def test_rotation_keeps_recovery_snapshots(self):
        mod = load(ROOT / 'skills/fa/scripts/rotate_improvements.py', 'rotate_backup')
        text = '# Ledger\n## Topic\n### Applied\n- **Tag**: [APPLIED]\n'
        with tempfile.TemporaryDirectory() as d:
            source, archive = Path(d) / 'ledger.md', Path(d) / 'archive.md'
            source.write_text(text)
            archive.write_text('Earlier history\n')
            mod.rotate_file(str(source), str(archive))
            self.assertTrue(Path(str(source) + '.bak').exists())
            self.assertEqual(Path(str(source) + '.bak').read_text(), text)
            self.assertEqual(Path(str(archive) + '.bak').read_text(), 'Earlier history\n')

    def test_rotate_ignores_example_headings_and_tags(self):
        mod = load(ROOT / 'skills/fa/scripts/rotate_improvements.py', 'rotate')
        text = '# Ledger\n## Topic\n### Real active\n```markdown\n### Example resolved\n- **Tag**: [APPLIED]\n```\n> - **Tag**: [DONE]\n- **Tag**: [NEEDS_REVIEW]\n'
        _, _, active, resolved = mod.parse_improvements(text)
        self.assertEqual(len(active), 1)
        self.assertEqual(len(resolved), 0)
        self.assertIn('Example resolved', active[0]['text'])

    def test_loop_threshold_ignores_task_count(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            script = base / 'guard.sh'
            shutil.copy(ROOT / 'skills/hook-kit/resources/block-premature-ralph-loop-cleanup.sh', script)
            (base / 'context-usage-inject.sh').write_text('printf "Context usage: ~30k / 100k tokens (30%%)\\n"\n')
            (base / '.claude').mkdir()
            (base / '.claude/ralph-loop.local.md').write_text('active: true\ncompletion_promise: finish 3 tasks then context usage > 45%\n')
            transcript = base / 'transcript.jsonl'
            transcript.write_text('{}\n')
            payload = {'tool_name': 'Skill', 'tool_input': {'skill': 'cleanup'}, 'cwd': d, 'transcript_path': str(transcript)}
            p = subprocess.run(['bash', str(script)], cwd=d, input=json.dumps(payload), text=True, capture_output=True)
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertIn('45%', p.stderr)

    def test_stream_search_waits_for_async_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'ledger.md').write_text('needle\\n')
            script = str(ROOT / 'skills/fa/scripts/stream-search-fa.js')
            # Delayed writable models the async pipe contract on Linux. The actual
            # CLI source still runs unchanged; this is not a live Linux claim.
            wrapper = ('const real=process.stdout.write.bind(process.stdout);'
                       'process.stdout.write=(s)=>{setTimeout(()=>real(s),10);return true;};'
                       'process.argv=[process.execPath,' + json.dumps(script) + ',"needle","--dir",' + json.dumps(d) + ',"--json"];'
                       'require(' + json.dumps(script) + ');')
            p = subprocess.run(['node', '-e', wrapper], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(len(p.stdout.splitlines()), 1)

    def test_stream_search_flushes_all_pipe_records(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'ledger.md').write_text(('needle ' + 'x' * 280 + '\n') * 1200)
            p = subprocess.run(['node', str(ROOT / 'skills/fa/scripts/stream-search-fa.js'), 'needle', '--dir', d, '--max-matches', '1200', '--json'], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            rows = [json.loads(l) for l in p.stdout.splitlines()]
            self.assertEqual(len(rows), 1200)


if __name__ == '__main__':
    unittest.main()
