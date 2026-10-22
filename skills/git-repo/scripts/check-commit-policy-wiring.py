#!/usr/bin/env python3
"""Read-only wiring audit plus isolated acceptance/rejection probes.

Never stage or commit in the inspected repository. The probe executes its local
checker in a temporary Git fixture; use doctor only on trusted checkouts.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()


def uncomment(path):
    try:
        return '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines()
                         if not line.lstrip().startswith('#'))
    except (OSError, UnicodeError):
        return ''


def emit(identifier, status, message):
    tier = 'Base' if identifier.startswith('BASE') else 'Conditional'
    category = 'Global Commit Hook' if identifier == 'BASE-8' else 'Commit Tag Semantics'
    print('|'.join((identifier, tier, category, status, message.replace('|', '/').replace('\n', ' '))))


def probe(source, active):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM='1')
    with tempfile.TemporaryDirectory(prefix='commit-policy-doctor-') as directory:
        root = Path(directory)
        def run(*args, **kwargs):
            return subprocess.run(['git', '-C', str(root), *args], env=env, capture_output=True,
                                  timeout=15, **kwargs)
        run('init', '-q', check=True)
        run('config', 'user.name', 'Doctor Fixture', check=True)
        run('config', 'user.email', 'fixture@example.invalid', check=True)
        (root / 'scripts').mkdir()
        (root / '.githooks').mkdir()
        for name in ('check_commit_tags.py', 'commit-tag-policy-hook.sh'):
            shutil.copy2(source / 'scripts' / name, root / 'scripts' / name)
        for name in ('commit-msg', 'pre-push'):
            shutil.copy2(active / name, root / '.githooks' / name)
        run('config', 'core.hooksPath', str(root / '.githooks'), check=True)
        (root / 'README.md').write_text('fixture\n', encoding='utf-8')
        run('add', 'README.md', check=True)
        run('commit', '-qm', 'docs: initialize fixture', check=True)
        base = run('rev-parse', 'HEAD', check=True).stdout.strip()
        path = root / 'plugins/probe/skills/example/SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text('fixture instructions\n', encoding='utf-8')
        run('add', '--', str(path.relative_to(root)), check=True)
        # Git commit may refresh index stat/cache metadata itself. Compare the
        # staged tree here; the checker-only suite separately compares raw bytes.
        before = run('write-tree', check=True).stdout.strip()
        bad = run('commit', '-qm', 'docs(probe): hide behavior')
        if bad.returncode == 0 or b'skill behavior' not in bad.stdout + bad.stderr:
            return False
        if run('rev-parse', 'HEAD', check=True).stdout.strip() != base or run('write-tree', check=True).stdout.strip() != before:
            return False
        run('commit', '-qm', 'feat(probe): add behavior', check=True)
        good = run('rev-parse', 'HEAD', check=True).stdout.strip()
        # Create one deliberately invalid fixture commit via plumbing, without
        # bypassing or mutating any hook/configuration in the inspected checkout.
        path.write_text('changed instructions\n', encoding='utf-8')
        run('add', '--', str(path.relative_to(root)), check=True)
        tree = run('write-tree', check=True).stdout.strip()
        bad_head = run('commit-tree', tree.decode(), '-p', good.decode(),
                       input=b'docs(probe): hide behavior\n', check=True).stdout.strip()
        protocol = b'refs/heads/probe ' + bad_head + b' refs/heads/probe ' + good + b'\n'
        pushed = subprocess.run([str(root / '.githooks/pre-push'), 'origin', 'unused'],
                                cwd=root, env=env, input=protocol, capture_output=True, timeout=15)
        return pushed.returncode == 1 and b'skill behavior' in pushed.stdout + pushed.stderr


def main():
    root = Path(sys.argv[1]).resolve()
    active = Path(git(root, 'rev-parse', '--git-path', 'hooks'))
    if not active.is_absolute():
        active = root / active
    msg = active / 'commit-msg'
    push = active / 'pre-push'
    global_result = subprocess.run(['git', '-C', str(root), 'config', '--global', '--get', 'core.hooksPath'],
                                   capture_output=True, text=True)
    global_dir = Path(global_result.stdout.strip()).expanduser() if global_result.stdout.strip() else None
    if global_dir and not global_dir.is_absolute():
        global_dir = root / global_dir
    if global_dir and (global_dir / 'commit-msg').is_file() and os.access(global_dir / 'commit-msg', os.X_OK) \
            and global_dir.resolve() != active.resolve():
        content = uncomment(msg)
        if not os.access(msg, os.X_OK) or not re.search(r'git\s+config\s+--global', content) \
                or not re.search(r'^\s*["\x27]?\$.*?/commit-msg["\x27]?\s', content, re.M):
            emit('BASE-8', 'FAIL', 'Local hooksPath shadows an executable global commit-msg without a declared forwarding call.')
        else:
            emit('BASE-8', 'PASS', 'Repository commit-msg declares forwarding to the global validator; live global behavior is not certified.')
    else:
        emit('BASE-8', 'PASS', 'No separate executable global commit-msg is shadowed.')
    tracked = git(root, 'ls-files').splitlines()
    if not any(p.endswith('/SKILL.md') for p in tracked):
        return
    checker = root / 'scripts/check_commit_tags.py'
    runner = root / 'scripts/commit-tag-policy-hook.sh'
    missing = []
    for path, token in ((msg, '--staged'), (push, '--pre-push')):
        content = uncomment(path)
        invocation = re.search(r'^\s*(?:exec\s+)?(?:(?:bash|sh)\s+)?["\x27]?(?:\$[^\s\n]+/|[^\s\n]*/)?commit-tag-policy-hook\.sh["\x27]?\s+.*' + re.escape(token), content, re.M)
        if not path.is_file() or not os.access(path, os.X_OK) or not invocation:
            missing.append(path.name + ' executable invocation')
    if not checker.is_file() or not runner.is_file() or not os.access(runner, os.X_OK):
        missing.append('shared checker/runner')
    workflows = list((root / '.github/workflows').glob('*.yml')) + list((root / '.github/workflows').glob('*.yaml'))
    ci = '\n'.join(uncomment(p) for p in workflows)
    if not re.search(r'(?:run:\s*|^\s*)(?:python3?|["\x27]?\$[^\s]+)\s+scripts/check_commit_tags\.py\s+.*--base', ci, re.M):
        missing.append('CI range-policy invocation')
    if missing:
        emit('COND-COMMIT-TAG', 'FAIL', 'Missing commit-type enforcement: ' + ', '.join(missing))
        return
    try:
        passed = probe(root, active)
    except (OSError, ValueError, subprocess.SubprocessError):
        passed = False
    if passed:
        emit('COND-COMMIT-TAG', 'PASS', 'Declared commit-msg/pre-push/CI wiring; isolated nested-skill docs rejection and feat acceptance passed. Not a live CI/branch-protection receipt.')
    else:
        emit('COND-COMMIT-TAG', 'FAIL', 'Shared checker failed isolated acceptance/rejection or index-preservation probe.')


if __name__ == '__main__':
    main()
