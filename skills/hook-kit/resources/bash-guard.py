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
import tempfile

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
    # /tmp/<subpath> is exempt (OS scratch space, routinely rm -rf'd by tests/cleanup);
    # bare `/tmp` (no subpath) still blocks below since the lookahead requires "tmp/".
    (r"\brm\s+-rf\s+/(?!tmp/)", "rm -rf / is extremely dangerous"),
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
    # NOTE: a narrow `reset\s+--hard` pattern used to live here, missing other
    # destructive reset forms (arbitrary ref, large-N mixed history rewrite).
    # Moved to check_git_reset() below, which blocks everything except a
    # small-N --soft/--mixed HEAD~N undo (git.md: N<=2 needs no confirmation).
    # NOTE: newline excluded from the span — without it, "git branch --show-current"
    # on one line and "git commit -F" lines later false-matched as "branch -f"
    # (IGNORECASE makes -F hit -f\b). Same \n-exclusion applied to the rm/.tmp spans.
    (r"branch\s+[^|;&\n]*(?:-f\b|--force)",
     "git branch -f force-moves a branch ref, equivalent to reset --hard (previous commits on that ref become unreachable)"),
    # NOTE: force-push moved to check_git_force_push() below — it is no longer
    # an unconditional block, it is allowed in a narrow, verified exception
    # (worktree + non-main/master target). See that function's docstring.
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


def check_git_reset(scan: str) -> str | None:
    """git reset guard, split out of GIT_BLOCKS: --hard is always destructive
    (working tree loss) and stays hard-blocked. --soft/--mixed to HEAD~N is a
    low-risk "undo the last commit(s), keep the changes staged" operation —
    git.md only requires confirmation once N > 2, so small-N soft/mixed
    resets are allowed. Bare reset (no --soft/--mixed) or any ref other than
    HEAD~1/HEAD~2 falls back to the same blanket prohibition as before."""
    for m in re.finditer(GITPFX + r"\s+reset\b([^|;&\n]*)", scan, IM):
        tail = m.group(1)
        if re.search(r"--hard\b", tail, I):
            return "git reset --hard is ABSOLUTELY PROHIBITED for agents. Never execute under any circumstances."
        mode = re.search(r"--(soft|mixed)\b", tail, I)
        head = re.search(r"HEAD~(\d+)\b", tail, I)
        if mode and head and int(head.group(1)) <= 2:
            continue  # small-N soft/mixed reset — allowed, no confirmation needed per git.md
        return ("git reset (hard/soft/mixed/ref) beyond a small --soft/--mixed HEAD~1 or "
                "HEAD~2 is ABSOLUTELY PROHIBITED for agents. Never execute under any circumstances.")
    return None


FORCE_PUSH_SUB = r"push\s+.*(?:--force(?:-with-lease(?:=\S+)?)?\b|(?<!\S)-f\b)"


def _extract_dash_c_path(command: str) -> str | None:
    m = re.search(r"\bgit\s+(?:-C\s+([^\s]+)\s+)", command)
    if not m:
        return None
    return m.group(1).strip("'\"")


def _resolve_push_target_branch(tokens: list[str]) -> str | None:
    """From tokenized `git ... push [remote] [branch] [flags...]`, return the
    explicit branch token if present. Returns None when the branch cannot be
    read off the command itself (caller must resolve HEAD instead) — this
    includes the ambiguous single-non-flag-token case ("git push origin" vs
    "git push <configured-remote-alias>"), which is deliberately NOT guessed."""
    try:
        push_idx = tokens.index("push")
    except ValueError:
        return None
    non_flags = [t for t in tokens[push_idx + 1:] if not t.startswith("-")]
    if len(non_flags) >= 2:
        return non_flags[1]
    return None


def _resolve_push_destination(branch: str) -> str:
    """Strip a refspec source before taking the leaf branch name, so
    `feature:main` (push refspec `src:dst`) resolves to `main` rather than
    the literal `feature:main` (which matches neither `main` nor `master`).
    A bare target (no `:`) is unaffected."""
    dst = branch.rsplit(":", 1)[-1] if ":" in branch else branch
    return dst.rsplit("/", 1)[-1]


def _split_git_invocations(command: str) -> list[str]:
    """Split a (possibly compound) command into per-invocation segments, each
    starting at a `git` word boundary and running up to (not including) the
    next one. Scoping -C/push/branch resolution to a single segment prevents
    an unrelated git invocation elsewhere in the same command (a decoy
    `git -C <worktree> status &&`, or an earlier non-force `git push`) from
    supplying the path/branch actually used to evaluate a LATER force push.

    A `git` token that falls inside a quoted literal (e.g. a commit message
    or `echo`/`printf` argument mentioning "git push --force") must NOT start
    a segment — it is text, not an invocation. Quote spans are computed on
    this same unstripped `command` (not git_scan_text's output) so a segment
    boundary is never chosen from inside a quote that the segment itself
    would go on to correctly strip via git_scan_text."""
    quoted_spans = []
    for pat in (r"'[^']*'", r'"[^"]*"'):
        quoted_spans.extend((m.start(), m.end()) for m in re.finditer(pat, command))

    def _in_quotes(pos: int) -> bool:
        return any(start <= pos < end for start, end in quoted_spans)

    starts = [m.start() for m in re.finditer(r"\bgit\b", command) if not _in_quotes(m.start())]
    if not starts:
        return []
    starts.append(len(command))
    return [command[starts[i]:starts[i + 1]] for i in range(len(starts) - 1)]


_GIT_REPO_ENV_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def _subprocess_git_env() -> dict:
    """`-C <path>` is meaningless if GIT_DIR/GIT_WORK_TREE/etc. are already
    set in the environment — git honors those over -C's repository
    discovery, so an ambient GIT_DIR (this hook process itself running
    inside another git hook, for example) would silently redirect every
    `git -C <target_dir> ...` call below onto a DIFFERENT repository than
    the one -C names. Strip them so -C is authoritative."""
    return {k: v for k, v in os.environ.items() if k not in _GIT_REPO_ENV_VARS}


def check_git_force_push(command: str) -> str | None:
    """Force push is destructive to shared remote history and stays blocked
    BY DEFAULT — this only narrows the exception, it never widens it. Allowed
    ONLY when BOTH are positively confirmed, using the SAME single git
    invocation that carries the force flag (never a different `-C`/push
    elsewhere in a compound command):
      1. The target checkout is a git WORKTREE (git-dir != git-common-dir),
         never the primary/main checkout.
      2. The resolved target branch is NOT main/master (case-insensitive).
    Any failure to confirm both (subprocess error, ambiguous branch
    resolution, non-git-repo cwd, un-isolatable invocation) falls back to the
    original unconditional block. User-requested narrowing (worktree-only,
    main/master excluded):
    2026-08-24, /fix "PR URL 누락" Step 3 Resume redirect — the user ran the
    2 gh pr close commands manually but asked that force-push specifically
    become agent-executable under these two conditions.
    """
    block_msg = "git push --force/-f overwrites remote history"

    scan = re.sub(r"\\[ \t]*\n", " ", git_scan_text(command))
    if not re.search(GITPFX + r"\s+" + FORCE_PUSH_SUB, scan, IM):
        return None

    # Isolate the ONE git invocation that actually carries the force flag —
    # a backslash-newline continuation before --force must still be detected
    # (`.` does not cross a newline; PR #374 CodeRabbit finding), and -C/push
    # must come from THIS invocation, not from any other `git` text sharing
    # the same compound command (PR #374 CodeRabbit finding).
    invocation = None
    for seg in _split_git_invocations(command):
        seg_scan = re.sub(r"\\[ \t]*\n", " ", git_scan_text(seg))
        if re.search(GITPFX + r"\s+" + FORCE_PUSH_SUB, seg_scan, IM):
            invocation = re.sub(r"\\[ \t]*\n", " ", seg)
            break
    if invocation is None:
        return None

    dash_c = _extract_dash_c_path(invocation)
    target_dir = dash_c or os.getcwd()

    git_env = _subprocess_git_env()
    try:
        common_dir = subprocess.run(
            ["git", "-C", target_dir, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, env=git_env,
        )
        git_dir = subprocess.run(
            ["git", "-C", target_dir, "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=5, env=git_env,
        )
        if common_dir.returncode != 0 or git_dir.returncode != 0:
            return block_msg + " (blocked: could not resolve git-dir/git-common-dir — worktree status unverifiable)"
        common_path = os.path.realpath(os.path.join(target_dir, common_dir.stdout.strip()))
        git_path = os.path.realpath(os.path.join(target_dir, git_dir.stdout.strip()))
        is_worktree = common_path != git_path
    except Exception:
        return block_msg + " (blocked: worktree check raised an exception — failing closed)"

    if not is_worktree:
        return block_msg + " (blocked: not running from a git worktree — the primary checkout is never exempt)"

    try:
        tokens = shlex.split(invocation)
    except ValueError:
        return block_msg + " (blocked: command not shell-tokenizable — target branch unverifiable)"

    branch = _resolve_push_target_branch(tokens)
    if branch is None:
        try:
            head = subprocess.run(
                ["git", "-C", target_dir, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5, env=git_env,
            )
            if head.returncode != 0 or not head.stdout.strip():
                return block_msg + " (blocked: could not resolve current branch — target unverifiable)"
            branch = head.stdout.strip()
        except Exception:
            return block_msg + " (blocked: current-branch check raised an exception — failing closed)"

    branch_bare = _resolve_push_destination(branch)
    if not branch_bare:
        return block_msg + f" (blocked: target branch '{branch}' has no resolvable destination — failing closed)"
    if re.match(r"^(main|master)$", branch_bare, I):
        return block_msg + f" (blocked: target branch '{branch}' is main/master — the worktree exemption never covers main/master)"

    return None


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

# Ceiling on the time bound itself — a single silent watch/wait long enough to
# outlast the prompt-cache TTL is the exact failure mode this hook exists to
# prevent (failed-attempts.md "idle-cache-ttl"). Extracts the numeric value
# following timeout/-m/--max-time (ConnectTimeout excluded — it bounds only the
# TCP handshake phase, not overall command wait time).
TIME_BOUND_VALUE = re.compile(
    r"(?:(?:^|[;&|(]\s*|\s)g?timeout\s+(?:-[a-zA-Z-]+\s+)*|--max-time[= ]|(?:^|\s)-m\s*)(\d+)",
    IM,
)
TIME_BOUND_CEILING = 270

EXECUTOR = re.compile(r"\b(?:ba|z|k)?sh\s+-c\b|\bssh\b|\beval\b|\bxargs\b", I)
HEREDOC_WRITER = re.compile(r"^[ \t]*(cat|tee)[ \t].*<<")

# ── gh pr create --draft guard (ported from block-pr-create-without-draft.sh) ──
GH_TOKEN_RE = re.compile(r"\bgh\b")
PR_CREATE_PREFILTER = re.compile(r"pr[ \t]+create")

# shlex.split() has no concept of bash heredocs (`<<'EOF' ... EOF`) — it just
# tokenizes the body text like any other unquoted words. Prose inside a
# heredoc (e.g. a commit message body mentioning "gh pr create" in a sentence)
# then produces 3 adjacent bare tokens that false-positive-match a real
# invocation. Strip heredoc bodies before token-scanning for this reason.
HEREDOC_BLOCK = re.compile(
    r"<<-?\s*(['\"]?)(\w+)\1.*?\n^\2\s*$", re.MULTILINE | re.DOTALL
)


def strip_heredoc_bodies(command: str) -> str:
    return HEREDOC_BLOCK.sub("<<HEREDOC", command)


def check_pr_create_draft(command: str, transcript_path: str = "") -> str | None:
    """Real `gh pr create` invocation (3 adjacent bare tokens, via shlex — a
    quoted string reference like a grep pattern stays one token and never
    matches) must carry --draft or the PR_READY_APPROVED=1 opt-out. Once that
    passes, also require evidence that Skill("github-flow", ...) was invoked
    earlier in this transcript — a well-formed --draft + templated PR can
    still skip pr.md's other mandatory steps (Step 6 milestone check, Step 7.5
    CI-watch->ready same-turn transition, Step 9 Copilot/CodeRabbit follow-up
    scheduling) when `gh pr create` runs directly instead of via the skill
    (failed-attempts.md "pr-create-bypass", 4th recurrence)."""
    command = strip_heredoc_bodies(command)
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

    def _draft_true(token: str) -> bool:
        # `--draft` alone means true (cobra boolean-flag convention). `--draft=<value>`
        # must be checked, not just matched as a prefix — `--draft=false` is a valid,
        # explicit non-draft invocation and must NOT satisfy this guard.
        if token == "--draft":
            return True
        if token.startswith("--draft="):
            value = token.split("=", 1)[1].strip().lower()
            return value not in ("false", "0", "no", "n")
        return False

    has_draft = any(_draft_true(t) for t in tokens)
    has_bypass = any(t == "PR_READY_APPROVED=1" for t in tokens)
    if not (has_draft or has_bypass):
        return (
            "`gh pr create` must include --draft.\n\n"
            "Why blocked:\n"
            "  - Draft is the DEFAULT (github-flow/pr.md:13 HARD STOP). A ready (non-draft) PR "
            "fires CodeRabbit/Copilot review immediately - cost grows per non-draft PR.\n"
            "  - PR creation should route through Skill(\"github-flow\", \"pr\"), which "
            "applies the draft default + base-convention checks. Raw `gh pr create` bypasses them.\n\n"
            "Required action (pick one):\n"
            "  1. Add --draft to the gh pr create command (default), OR\n"
            "  2. Prefer Skill(\"github-flow\", \"pr\") over a raw gh pr create, OR\n"
            "  3. If the user EXPLICITLY requested a ready PR (\"ready PR\" / \"non-draft\" / \"--ready\"), "
            "prefix the command with PR_READY_APPROVED=1 gh pr create ... so the opt-out is auditable.\n\n"
            "Reference: failed-attempts.md 'raw gh pr create bypass / non-draft' (github-flow/pr.md:13)."
        )

    # Draft/bypass satisfied — now check for skill-invocation evidence.
    if any(t == "GH_PR_CREATE_SKILL_BYPASS=1" for t in tokens):
        return None
    if not transcript_path:
        return None  # no transcript to check — fail open
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            transcript = f.read()
    except OSError:
        return None  # unreadable — fail open
    # The harness records the skill name as invoked. When the skill ships inside a
    # plugin, that name is plugin-qualified ("es6kr:github-flow"), so a bare-literal
    # match sees nothing and the guard becomes unsatisfiable through its own
    # documented path #1 — leaving the audit bypass as the only way through.
    # Accept an optional "<plugin>:" prefix.
    if re.search(r'"skill":"(?:[A-Za-z0-9_.-]+:)?github-flow"', transcript):
        return None
    return (
        "`gh pr create` has no prior Skill(\"github-flow\", ...) invocation in this session's transcript.\n\n"
        "Why blocked:\n"
        "  - --draft is present, but draft/template alone does not mean the github-flow "
        "procedure was followed. Raw `gh pr create` skips pr.md's other mandatory steps: "
        "Step 6 (milestone check), Step 7.5 (CI-watch -> ready, same-turn), Step 9 "
        "(Copilot reviewer registration + CodeRabbit walkthrough follow-up scheduling).\n"
        "  - See failed-attempts.md 'pr-create-bypass' (4th recurrence) / 'skill-invoke-bypass'.\n\n"
        "Required action (pick one):\n"
        "  1. Call Skill(\"github-flow\", \"pr\") first, then let it run gh pr create, OR\n"
        "  2. If github-flow genuinely does not apply here (non-GitHub forge, scripted "
        "automation context, etc.), prefix the command with GH_PR_CREATE_SKILL_BYPASS=1 "
        "gh pr create ... so the opt-out is auditable.\n\n"
        "Reference: failed-attempts.md 'pr-create-bypass' (github-flow/pr.md)."
    )


GH_PR_MERGE_READY_RE = re.compile(r"\bgh\s+pr\s+(merge|ready)\b")


def check_pr_merge_ready_empty_commits(command: str) -> str | None:
    """`gh pr merge`/`gh pr ready` on a PR with 0 commits is almost always a
    symptom of a broken creation path (e.g. a GraphQL createPullRequest
    workaround against a head repository with no fork-network relationship to
    origin), not a genuinely empty change. `gh pr diff --name-only` can still
    print file names for such a PR — it reflects a diff computation, not the
    PR's own registered commit range — so it is not proof of real content.
    This queries the PR's own `commits` field live and blocks only when it can
    positively confirm the array is empty (github-flow/merge.md 'Empty-PR
    guard')."""
    if not GH_PR_MERGE_READY_RE.search(command):
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None  # unparseable — fail open
    verb_idx = None
    for i in range(len(tokens) - 2):
        if tokens[i] == "gh" and tokens[i + 1] == "pr" and tokens[i + 2] in ("merge", "ready"):
            verb_idx = i + 2
            break
    if verb_idx is None:
        return None
    pr_number = None
    repo = None
    i = verb_idx + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-R", "--repo"):
            if i + 1 < len(tokens):
                repo = tokens[i + 1]
            i += 2
            continue
        if tok.startswith("--repo="):
            repo = tok[len("--repo="):]
            i += 1
            continue
        if not tok.startswith("-") and pr_number is None and re.fullmatch(r"\d+", tok):
            pr_number = tok
        i += 1
    if pr_number is None:
        return None  # no explicit PR number (current-branch PR) — fail open
    args = ["gh", "pr", "view", pr_number, "--json", "commits"]
    if repo:
        args += ["-R", repo]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=15)
    except Exception:
        return None  # network/timeout — fail open
    if out.returncode != 0:
        return None  # gh itself failed (auth, not found, etc.) — fail open, not this hook's job
    try:
        data = json.loads(out.stdout)
    except Exception:
        return None
    commits = data.get("commits", [])
    if len(commits) != 0:
        return None
    return (
        f"PR #{pr_number} has 0 commits.\n\n"
        "Why blocked:\n"
        "  - `gh pr view --json commits` shows an empty commits array for this PR.\n"
        "  - Merging or readying an empty PR is almost always a symptom of a broken "
        "PR-creation path (e.g. a GraphQL createPullRequest workaround after `gh pr "
        "create` failed), not a genuinely empty change.\n"
        "  - `gh pr diff --name-only` can print misleading file names even when "
        "commits is empty — do not trust it alone as evidence the PR has real content.\n\n"
        "Required action:\n"
        f"  - Run `gh pr view {pr_number} --json commits,additions,deletions,changedFiles` "
        "yourself to confirm.\n"
        "  - If genuinely empty, close it and recreate via a path that actually "
        "registers the head branch's commits (e.g. a same-repo branch push + `gh pr "
        "create`, not a cross-repo createPullRequest against a non-fork-network head).\n\n"
        "Reference: github-flow/merge.md 'Empty-PR guard'."
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

    if has_walkthrough:
        # The walkthrough_start marker is present in EVERY CodeRabbit review
        # comment, whether or not it also posted inline line-by-line comments
        # — it cannot by itself distinguish a genuinely walkthrough-only
        # review (the actual Step 3.5 trigger condition) from a full review
        # (Internal Review Fallback finding #19, PR #197). Inline comments
        # post via the PR *review comments* endpoint (pulls/{N}/comments),
        # not the issue-comments endpoint already fetched above — check it
        # before treating the walkthrough marker as a trigger.
        try:
            r = subprocess.run(
                ["gh", "api", f"repos/{repo}/pulls/{pr_num}/comments"],
                capture_output=True, text=True, timeout=10,
            )
            review_comments = json.loads(r.stdout) if r.stdout else []
            if any("coderabbit" in (c.get("user", {}).get("login") or "").lower() for c in review_comments):
                has_walkthrough = False  # full review (has inline comments) — not the Step 3.5 trigger
        except Exception:
            pass  # API/infra failure — fall through with has_walkthrough as-is (fail toward the existing behavior)

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
        "  - CodeRabbit review: walkthrough-only, no inline comments found (Step 3.5 trigger met)\n"
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


_PROD_BRANCHES = r"(?<![\w-])(?:production|master|release|prod|stable)"
_PROD_BRANCH_PATTERNS = [
    (r"git\s+push\s+.*:" + _PROD_BRANCHES + r"(?:$|\s)", "git push deleting protected branch"),
    (r"git\s+push\s+.*" + _PROD_BRANCHES + r"(?:$|\s|:)", "git push targeting protected branch"),
    (r"git\s+branch\s+(?:-[a-zA-Z]+\s+)*" + _PROD_BRANCHES + r"(?:$|\s)", "git branch create/force on protected branch"),
    (r"git\s+(?:checkout|switch)\s+-[bBcC]\s+" + _PROD_BRANCHES + r"(?:$|\s)", "git branch create via checkout/switch on protected branch"),
    (r"gh\s+api\s+.*branches/" + _PROD_BRANCHES, "gh api mutation on protected branch"),
    (r"git\s+worktree\s+add\s+.*" + _PROD_BRANCHES + r"(?:$|\s)", "git worktree add on protected branch"),
    (r"git\s+update-ref\s+refs/heads/" + _PROD_BRANCHES, "git update-ref on protected branch"),
    (r"gh\s+workflow\s+run\s+.*(?:--ref|-r)\s+" + _PROD_BRANCHES + r"(?:$|\s)", "gh workflow run (workflow_dispatch) targeting protected branch"),
]


def _worktree_add_new_nonprod_branch(scan: str) -> bool:
    """True for `git worktree add ... -b/-B <new-branch> [<prod-base>]` where <new-branch>
    is not itself a protected branch. In that form a protected branch can appear only as
    the start-point (safe: it is never checked out for mutation), so creating a feature
    branch FROM master/prod is allowed, while `git worktree add <path> <prod-branch>`
    (which checks out the protected branch itself) stays blocked."""
    if not re.search(r"git\s+worktree\s+add\b", scan, IM):
        return False
    m = re.search(r"-[bB]\s+(\S+)", scan)
    if not m:
        return False
    new_branch = m.group(1)
    # -b target must not itself be a protected branch (blocks `-b master`, `-b release/x`)
    if re.match(_PROD_BRANCHES + r"(?:$|[/_-])", new_branch, IM):
        return False
    return True


def check_prod_branch_ops(command: str) -> str | None:
    """Block autonomous git/gh operations that create, push, delete, protect, or
    workflow_dispatch against release-trigger branches (production/master/release/
    prod/stable). `main` is deliberately excluded (already gated by the
    push-confirmation rule). Bypass: prefix the command with
    ALLOW_PROD_BRANCH_OPS=1 (per-command only — never session-wide).

    Ported from the standalone block-prod-branch-autonomous-ops.sh hook into
    bash-guard.py to avoid an extra PreToolUse:Bash process spawn per command."""
    if os.environ.get("ALLOW_PROD_BRANCH_OPS") == "1":
        return None
    if re.search(r"ALLOW_PROD_BRANCH_OPS=1", command):
        return None
    scan = git_scan_text(command)
    reason = None
    for pat, r in _PROD_BRANCH_PATTERNS:
        if re.search(pat, scan, IM):
            reason = r
            break
    if reason == "git worktree add on protected branch" and _worktree_add_new_nonprod_branch(scan):
        # `git worktree add -b <new-nonprod-branch> <prod-base>` branches FROM a protected
        # branch without checking it out mutably (safe) — exempt it while keeping the block
        # on `git worktree add <path> <prod-branch>` (checks out the protected branch).
        reason = None
    if reason is None and (
        re.search(r"gh\s+api\s+.*actions/workflows/.*dispatches", scan, IM)
        and re.search(r"(?:-f|-F|--field|--raw-field)\s+ref=" + _PROD_BRANCHES + r"(?:$|\s)", scan, IM)
    ):
        reason = "gh api workflow_dispatch targeting protected branch"
    if reason is None:
        return None
    return (
        f"{reason}\n\n"
        "Branches matching /(production|master|release|prod|stable)/ are release triggers. "
        "A single autonomous operation on them can trigger real user-facing publishes "
        "(semantic-release, Marketplace stable, npm dist-tag latest, GitOps ArgoCD sync) "
        "with no dry-run and no rollback.\n\n"
        "To proceed with a genuinely user-approved operation, prefix the command with "
        "ALLOW_PROD_BRANCH_OPS=1 (per-command only — never session-wide)."
    )


_GIT_GLOBAL_OPTS = r"(?:-C\s+\S+\s+|--no-pager\s+|-c\s+\S+=\S+\s+)*"

_STAGING_BRANCH_TARGET = re.compile(
    r"(?:git\s+" + _GIT_GLOBAL_OPTS + r"worktree\s+add|"
    r"git\s+" + _GIT_GLOBAL_OPTS + r"switch\s+-[cC]|"
    r"git\s+" + _GIT_GLOBAL_OPTS + r"checkout\s+-[bB]|"
    r"gh\s+pr\s+create[^\n]*--base)\b[^\n]*\b(?:origin/)?(next-fix|next-feat)\b",
    IM,
)

_STAGING_DIVERGENCE_EVIDENCE = re.compile(
    r"git\s+" + _GIT_GLOBAL_OPTS + r"(?:log|diff)\s+origin/main(?:\.\.\.?|\s+)origin/next-|baseRefName",
    IM,
)


def check_staging_branch_without_divergence(command: str) -> str | None:
    """Block creating/targeting a worktree, branch, or PR base on next-fix/next-feat
    without evidence (in the same command) that the branch's actual staging-branch
    home was checked first. next-fix and next-feat independently diverge from main and
    from each other — assuming "this is a fix/* change so next-fix" (or the reverse)
    without checking has caused repeated scope-contamination and wrong-base incidents
    (failed-attempts.md class pr-base-divergence-check-reactive-not-preemptive, 3rd
    occurrence triggered this check).

    Evidence accepted (same command string): a divergence check
    (`git log/diff origin/main..origin/next-*`) or a `baseRefName` lookup
    (`gh pr view --json baseRefName`) confirming an existing PR's real base."""
    if not _STAGING_BRANCH_TARGET.search(command):
        return None
    if _STAGING_DIVERGENCE_EVIDENCE.search(command):
        return None
    return (
        "git worktree/branch/PR-base targets next-fix or next-feat without a "
        "divergence check in the same command.\n\n"
        "next-fix and next-feat independently diverge from main and from each other — "
        "assuming one is the right base for a given branch (e.g. \"this is a fix/* "
        "change so next-fix\") has repeatedly caused wrong-base branches (unrelated "
        "commits pulled in, or a rebase mixing in another staging branch's history).\n\n"
        "Run one of these first (in the same command), then retry:\n"
        "  gh pr view <N> --json baseRefName   # if a PR already exists for this branch\n"
        "  git log origin/main..origin/next-fix --oneline   # + reverse, to see actual divergence\n"
        "  git log origin/main..origin/next-feat --oneline  # + reverse"
    )


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

    if run_bg:
        bound_values = [int(v) for v in TIME_BOUND_VALUE.findall(command)]
        if bound_values and max(bound_values) > TIME_BOUND_CEILING:
            return hard(
                f"run_in_background command-level time bound ({max(bound_values)}s) exceeds "
                f"the {TIME_BOUND_CEILING}s ceiling — one long silent wait risks the prompt "
                f"cache TTL expiring before you check back. Re-arm as a short cycle instead: "
                f"timeout <= {TIME_BOUND_CEILING} <cmd>, then on notification either drive "
                "other pending work or re-issue another bounded background call."
            )

    for pat, msg in SIMPLE_BLOCKS:
        if re.search(pat, command, IM):
            return hard(msg)

    scan = git_scan_text(command)
    for sub, msg in GIT_BLOCKS:
        if re.search(GITPFX + r"\s+" + sub, scan, IM):
            return hard(msg)

    reset_reason = check_git_reset(scan)
    if reset_reason:
        return hard(reset_reason)

    force_push_reason = check_git_force_push(command)
    if force_push_reason:
        return hard(force_push_reason)

    pr_reason = check_pr_create_draft(command, transcript_path)
    if pr_reason:
        return hard(pr_reason)

    pr_merge_ready_reason = check_pr_merge_ready_empty_commits(command)
    if pr_merge_ready_reason:
        return hard(pr_merge_ready_reason)

    ghapi_reason = check_gh_api_lowercase_f(command)
    if ghapi_reason:
        return hard(ghapi_reason)

    pm2_reason = check_pm2_start_without_resurrect(command)
    if pm2_reason:
        return hard(pm2_reason)

    summary_reason = check_summary_without_internal_review(command)
    if summary_reason:
        return hard(summary_reason)

    prod_branch_reason = check_prod_branch_ops(command)
    if prod_branch_reason:
        return hard(prod_branch_reason)

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
        # ── staging-branch base gate (merged from the tracked copy) ──
        (True, False, "git switch -C fix/x origin/next-fix"),
        (True, False, "git checkout -b fix/y origin/next-feat"),
        (True, False, "git worktree add ../wt origin/next-fix"),
        (True, False, "gh pr create --base next-fix --draft --title x --body y"),
        (False, False, "git log origin/main..origin/next-fix --oneline; git switch -C fix/x origin/next-fix"),
        (False, False, "gh pr view 238 --json baseRefName; git switch -C fix/x origin/next-feat"),
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
        # ── PR #374 CodeRabbit findings: force-push detection must survive a
        # backslash-newline continuation before --force, and must resolve -C
        # from the SAME invocation that carries the flag (not a decoy git -C
        # earlier in the same command). Both use an unresolvable fake path so
        # the exception's own "unverifiable -> fail closed" path still blocks
        # (see tests/test_bash_guard_force_push.py for the full ALLOW-path
        # coverage against real worktrees). ──
        (True, False, "git -C /p push \\\n  --force origin main"),
        (True, False, "git push \\\n  --force origin main"),
        (True, False, "git -C /wt status && git -C /p push --force origin topic"),
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
        # ── soft/mixed reset split (TaskList #15): --hard always blocks;
        # bare reset, non-HEAD~N refs, and N>2 fall back to the same block ──
        (True, False, "git reset"),
        (True, False, "git reset --soft HEAD~3"),
        (True, False, "git -C /p reset --soft main"),
        (True, False, "git reset --soft --hard"),
        # ── FP cases: mentions / safe commands that MUST be allowed ──
        (False, False, "git status"),
        (False, False, "git -C /srv/app log --oneline -5"),
        (False, False, "git -C /p reset --soft HEAD~1"),
        (False, False, "git reset --soft HEAD~2"),
        (False, False, "git reset --mixed HEAD~1"),
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
        (False, True, "curl --max-time 30 http://example.com"),
        (False, True, "curl -m 10 http://example.com"),
        (False, True, "ssh -o ConnectTimeout=10 host uptime"),
        # ── background time-bound ceiling (>270s risks outlasting cache TTL) ──
        (True, True, "cd /repo && timeout 300 gh pr create --draft"),
        (True, True, "timeout 330 clawo session-send name msg"),
        (False, True, "timeout 270 gh pr checks"),
        (False, True, "timeout 240 sleep 1"),
        # foreground: ceiling does not apply (tool timeout param governs)
        (False, False, "timeout 330 gh pr create --draft"),
        # foreground: same commands must stay allowed (tool timeout param governs)
        (False, False, "git push origin main"),
        (False, False, "gh run watch 12345"),
        # ── non-git hard blocks ──
        (True, False, "rm -rf /var/lib/rancher/k3s"),
        (True, False, "docker volume rm mydata"),
        (True, False, "gh pr close 123"),
        (True, False, "rm -rf .tmp"),
        (False, False, "rm -f .tmp/pr-body.md"),
        # ── /tmp/<subpath> exemption from the generic rm -rf / root guard —
        # OS scratch space, routinely rm -rf'd by tests/cleanup. Bare /tmp
        # (no subpath) still blocks (whole shared system temp dir).
        (False, False, "rm -rf /tmp/hooktest"),
        (False, False, "rm -rf /tmp/some/nested/dir"),
        (True, False, "rm -rf /tmp"),
        (True, False, "rm -rf /"),
        # ── gh pr create --draft guard (ported from block-pr-create-without-draft.sh) ──
        (True, False, "gh pr create --title x --body y"),
        (False, False, "gh pr create --draft --title x --body y"),
        # --draft=false is a valid, explicit non-draft invocation — a naive
        # `startswith("--draft=")` prefix check would wrongly treat this as
        # satisfying the draft requirement (Critical finding, PR #197 review).
        (True, False, "gh pr create --draft=false --title x --body y"),
        (True, False, "gh pr create --draft=0 --title x --body y"),
        (False, False, "gh pr create --draft=true --title x --body y"),
        (False, False, "PR_READY_APPROVED=1 gh pr create --title x --body y"),
        (False, False, 'grep "gh pr create" README.md'),
        (False, False, 'echo "run gh pr create --draft next"'),
        # heredoc body prose mentioning "gh pr create" must not false-positive
        # (shlex has no heredoc concept — tokenizes body words like bare tokens)
        (False, False, "git commit -F - <<'EOF'\nfix: gh pr create fires CI\nEOF"),
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

    # ── gh pr create --draft + Skill(github-flow) invocation-evidence guard ──
    # (failed-attempts.md "pr-create-bypass" 4th recurrence): the main `cases`
    # list above always passes transcript_path="" (fail-open), so this check's
    # transcript-dependent branch is untested there. Exercise it explicitly.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("no skill marker on this line\n")
        no_skill_transcript = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"skill":"github-flow","args":"pr"}\n')
        with_skill_transcript = f.name
    # When the skill ships inside a plugin the harness records a plugin-qualified
    # name. A bare-literal match misses it, which made this guard unsatisfiable
    # through its own documented path #1 in plugin installs.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"skill":"es6kr:github-flow","args":"pr"}\n')
        with_qualified_skill_transcript = f.name
    # A different skill must not satisfy the check just by ending in the same name.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"skill":"not-github-flow","args":"pr"}\n')
        wrong_skill_transcript = f.name
    try:
        transcript_cases = [
            # (expect_block, command, transcript_path)
            (True, "gh pr create --draft --title x", no_skill_transcript),
            (False, "gh pr create --draft --title x", with_skill_transcript),
            (False, "gh pr create --draft --title x", with_qualified_skill_transcript),
            (True, "gh pr create --draft --title x", wrong_skill_transcript),
            (False, "GH_PR_CREATE_SKILL_BYPASS=1 gh pr create --draft --title x", no_skill_transcript),
            (False, "gh pr create --draft --title x", ""),  # no transcript — fail open
            (False, 'grep "gh pr create" README.md', no_skill_transcript),  # not a real invocation
        ]
        for expect_block, cmd, tpath in transcript_cases:
            code, _, _ = evaluate(cmd, False, transcript_path=tpath)
            got_block = code in (1, 2)
            if got_block == expect_block:
                passed += 1
            else:
                failed += 1
                print(f"FAIL(transcript) expected={'BLOCK' if expect_block else 'ALLOW'} "
                      f"got={'BLOCK' if got_block else 'ALLOW'} :: {cmd!r} transcript={tpath!r}")
    finally:
        os.unlink(no_skill_transcript)
        os.unlink(with_skill_transcript)
        os.unlink(with_qualified_skill_transcript)
        os.unlink(wrong_skill_transcript)

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
