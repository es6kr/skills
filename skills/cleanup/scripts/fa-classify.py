#!/usr/bin/env python3
"""FA HOT/COLD classifier + section cutter for fa-prune.

Extends fa-analyze.py with a **recurrence-resolved** exception. Without it,
recurrence markers and future-hook obligations pin almost every section HOT,
making a strict numeric cap unreachable in practice. The exception lets a
section demote once the recurring risk is actually resolved — a hook/escalation
has been implemented (matched by the RESOLVED pattern below) — while still
keeping live/unresolved recurrences HOT.

Classification per section (date = latest `(YYYY-MM-DD` in title, else body):
  blocked = (recur_marker OR future_hook) AND NOT resolved
  cold    = old(date < cutoff) AND NOT blocked AND NOT later_body_recurrence
  hot     = otherwise

--relaxed (stale-recurrence policy, fa-prune option B, user-approved):
  a recurrence marker no longer blocks demotion when the section's NEWEST date
  anywhere (title or body — i.e. the last recorded recurrence) is older than
  cutoff. Unresolved future-hook obligations still block. Undated sections stay
  HOT (file-top = newest — avoids a false-positive on the most recent entries).
  cold_relaxed = has_date AND newest_date < cutoff AND NOT (future_hook AND NOT resolved)

`resolved` matches DONE wording only (completed hook/escalation). It must NOT
match future obligations (e.g. "hook implementation mandatory", "hook
automation under review", "hook implementation to execute immediately",
"not yet implemented", "hook on Nth occurrence").

hook=True/resolved=False rows also get their referenced hook/script file paths
(backtick-wrapped `~/.claude/...` or `~/.agents/...` .sh/.py) extracted and
checked for existence. A path that already exists usually means the hook was
actually implemented and the row is a false negative of the RESOLVED regex —
flagged in the default output so fa-prune doesn't need a manual Read+find per
row (2026-07-16: 18 such rows needed manual verification, 17 were false
negatives).

Modes:
  (default)     print summary + COLD candidates (R = demoted via resolved-exception)
  --cut OUTDIR  write each COLD section body to OUTDIR/NNN.md (+ index.json),
                ready as input for a RAG store step (see scripts ref: fa-batch-store.py)
  --json OUT    dump full rows JSON (bodies stripped)

Usage:
  uv run python fa-classify.py [--file PATH] [--cutoff YYYY-MM-DD]
                               [--cut OUTDIR] [--json OUT]

Encoding-safe: UTF-8 output regardless of console codepage (Windows dual-sync).

Note: the failed-attempts.md data file this script analyzes is a personal,
locale-specific log (not part of this skill's published content), so the
regex patterns below intentionally match Korean-language recurrence/hook/
resolution phrasing used in that data file.
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_FILE = os.path.expanduser(
    "~/.claude/skills/cleanup/data/failed-attempts.md"
)

DATE = re.compile(r"\((\d{4}-\d{2}-\d{2})")
# check #1: recurrence marker in title (Korean-language "Nth occurrence" / "recurred")
RECUR_TITLE = re.compile(r"\d+\s*회(차|째)|재발")
# backtick-wrapped hook/script file path (~/.claude/... or ~/.agents/...) — used to
# auto-verify hook=True/resolved=False rows: if the referenced file already exists on
# disk, the row is very likely a false negative (hook was implemented but the RESOLVED
# wording didn't match), not a genuinely unresolved obligation.
HOOK_PATH = re.compile(r"`(~/\.(?:claude|agents)/[\w./-]+\.(?:sh|py))`")
# check #3: future-hook obligation in body (kept HOT unless resolved)
HOOK_FUTURE = re.compile(
    r"(회차|회째|다음 발생|재발).{0,20}(시|이상).{0,10}hook|hook (자동화|필수|검토)",
    re.I,
)
# resolution marker — the recurring risk is already handled (DONE wording only).
# Anchored on the Korean "completed" word within a short window so future-tense
# phrasing ("implementation mandatory" / "under review" / "not implemented") does NOT match.
RESOLVED = re.compile(
    r"escalation[^\n]{0,15}완료"
    r"|hook[^\n]{0,15}(구현|자동화|등록|설치)[^\n]{0,6}완료"
    r"|재발[^\n]{0,10}(방지|해결)[^\n]{0,6}완료"
    r"|자동[^\n]{0,6}(차단|방지)[^\n]{0,6}완료",
    re.I,
)

# the hook skill was renamed hook -> hook-kit; older log entries still reference
# the pre-rename path, so fall back to the renamed location before giving up.
_HOOK_RENAME = ("/skills/hook/resources/", "/skills/hook-kit/resources/")


def _hook_path_exists(p):
    expanded = os.path.expanduser(p)
    if os.path.exists(expanded):
        return True
    if _HOOK_RENAME[0] in expanded:
        return os.path.exists(expanded.replace(*_HOOK_RENAME))
    return False


def analyze(path, cutoff, relaxed=False):
    text = io.open(path, encoding="utf-8").read()
    parts = re.split(r"(?m)^## ", text)
    sections = ["## " + p for p in parts[1:]]

    rows = []
    for i, s in enumerate(sections):
        title = s.split("\n", 1)[0][3:].strip()
        dates = DATE.findall(s)
        latest = max(dates) if dates else ""
        title_dates = DATE.findall(title)
        title_date = max(title_dates) if title_dates else ""
        recur = bool(RECUR_TITLE.search(title))
        hook = bool(HOOK_FUTURE.search(s))
        resolved = bool(RESOLVED.search(s))
        later_body = bool(title_date and latest and latest > title_date)
        old = (title_date or latest or "9999") < cutoff
        blocked = (recur or hook) and not resolved
        hook_paths = sorted(set(HOOK_PATH.findall(s)))
        hook_paths_exist = {p: _hook_path_exists(p) for p in hook_paths}
        # only meaningful for the false-negative case this feature targets: an
        # unresolved-per-regex hook obligation that already has an implemented file
        hook_false_negative = hook and not resolved and any(hook_paths_exist.values())
        cold_strict = old and not blocked and not later_body
        # relaxed: stale recurrence (newest date < cutoff) demotes; hook-unresolved still blocks
        stale = bool(latest) and latest < cutoff
        cold_relaxed = stale and not (hook and not resolved)
        cold = cold_relaxed if relaxed else cold_strict
        rows.append({
            "idx": i,
            "title": title,
            "latest": latest,
            "title_date": title_date,
            "recur": recur,
            "hook": hook,
            "resolved": resolved,
            "later_body": later_body,
            "old": old,
            "cold": cold,
            "via_resolve": cold and (recur or hook) and resolved,
            "via_relaxed": cold and relaxed and not cold_strict,
            "hook_paths": hook_paths,
            "hook_paths_exist": hook_paths_exist,
            "hook_false_negative": hook_false_negative,
            "body": s.rstrip() + "\n",
        })
    return rows


def cut(rows, outdir):
    os.makedirs(outdir, exist_ok=True)
    cold = [r for r in rows if r["cold"]]
    index = []
    for r in cold:
        fn = f"{r['idx']:03d}.md"
        io.open(os.path.join(outdir, fn), "w", encoding="utf-8").write(r["body"])
        index.append({
            "file": fn,
            "idx": r["idx"],
            "title": r["title"],
            "date": r["title_date"] or r["latest"] or "",
            "resolved": r["resolved"],
            "recur": r["recur"],
            "via_resolve": r["via_resolve"],
        })
    json.dump(
        index,
        io.open(os.path.join(outdir, "index.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    return cold, index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument(
        "--cutoff",
        default=(date.today() - timedelta(days=30)).isoformat(),
        help="sections dated older than this are COLD-eligible (default: today-30d)",
    )
    ap.add_argument("--cut", dest="cut_dir", default=None,
                    help="write COLD section bodies to this dir (+ index.json)")
    ap.add_argument("--relaxed", action="store_true",
                    help="stale-recurrence policy (option B): newest date < cutoff "
                         "demotes despite recurrence markers; unresolved hook still blocks")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()

    rows = analyze(args.file, args.cutoff, relaxed=args.relaxed)
    n = len(rows)
    recur = [r for r in rows if r["recur"]]
    resolved_recur = [r for r in rows if r["recur"] and r["resolved"]]
    cold = [r for r in rows if r["cold"]]
    via_resolve = [r for r in cold if r["via_resolve"]]

    via_relaxed = [r for r in cold if r.get("via_relaxed")]
    mode = "relaxed" if args.relaxed else "strict"
    print(
        f"total={n} recur-marker={len(recur)} recur-resolved={len(resolved_recur)} "
        f"COLD={len(cold)} (via resolved-exception={len(via_resolve)}, "
        f"via relaxed={len(via_relaxed)}) mode={mode} cutoff={args.cutoff}"
    )
    print("\n--- COLD candidates (oldest first; R = resolved-exception, S = stale-recurrence) ---")
    for r in sorted(cold, key=lambda x: x["title_date"] or x["latest"]):
        flag = "S" if r.get("via_relaxed") else ("R" if r["via_resolve"] else " ")
        print(f"[{r['idx']:3d}] {r['latest'] or r['title_date']} {flag} | {r['title'][:88]}")

    # HOT rows kept blocked solely by an unresolved hook obligation, where a
    # referenced hook path already exists on disk — likely false negatives
    # (RESOLVED wording didn't match, but the file is there).
    blocked_hook = [r for r in rows if r["hook"] and not r["resolved"] and r["hook_paths"]]
    fneg = [r for r in blocked_hook if r["hook_false_negative"]]
    if blocked_hook:
        print(
            f"\n--- hook=True/resolved=False rows with a referenced path ({len(blocked_hook)}, "
            f"{len(fneg)} likely false negative — path already exists) ---"
        )
        for r in blocked_hook:
            mark = "FALSE-NEG" if r["hook_false_negative"] else "missing  "
            paths = ", ".join(
                f"{'OK' if ok else 'no'}:{p}" for p, ok in r["hook_paths_exist"].items()
            )
            print(f"[{r['idx']:3d}] {mark} | {r['title'][:70]} | {paths}")

    if args.cut_dir:
        c, _ = cut(rows, args.cut_dir)
        print(f"\ncut {len(c)} COLD bodies -> {args.cut_dir} (index.json written)")

    if args.json_out:
        for r in rows:
            r.pop("body", None)
        json.dump(rows, io.open(args.json_out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"rows JSON -> {args.json_out}")


if __name__ == "__main__":
    main()
