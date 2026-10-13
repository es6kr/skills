"""Compound live-write/query gate regressions; command text is data only."""
import json
import os
from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('command,expected', [
    ('curl -X POST https://example.invalid/points/search -d "{}"', 0),
    ('curl -X POST https://example.invalid/points/scroll -d "{}"', 0),
    ('kubectl apply -f mutation.yaml; curl -X POST https://example.invalid/points/search -d "{}"', 2),
    ('curl -X POST https://example.invalid/points/upsert -d "{}"; curl -X POST https://example.invalid/points/search -d "{}"', 2),
    ('curl -X POST https://example.invalid/points/search -d "{}"; git push', 2),
])
def test_readonly_query_exemption_does_not_clear_compound_mutation(tmp_path, command, expected):
    transcript = tmp_path / 'transcript.jsonl'
    transcript.write_text(json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': '/fixture/checklist.md'}}]}}) + '\n')
    payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'transcript_path': str(transcript)}
    env = dict(os.environ)
    env.pop('RALPH_LOOP', None)
    env.pop('AGENT_HEADLESS', None)
    result = subprocess.run(['bash', str(ROOT / 'skills/hook-kit/resources/block-live-action-without-workflow-skill.sh')], input=json.dumps(payload), text=True, capture_output=True, env=env)
    assert result.returncode == expected, result.stdout + result.stderr