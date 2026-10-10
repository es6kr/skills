"""Ensure native pre-push clears Git-local context before repository fixtures."""
import json
import os
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('variables', [('GIT_DIR',), ('GIT_DIR', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE', 'GIT_WORK_TREE')])
def test_pre_push_prefix_clears_git_local_variables(tmp_path, variables):
    clean = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    repo = tmp_path / 'sandbox'
    subprocess.run(['git', 'init', '-q', str(repo)], env=clean, check=True, capture_output=True)
    values = {'GIT_DIR': str(repo / '.git'), 'GIT_COMMON_DIR': str(repo / '.git'), 'GIT_INDEX_FILE': str(repo / '.git/index'), 'GIT_WORK_TREE': str(repo)}
    env = {**clean, **{k: values[k] for k in variables}, 'GIT_EDITOR': 'true'}
    prefix = (ROOT / '.githooks/pre-push').read_text().split("# 'local' branch push guard", 1)[0]
    probe = prefix + '\npython3 -c "import os,json;print(json.dumps(dict(os.environ)))"\n'
    result = subprocess.run(['sh'], input=probe, text=True, capture_output=True, cwd=repo, env=env, check=True)
    observed = json.loads(result.stdout)
    assert all(k not in observed for k in variables), 'Git context leaked into fixture processes'
    assert observed['GIT_EDITOR'] == 'true'
