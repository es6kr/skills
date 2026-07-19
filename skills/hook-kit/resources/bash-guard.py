#!/usr/bin/env python3
"""bash-guard.py — PreToolUse:Bash integrated guard (single-process Python port).

Port of bash-guard.sh. The shell version spawns ~80 processes per pass
(jq + one grep -P per pattern), which costs ~30s/call on Windows Git Bash
(MSYS fork emulation + Defender per-process scanning). This port parses JSON
and evaluates every pattern inside one interpreter.

Phase 1: immediate block (dangerous command pattern matching)
Phase 2: informational checks + conditional block
Exit codes: 0 = allow, 1 = soft block (BLOCK), 2 = hard block

Self-test: python bash-guard.py --test   (runs in-process — no per-case spawn)
"""
import json
import os
import re
import subprocess
import sys

I = re.IGNORECASE
IM = re.IGNORECASE | re.MULTILINE  # sh version greps per line — keep line semantics

# ── Phase 1: simple hard-block patterns ──
SIMPLE_BLOCKS = [
    # System / file destruction
    (r"\brm\s+-rf\s+/", "rm -rf / is extremely dangerous"),
    (r"\brm\s+-rf\s+~", "rm -rf ~ deletes your home directory"),
    (r"\brm\s+-rf\s+\.\.", "rm -rf .. can delete a parent directory"),
    (r"\brm\s+-rf\s+\*", "rm -rf * is dangerous"),
    # .tmp shared temporary directory protection (file-operations.md convention)
    (r"\brm\b[^|;&]*\s(\./)?\.tmp(?![\w/.\-])",
     "Deleting the entire .tmp/ folder (rm -rf .tmp) will destroy in-progress files of concurrent sessions. Delete only your specific .tmp/<file>"),
    (r"\brm\b[^|;&]*\s(\./)?\.tmp/\*",
     "Glob-deleting .tmp/* will destroy other sessions' files. Delete only your specific .tmp/<file>"),
    # Docker destruction
    (r"docker\s+volume\s+rm", "docker volume rm permanently deletes volume data"),
    (r"docker\s+rm\b", "docker rm deletes the container. Check if stop is sufficient"),
    # GitHub PR/Issue close (permanent history pollution)
    (r"gh\s+(pr|issue)\s+close",
     "gh pr/issue close is forbidden without explicit user instruction. close/reopen history is permanently recorded on GitHub"),
    # K3s / cluster destruction
    (r"curl.*get\.k3s\.io", "k3s reinstall risks overwriting existing data"),
    (r"helm\s+uninstall", "helm uninstall deletes the release and its resources. Use ArgoCD or the helm-orphan skill"),
    (r"k3s-uninstall", "k3s-uninstall completely destroys cluster data"),
    (r"kubectl\s+delete\s+node", "kubectl delete node removes a node from the cluster"),
    (r"kubectl\s+delete\s+pod", "kubectl delete pod risks losing local storage data"),
    (r"kubectl\s+drain", "kubectl drain evicts all workloads from the node"),
    (r"rm\s+-rf\s+/var/lib/rancher", "Deleting rancher data permanently destroys etcd data"),
    # Terraform
    (r"terraform\s+apply.*-auto-approve", "terraform apply -auto-approve changes infrastructure without confirmation"),
    # Database destruction
    (r"DROP\s+DATABASE", "DROP DATABASE is destructive"),
    (r"DROP\s+TABLE", "DROP TABLE is destructive"),
    (r"TRUNCATE\s+TABLE", "TRUNCATE TABLE deletes all data"),
]

# ── git destructive guards (global-option-aware + command-position aware) ──
# GITPFX absorbs global options between `git` and the subcommand
# (`git -C <path> reset --hard`, `git -c x=y ...`, `git --git-dir=... ...`).
GITPFX = r"\bgit(?:\s+-\S+(?:\s+[^-\s]\S*)?)*"
GIT_BLOCKS = [
    # Git history destruction
    (r"reset\s+--hard", "git reset --hard deletes uncommitted work"),
    (r"branch\s+[^|;&]*(?:-f\b|--force)",
     "git branch -f force-moves a branch ref, equivalent to reset --hard (previous commits on that ref become unreachable)"),
    (r"push\s+.*--force", "git push --force overwrites remote history"),
    (r"push\s+.*-f\b", "git push -f overwrites remote history"),
    # Git working directory destruction
    (r"clean\s+-.*f", "git clean -f permanently deletes untracked files"),
    (r"checkout\s+\.\s*$", "git checkout . discards all changes"),
    (r"restore\s+\.\s*$", "git restore . discards all changes"),
    (r"stash\s+drop", "git stash drop permanently deletes the stash"),
    (r"stash\s+clear", "git stash clear deletes all stashes"),
    # Git staging / other
    (r"add\s+-A", "git add -A causes indiscriminate staging. Specify individual files"),
    (r"add\s+\.\s*($|&&|\|)", "git add . causes indiscriminate staging. Specify individual files"),
    (r"read-tree", "git read-tree destroys staged changes"),
    (r"commit\s+--allow-empty", "Empty commits risk being abused as CI/CD triggers"),
    (r"merge\s+--abort", "git merge --abort discards in-progress conflict resolution work"),
]

# Background dispatch without a command-level time bound
# (claudify/background-polling.md HARD STOP: the Bash tool `timeout` parameter does
#  NOT apply to run_in_background — a hung command is never notified. A time bound
#  inside the command itself is mandatory.)
TIME_BOUND = re.compile(
    r"(^|[;&|(]\s*|\s)(g?timeout)\s+(-[a-zA-Z-]+\s+)*[0-9]"
    r"|--max-time[= ]"
    r"|(^|\s)-m\s*[0-9]+"
    r"|ConnectTimeout",
    IM,
)

EXECUTOR = re.compile(r"\b(?:ba|z|k)?sh\s+-c\b|\bssh\b|\beval\b|\bxargs\b", I)
HEREDOC_WRITER = re.compile(r"^[ \t]*(cat|tee)[ \t].*<<")


def git_scan_text(command: str) -> str:
    """FP fix: quoted literals mentioning git commands must not trip the guards.
    Strip quoted strings ONLY when no subshell/remote executor is present (with
    bash -c / ssh / eval / xargs the quoted git DOES execute). Heredoc bodies fed
    to PURE WRITERS (cat/tee) are document text — drop them before quote-strip."""
    if EXECUTOR.search(command):
        return command
    out_lines = []
    term = None
    for line in command.split("\n"):
        if term is not None:
            if line.strip() == term:
                term = None
            continue
        m = HEREDOC_WRITER.match(line)
        if m and "<<" in line:
            s = re.sub(r".*<<-?[ \t]*", "", line)
            s = s.replace("'", "").replace('"', "")
            first = re.split(r"[ \t<>|;&]", s)[0]
            if first:
                term = first
            out_lines.append(line)
            continue
        out_lines.append(line)
    scan = "\n".join(out_lines)
    scan = re.sub(r"'[^']*'", "", scan)
    scan = re.sub(r'"[^"]*"', "", scan)
    return scan


def evaluate(command: str, run_bg: bool, raw_input_json: str = "") -> tuple[int, list[str], list[str]]:
    """Returns (exit_code, stderr_lines, stdout_lines)."""
    warnings: list[str] = []
    soft_blocks: list[str] = []

    def hard(reason: str) -> tuple[int, list[str], list[str]]:
        return 2, [
            f"[Safety Hook] BLOCKED: {reason}",
            f"Attempted command: {command}",
            "If genuinely needed, run it directly in a terminal.",
        ], []

    # ── Phase 1 ──
    if run_bg and not TIME_BOUND.search(command):
        return hard(
            "run_in_background without a command-level time bound. The tool timeout "
            "parameter does not apply to background — prefix with 'timeout N <cmd>' "
            "(or add curl --max-time / ssh -o ConnectTimeout)"
        )

    for pat, msg in SIMPLE_BLOCKS:
        if re.search(pat, command, IM):
            return hard(msg)

    scan = git_scan_text(command)
    for sub, msg in GIT_BLOCKS:
        if re.search(GITPFX + r"\s+" + sub, scan, IM):
            return hard(msg)

    # ── Phase 2 ──
    if re.search(r"git\s+commit", command) and "--amend" not in command:
        try:
            r = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, timeout=5,
            )
            staged = len([l for l in r.stdout.splitlines() if l.strip()])
            if staged == 0:
                warnings.append("[staged-guard] No staged files. Run git add first.")
            elif staged > 2:
                warnings.append(f"[commit-split] {staged} files staged. Consider splitting the commit.")
        except Exception:
            pass

        m = re.search(r"-m\s+[\"']?([^\"']+)", command)
        if m:
            msg = m.group(1)
            if not re.match(r"^(feat|fix|docs|style|refactor|test|chore|ci|perf|build|revert)(\(.+\))?!?:", msg):
                warnings.append("[commit-validator] Conventional Commit format recommended: type(scope): description")

    if re.match(r"^(kubectl|helm)\s", command):
        if re.search(r"--context\s+kvm|KUBECONFIG.*kvm", command) and re.search(r"\sdelete\s", command):
            m = re.search(
                r"(pod|deployment|sts|statefulset|pvc|svc|service|configmap|secret|namespace|application)s?\s+\S+",
                command,
            )
            if m:
                soft_blocks.append(f"BLOCK: Attempting to delete {m.group(0)} on production cluster. AskUserQuestion required.")

    if re.search(r"make\s+fast-android|make\s+fast-ios|fastlane\s+beta|flutter\s+build", command):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        checker = os.path.join(script_dir, "flutter-version-check.sh")
        if os.path.isfile("./pubspec.yaml") and os.access(checker, os.X_OK):
            try:
                r = subprocess.run(
                    ["bash", checker], input=raw_input_json, capture_output=True,
                    text=True, timeout=30, env={**os.environ, "TOOL_INPUT": command},
                )
                out = (r.stdout + r.stderr).strip()
                if out:
                    warnings.append(out)
            except Exception:
                pass

    if re.search(r"cat\s*<<|cat\s*>|echo\s.*>|printf\s.*>", command):
        if re.search(r">\s*['\"]?[^|&;]+\.(md|yaml|yml|json|sh|ts|js|py|txt|conf|cfg)", command):
            soft_blocks.append("BLOCK: Do not modify files via cat/echo. Use the Write tool.")

    if soft_blocks:
        return 1, [], soft_blocks
    return 0, [], warnings


def self_test() -> int:
    cases = [
        # (expect_block, run_bg, command)
        # ── FN cases: destructive git that MUST be blocked ──
        (True, False, "git reset --hard"),
        (True, False, "git reset --hard HEAD~3"),
        (True, False, "git -C /srv/app reset --hard"),
        (True, False, "git -C /srv/app reset --hard origin/main"),
        (True, False, "git -c core.pager=cat reset --hard"),
        (True, False, "git --git-dir=/srv/app/.git reset --hard"),
        (True, False, "git -C /p -c a.b=c reset --hard"),
        (True, False, "sudo git reset --hard"),
        (True, False, "time git -C /p reset --hard"),
        (True, False, 'bash -c "git reset --hard"'),
        (True, False, "sh -c 'git -C /p reset --hard'"),
        (True, False, 'ssh host "git -C /srv/app reset --hard"'),
        (True, False, "git -C /p push origin main --force"),
        (True, False, "git -C /p push --force-with-lease"),
        (True, False, "git -C /p push -f"),
        (True, False, "git -C /p clean -fd"),
        (True, False, "git -C /p branch -f main deadbeef"),
        (True, False, "git -C /p branch --force main deadbeef"),
        (True, False, "git -C /p stash drop"),
        (True, False, "git -C /p stash clear"),
        (True, False, "git -C /p checkout ."),
        (True, False, "git -C /p restore ."),
        (True, False, "git -C /p add -A"),
        (True, False, "git -C /p read-tree HEAD"),
        (True, False, "git -C /p commit --allow-empty -m x"),
        (True, False, "git -C /p merge --abort"),
        (True, False, "git    -C   /p    reset   --hard"),
        (True, False, "GIT -C /p RESET --HARD"),
        (True, False, 'git -C "/path with space" reset --hard'),
        (True, False, "foo && git -C /p reset --hard"),
        # ── FP cases: mentions / safe commands that MUST be allowed ──
        (False, False, "git status"),
        (False, False, "git -C /srv/app log --oneline -5"),
        (False, False, "git -C /p reset --soft HEAD~1"),
        (False, False, "git clean -n"),
        (False, False, 'echo "git reset --hard undoes uncommitted work"'),
        (False, False, "grep 'git reset --hard' /tmp/notes.md"),
        (False, False, 'echo "run git -C /p reset --hard to wipe"'),
        (False, False, 'printf "%s" "git push --force is dangerous"'),
        (False, False, 'git commit -m "document git reset --hard behaviour"'),
        (False, False, 'git commit -m "fix: git push --force guard"'),
        (False, False, 'rg "git -C \\S+ reset --hard" skills/'),
        (False, False, "cat <<'EOF'\ncase history: git push --force overwrites remote history\nEOF"),
        (False, False, "tee -a /tmp/notes.md <<'EOF'\nexample: git reset --hard deletes work\nEOF"),
        (True, False, "bash <<'EOF'\ngit push --force origin main\nEOF"),
        # ── background time-bound guard ──
        (True, True, "git push origin main"),
        (True, True, "gh run watch 12345"),
        (True, True, 'ssh host "docker ps"'),
        (False, True, "timeout 120 git push origin main"),
        (False, True, "cd /repo && timeout 300 gh pr create --draft"),
        (False, True, "curl --max-time 30 http://example.com"),
        (False, True, "curl -m 10 http://example.com"),
        (False, True, "ssh -o ConnectTimeout=10 host uptime"),
        # foreground: same commands must stay allowed (tool timeout param governs)
        (False, False, "git push origin main"),
        (False, False, "gh run watch 12345"),
        # ── non-git hard blocks ──
        (True, False, "rm -rf /var/lib/rancher/k3s"),
        (True, False, "docker volume rm mydata"),
        (True, False, "gh pr close 123"),
        (True, False, "rm -rf .tmp"),
        (False, False, "rm -f .tmp/pr-body.md"),
    ]
    passed = failed = 0
    for expect_block, run_bg, cmd in cases:
        code, _, _ = evaluate(cmd, run_bg)
        got_block = code in (1, 2)
        if got_block == expect_block:
            passed += 1
        else:
            failed += 1
            tag = "bg" if run_bg else "fg"
            print(f"FAIL({tag}) expected={'BLOCK' if expect_block else 'ALLOW'} "
                  f"got={'BLOCK' if got_block else 'ALLOW'} :: {cmd!r}")
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.exit(self_test())

    raw = os.environ.get("CLAUDE_TOOL_INPUT") or sys.stdin.read()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_input = data.get("tool_input", {}) or {}
    command = tool_input.get("command") or data.get("command") or ""
    if not command:
        sys.exit(0)
    run_bg = bool(tool_input.get("run_in_background", False))

    code, err_lines, out_lines = evaluate(command, run_bg, raw)
    for l in err_lines:
        print(l, file=sys.stderr)
    for l in out_lines:
        print(l)
    sys.exit(code)


if __name__ == "__main__":
    main()
