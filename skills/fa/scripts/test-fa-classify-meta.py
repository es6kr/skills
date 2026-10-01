#!/usr/bin/env python3
"""TDD test for fa-classify.py meta-field parser (Phase 2, backward-compatible).

Run: uv run python scripts/test-fa-classify-meta.py
Exits non-zero on any assertion failure. No external test framework (the skill
ships no test deps); plain asserts keep it runnable in a fresh shell.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "fa_classify", os.path.join(HERE, "fa-classify.py")
)
fa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fa)

failures = []


def check(name, cond):
    if cond:
        print(f"ok   - {name}")
    else:
        print(f"FAIL - {name}")
        failures.append(name)


# 1. parse_section_meta extracts key=value fields
m = fa.parse_section_meta(
    "## title\n<!-- fa: class=ask-detour count=6 last=2026-07-06 "
    "status=hook-pending hooks=block-without-guards-skill.sh -->\nbody"
)
check("meta parsed to dict", m is not None)
check("meta class field", m and m.get("class") == "ask-detour")
check("meta count field", m and m.get("count") == "6")
check("meta last field", m and m.get("last") == "2026-07-06")
check("meta status field", m and m.get("status") == "hook-pending")
check("meta hooks field", m and m.get("hooks") == "block-without-guards-skill.sh")

# 2. no meta -> None (fallback to heuristic)
check("no meta returns None", fa.parse_section_meta("## title\nbody no meta") is None)

# 3. meta status classification helpers (deterministic replacement of regex)
check("hook-active is resolved", fa.meta_is_resolved("hook-active") is True)
check("guard-added is resolved", fa.meta_is_resolved("guard-added") is True)
check("fixed is resolved", fa.meta_is_resolved("fixed") is True)
check("rule-covered is resolved", fa.meta_is_resolved("rule-covered") is True)
check("hook-pending not resolved", fa.meta_is_resolved("hook-pending") is False)
check("watch not resolved", fa.meta_is_resolved("watch") is False)

# 4. analyze() honours meta: a hook-pending section stays blocked (not cold),
#    a rule-covered section that is old becomes cold-eligible via meta.
import tempfile

sample = (
    "# Failed Attempts\n\n"
    "## pending-risk\n"
    "<!-- fa: class=pending-risk count=3 last=2026-07-01 status=hook-pending -->\n"
    "- 3rd occurrence, guard not yet built.\n\n"
    "## resolved-old\n"
    "<!-- fa: class=resolved-old count=2 last=2026-01-01 status=rule-covered -->\n"
    "- rule added long ago.\n\n"
    "## legacy-no-meta\n"
    "- plain heuristic section (2026-01-01), 5회차 재발.\n"
)
with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
    f.write(sample)
    tmp = f.name
rows = fa.analyze(tmp, cutoff="2026-06-01")
by_title = {r["title"]: r for r in rows}
check("pending-risk blocked (not cold)", by_title["pending-risk"]["cold"] is False)
check("pending-risk via meta", by_title["pending-risk"].get("via_meta") is True)
check("resolved-old is cold (old + resolved via meta)", by_title["resolved-old"]["cold"] is True)
check("legacy-no-meta falls back to heuristic (recur -> blocked)",
      by_title["legacy-no-meta"].get("via_meta") in (False, None))
os.unlink(tmp)

# 5. header placement as the real corpus writes it: the `fa:` header sits on the
# line BEFORE the `## ` heading. The fixtures above put it after, which is why a
# mis-attribution bug survived them — every section was reading its successor's
# header, and the final section none at all.
corpus = (
    "<!-- fa: class=alpha count=1 last=2026-01-01 status=watch -->\n\n"
    "## Alpha (2026-01-01, 1회차)\n\nbody a\n\n"
    "<!-- fa: class=beta count=3 last=2026-09-26 status=rule-covered -->\n\n"
    "## Beta (2026-08-31, 2회차)\n\nbody b\n\n"
    "<!-- fa: class=gamma count=1 last=2026-02-02 status=watch -->\n\n"
    "## Gamma (2026-02-02, 1회차)\n\nbody c\n"
)
secs = fa.split_sections(corpus)
metas = [(fa.parse_section_meta(x) or {}).get("class") for x in secs]
lasts = [(fa.parse_section_meta(x) or {}).get("last") for x in secs]
check("header-before-heading: three sections", len(secs) == 3)
check("header-before-heading: each section owns its header",
      metas == ["alpha", "beta", "gamma"])
check("header-before-heading: last= is the section's own",
      lasts == ["2026-01-01", "2026-09-26", "2026-02-02"])
check("header-before-heading: no section carries a successor's header",
      all(x.count("<!-- fa:") == 1 for x in secs))

with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
    f.write(corpus)
    tmp2 = f.name
rows2 = {r["title"]: r for r in fa.analyze(tmp2, cutoff="2026-09-01", relaxed=True)}
# Beta recurred on 2026-09-26; its title still shows the first occurrence (2026-08-31).
# Demoting it would archive a live pattern, so the next recurrence reads as "1st".
check("fresh recurrence is not demoted despite an old title date",
      rows2["Beta (2026-08-31, 2회차)"]["cold"] is False)
check("genuinely stale section is still demoted",
      rows2["Alpha (2026-01-01, 1회차)"]["cold"] is True)
check("final section is not starved of its header",
      rows2["Gamma (2026-02-02, 1회차)"].get("via_meta") is True)
os.unlink(tmp2)

# 6. a header block can be several comment lines — the `fa:` line plus sibling
# annotations such as `<!-- hook: ... -->`. The terminator is "only comments and
# blanks follow", not "nothing follows"; otherwise the annotated sections (the
# ones carrying a hook reference, i.e. the escalated ones) silently lose their
# header to the preceding section.
annotated = (
    "<!-- fa: class=one count=1 last=2026-01-01 status=watch -->\n\n"
    "## One (2026-01-01, 1회차)\n\nbody one\n\n"
    "<!-- fa: class=two count=4 last=2026-09-08 status=hook-implemented -->\n"
    "<!-- hook: some-guard.sh — commit abc1234 -->\n\n"
    "## Two (2026-08-31, 1회차)\n\nbody two\n"
)
secs3 = fa.split_sections(annotated)
metas3 = [(fa.parse_section_meta(x) or {}).get("class") for x in secs3]
check("multi-line header block: each section owns its header",
      metas3 == ["one", "two"])
check("multi-line header block: annotation travels with its fa line",
      "some-guard.sh" in secs3[1] and "some-guard.sh" not in secs3[0])

with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
    f.write(annotated)
    tmp3 = f.name
rows3 = {r["title"]: r for r in fa.analyze(tmp3, cutoff="2026-09-01", relaxed=True)}
check("annotated fresh section is not demoted",
      rows3["Two (2026-08-31, 1회차)"]["cold"] is False)
os.unlink(tmp3)

if failures:
    print(f"\n{len(failures)} FAILED")
    sys.exit(1)
print("\nall passed")
