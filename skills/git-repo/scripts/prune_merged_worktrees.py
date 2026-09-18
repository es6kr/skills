#!/usr/bin/env python3
"""
prune_merged_worktrees.py - Prune clean worktrees whose branches have been merged.

Features:
- Discovers git worktrees for a repository or multiple repositories (--scan).
- Enforces safety gates (HARD STOPS):
  * Operation-state gate: skips worktrees mid-operation (rebase/merge/cherry-pick/conflicts).
  * Cleanliness gate: skips dirty worktrees with uncommitted changes.
  * Preserves main/root repository worktree.
- Multi-vendor merge detection:
  * GitHub: queries `gh pr list` for merged status and compares local vs PR headRefOid SHA.
  * Git-native fallback: uses `git merge-base --is-ancestor` against upstream branch.
- Formats output according to strict user specifications:
  * Single combined column for repository + PR markdown link ([repo/pull/N](url)).
  * Single combined column for Local / PR HEAD SHA.
  * Zero bare URLs or footnote citation blocks.
- Safe execution: defaults to --dry-run unless --execute is specified.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


class WorktreeInfo:
    def __init__(self, path: Path, head_sha: str, branch: Optional[str] = None, is_bare: bool = False, is_main: bool = False):
        self.path = path
        self.head_sha = head_sha
        self.branch = branch
        self.is_bare = is_bare
        self.is_main = is_main


class WorktreeReport:
    def __init__(self, wt: WorktreeInfo, repo_name: str):
        self.wt = wt
        self.repo_name = repo_name
        self.is_clean = False
        self.is_mid_operation = False
        self.mid_operation_reason = ""
        self.is_merged = False
        self.merge_method = ""  # "github" or "git-native"
        self.pr_number: Optional[int] = None
        self.pr_url: Optional[str] = None
        self.pr_head_sha: Optional[str] = None
        self.upstream_branch: Optional[str] = None
        self.action = "Skipped"
        self.skip_reason = ""


def run_git(repo_dir: Path, args: List[str]) -> Tuple[int, str, str]:
    cmd = ["git", "-C", str(repo_dir)] + args
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def get_worktrees(repo_dir: Path) -> List[WorktreeInfo]:
    ret, stdout, _ = run_git(repo_dir, ["worktree", "list", "--porcelain"])
    if ret != 0 or not stdout:
        return []

    worktrees: List[WorktreeInfo] = []
    current_entry: Dict[str, str] = {}
    is_first = True

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            if current_entry and "worktree" in current_entry:
                wt_path = Path(current_entry["worktree"])
                head_sha = current_entry.get("HEAD", "")
                branch = current_entry.get("branch")
                if branch and branch.startswith("refs/heads/"):
                    branch = branch[len("refs/heads/"):]
                is_bare = "bare" in current_entry
                worktrees.append(WorktreeInfo(
                    path=wt_path,
                    head_sha=head_sha,
                    branch=branch,
                    is_bare=is_bare,
                    is_main=is_first
                ))
                is_first = False
                current_entry = {}
            continue

        parts = line.split(" ", 1)
        key = parts[0]
        val = parts[1] if len(parts) > 1 else ""
        current_entry[key] = val

    if current_entry and "worktree" in current_entry:
        wt_path = Path(current_entry["worktree"])
        head_sha = current_entry.get("HEAD", "")
        branch = current_entry.get("branch")
        if branch and branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/"):]
        is_bare = "bare" in current_entry
        worktrees.append(WorktreeInfo(
            path=wt_path,
            head_sha=head_sha,
            branch=branch,
            is_bare=is_bare,
            is_main=is_first
        ))

    return worktrees


def check_mid_operation(wt_path: Path) -> Tuple[bool, str]:
    ret, gitdir, _ = run_git(wt_path, ["rev-parse", "--absolute-git-dir"])
    if ret != 0 or not gitdir:
        return False, ""

    gitdir_path = Path(gitdir)
    op_indicators = [
        "CHERRY_PICK_HEAD",
        "MERGE_HEAD",
        "REBASE_HEAD",
        "BISECT_LOG",
        "rebase-merge",
        "rebase-apply",
    ]
    for ind in op_indicators:
        if (gitdir_path / ind).exists():
            return True, f"In-progress operation detected: {ind}"

    # Check unmerged index status (DD, AU, UD, UA, DU, AA, UU)
    ret, stdout, _ = run_git(wt_path, ["status", "--porcelain"])
    if ret == 0 and stdout:
        for line in stdout.splitlines():
            code = line[:2]
            if any(code.startswith(u) or code.endswith(u) for u in ["DD", "AU", "UD", "UA", "DU", "AA", "UU"]):
                return True, f"Unmerged conflict entries present: {code}"

    return False, ""


def check_clean(wt_path: Path) -> bool:
    ret, stdout, _ = run_git(wt_path, ["status", "--porcelain"])
    return ret == 0 and len(stdout.strip()) == 0


def get_origin_info(repo_dir: Path) -> Tuple[str, Optional[str], Optional[str]]:
    """Returns (remote_url, provider, slug). provider in ['github', 'generic', None]"""
    ret, stdout, _ = run_git(repo_dir, ["remote", "get-url", "origin"])
    if ret != 0 or not stdout:
        return "", None, None

    url = stdout.strip()
    # Check for github
    github_match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)(?:\.git)?$", url)
    if github_match:
        slug = f"{github_match.group(1)}/{github_match.group(2)}"
        return url, "github", slug

    return url, "generic", None


def check_github_merged(repo_slug: str, branch: str) -> Optional[Dict[str, str]]:
    if not shutil.which("gh"):
        return None

    cmd = [
        "gh", "pr", "list",
        "--repo", repo_slug,
        "--head", branch,
        "--state", "all",
        "--json", "number,state,url,headRefOid,title,mergedAt",
        "--limit", "1"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0 or not res.stdout.strip():
        return None

    try:
        prs = json.loads(res.stdout)
        if prs and isinstance(prs, list) and len(prs) > 0:
            pr = prs[0]
            if pr.get("state") == "MERGED":
                return pr
    except Exception:
        return None

    return None


def get_default_upstream(repo_dir: Path) -> Optional[str]:
    # Try origin/HEAD first
    ret, stdout, _ = run_git(repo_dir, ["symbolic-ref", "refs/remotes/origin/HEAD"])
    if ret == 0 and stdout:
        return stdout.strip().replace("refs/remotes/", "")

    # Candidate defaults
    for cand in ["origin/main", "origin/master", "origin/develop"]:
        ret, _, _ = run_git(repo_dir, ["rev-parse", "--verify", cand])
        if ret == 0:
            return cand

    return None


def check_git_ancestor_merged(repo_dir: Path, branch: str, upstream: str) -> bool:
    ret, _, _ = run_git(repo_dir, ["merge-base", "--is-ancestor", branch, upstream])
    return ret == 0


def format_table(reports: List[WorktreeReport], execute: bool) -> str:
    lines = []
    lines.append("| Worktree Path | Branch | PR / Upstream | Local / Remote SHA | Clean? | Action |")
    lines.append("|---|---|---|---|:---:|---|")

    for r in reports:
        # Worktree path normalized to forward slashes for clean output
        norm_path = str(r.wt.path).replace("\\", "/")

        # Branch
        branch_str = f"`{r.wt.branch}`" if r.wt.branch else "*(detached)*"

        # PR / Upstream (Combined markdown link, NO bare URL)
        if r.pr_number and r.pr_url:
            short_repo = r.repo_name.split("/")[-1] if "/" in r.repo_name else r.repo_name
            pr_col = f"[{short_repo}/pull/{r.pr_number}]({r.pr_url})"
        elif r.upstream_branch:
            pr_col = f"Merged into `{r.upstream_branch}`"
        else:
            pr_col = "-"

        # Local / Remote SHA (Combined column)
        local_sha = r.wt.head_sha[:8] if r.wt.head_sha else "-"
        if r.pr_head_sha:
            remote_sha = r.pr_head_sha[:8]
            if local_sha == remote_sha:
                sha_col = f"`{local_sha}` / `{remote_sha}` (match)"
            else:
                sha_col = f"`{local_sha}` / `{remote_sha}` (rebased/squashed)"
        elif r.upstream_branch:
            sha_col = f"`{local_sha}` / `{r.upstream_branch}`"
        else:
            sha_col = f"`{local_sha}` / -"

        # Clean?
        clean_col = "Clean" if r.is_clean else "Dirty"
        if r.is_mid_operation:
            clean_col = "Mid-Op"

        # Action
        action_col = r.action
        if r.skip_reason:
            action_col = f"{r.action} ({r.skip_reason})"

        lines.append(f"| `{norm_path}` | {branch_str} | {pr_col} | {sha_col} | {clean_col} | {action_col} |")

    return "\n".join(lines)


def process_repository(repo_dir: Path, execute: bool = False, delete_branch: bool = False) -> List[WorktreeReport]:
    repo_dir = repo_dir.resolve()
    ret, toplevel, _ = run_git(repo_dir, ["rev-parse", "--show-toplevel"])
    if ret == 0 and toplevel:
        repo_dir = Path(toplevel)

    worktrees = get_worktrees(repo_dir)
    if not worktrees:
        return []

    _, provider, slug = get_origin_info(repo_dir)
    repo_name = slug if slug else repo_dir.name
    upstream = get_default_upstream(repo_dir)

    reports: List[WorktreeReport] = []

    for wt in worktrees:
        if wt.is_main or wt.is_bare:
            continue

        report = WorktreeReport(wt, repo_name)

        # 1. Operation-state gate
        mid_op, mid_op_reason = check_mid_operation(wt.path)
        if mid_op:
            report.is_mid_operation = True
            report.mid_operation_reason = mid_op_reason
            report.action = "Skipped"
            report.skip_reason = "mid-operation"
            reports.append(report)
            continue

        # 2. Cleanliness gate
        is_clean = check_clean(wt.path)
        report.is_clean = is_clean
        if not is_clean:
            report.action = "Skipped"
            report.skip_reason = "dirty working tree"
            reports.append(report)
            continue

        # 3. Branch check
        if not wt.branch:
            report.action = "Skipped"
            report.skip_reason = "detached HEAD"
            reports.append(report)
            continue

        # 4. Merge check
        merged = False
        if provider == "github" and slug:
            pr_data = check_github_merged(slug, wt.branch)
            if pr_data:
                merged = True
                report.is_merged = True
                report.merge_method = "github"
                report.pr_number = pr_data.get("number")
                report.pr_url = pr_data.get("url")
                report.pr_head_sha = pr_data.get("headRefOid")

        if not merged and upstream:
            if check_git_ancestor_merged(repo_dir, wt.branch, upstream):
                merged = True
                report.is_merged = True
                report.merge_method = "git-native"
                report.upstream_branch = upstream

        if not merged:
            report.action = "Skipped"
            report.skip_reason = "branch not merged"
            reports.append(report)
            continue

        # 5. Prune action
        if execute:
            rem_ret, _, rem_err = run_git(repo_dir, ["worktree", "remove", str(wt.path)])
            if rem_ret == 0:
                report.action = "Pruned"
                run_git(repo_dir, ["worktree", "prune"])
                if delete_branch and wt.branch:
                    run_git(repo_dir, ["branch", "-d", wt.branch])
            else:
                report.action = "Failed"
                report.skip_reason = f"remove error: {rem_err}"
        else:
            report.action = "Dry-run (eligible)"

        reports.append(report)

    return reports


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Prune clean git worktrees whose branches have been merged into PR/upstream."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to inspect (defaults to current directory)."
    )
    parser.add_argument(
        "--repo", "-r",
        dest="repo_path",
        help="Explicit repository path (alias for path)."
    )
    parser.add_argument(
        "--scan",
        help="Scan all git repositories under the specified root directory."
    )
    parser.add_argument(
        "--execute", "--apply",
        action="store_true",
        help="Physically remove eligible clean merged worktrees (default: dry-run)."
    )
    parser.add_argument(
        "--delete-branch", "-d",
        action="store_true",
        help="Also delete the local branch with 'git branch -d' if merged."
    )

    args = parser.parse_args()
    execute = args.execute

    target_repos: List[Path] = []
    if args.scan:
        scan_root = Path(args.scan).resolve()
        if not scan_root.exists():
            print(f"Error: scan path does not exist: {scan_root}", file=sys.stderr)
            sys.exit(1)
        seen_repos = set()
        for git_dir in scan_root.rglob(".git"):
            if git_dir.is_dir():
                repo_path = git_dir.parent.resolve()
                if repo_path not in seen_repos:
                    seen_repos.add(repo_path)
                    target_repos.append(repo_path)
    else:
        target_path = Path(args.repo_path or args.path).resolve()
        target_repos.append(target_path)

    all_reports: List[WorktreeReport] = []
    for repo in target_repos:
        repo_reports = process_repository(repo, execute=execute, delete_branch=args.delete_branch)
        all_reports.extend(repo_reports)

    if not all_reports:
        print("No auxiliary worktrees found across specified repositories.")
        return

    table_md = format_table(all_reports, execute=execute)
    print("\n" + table_md + "\n")

    eligible_count = sum(1 for r in all_reports if r.is_clean and r.is_merged and not r.is_mid_operation)
    pruned_count = sum(1 for r in all_reports if "Pruned" in r.action)
    skipped_count = len(all_reports) - (pruned_count if execute else eligible_count)

    print(f"Total auxiliary worktrees inspected: {len(all_reports)}")
    if execute:
        print(f"Pruned: {pruned_count} | Skipped: {skipped_count}")
    else:
        print(f"Eligible for pruning: {eligible_count} | Skipped: {skipped_count}")
        if eligible_count > 0:
            print("Note: This was a dry-run. Pass '--execute' to perform physical worktree deletion.")


if __name__ == "__main__":
    main()
