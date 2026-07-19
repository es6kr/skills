#!/usr/bin/env python3
"""FA section lifecycle analyzer for fa-prune.

Parses failed-attempts.md (HOT) sections and classifies each by:
  - latest/title date (from `(YYYY-MM-DD` patterns)
  - recurrence marker in title (Korean-language phrasing for "recurred" / "Nth occurrence")
  - future-hook obligation in body
  - post-title dates in body (possible later recurrence)

Usage:
  uv run python fa-analyze.py [--file PATH] [--cutoff YYYY-MM-DD] [--json OUT]

Output: summary counts + COLD candidates (old, no title-recurrence marker).
Encoding-safe: writes UTF-8 regardless of console codepage.

Note: the failed-attempts.md data file this script analyzes is a personal,
locale-specific log (not part of this skill's published content), so the
regex patterns below intentionally match Korean-language recurrence/hook
phrasing used in that data file.
"""
import argparse, io, json, os, re, sys
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_FILE = os.path.expanduser("~/.claude/skills/cleanup/data/failed-attempts.md")
DATE = re.compile(r"\((\d{4}-\d{2}-\d{2})")
RECUR_TITLE = re.compile(r"\d+\s*회(차|째)|재발")
HOOK_FUTURE = re.compile(r"(회차|회째|다음 발생|재발).{0,20}(시|이상).{0,10}hook|hook (자동화|필수|검토)", re.I)


def analyze(path: str, cutoff: str):
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
        rows.append({
            "idx": i,
            "title": title,
            "latest": latest,
            "title_date": title_date,
            "recur": bool(RECUR_TITLE.search(title)),
            "hook": bool(HOOK_FUTURE.search(s)),
            "later_body": bool(title_date and latest and latest > title_date),
            "old": (title_date or latest or "9999") < cutoff,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--cutoff", default=(date.today() - timedelta(days=30)).isoformat(),
                    help="dates older than this are COLD candidates (default: today-30d)")
    ap.add_argument("--json", dest="json_out", default=None, help="write full rows JSON to this path")
    args = ap.parse_args()

    rows = analyze(args.file, args.cutoff)
    recur_t = [r for r in rows if r["recur"]]
    cold = [r for r in rows if not r["recur"] and r["old"]]

    print(f"total={len(rows)} title-recur-marker={len(recur_t)} cold_cand(old,no-title-recur)={len(cold)} cutoff={args.cutoff}")
    print("\n--- COLD candidates (oldest first; verify hook/later_body before demote) ---")
    for r in sorted(cold, key=lambda x: x["title_date"] or x["latest"]):
        print(f"[{r['idx']:3d}] {r['title_date'] or r['latest']} hook={int(r['hook'])} later={int(r['later_body'])} | {r['title'][:100]}")

    if args.json_out:
        json.dump(rows, io.open(args.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\nrows JSON -> {args.json_out}")


if __name__ == "__main__":
    main()
