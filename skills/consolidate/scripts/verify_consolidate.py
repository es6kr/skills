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
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


def run_gh_api(endpoint: str, repo: Optional[str] = None) -> Any:
    """Fetch every REST list page; endpoint carries the explicit owner/repo.

    gh api has no -R flag. --slurp makes paginated arrays one JSON document,
    which must be flattened before counting or sorting artifacts.
    """
    cmd = ["gh", "api", endpoint, "--paginate", "--slurp"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    pages = json.loads(res.stdout)
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise ValueError("Expected paginated REST list response")
    return [item for page in pages for item in page]


def git_sha_exists(sha: str, repo: Optional[str] = None) -> bool:
    """Check if a git SHA exists in the local repository.

    `--repo <repo>` steers the API endpoint; git itself always resolves
    against the process cwd. When `repo` is given, resolve it to the local
    ghq checkout (`~/ghq/github.com/<owner>/<name>`) instead of assuming cwd.
    """
    cmd = ["git"]
    if repo:
        cmd.extend(["-C", os.path.expanduser(f"~/ghq/github.com/{repo}")])
    cmd.extend(["cat-file", "-e", sha])
    res = subprocess.run(cmd, capture_output=True)
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


# The `requesting-code-review` link is a PROVENANCE CLAIM: "this artifact is the
# superpowers requesting-code-review framework's own output". internal.md's
# "Bot-layer content in the body drops the suffix" rule therefore FORBIDS that link
# whenever the body carries bot-layer findings -- a CodeRabbit CLI substitute run, for
# instance -- and prescribes an engine-naming heading instead.
#
# Requiring the link unconditionally put this script in direct contradiction with that
# rule: a review authored by the CLI could satisfy the skill or the verifier, never
# both, and the only way to pass was to state a provenance the artifact did not have.
#
# The path below accepts an engine-named Code Review, but it is deliberately a
# CONJUNCTION of independent conditions -- a single weak signal must never pass a
# provenance gate:
#   1. the invisible `<!-- consolidate:verified -->` marker (it came through consolidate)
#   2. a Code Review heading naming a recognised review engine (it states WHICH)
#   3. the heading does not claim the word "Summary" (post.md reserves that for Step 7)
# Dropping any one of them would let an ordinary comment that merely says "code review"
# in its heading register as the artifact.
ENGINE_RE = re.compile(r"coderabbit|copilot|superpowers|code-reviewer", re.IGNORECASE)
CODE_REVIEW_TITLE_RE = re.compile(r"code\s+review", re.IGNORECASE)
VERIFIED_MARKER = "<!-- consolidate:verified -->"


def titled_as_internal_by_engine(body: str) -> bool:
    """True when an engine-named Code Review satisfies ALL of the conditions above.

    This is the sanctioned shape for a Code Review whose body holds bot-layer content,
    per internal.md's suffix-drop rule. It does not relax the provenance gate -- it
    replaces one strong signal (the framework link) with the conjunction of three
    weaker but independent ones.
    """
    if VERIFIED_MARKER not in (body or ""):
        return False
    line = title_line(body)
    if not HEADING_RE.match(line):
        return False
    if not CODE_REVIEW_TITLE_RE.search(line):
        return False
    if "summary" in line.lower():
        return False
    return bool(ENGINE_RE.search(line))


def is_internal_review(body: str) -> bool:
    """Internal Code Review detection: framework link OR engine-named conjunction."""
    return titled_as(body, INTERNAL_SLUG) or titled_as_internal_by_engine(body)


# A consolidate artifact can be posted as an issue comment OR as a review.
# internal.md routes the Internal Code Review to the reviews API whenever
# line-specific Critical/Important findings exist, because only that API carries
# inline annotations; post.md likewise allows a unified Formal Review POST to
# carry the Summary. Searching issue comments alone therefore reports a correctly
# posted artifact as missing, and the expected-row arithmetic below silently
# drops every finding that artifact carried.
BOT_LOGIN_RE = re.compile(r"copilot|coderabbit|github-actions|dependabot|\[bot\]", re.IGNORECASE)
SUPPRESSED_RE = re.compile(r"Suppressed comments\s*\((\d+)\)", re.IGNORECASE)


# A findings cell often has to quote a regex, and a literal pipe inside a markdown
# table cell must be written `\|`. Splitting on every pipe shifts every column after
# it, so the Status check ends up reading a regex fragment and reports an
# off-contract value on a table that is actually correct.
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def split_cells(row: str) -> List[str]:
    """Split a markdown table row on unescaped pipes only."""
    return [c.strip() for c in CELL_SPLIT_RE.split(row.strip().strip("|"))]


def posted_at(item: Dict[str, Any]) -> str:
    """Timestamp of a posted artifact -- issue comments and reviews name it differently."""
    return item.get("created_at") or item.get("submitted_at") or ""


def is_bot(login: str) -> bool:
    return bool(BOT_LOGIN_RE.search(login or ""))


def looks_like(body: str, *keywords: str) -> bool:
    """Heuristic used only to explain a miss: the title line reads like the artifact
    but carries no link, so the author almost certainly meant it as one."""
    line = title_line(body)
    return bool(HEADING_RE.match(line)) and all(k.lower() in line.lower() for k in keywords)


def reviewer_engine(login: str) -> str:
    """Normalize engine variants without counting cloud and CLI twice."""
    lowered = login.lower()
    for engine in ("copilot", "coderabbit"):
        if engine in lowered:
            return engine
    return login


def completed_review_engines(reviews: List[Dict[str, Any]],
                             inline: List[Dict[str, Any]], before: str,
                             reviewed_commit: Optional[str] = None) -> set[str]:
    """API evidence, not a Summary's self-reported Completed badges, grants quorum.

    Inline findings must belong to the submitted review; zero-finding reviews
    require an explicit completed-review signal rather than a walkthrough.
    """
    by_commit: Dict[str, set[str]] = {}
    for review in reviews:
        engine = reviewer_engine((review.get("user") or {}).get("login", ""))
        body = (review.get("body") or "").strip()
        timestamp = review.get("submitted_at") or ""
        commit = review.get("commit_id") or ""
        if (engine not in {"copilot", "coderabbit"} or not body or not timestamp
                or not commit or (reviewed_commit and not commit.startswith(reviewed_commit))
                or timestamp > before
                or review.get("state") not in {"COMMENTED", "APPROVED", "CHANGES_REQUESTED"}
                or is_internal_review(body) or titled_as(body, SUMMARY_SLUG)):
            continue
        if re.search(r"review\s+skipped|skipped\s+review|unable to review|encountered an error|review failed|review in progress", body, re.I):
            continue
        # Badge-only and walkthrough-only bodies are not substantive reviews,
        # even if a stale inline annotation happens to reference their ID.
        prose = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body).strip()
        if not prose or re.match(r"^#{1,6}\s+walkthrough\b", prose, re.I):
            continue
        findings = any(
            review.get("id") is not None
            and c.get("pull_request_review_id") == review["id"]
            and reviewer_engine((c.get("user") or {}).get("login", "")) == engine
            and (c.get("body") or "").strip()
            for c in inline
        )
        completion = re.search(r"reviewed (?:changes|\d+ files)|actionable comments posted:\s*\d+|no (?:issues|findings)(?: found)?", prose, re.I)
        if findings or completion:
            by_commit.setdefault(commit, set()).add(engine)
    for engines in by_commit.values():
        if engines == {"copilot", "coderabbit"}:
            return engines
    return set()


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

        # Reviews are a second medium for both artifacts and the only place a bot's
        # suppressed findings or a human reviewer's own review body ever appear.
        # Fetched separately and tolerantly: a caller that cannot reach this endpoint
        # should lose the extra coverage, not the whole validation run.
        try:
            reviews: List[Dict[str, Any]] = run_gh_api(f"{repo_prefix}pulls/{self.pr_num}/reviews")
        except Exception:
            reviews = []
        if not isinstance(reviews, list):
            reviews = []

        # 2. Extract Internal Code Review and AI Review Summary comments
        posted_artifacts = sorted(list(issue_comments) + list(reviews), key=posted_at)
        internal_reviews = [c for c in posted_artifacts if is_internal_review(c.get("body", ""))]
        summaries = [c for c in posted_artifacts if titled_as(c.get("body", ""), SUMMARY_SLUG)]

        reviewed_match = re.search(r"Reviewed commit\s+`?([0-9a-f]{7,40})", summaries[-1].get("body", ""), re.I) if summaries else None
        quorum = bool(summaries) and completed_review_engines(
            reviews, inline_comments, posted_at(summaries[-1]),
            reviewed_match.group(1) if reviewed_match else None) == {"copilot", "coderabbit"}
        if not internal_reviews and not quorum:
            near_miss = [c for c in posted_artifacts
                         if looks_like(c.get("body", ""), "code review")
                         and not titled_as(c.get("body", ""), SUMMARY_SLUG)]
            hint = (f" (comment {near_miss[-1].get('id')} has a Code Review heading, but it carries "
                    f"neither a [{INTERNAL_SLUG}](...) link nor the engine-named form: the "
                    f"{VERIFIED_MARKER} marker AND a named engine in the heading)") if near_miss else ""
            self.errors.append(
                f"Missing Internal Code Review comment -- its title line must carry a "
                f"[{INTERNAL_SLUG}](...) link, or name the contributing engine(s) in the heading "
                f"alongside the {VERIFIED_MARKER} marker{hint}.")
        if not summaries:
            near_miss = [c for c in posted_artifacts if looks_like(c.get("body", ""), "summary")]
            hint = (f" (comment {near_miss[-1].get('id')} has a Summary heading but no "
                    f"[{SUMMARY_SLUG}](...) link in it)") if near_miss else ""
            self.errors.append(
                f"Missing AI Review Summary comment -- its title line must carry a "
                f"[{SUMMARY_SLUG}](...) link{hint}.")

        # A single comment titled as both artifacts collapses the pair the whole
        # workflow rests on; without this the two lists below would resolve to it twice.
        both = [c for c in posted_artifacts
                if is_internal_review(c.get("body", ""))
                and titled_as(c.get("body", ""), SUMMARY_SLUG)]
        if both:
            self.errors.append(
                f"Comment {both[-1].get('id')} is titled as BOTH the Internal Code Review and "
                f"the AI Review Summary. They must be two separate comments.")

        # Graph Causal Validation Gate:
        # A summary comment without a preceding internal review comment breaks the
        # causal lineage DAG (Finding -> InternalReview -> AISummary).
        if summaries and not internal_reviews and not quorum:
            self.errors.append(
                f"Broken review causality: Summary comment {summaries[-1].get('id')} is disconnected. "
                f"Missing preceding internal review comment in PR {self.pr_num} causal DAG."
            )

        if not summaries or (not internal_reviews and not quorum):
            return False

        # Summary-only lineage is Finding -> completed independent reviews -> Summary.
        # Do not manufacture an Internal Review to satisfy the old DAG shape.
        internal_review = internal_reviews[-1] if internal_reviews else {}
        summary = summaries[-1]

        # 3. Check chronological ordering
        internal_created = posted_at(internal_review)
        summary_created = posted_at(summary)
        if internal_created > summary_created:
            self.errors.append(
                f"Chronological order error: Internal Code Review ({internal_created}) was posted after AI Review Summary ({summary_created})."
            )

        # 4. Check Internal Code Review structure and isolation
        internal_body = internal_review.get("body", "")
        if internal_reviews and "<!-- consolidate:verified -->" not in internal_body:
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
        # An Internal Review posted as a review carries its findings as inline
        # annotations, which also surface in pulls/<N>/comments. Those are the very
        # findings already counted as internal findings -- counting them here too
        # would inflate the expected total and demand a duplicate table row.
        internal_review_id = internal_review.get("id")
        reviewer_counts: Dict[str, int] = {}
        for ic in inline_comments:
            if internal_review_id is not None and ic.get("pull_request_review_id") == internal_review_id:
                continue
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
        # Count findings in superpowers internal review. The numbered and
        # backticked forms are the documented ones, but the heading style is not
        # actually fixed anywhere -- `#### IR-1 - ...` is just as valid and used to
        # count as zero, which dropped every internal finding from the expected
        # total and failed an otherwise correct Summary.
        internal_findings = len(re.findall(r"^####\s+\d+\.", internal_body, re.MULTILINE))
        if internal_findings == 0:
            internal_findings = len(re.findall(r"^####\s+`", internal_body, re.MULTILINE))
        if internal_findings == 0:
            internal_findings = len(re.findall(r"^####\s+\S", internal_body, re.MULTILINE))

        # Findings that exist but never appear in pulls/<N>/comments:
        #   - a bot's suppressed findings, which it lists inside its review body
        #   - a human reviewer's own review body
        # Both are real findings a Summary must carry, so both belong in the
        # expected total. The consolidate artifacts themselves are excluded --
        # they are accounted for by internal_findings and by the table itself.
        suppressed_findings = 0
        human_review_findings = 0
        for review in reviews:
            review_body = review.get("body") or ""
            if titled_as(review_body, INTERNAL_SLUG) or titled_as(review_body, SUMMARY_SLUG):
                continue
            login = (review.get("user") or {}).get("login", "")
            if is_bot(login):
                for hit in SUPPRESSED_RE.finditer(review_body):
                    suppressed_findings += int(hit.group(1))
            elif review_body.strip():
                human_review_findings += 1

        total_expected_findings = (
            sum(reviewer_counts.values())
            + suppressed_findings
            + human_review_findings
            + internal_findings
        )

        # Parse rows in Consolidated Findings table
        table_rows = []
        provenance_rows = []
        table_header = []
        for line in summary_body.splitlines():
            line = line.strip()
            if line.startswith("|") and line.endswith("|"):
                parts = split_cells(line)
                if parts and parts[0] == "#":
                    table_header = [p.lower() for p in parts]
                if parts and parts[0].isdigit():
                    table_rows.append(parts)
                    provenance_rows.append((table_header, parts))
            else:
                table_header = []

        # Counts are only a floor. Each API finding still needs its own attributed
        # row; padding with unrelated/local findings cannot cover missing sources.
        used_rows = set()
        for ic in inline_comments:
            internal_inline = internal_review_id is not None and ic.get("pull_request_review_id") == internal_review_id
            engine = reviewer_engine((ic.get("user") or {}).get("login", "unknown"))
            finding_id = ic.get("id")
            found = False
            for index, (header, row) in enumerate(provenance_rows):
                if index in used_rows:
                    continue
                source_index = next((i for i, h in enumerate(header) if h.startswith("source")), None)
                if source_index is None or source_index >= len(row):
                    continue
                source = row[source_index]
                # Engine attribution comes from visible source text, not its URL.
                label = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", source).lower()
                attributed = engine.lower() in label
                if internal_inline:
                    attributed = attributed or "superpowers" in label or "internal code review" in label
                if not attributed:
                    continue
                location_indices = [i for i, h in enumerate(header) if h in {"file", "location"}]
                if finding_id is not None:
                    expected = f"https://github.com/{repo_prefix.removeprefix('repos/').rstrip('/')}/pull/{self.pr_num}#discussion_r{finding_id}"
                    # Templates link either the Source or the Location cell.
                    # Finding prose/status and non-table mentions are not attribution.
                    link_cells = [source] + [row[i] for i in location_indices if i < len(row)]
                    covered = any(link.group(1) == expected for cell in link_cells
                                  for link in re.finditer(r"\[[^\]]*\]\(([^)]*)\)", cell))
                else:
                    # Compatibility only for historical fixtures without API IDs.
                    line_number = ic.get("line") or ic.get("original_line")
                    location = f"{ic.get('path', '')}:{line_number}"
                    covered = bool(ic.get("path") and line_number) and any(
                        i < len(row) and re.search(r"(?<![\w/.-])" + re.escape(location) + r"(?!\d)", row[i])
                        for i in location_indices)
                if covered:
                    used_rows.add(index)
                    found = True
                    break
            if not found:
                self.errors.append(f"Missing source provenance for {engine} inline finding {finding_id or str(ic.get('path')) + ':' + str(ic.get('line'))}: numbered Summary row must attribute its source link (discussion_r<ID>), or historical path+line when no ID exists.")

        print(
            f"[*] Expected findings: {total_expected_findings} "
            f"(inline: {sum(reviewer_counts.values())}, suppressed: {suppressed_findings}, "
            f"human reviews: {human_review_findings}, internal: {internal_findings}) "
            f"| Table rows: {len(table_rows)}"
        )

        # total_expected_findings is a floor, not an exact total: it only counts
        # sources this script can see from the GitHub API (inline comments, human
        # reviews) plus the Internal Code Review heading count. A reviewer engine
        # run locally and never posted to GitHub as its own artifact (e.g. a
        # CodeRabbit CLI pass run against the working tree) contributes real rows
        # the Summary is right to include, but this script has no path to count
        # them independently -- so the table legitimately has MORE rows than this
        # formula predicts. Only under-reporting (missing/dropped findings) is an
        # actual defect; extra rows from a local-only engine are not.
        if len(table_rows) < total_expected_findings:
            self.errors.append(
                f"Consolidated Findings table row count mismatch: expected at least {total_expected_findings} rows, but table has {len(table_rows)} rows."
            )

        # 8. Check that Internal Code Review findings are present in the table.
        # post.md's own Summary body example sources these rows as "Internal Code
        # Review", not "superpowers" -- "superpowers" is the provenance-link slug
        # used in the comment TITLE (see INTERNAL_SLUG), not the Source cell text
        # a table row is expected to carry. Accept either so a Summary written to
        # the documented convention is not flagged as missing its own findings.
        internal_review_in_table = [
            r for r in table_rows
            if len(r) > 1 and ("superpowers" in r[1].lower() or "internal code review" in r[1].lower())
        ]
        if internal_findings > 0 and len(internal_review_in_table) == 0:
            self.errors.append("Consolidated Findings table is missing Internal Code Review findings.")

        # 9. Check SHA existence for all cited commit SHAs
        sha_matches = re.findall(r"(?:commit\s+`?|#)([0-9a-f]{7,40})`?", summary_body, re.IGNORECASE)
        for sha in sha_matches:
            # Avoid matching purely numeric issue IDs like #347
            if re.match(r"^[0-9]+$", sha):
                continue
            if not git_sha_exists(sha, self.repo):
                self.errors.append(f"Hallucinated or non-existent commit SHA cited in Summary: '{sha}'")

        # 10. Check merge recommendation format
        if "gh pr merge" in summary_body and "/github-flow merge" not in summary_body:
            self.errors.append("Summary recommends raw 'gh pr merge' instead of '/github-flow merge <N>'.")

        # 11. Check findings-table Status column vocabulary
        #
        # post.md fixes the column name to `Status` and its values to exactly five.
        # Checks 1-10 never looked at the values, so four separate runs shipped a
        # self-invented vocabulary (`Verified`, `\U0001F7E2 Verified`, `\u2705 Accept`, `\u2705 VALID`)
        # while this gate reported "ALL GATES PASSED". That matters beyond wording:
        # post.md derives the merge recommendation FROM this column (any
        # `\U0001F534 Pending` -> Hold), so an off-contract value zeroes the Pending
        # count and flips the verdict to "no merge blocker".
        self._check_status_vocabulary(summary_body)

        return len(self.errors) == 0

    # The leading emoji is the documented form but is treated as optional here:
    # the failure class this guard exists for is an invented *word* (VALID /
    # Accept / Verified / Unverified / Out of scope), not a missing emoji.
    # Requiring the emoji too would reject plain "Pending", which is already in
    # use and is not the defect.
    ALLOWED_STATUS_RE = [
        re.compile(r"^(\U0001F7E2\s*)?Fixed\b"),
        re.compile(r"^(\U0001F534\s*)?Pending\b"),
        re.compile(r"^(\U0001F7E1\s*|\U0001F7E2\s*)?Deferred\b"),
        re.compile(r"^(\u26AA\s*)?Rejected\b"),
    ]

    def _check_status_vocabulary(self, summary_body: str) -> None:
        """Findings table must use the `Status` column with post.md's five values."""
        block: List[str] = []
        tables: List[tuple] = []
        for line in summary_body.splitlines() + [""]:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                block.append(stripped)
                continue
            if len(block) >= 3:
                header = split_cells(block[0])
                rows = [split_cells(r) for r in block[2:]]
                rows = [r for r in rows if r and r[0].isdigit()]
                if rows:
                    tables.append((header, rows))
            block = []

        for header, rows in tables:
            lowered = [h.lower() for h in header]
            if "status" not in lowered:
                self.errors.append(
                    "Findings table has no 'Status' column (header: "
                    + " | ".join(header)
                    + "). post.md fixes the column name to 'Status'; renaming it "
                    "(e.g. 'Verdict') leaks the receiving-code-review judgement frame "
                    "into the published column, which post.md derives the merge "
                    "recommendation from."
                )
                continue
            idx = lowered.index("status")
            for row in rows:
                cell = row[idx] if idx < len(row) else ""
                plain = re.sub(r"[*`_]", "", cell).strip()
                if not any(rx.match(plain) for rx in self.ALLOWED_STATUS_RE):
                    self.errors.append(
                        f"Findings row {row[0]}: Status {cell!r} is outside the post.md "
                        "contract. Allowed: '\U0001F7E2 Fixed (commit <sha>)', "
                        "'\U0001F534 Pending', '\U0001F7E1 Deferred (author follow-up)', "
                        "'\U0001F7E2 Deferred (no action)', '\u26AA Rejected \u2014 <reason>'. "
                        "A valid in-diff finding that is not yet fixed is "
                        "'\U0001F534 Pending' from the start."
                    )


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
