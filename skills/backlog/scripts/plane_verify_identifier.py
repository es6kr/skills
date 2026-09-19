#!/usr/bin/env python3
"""plane_verify_identifier.py — confirm a Plane identifier actually refers to
what the caller believes it does, before citing it in an ask/issue/PR comment.

Motivation: a wrong-key reference (e.g. citing ES6KR-128 when the intended
issue is actually ES6KR-129) has recurred several times — Gemini-registered
identifiers pointing at an unrelated issue, or a stale reference surviving a
tracker re-shuffle. Nothing mechanically checked "does this key's real title
match what I think it's about" before the reference was published.

Usage::

    python3 plane_verify_identifier.py ES6KR-128
    python3 plane_verify_identifier.py ES6KR-128 --expect-title-contains "hook registry"
    python3 plane_verify_identifier.py --browse-url https://plane.dgs.ai.kr/dgs/browse/ES6KR-128

Exit codes:
    0  identifier resolved (and, if given, --expect-title-contains matched)
    1  identifier does not resolve, or a usage/profile error
    2  identifier resolves but --expect-title-contains did NOT match —
       the reference is likely citing the wrong key
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plane_client import PlaneClient, PlaneError, format_browse_url  # noqa: E402

IDENTIFIER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-(\d+)$")
BROWSE_URL_RE = re.compile(r"/browse/([A-Za-z][A-Za-z0-9]*)-(\d+)\b")


def parse_identifier(raw):
    m = IDENTIFIER_RE.match(raw.strip())
    if not m:
        raise ValueError('not a valid Plane identifier: %r (expected a form like "ES6KR-128")' % raw)
    return m.group(1).upper(), int(m.group(2))


def parse_browse_url(url):
    m = BROWSE_URL_RE.search(url)
    if not m:
        raise ValueError("could not find an IDENTIFIER-SEQ in browse URL: %r" % url)
    return m.group(1).upper(), int(m.group(2))


def resolve(client, project_code, sequence_id):
    """Return (project, issue) or raise LookupError with a clear message."""
    projects = client.list_projects()
    project = next((p for p in projects if (p.get("identifier") or "").upper() == project_code), None)
    if project is None:
        known = ", ".join(sorted((p.get("identifier") or "?") for p in projects)) or "(none)"
        raise LookupError(
            "no project with identifier %r in this workspace (known: %s)" % (project_code, known)
        )

    issues = client.list_issues(project["id"])
    issue = next((i for i in issues if i.get("sequence_id") == sequence_id), None)
    if issue is None:
        raise LookupError(
            "%s-%d does not exist (project %r has %d issues)"
            % (project_code, sequence_id, project_code, len(issues))
        )
    return project, issue


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("identifier", nargs="?", help='e.g. "ES6KR-128"')
    parser.add_argument("--browse-url", help="alternative to a bare identifier: a full browse URL")
    parser.add_argument(
        "--expect-title-contains",
        help="case-insensitive substring the real issue title must contain",
    )
    args = parser.parse_args(argv)

    if not args.identifier and not args.browse_url:
        parser.error("provide either a bare IDENTIFIER-SEQ or --browse-url")

    try:
        project_code, sequence_id = (
            parse_browse_url(args.browse_url) if args.browse_url else parse_identifier(args.identifier)
        )
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    try:
        client = PlaneClient()
    except PlaneError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    try:
        project, issue = resolve(client, project_code, sequence_id)
    except PlaneError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    except LookupError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    title = issue.get("name", "")
    browse = format_browse_url(client.profile["plane_host"], client.profile["workspace_slug"], project_code, sequence_id)
    print("%s-%d: %s" % (project_code, sequence_id, title))
    print("  state_id: %s" % issue.get("state_id", "?"))
    print("  browse:   %s" % browse)

    if args.expect_title_contains:
        if args.expect_title_contains.lower() not in title.lower():
            print(
                "\nMISMATCH: expected the title to contain %r, but the actual title is %r. "
                "This identifier likely refers to a DIFFERENT issue than intended — "
                "do not cite it without re-checking." % (args.expect_title_contains, title),
                file=sys.stderr,
            )
            return 2
        print("\nOK: title contains %r" % args.expect_title_contains)

    return 0


if __name__ == "__main__":
    sys.exit(main())
