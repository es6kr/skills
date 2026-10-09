#!/usr/bin/env bash
# PostToolUse:Bash — inspect only HEAD in the effective rebase repository.
# Command text is parsed as data; never evaluated or executed. Produced-range
# lifecycle tracking for multi-commit rebases is deliberately out of scope.
set -u
if [[ "${1:-}" == "--test" ]]; then
  echo "check-rebase-conflict-residue.sh: self-test mode OK"
  exit 0
fi
INPUT="$(cat)"
HOOK_INPUT="$INPUT" python3 - <<'PY'
import json
import os
import re
import shlex
import subprocess
import sys

try:
    payload = json.loads(os.environ['HOOK_INPUT'])
except (ValueError, KeyError):
    sys.exit(0)
if payload.get('tool_name') != 'Bash':
    sys.exit(0)
command = payload.get('tool_input', {}).get('command', '')
if not isinstance(command, str):
    sys.exit(0)


def segments(text):
    """Split simple shell lists without treating quoted operators as syntax."""
    start, quote, escaped = 0, None, False
    for i, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == '\\' and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in ';&|\n':
            yield text[start:i]
            start = i + 1
    yield text[start:]


cwd = payload.get('cwd') or os.getcwd()
assignment = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
seen = set()
for segment in segments(command):
    # Unsupported expansions/control structures are not shell-interpreted.
    if any(char in segment for char in ('`', '$', '(', ')', '<', '>')):
        # A dynamic cd/subshell could change the effective repository. Stop
        # rather than falling back to the unrelated hook working directory.
        break
    try:
        words = shlex.split(segment, comments=True)
    except ValueError:
        continue
    env = os.environ.copy()
    while words and assignment.match(words[0]):
        key, value = words.pop(0).split('=', 1)
        if key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR'):
            env[key] = value
    if words and os.path.basename(words[0]) == 'env':
        words.pop(0)
        while words and assignment.match(words[0]):
            key, value = words.pop(0).split('=', 1)
            if key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR'):
                env[key] = value
    if not words:
        continue
    if words[0] == 'cd':
        args = words[1:]
        if args[:1] == ['--']:
            args = args[1:]
        if len(args) == 1 and args[0] != '-':
            target = os.path.abspath(os.path.join(cwd, args[0]))
            if os.path.isdir(target):
                cwd = target
            else:
                break
        else:
            break
        continue
    executable = words.pop(0)
    if executable != 'git' and not (os.path.isabs(executable) and os.path.basename(executable) == 'git'):
        continue
    options = []
    while words and words[0].startswith('-'):
        option = words.pop(0)
        if option in ('-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env'):
            if not words:
                break
            options.extend((option, words.pop(0)))
        elif option in ('--no-pager', '--paginate', '--bare', '--no-replace-objects', '--literal-pathspecs', '--no-optional-locks') or option.startswith(('--git-dir=', '--work-tree=', '--namespace=', '--config-env=')):
            options.append(option)
        else:
            # Unknown global options must not accidentally select another repo.
            words = []
            break
    if not words or words[0] != 'rebase' or '--continue' not in words[1:]:
        continue
    # No shell=True, no payload subcommand, and no ancestor scan. Forward only
    # parsed Git global options to a fixed read-only HEAD query.
    key = (cwd, tuple(options), env.get('GIT_DIR'), env.get('GIT_WORK_TREE'))
    if key in seen:
        continue
    seen.add(key)
    try:
        result = subprocess.run(['git', *options, 'log', '-1', '--format=%B'], cwd=cwd,
                                env=env, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        continue
    if result.returncode == 0 and re.search(r'^[#±]\s*Conflicts:', result.stdout, re.M):
        print('<rebase-conflict-residue-detected>\nERROR: Rebase conflict residue detected in HEAD commit message:\n'
              + result.stdout + '\nHARD STOP: Sanitize the commit message with git commit --amend.\n'
              '</rebase-conflict-residue-detected>', file=sys.stderr)
        sys.exit(2)
sys.exit(0)
PY
