"""Regression tests for bounded PR623 tracker/index integrity corrections."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('completed', ['## Completed Projects', '## Completed'])
def test_graduation_preserves_other_sections_and_unmonitored_duplicate(tmp_path, completed):
    module = load('pinned623', 'skills/fix-plan/scripts/pinned_liveness_check.py')
    tracker = tmp_path / 'tracker.md'
    tracker.write_text('- **Mission**: resolved <!-- pinned-backing: todo:"backing" -->\n'
                       '- **Mission**: unrelated pinned objective\n\n## TODO\n'
                       '- [x] backing\n- **Mission**: unrelated task\n\n' + completed + '\n')
    result = module.auto_graduate(str(tracker))
    text = tracker.read_text()
    assert result['graduated_count'] == 1
    assert 'unrelated task' in text
    assert 'unrelated pinned objective' in text
    assert '\n## Completed\n' in text
    assert module.auto_graduate(str(tracker))['graduated_count'] == 0

def test_executable_index_does_not_mask_missing_filesystem_bit(tmp_path):
    module = load('hooks623', 'scripts/verify-hooks-json.py')
    root = tmp_path / 'repo'
    (root / 'hooks').mkdir(parents=True)
    script = root / 'guard.sh'
    script.write_text('#!/bin/sh\nexit 0\n')
    script.chmod(0o755)
    config = root / 'hooks/hooks.json'
    config.write_text(json.dumps({'hooks': {'Stop': [{'hooks': [{'command': '${CLAUDE_PLUGIN_ROOT}/guard.sh'}]}]}}))
    subprocess.run(['git', 'init', str(root)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(root), 'add', 'guard.sh', 'hooks/hooks.json'], check=True, capture_output=True)
    script.chmod(0o644)
    errors, _, _ = module.check_hooks_file(config, root)
    assert len(errors) == 1 and 'Non-executable' in errors[0]
