"""Post-commit reporting must not invent successful reflection."""
import os
from pathlib import Path
import subprocess
import shutil
import pytest
ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash')

@pytest.mark.parametrize('helper,expected', [('echo "[dev-reflect] SKIP: same repository"', 'SKIP'), ('exit 7', 'WARNING')])
def test_post_commit_reports_real_helper_outcome(tmp_path, helper, expected, monkeypatch):
    # The helper-outcome contract must not inherit a developer's opt-out.
    monkeypatch.setenv('ES6KR_DEV_REFLECT', '0')
    home = tmp_path / 'home'
    (home / '.claude/plugins/marketplaces/es6kr-skills').mkdir(parents=True)
    repo = tmp_path / 'repo'
    script = repo / 'skills/cc-plugin/scripts/dev-reflect.sh'
    script.parent.mkdir(parents=True)
    script.write_text('#!/bin/bash\n'+helper+'\n')
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('GIT_') and k != 'ES6KR_DEV_REFLECT'}
    env['HOME'] = home.as_posix()
    env['USERPROFILE'] = str(home)
    subprocess.run(['git', 'init', '-q', str(repo)], env=env, check=True, capture_output=True)
    result = subprocess.run([BASH, (ROOT / '.githooks/post-commit').as_posix()], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert expected in result.stdout+result.stderr
    assert 'completed' not in result.stdout


@pytest.mark.parametrize('setting', [None, '0', '1', 'false'])
def test_post_commit_reflection_is_explicitly_optional(tmp_path, setting):
    home = tmp_path / 'home'
    (home / '.claude/plugins/marketplaces/es6kr-skills').mkdir(parents=True)
    repo = tmp_path / 'repo'
    script = repo / 'skills/cc-plugin/scripts/dev-reflect.sh'
    script.parent.mkdir(parents=True)
    script.write_text('#!/bin/sh\nprintf reflected > reflected-marker\n')
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('GIT_') and k != 'ES6KR_DEV_REFLECT'}
    env.update(HOME=home.as_posix(), USERPROFILE=str(home))
    if setting is not None:
        env['ES6KR_DEV_REFLECT'] = setting
    subprocess.run(['git', 'init', '-q', str(repo)], env=env, check=True, capture_output=True)
    result = subprocess.run([BASH, (ROOT / '.githooks/post-commit').as_posix()],
                            cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (repo / 'reflected-marker').exists() == (setting != '0')
    if setting == '0':
        assert 'SKIP' in result.stdout
