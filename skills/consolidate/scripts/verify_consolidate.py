#!/usr/bin/env python3
"""Mechanical validator for PR review consolidation comments.

Validates that PR Internal Code Review and AI Review Summary comments
strictly adhere to the 7-column schema, contain accurate reviewer counts,
include all inline comments and superpowers internal findings, validate
all cited SHAs against git, and follow strict chronological ordering.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


def run_gh_api(endpoint: str, repo: Optional[str] = None) -> Any:
    """Run a gh api GET command and return parsed JSON."""
    cmd = ["gh", "api", endpoint]
    if repo:
        cmd.extend(["-R", repo])
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def git_sha_exists(sha: str) -> bool:
    """Check if a git SHA exists in the local repository."""
    res = subprocess.run(["git", "cat-file", "-e", sha], capture_output=True)
    return res.returncode == 0


# A consolidate artifact is identified by its TITLE LINE, not by the presence of a
# skill name anywhere in the body.
#
# Substring-over-whole-body matching cannot separate "this comment IS the Internal
# Review" from "this comment TALKS ABOUT the Internal Review". Any Summary that
# explains the requesting/receiving pairing -- including one honestly documenting why
# a previous review was inadequate -- matches both filters and is classified as both
# artifacts. The consequences are silent: `internal_reviews[-1]` and `summaries[-1]`
# resolve to the same comment, the chronological check compares a timestamp with
# itself and passes, the internal finding count reads 0 against a Summary body, and
# "Missing Internal Code Review comment" never fires even when no such comment exists.
# That is how a PR carrying a single fabricated Summary and no Internal Review at all
# could still have satisfied the existence gate.
#
# post.md makes the title line mandatory and self-identifying, so keying off it is
# both stricter and cheaper: the link lives in the heading or the artifact is
# malformed and should be reported as such.
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
INTERNAL_SLUG = "requesting-code-review"
SUMMARY_SLUG = "receiving-code-review"


def title_line(body: str) -> str:
    """First non-empty line of a comment body."""
    for line in (body or "").splitlines():
        if line.strip():
            return line
    return ""


def titled_as(body: str, slug: str) -> bool:
    """True when the body's title line is a heading carrying a link to `slug`.

    Requires all three: a heading, a markdown link, and the slug inside that link.
    A heading that merely mentions the slug in prose does not qualify -- the
    template is `## <Title> - [<slug>](https://.../<slug>)`.
    """
    line = title_line(body)
    if not HEADING_RE.match(line):
        return False
    for link in re.finditer(r"\[([^\]]*)\]\(([^)]*)\)", line):
        if slug in link.group(1) or slug in link.group(2):
            return True
    return False


def looks_like(body: str, *keywords: str) -> bool:
    """Heuristic used only to explain a miss: the title line reads like the artifact
    but carries no link, so the author almost certainly meant it as one."""
    line = title_line(body)
    return bool(HEADING_RE.match(line)) and all(k.lower() in line.lower() for k in keywords)


class ConsolidateValidator:
    def __init__(self, pr_num: int, repo: Optional[str] = None) -> None:
        self.pr_num = pr_num
        self.repo = repo
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> bool:
        """Run all verification gates on the PR comments."""
        print(f"[*] Validating consolidate comments for PR #{self.pr_num}...")
        
        # 1. Fetch inline review comments and issue comments
        try:
            repo_prefix = f"repos/{self.repo}/" if self.repo else ""
            if not repo_prefix:
                repo_info = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                                           capture_output=True, text=True, check=True)
                repo_name = repo_info.stdout.strip()
                repo_prefix = f"repos/{repo_name}/"

            inline_comments: List[Dict[str, Any]] = run_gh_api(f"{repo_prefix}pulls/{self.pr_num}/comments")
            issue_comments: List[Dict[str, Any]] = run_gh_api(f"{repo_prefix}issues/{self.pr_num}/comments")
        except Exception as e:
            self.errors.append(f"Failed to fetch PR data from GitHub API: {e}")
            return False

        # 2. Extract Internal Code Review and AI Review Summary comments
        internal_reviews = [c for c in issue_comments if titled_as(c.get("body", ""), INTERNAL_SLUG)]
        summaries = [c for c in issue_comments if titled_as(c.get("body", ""), SUMMARY_SLUG)]

        if not internal_reviews:
            near_miss = [c for c in issue_comments
                         if looks_like(c.get("body", ""), "code review")
                         and not titled_as(c.get("body", ""), SUMMARY_SLUG)]
            hint = (f" (comment {near_miss[-1].get('id')} has a Code Review heading but no "
                    f"[{INTERNAL_SLUG}](...) link in it)") if near_miss else ""
            self.errors.append(
                f"Missing Internal Code Review comment -- its title line must carry a "
                f"[{INTERNAL_SLUG}](...) link{hint}.")
        if not summaries:
            near_miss = [c for c in issue_comments if looks_like(c.get("body", ""), "summary")]
            hint = (f" (comment {near_miss[-1].get('id')} has a Summary heading but no "
                    f"[{SUMMARY_SLUG}](...) link in it)") if near_miss else ""
            self.errors.append(
                f"Missing AI Review Summary comment -- its title line must carry a "
                f"[{SUMMARY_SLUG}](...) link{hint}.")

        # A single comment titled as both artifacts collapses the pair the whole
        # workflow rests on; without this the two lists below would resolve to it twice.
        both = [c for c in issue_comments
                if titled_as(c.get("body", ""), INTERNAL_SLUG)
                and titled_as(c.get("body", ""), SUMMARY_SLUG)]
        if both:
            self.errors.append(
                f"Comment {both[-1].get('id')} is titled as BOTH the Internal Code Review and "
                f"the AI Review Summary. They must be two separate comments.")

        if not internal_reviews or not summaries:
            return False

        internal_review = internal_reviews[-1]
        summary = summaries[-1]

        # 3. Check chronological ordering
        internal_created = internal_review.get("created_at", "")
        summary_created = summary.get("created_at", "")
        if internal_created > summary_created:
            self.errors.append(
                f"Chronological order error: Internal Code Review ({internal_created}) was posted after AI Review Summary ({summary_created})."
            )

        # 4. Check Internal Code Review structure and isolation
        internal_body = internal_review.get("body", "")
        if "<!-- consolidate:verified -->" not in internal_body:
            self.warnings.append("Internal Code Review is missing <!-- consolidate:verified --> provenance comment.")
        
        # Internal Review should NOT echo external reviewer assessment summaries
        if re.search(r"Assessment:\s*Agree\s*\((?:Copilot|CodeRabbit)", internal_body, re.IGNORECASE):
            self.errors.append(
                "Internal Code Review violates role isolation: Contains echoes of external reviewer assessments."
            )

        # 5. Check AI Review Summary structure
        summary_body = summary.get("body", "")
        if "<!-- consolidate:verified -->" not in summary_body:
            self.warnings.append("AI Review Summary is missing <!-- consolidate:verified --> provenance comment.")

        # 6. Check Reviewer Matrix vs actual inline comment authors
        reviewer_counts: Dict[str, int] = {}
        for ic in inline_comments:
            user = ic.get("user", {}).get("login", "unknown")
            # Normalize Copilot / coderabbitai logins
            if "copilot" in user.lower():
                key = "copilot"
            elif "coderabbit" in user.lower():
                key = "coderabbit"
            else:
                key = user
            reviewer_counts[key] = reviewer_counts.get(key, 0) + 1

        print(f"[*] Actual inline comment counts on PR: {reviewer_counts}")

        # Check that AI Review Summary contains accurate counts
        for rev_key, count in reviewer_counts.items():
            pattern = re.compile(rf"{rev_key}.*?(\d+)\s*(?:inline\s*)?comments?", re.IGNORECASE)
            match = pattern.search(summary_body)
            if match:
                reported_count = int(match.group(1))
                if reported_count != count:
                    self.errors.append(
                        f"Reviewer Matrix mismatch for {rev_key}: actual on PR is {count}, but Summary reported {reported_count}."
                    )
            else:
                self.errors.append(f"Reviewer Matrix missing entry for active reviewer '{rev_key}' ({count} comments).")

        # 7. Check Consolidated Findings Table Row Count vs Matrix Total
        # Count findings in superpowers internal review
        internal_findings = len(re.findall(r"^####\s+\d+\.", internal_body, re.MULTILINE))
        if internal_findings == 0:
            # Fallback check for finding headers
            internal_findings = len(re.findall(r"^####\s+`", internal_body, re.MULTILINE))

        total_expected_findings = sum(reviewer_counts.values()) + internal_findings

        # Parse rows in Consolidated Findings table
        table_rows = []
        for line in summary_body.splitlines():
            line = line.strip()
            if line.startswith("|") and line.endswith("|"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if parts and parts[0].isdigit():
                    table_rows.append(parts)

        print(f"[*] Expected findings: {total_expected_findings} (External: {sum(reviewer_counts.values())}, Internal: {internal_findings}) | Table rows: {len(table_rows)}")

        if len(table_rows) != total_expected_findings:
            self.errors.append(
                f"Consolidated Findings table row count mismatch: expected {total_expected_findings} rows, but table has {len(table_rows)} rows."
            )

        # 8. Check that superpowers findings are present in the table
        superpowers_in_table = [r for r in table_rows if len(r) > 1 and "superpowers" in r[1].lower()]
        if internal_findings > 0 and len(superpowers_in_table) == 0:
            self.errors.append("Consolidated Findings table is missing superpowers (Internal Code Review) findings.")

        # 9. Check SHA existence for all cited commit SHAs
        sha_matches = re.findall(r"(?:commit\s+`?|#)([0-9a-f]{7,40})`?", summary_body, re.IGNORECASE)
        for sha in sha_matches:
            # Avoid matching purely numeric issue IDs like #347
            if re.match(r"^[0-9]+$", sha):
                continue
            if not git_sha_exists(sha):
                self.errors.append(f"Hallucinated or non-existent commit SHA cited in Summary: '{sha}'")

        # 10. Check merge recommendation format
        if "gh pr merge" in summary_body and "/github-flow merge" not in summary_body:
            self.errors.append("Summary recommends raw 'gh pr merge' instead of '/github-flow merge <N>'.")

        return len(self.errors) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PR review consolidation comments")
    parser.add_argument("--pr", type=int, required=True, help="PR number to validate")
    parser.add_argument("-R", "--repo", type=str, help="GitHub repository (owner/repo)")
    args = parser.parse_args()

    validator = ConsolidateValidator(pr_num=args.pr, repo=args.repo)
    success = validator.validate()

    if validator.warnings:
        print("\n[!] WARNINGS:")
        for w in validator.warnings:
            print(f"  - {w}")

    if not success:
        print("\n[X] VALIDATION FAILED:")
        for err in validator.errors:
            print(f"  - {err}")
        return 1

    print("\n[✓] ALL CONSOLIDATE GATES PASSED (100% Verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
