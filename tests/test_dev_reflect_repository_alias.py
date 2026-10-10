"""Never mirror a linked worktree over another checkout of its repository."""
import json
import os
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/cc-plugin/scripts/dev-reflect.sh'

@pytest.mark.parametrize('inherited_git_dir', [False, True])
def test_separate_destination_still_reflects(tmp_path, inherited_git_dir):
    home = tmp_path / 'home'
    clone = home / '.claude/plugins/marketplaces/local'
    source = tmp_path / 'source'
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['HOME'] = str(home)
    for repo in (source, clone):
        (repo / '.claude-plugin').mkdir(parents=True)
        (repo / 'skills').mkdir()
        (repo / '.claude-plugin/marketplace.json').write_text(json.dumps({'name': 'local', 'plugins': []}))
        subprocess.run(['git', 'init', '-q', str(repo)], env=env, check=True, capture_output=True)
    (source / 'skills/new.md').write_text('source content')
    if inherited_git_dir:
        env['GIT_DIR'] = str(source / '.git')
    result = subprocess.run(['bash', str(SCRIPT), '--source', str(source), '--marketplace', 'local'], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert 'SKIP' not in result.stdout
    assert (clone / 'skills/new.md').read_text() == 'source content'


@pytest.mark.parametrize('linked', [False, True])
@pytest.mark.parametrize('inherited_git_dir', [False, True])
def test_same_repository_destination_is_skipped(tmp_path, linked, inherited_git_dir):
    home = tmp_path / 'home'
    clone = home / '.claude/plugins/marketplaces/local'
    clone.parent.mkdir(parents=True)
    repo = tmp_path / 'repo'
    (repo / '.claude-plugin').mkdir(parents=True)
    (repo / 'skills').mkdir()
    (repo / '.claude-plugin/marketplace.json').write_text(json.dumps({'name': 'local', 'plugins': []}))
    (repo / 'skills/kept.md').write_text('tracked source')
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['HOME'] = str(home)
    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], env=env, text=True, capture_output=True, check=True)
    git('init', '-q')
    git('add', '--all')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')
    source = repo
    if linked:
        source = tmp_path / 'linked'
        git('worktree', 'add', '--detach', str(source))
    clone.symlink_to(repo, target_is_directory=True)
    marker = repo / 'skills/preserve-local-only.md'
    marker.write_text('uncommitted user content')
    before = {p: p.read_bytes() for p in (marker, repo / '.claude-plugin/marketplace.json', repo / 'skills/kept.md')}
    if inherited_git_dir:
        env['GIT_DIR'] = git('rev-parse', '--absolute-git-dir').stdout.strip()
    result = subprocess.run(['bash', str(SCRIPT), '--source', str(source), '--marketplace', 'local'], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert 'SKIP' in result.stdout, result.stdout
    assert all(p.is_file() and p.read_bytes() == content for p, content in before.items())
