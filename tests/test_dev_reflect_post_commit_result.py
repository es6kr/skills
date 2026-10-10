"""Post-commit reporting must not invent successful reflection."""
import os
from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('helper,expected', [('echo "[dev-reflect] SKIP: same repository"', 'SKIP'), ('exit 7', 'WARNING')])
def test_post_commit_reports_real_helper_outcome(tmp_path, helper, expected):
    home = tmp_path / 'home'
    (home / '.claude/plugins/marketplaces/es6kr-skills').mkdir(parents=True)
    repo = tmp_path / 'repo'
    script = repo / 'skills/cc-plugin/scripts/dev-reflect.sh'
    script.parent.mkdir(parents=True)
    script.write_text('#!/bin/bash\n'+helper+'\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['HOME'] = str(home)
    subprocess.run(['git', 'init', '-q', str(repo)], env=env, check=True, capture_output=True)
    result = subprocess.run(['bash', str(ROOT / '.githooks/post-commit')], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert expected in result.stdout+result.stderr
    assert 'completed' not in result.stdout
