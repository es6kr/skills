#!/usr/bin/env python3
"""bash-guard.py — PreToolUse:Bash integrated guard (single-process Python port).

Port of bash-guard.sh. The shell version spawns ~80 processes per pass
(jq + one grep -P per pattern), which costs ~30s/call on Windows Git Bash
(MSYS fork emulation + Defender per-process scanning). This port parses JSON
and evaluates every pattern inside one interpreter.

Phase 1: immediate block (dangerous command pattern matching)
Phase 2: informational checks + conditional block
Exit codes: 0 = allow, 1 = soft block (BLOCK), 2 = hard block

2026-07-24: absorbed the standalone PreToolUse:Bash/PowerShell scripts with the
highest timeout counts in a single session (block-semaphore-cmd-without-skill.sh 28,
block-pr-create-without-draft.sh 27, block-authentik-api-mutate.sh 22 — each a
separate bash.exe/jq spawn per Bash call). Same day, follow-up pass absorbed the
remaining 3 deferred standalone scripts: block-gh-api-lowercase-f-file-read.sh,
block-pm2-start-without-resurrect.sh, block-summary-without-internal-review.sh.
New PreToolUse:Bash/PowerShell constraints should default to a SIMPLE_BLOCKS
entry (pure regex) or a new check_*() function here rather than a new standalone
script — every extra registered hook is another subprocess spawn on Windows Git
Bash.

This file lives in this skill's `resources/` (git-tracked, PUBLIC — this repo
is es6kr/skills). It must stay generic: no hardcoded internal IPs/hostnames,
account-specific paths, or vendor/company project names. Deployment-specific
constraints (the two scripts above were exactly this — a Semaphore host IP and
an Authentik-terraform-pam gate) belong in the optional LOCAL overlay module
instead — see `LOCAL_OVERLAY` below, loaded from `../data/bash-guard.local.py`
(covered by this repo's `skills/*/data` .gitignore pattern, so it never leaves
this machine). Absence of that file is the normal case for any other clone of
this repo — the overlay hook is a no-op when the module can't be imported.

Self-test: python bash-guard.py --test   (runs in-process — no per-case spawn)
"""
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys

# ── Optional local overlay (git-ignored, machine-specific) ──
# Must expose: check(command: str, tool_name: str, transcript_path: str) -> str | None
# Returning a non-None string hard-blocks with that string as the reason.
_LOCAL_OVERLAY_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "data", "bash-guard.local.py")
LOCAL_OVERLAY = None
if os.path.isfile(_LOCAL_OVERLAY_PATH):
    try:
        _spec = importlib.util.spec_from_file_location("bash_guard_local", _LOCAL_OVERLAY_PATH)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        if hasattr(_mod, "check"):
            LOCAL_OVERLAY = _mod
    except Exception:
        LOCAL_OVERLAY = None  # fail open — a broken local overlay must not break the generic guard

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
    (r"\brm\b[^|;&\n]*\s(\./)?\.tmp(?![\w/.\-])",
     "Deleting the entire .tmp/ folder (rm -rf .tmp) will destroy in-progress files of concurrent sessions. Delete only your specific .tmp/<file>"),
    (r"\brm\b[^|;&\n]*\s(\./)?\.tmp/\*",
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
    # NOTE: newline excluded from the span — without it, "git branch --show-current"
    # on one line and "git commit -F" lines later false-matched as "branch -f"
    # (IGNORECASE makes -F hit -f\b). Same \n-exclusion applied to the rm/.tmp spans.
    (r"branch\s+[^|;&\n]*(?:-f\b|--force)",
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

# ── gh pr create --draft guard (ported from block-pr-create-without-draft.sh) ──
GH_TOKEN_RE = re.compile(r"\bgh\b")
PR_CREATE_PREFILTER = re.compile(r"pr[ \t]+create")


def check_pr_create_draft(command: str) -> str | None:
    """Real `gh pr create` invocation (3 adjacent bare tokens, via shlex — a
    quoted string reference like a grep pattern stays one token and never
    matches) must carry --draft or the PR_READY_APPROVED=1 opt-out."""
    if not GH_TOKEN_RE.search(command) or not PR_CREATE_PREFILTER.search(command):
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None  # unparseable (unbalanced quotes) — fail open, do not block
    invocation = any(
        tokens[i] == "gh" and tokens[i + 1] == "pr" and tokens[i + 2] == "create"
        for i in range(len(tokens) - 2)
    )
    if not invocation:
        return None
    has_draft = any(t == "--draft" or t.startswith("--draft=") for t in tokens)
    has_bypass = any(t == "PR_READY_APPROVED=1" for t in tokens)
    if has_draft or has_bypass:
        return None
    return (
        "`gh pr create` must include --draft.\n\n"
        "Why blocked:\n"
        "  - Draft is the DEFAULT (github-flow/pr.md:13 HARD STOP). A ready (non-draft) PR "
        "fires CodeRabbit/Copilot review immediately - cost grows per non-draft PR.\n"
        "  - PR creation should route through Skill(\"github-flow\", \"register\"), which "
        "applies the draft default + base-convention checks. Raw `gh pr create` bypasses them.\n\n"
        "Required action (pick one):\n"
        "  1. Add --draft to the gh pr create command (default), OR\n"
        "  2. Prefer Skill(\"github-flow\", \"register\") over a raw gh pr create, OR\n"
        "  3. If the user EXPLICITLY requested a ready PR (\"ready PR\" / \"non-draft\" / \"--ready\"), "
        "prefix the command with PR_READY_APPROVED=1 gh pr create ... so the opt-out is auditable.\n\n"
        "Reference: failed-attempts.md 'raw gh pr create bypass / non-draft' (github-flow/pr.md:13)."
    )


# ── gh api -f/--raw-field with @<path> file-read syntax (ported from
# block-gh-api-lowercase-f-file-read.sh) — -f always sends a literal string;
# only -F/--field supports @file reads. The bug silently PATCHes/POSTs the
# literal text "@path" instead of the file's content (gh reports success).
GH_API_RE = re.compile(r"\bgh\s+api\b", I)
# NOTE: this flag check must stay case-SENSITIVE (no I flag) — -f vs -F is the
# entire bug being guarded against.
GH_API_LOWERCASE_F_RE = re.compile(r"(\s-f\s|\s--raw-field(=|\s))[A-Za-z0-9_]+=@")


def check_gh_api_lowercase_f(command: str) -> str | None:
    if not GH_API_RE.search(command) or not GH_API_LOWERCASE_F_RE.search(command):
        return None
    return (
        "gh api -f/--raw-field with @<path> file-read syntax is not supported.\n\n"
        "-f/--raw-field always sends the value as a LITERAL string — '@<path>' is sent "
        "as-is (e.g. the field ends up containing the text '@.tmp/summary.md', not the "
        "file's content). gh reports success (200 + URL) either way, so this fails silently.\n\n"
        "Use one of instead:\n"
        "  1. -F/--field key=@<path>   (uppercase -F DOES support @file read)\n"
        "  2. --input <json-file>      (build {\"key\": \"...\"} via a JSON file, e.g. python json.dump)\n\n"
        "After the call, read back and diff: gh api <same-endpoint> --jq '.body' (or the relevant field)\n"
        "— an HTTP 200 / returned URL is not proof the content landed correctly.\n\n"
        "Reference: failed-attempts.md 'gh api -f body=@file posts literal string instead of file content'."
    )


# ── pm2 start requires resurrect first when the process list is empty but a
# saved dump exists (ported from block-pm2-start-without-resurrect.sh) ──
PM2_START_RE = re.compile(r"\bpm2\s+start\b", I)


def check_pm2_start_without_resurrect(command: str) -> str | None:
    if not PM2_START_RE.search(command):
        return None
    dump_file = os.path.join(os.path.expanduser("~"), ".pm2", "dump.pm2")
    if not os.path.isfile(dump_file):
        return None
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None  # pm2 not on PATH / infra issue — fail open
    out = r.stdout or ""
    m = re.search(r"^\[.*", out, re.DOTALL | re.MULTILINE)
    clean = m.group(0).strip() if m else out.strip()
    if clean != "[]":
        return None
    return (
        "'pm2 start' blocked because pm2 has no active processes but a saved dump exists.\n\n"
        "Reason: pm2 list is empty, but ~/.pm2/dump.pm2 is present.\n"
        "Action Required: run 'pm2 resurrect' first to restore previously defined processes.\n"
        "If the process you want to start is still missing after resurrect, then run 'pm2 start'.\n\n"
        "pm2/start.md rule: run resurrect first when pm2 list is empty (HARD STOP)"
    )


# ── AI Review Summary requires a prior Internal Code Review comment on the
# same PR (ported from block-summary-without-internal-review.sh) ──
SUMMARY_MARKER_RE = re.compile(r"## AI Review Summary|AI Review Summary")
PR_COMMENT_BODY_FLAG_RE = re.compile(r"--body(=| )|--body-file(=| )")
GH_API_COMMENTS_POST_RE = re.compile(
    r"gh api.*(/issues/[0-9]+/comments|issues/comments).*"
    r"(-X\s+POST|--method\s+POST|--input(=| )|-f\s+body=|-F\s+body=)"
)


def check_summary_without_internal_review(command: str) -> str | None:
    """Block posting '## AI Review Summary' before an Internal Code Review
    comment exists on the same PR (consolidate/internal.md Step 3.5.3)."""
    is_post = False
    if "gh pr comment" in command and PR_COMMENT_BODY_FLAG_RE.search(command):
        is_post = True
    if not is_post and GH_API_COMMENTS_POST_RE.search(command):
        is_post = True
    if not is_post:
        return None

    has_summary = bool(SUMMARY_MARKER_RE.search(command))
    if not has_summary:
        m = re.search(r"--body-file(?:=| )(\S+)|--input(?:=| )(\S+)", command)
        if m:
            body_file = m.group(1) or m.group(2)
            try:
                with open(body_file, "r", encoding="utf-8", errors="replace") as f:
                    if SUMMARY_MARKER_RE.search(f.read()):
                        has_summary = True
            except OSError:
                pass
    if not has_summary:
        return None

    m = re.search(r"gh pr comment\s+([0-9]+)", command) or re.search(r"issues/([0-9]+)/comments", command)
    if not m:
        return None  # PR number unresolvable — skip, can't verify
    pr_num = m.group(1)

    m = re.search(r"-R\s+(\S+)", command) or re.search(r"repos/([^/]+/[^/]+)/", command)
    if not m:
        return None  # repo unresolvable — skip
    repo = m.group(1)

    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{repo}/issues/{pr_num}/comments"],
            capture_output=True, text=True, timeout=10,
        )
        comments = json.loads(r.stdout) if r.stdout else []
    except Exception:
        return None  # API/infra failure — do not block on infrastructure issues

    has_walkthrough = any("<!-- walkthrough_start -->" in (c.get("body") or "") for c in comments)
    has_internal_review = any((c.get("body") or "").startswith("## Internal Code Review") for c in comments)

    if has_walkthrough and not has_internal_review:
        # Medium decision: inline-comment reviews post via the reviews API, not
        # an issue comment — scan both media before declaring it missing.
        try:
            r = subprocess.run(
                ["gh", "api", f"repos/{repo}/pulls/{pr_num}/reviews"],
                capture_output=True, text=True, timeout=10,
            )
            reviews = json.loads(r.stdout) if r.stdout else []
            if any((rv.get("body") or "").startswith("## Internal Code Review") for rv in reviews):
                has_internal_review = True
        except Exception:
            pass

    if not (has_walkthrough and not has_internal_review):
        return None
    return (
        f"Posting AI Review Summary without Internal Code Review comment.\n\n"
        f"PR: {repo}#{pr_num}\n"
        "State:\n"
        "  - CodeRabbit walkthrough_start marker: PRESENT (Step 3.5 trigger met)\n"
        "  - Internal Code Review comment: MISSING\n"
        "  - About to POST: AI Review Summary\n\n"
        "consolidate/internal.md Step 3.5.3 requires an Internal Code Review comment posted "
        "BEFORE consolidate/post.md Step 7 Summary. The single-combined-comment pattern is "
        "deprecated — always 2 comments.\n\n"
        "Required action before retry:\n"
        f"  1. Post Internal Code Review comment first: gh pr comment {pr_num} -R {repo} --body-file <path>\n"
        f"  2. Verify: gh api repos/{repo}/issues/{pr_num}/comments --jq "
        "'.[] | select(.body | startswith(\"## Internal Code Review\"))'\n"
        "  3. Then re-issue this Summary POST command\n\n"
        "Reference: failed-attempts.md 'Internal Code Review comment posting missing' (5+ recurrences)."
    )


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


def evaluate(
    command: str,
    run_bg: bool,
    raw_input_json: str = "",
    tool_name: str = "Bash",
    transcript_path: str = "",
) -> tuple[int, list[str], list[str]]:
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

    pr_reason = check_pr_create_draft(command)
    if pr_reason:
        return hard(pr_reason)

    ghapi_reason = check_gh_api_lowercase_f(command)
    if ghapi_reason:
        return hard(ghapi_reason)

    pm2_reason = check_pm2_start_without_resurrect(command)
    if pm2_reason:
        return hard(pm2_reason)

    summary_reason = check_summary_without_internal_review(command)
    if summary_reason:
        return hard(summary_reason)

    if LOCAL_OVERLAY is not None:
        overlay_reason = LOCAL_OVERLAY.check(command, tool_name, transcript_path)
        if overlay_reason:
            return hard(overlay_reason)

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
        # multiline: "git branch --show-current" + later "git commit -F -" must NOT
        # cross-line match as "branch -f" (regression: 2026-07-20 gitops commit FP)
        (False, False, "git branch --show-current\ngit add a.yaml\ngit commit -F - <<'EOF'\nfeat: x\nEOF"),
        (False, False, "rm -f .tmp/my-file.md\necho done .tmp keep"),
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
        # ── gh pr create --draft guard (ported from block-pr-create-without-draft.sh) ──
        (True, False, "gh pr create --title x --body y"),
        (False, False, "gh pr create --draft --title x --body y"),
        (False, False, "PR_READY_APPROVED=1 gh pr create --title x --body y"),
        (False, False, 'grep "gh pr create" README.md'),
        (False, False, 'echo "run gh pr create --draft next"'),
        # ── gh api -f/--raw-field @file guard (ported from block-gh-api-lowercase-f-file-read.sh) ──
        (True, False, "gh api repos/o/r/issues/1/comments -f body=@.tmp/summary.md"),
        (True, False, "gh api repos/o/r/issues/1/comments --raw-field body=@.tmp/summary.md"),
        (False, False, "gh api repos/o/r/issues/1/comments -F body=@.tmp/summary.md"),
        (False, False, "gh api repos/o/r/issues/1/comments -f body=inline-text"),
        (False, False, 'echo "gh api uses -F for file reads"'),
        # ── pm2 start guard (ported from block-pm2-start-without-resurrect.sh) —
        # only the non-matching / no-subprocess-spawn branch is deterministic
        # cross-machine; the dump-exists+empty-list branch depends on live pm2 state.
        (False, False, "pm2 status"),
        (False, False, "pm2 startOrGracefulReload ecosystem.config.js"),
        # ── AI Review Summary guard (ported from block-summary-without-internal-review.sh) —
        # only the no-API-call branches (is_post=False or has_summary=False) are
        # deterministic without live gh auth/network; the walkthrough/internal-review
        # comparison branch requires an actual PR and is not covered here.
        (False, False, "gh pr comment 123 --body 'plain review comment'"),
        (False, False, "gh pr view 123"),
        (False, False, 'echo "posting AI Review Summary later"'),
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

    # Local overlay (machine-specific, git-ignored) runs its own self-test if present.
    if LOCAL_OVERLAY is not None and hasattr(LOCAL_OVERLAY, "self_test"):
        overlay_failed = LOCAL_OVERLAY.self_test()
        return 0 if failed == 0 and overlay_failed == 0 else 1

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
    tool_name = data.get("tool_name") or ""
    transcript_path = data.get("transcript_path") or ""

    code, err_lines, out_lines = evaluate(command, run_bg, raw, tool_name, transcript_path)
    for l in err_lines:
        print(l, file=sys.stderr)
    for l in out_lines:
        print(l)
    sys.exit(code)


if __name__ == "__main__":
    main()
