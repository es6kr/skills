"""check-pm-turn-budget.py — the advisory must actually reach the model.

The hook runs as PostToolUse. On that event an exit code of 0 discards stderr,
so a warning printed with `exit 0` is written to a channel nobody reads. The
repo's own convention for an advisory PostToolUse hook is stderr + `exit 2`
(documented in skills/fix-plan/resources/warn-fixplan-item-schema.sh: "PostToolUse
stderr + exit 2 is LLM-exposed. ADVISORY only").

`HOME` is redirected per-test because the script derives its state path from
`~/.claude/state` with no override — without this the suite would mutate the
real counter file.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(
    os.path.dirname(__file__), '..',
    'skills', 'hook-kit', 'resources', 'check-pm-turn-budget.py',
)

BUDGET_LIMIT = 30
SESSION = 'test-session'


def run_hook(home, payload):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home          # expanduser fallback on Windows runners
    env['PM_MODE'] = '1'
    return subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )


def seed_counter(home, count):
    state_dir = os.path.join(home, '.claude', 'state')
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, 'pm-session-counters.json'), 'w', encoding='utf-8') as f:
        json.dump({SESSION: {'count': count, 'is_pm': True}}, f)


class TestPmTurnBudgetVisibility(unittest.TestCase):
    def test_warning_is_exposed_to_the_model(self):
        with tempfile.TemporaryDirectory() as home:
            # One call short of the limit, so this invocation is the one that warns.
            seed_counter(home, BUDGET_LIMIT - 1)
            res = run_hook(home, {'session_id': SESSION, 'tool_name': 'Bash', 'tool_input': {}})
            self.assertIn('PM Turn Budget', res.stderr)
            self.assertEqual(
                res.returncode, 2,
                'a PostToolUse advisory needs exit 2 to be LLM-exposed; '
                'exit 0 discards stderr and the model never sees the warning',
            )

    def test_silent_call_stays_exit_zero(self):
        with tempfile.TemporaryDirectory() as home:
            seed_counter(home, 1)
            res = run_hook(home, {'session_id': SESSION, 'tool_name': 'Bash', 'tool_input': {}})
            self.assertEqual(res.stderr.strip(), '')
            self.assertEqual(res.returncode, 0, 'no advisory means nothing to surface')


if __name__ == '__main__':
    unittest.main()
