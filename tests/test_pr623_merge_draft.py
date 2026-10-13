"""Exercise the canonical-base/draft expression prescribed by merge.md."""
from pathlib import Path
import json
import re
import subprocess
import pytest

@pytest.mark.parametrize('base,draft,expected', [('main', True, False), ('master', True, False), ('main', False, True), ('master', False, True), ('develop', False, False)])
def test_merge_review_scope_excludes_drafts(base, draft, expected):
    text = (Path(__file__).resolve().parents[1] / 'skills/github-flow/merge.md').read_text()
    scope = text.split('**Scope gate', 1)[1].split('**Why the scoping exists', 1)[0]
    assert '--json baseRefName,isDraft' in scope
    expression = re.search(r"--jq '([^']+)'", scope).group(1)
    result = subprocess.run(['jq', expression], input=json.dumps({'baseRefName': base, 'isDraft': draft}), text=True, capture_output=True, check=True)
    assert json.loads(result.stdout) is expected
