#!/usr/bin/env python3
"""Read-only explicit-base/range/scope gate. No fetch, staging or mutation."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

class Rejected(ValueError):
    pass

def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, timeout=15)
    if result.returncode:
        raise Rejected('git command failed: ' + args[0] + ': ' + result.stderr.decode(errors='replace').strip())
    return result.stdout

def paths(repo, *args):
    return [os.fsdecode(p) for p in git(repo, *args).split(b'\0') if p]

def verify(repo, base, mode, expected_commits, allowed_paths):
    repo = Path(repo).resolve(strict=True)
    if expected_commits < 0 or (mode == 'start' and expected_commits != 0):
        raise Rejected('start requires zero expected commits; counts must be nonnegative')
    if not base or not re.match(r'^(?:[a-f0-9]{40}|[a-f0-9]{64})$', base):
        raise Rejected('explicit pinned commit SHA required for base')
    if not allowed_paths:
        raise Rejected('explicit nonempty allowed paths required')
    allowed = []
    for p in allowed_paths:
        if not isinstance(p, str) or not p or p.startswith(('/', ':')) or '\\' in p or '\0' in p:
            raise Rejected('scope must contain literal repository-relative paths')
        bits = p.rstrip('/').split('/')
        if any(b in ('', '.', '..') for b in bits):
            raise Rejected('scope cannot contain empty, dot or parent components')
        allowed.append((p.rstrip('/'), p.endswith('/')))
    root = Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip()).resolve()
    if root != repo:
        raise Rejected('repo must name the worktree root')
    base_sha = git(repo, 'rev-parse', '--verify', base + '^{commit}').decode().strip()
    head = git(repo, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    gitdir = Path(os.fsdecode(git(repo, 'rev-parse', '--absolute-git-dir')).strip())
    if any((gitdir / n).exists() for n in ('CHERRY_PICK_HEAD','MERGE_HEAD','REBASE_HEAD','BISECT_LOG','rebase-merge','rebase-apply')):
        raise Rejected('in-progress git operation')
    if git(repo, 'ls-files', '-u'):
        raise Rejected('unmerged index')
    git(repo, 'merge-base', '--is-ancestor', base_sha, head)
    count = int(git(repo, 'rev-list', '--count', base_sha + '..' + head))
    if count != expected_commits:
        raise Rejected(f'commit count {count} != expected {expected_commits}')
    if mode == 'start' and head != base_sha:
        raise Rejected('start HEAD must equal explicit base')
    if git(repo, 'rev-list', '--merges', base_sha + '..' + head):
        raise Rejected('feature range must be linear, not contain merge commits')
    if count == 1:
        parents = git(repo, 'rev-list', '--parents', '-n', '1', head).decode().split()[1:]
        if parents != [base_sha]:
            raise Rejected('single feature commit must be a direct child of base')
    changed = paths(repo, 'diff', '--no-renames', '--name-only', '-z', base_sha, head, '--')
    committed_paths = []
    for commit in git(repo, 'rev-list', base_sha + '..' + head).decode().splitlines():
        committed_paths += paths(repo, 'diff-tree', '--no-commit-id', '--no-renames',
                                 '--name-only', '-z', '-r', commit, '--')
    status = git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    if mode != 'stage' and status:
        raise Rejected('clean worktree required')
    dirty = []
    if mode == 'stage':
        dirty = paths(repo, 'diff', '--no-renames', '--name-only', '-z', 'HEAD', '--')
        dirty += paths(repo, 'diff', '--cached', '--no-renames', '--name-only', '-z', 'HEAD', '--')
        dirty += paths(repo, 'ls-files', '--others', '--exclude-standard', '-z')
    for p in committed_paths + changed + dirty:
        if not any(p == a or (directory and p.startswith(a + '/')) for a, directory in allowed):
            raise Rejected('out-of-scope path: ' + p)
    return {'valid': True, 'repo': str(repo), 'base': base_sha, 'head': head,
            'mode': mode, 'commits': count, 'changed_paths': changed,
            'committed_paths': sorted(set(committed_paths)), 'dirty_paths': sorted(set(dirty))}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--mode', choices=('start', 'stage', 'deliver'), required=True)
    parser.add_argument('--expected-commits', type=int, required=True)
    parser.add_argument('--allow-path', action='append', required=True)
    args = parser.parse_args()
    try:
        receipt = verify(args.repo, args.base, args.mode, args.expected_commits, args.allow_path)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({'valid': False, 'error': str(exc)}))
        return 3
    print(json.dumps(receipt))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
