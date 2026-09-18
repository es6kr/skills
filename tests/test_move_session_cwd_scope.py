"""Regression guard for move-session.py cwd rewriting scope.

Defect (observed 2026-09-11 while moving a real 2669-line session): the cwd
rewrite was a bare substring replace applied to any line that carried a `"cwd"`
field. A path fragment such as `/llm-wiki` or `skills/` therefore also vanished
from message bodies and recorded tool_use commands on those lines, silently
truncating transcript content. In `--cwd-mode first` the very first matching
line was often an unrelated one (its cwd pointed somewhere else entirely), so
the intended cwd was left alone while a body string got cut instead.

The rewrite is now scoped to the exact `"cwd":"<value>"` token, so these tests
assert both halves: the cwd field changes, and nothing else on the line does.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "session" / "scripts" / "move-session.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    if not SCRIPT.is_file():
        pytest.skip(f"{SCRIPT} not present")
    return _load("move_session_under_test", SCRIPT)


OLD = "/Users/u/ghq/github.com/org/repo/sub"
NEW = "/Users/u/ghq/github.com/org/repo"


def _line(cwd: str, body: str) -> str:
    """One JSONL record in the on-disk shape: compact separators, no spaces."""
    return json.dumps(
        {"cwd": cwd, "text": body}, ensure_ascii=False, separators=(",", ":")
    )


def test_body_text_mentioning_the_same_path_survives(mod):
    """The path also appears in the message body; only the cwd field may change."""
    body = f"ran: cd {OLD} && ls  # also see {OLD}/docs"
    content = _line(OLD, body)

    out, count = mod.replace_cwd(content, OLD, NEW, "all")

    assert count == 1
    record = json.loads(out)
    assert record["cwd"] == NEW
    assert record["text"] == body, "body text must be untouched"


def test_earlier_line_merely_mentioning_the_path_does_not_consume_first(mod):
    """`first` must rewrite the first matching *cwd*, not the first matching line.

    Line 1's cwd points elsewhere; the path only appears inside its body. The
    substring-based implementation spent its single replacement there, leaving
    the real target untouched and the body truncated -- exactly what happened
    on lines 9 and 26 of the session that exposed this.
    """
    other = "/Users/u/elsewhere/tooling/data"
    mention = f"earlier turn ran: cd {OLD}"
    content = "\n".join([_line(other, mention), _line(OLD, "target line")])

    out, count = mod.replace_cwd(content, OLD, NEW, "first")

    assert count == 1
    first, second = [json.loads(x) for x in out.split("\n")]
    assert first["cwd"] == other, "unrelated cwd must be left alone"
    assert first["text"] == mention, "unrelated body must be left alone"
    assert second["cwd"] == NEW, "the real target must be the one rewritten"


def test_first_stops_after_one_and_all_rewrites_every_occurrence(mod):
    content = "\n".join(_line(OLD, f"line {i}") for i in range(3))

    out_first, n_first = mod.replace_cwd(content, OLD, NEW, "first")
    out_all, n_all = mod.replace_cwd(content, OLD, NEW, "all")

    assert n_first == 1
    assert [json.loads(x)["cwd"] for x in out_first.split("\n")] == [NEW, OLD, OLD]
    assert n_all == 3
    assert [json.loads(x)["cwd"] for x in out_all.split("\n")] == [NEW] * 3


def test_windows_encoded_cwd_is_rewritten_without_touching_the_body(mod):
    """Windows paths are stored double-escaped in the JSON text."""
    win_old = "C:\\\\Users\\\\u\\\\ghq\\\\org\\\\repo\\\\sub"
    win_new = "C:\\\\Users\\\\u\\\\ghq\\\\org\\\\repo"
    body_fragment = "cd C:\\\\Users\\\\u\\\\ghq\\\\org\\\\repo\\\\sub"
    content = '{"cwd":"%s","text":"%s"}' % (win_old, body_fragment)

    out, count = mod.replace_cwd(content, win_old, win_new, "all")

    assert count == 1
    record = json.loads(out)
    assert record["cwd"] == "C:\\Users\\u\\ghq\\org\\repo"
    assert record["text"] == "cd C:\\Users\\u\\ghq\\org\\repo\\sub"


def test_noop_when_value_is_already_the_target(mod):
    content = _line(NEW, "already correct")
    out, count = mod.replace_cwd(content, NEW, NEW, "all")
    assert (out, count) == (content, 0)


def test_absent_value_reports_zero(mod):
    content = _line(NEW, "no match here")
    out, count = mod.replace_cwd(content, OLD, NEW, "all")
    assert (out, count) == (content, 0)
