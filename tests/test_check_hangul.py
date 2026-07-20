"""Tests for scripts/check-hangul.py — the Hangul scanner used by CI.

These tests exercise the scanner via subprocess (the public contract is the
CLI behavior). We deliberately do not import the module — it lives outside any
package.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
PY_SCRIPT = REPO_ROOT / "scripts" / "check-hangul.py"

# Sample Hangul characters composed programmatically so this test file itself
# contains zero Korean, keeping the scanner clean on its own repo.
HANGUL_SAMPLE_1 = chr(0xAC00) + chr(0xB098)
HANGUL_SAMPLE_2 = chr(0xD55C) + chr(0xAE00)


def _no_git_env():
    """Environment with every GIT_* variable dropped.

    Under a git hook (pre-push runs this suite), git exports GIT_DIR pointing
    at the invoking repository. Without scrubbing, the fixtures' git calls and
    the scanner's internal `git ls-files` ignore cwd=tmp_path and operate on
    the REAL repo — the fixture's `git commit` then lands a stray commit on
    the branch being pushed.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _run_py(args, cwd):
    return subprocess.run(
        [sys.executable, str(PY_SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=cwd,
        env=_no_git_env(),
    )


@pytest.fixture
def skill_tree(tmp_path):
    """Build a parent dir with one clean skill and one Hangul-containing skill."""
    clean = tmp_path / "skill-clean"
    clean.mkdir()
    (clean / "SKILL.md").write_text("# clean\nAll english.\n", encoding="utf-8")

    dirty = tmp_path / "skill-with-hangul"
    dirty.mkdir()
    (dirty / "SKILL.md").write_text(
        f"# dirty\nKorean line one: {HANGUL_SAMPLE_1}\nAnd two: {HANGUL_SAMPLE_2}\n",
        encoding="utf-8",
    )
    # A .sh file to confirm both extensions are scanned.
    (dirty / "helper.sh").write_text(
        f"#!/bin/sh\necho {HANGUL_SAMPLE_1}\n", encoding="utf-8"
    )
    return tmp_path


def test_parent_mode_reports_each_subdir(skill_tree):
    """Single-arg parent mode expands to immediate subdirectories."""
    result = _run_py([str(skill_tree)], cwd=REPO_ROOT)
    assert result.returncode == 1, result.stderr
    assert "skill-clean" in result.stdout
    assert "clean" in result.stdout
    assert "skill-with-hangul" in result.stdout
    assert "3 Korean lines found" in result.stdout  # 2 in SKILL.md + 1 in helper.sh
    assert "BLOCKED" in result.stdout


def test_parent_mode_all_clean_returns_zero(tmp_path):
    """All-clean parent tree exits 0."""
    skill = tmp_path / "ok"
    skill.mkdir()
    (skill / "SKILL.md").write_text("english only\n", encoding="utf-8")
    result = _run_py([str(tmp_path)], cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "All skills clean" in result.stdout


def test_parent_mode_empty_dir_exits_zero(tmp_path):
    """Empty parent dir prints a message and exits 0 (matches bash original)."""
    result = _run_py([str(tmp_path)], cwd=REPO_ROOT)
    assert result.returncode == 0
    assert "No skill subdirs found" in result.stdout


def test_explicit_mode_single_skill(skill_tree):
    """Passing a single skill dir (with SKILL.md) uses explicit mode."""
    dirty = skill_tree / "skill-with-hangul"
    result = _run_py([str(dirty)], cwd=REPO_ROOT)
    assert result.returncode == 1
    assert "skill-with-hangul" in result.stdout
    assert "3 Korean lines found" in result.stdout


def test_explicit_mode_multiple_dirs(skill_tree):
    """Passing multiple dirs scans each as an explicit skill."""
    clean = skill_tree / "skill-clean"
    dirty = skill_tree / "skill-with-hangul"
    result = _run_py([str(clean), str(dirty)], cwd=REPO_ROOT)
    assert result.returncode == 1
    assert "skill-clean — clean" in result.stdout
    assert "skill-with-hangul — 3 Korean lines found" in result.stdout


def test_nonexistent_dir_exits_one(tmp_path):
    """Non-directory argument is an error (matches bash original)."""
    missing = tmp_path / "does-not-exist"
    result = _run_py([str(missing)], cwd=REPO_ROOT)
    assert result.returncode == 1
    assert "Not a directory" in result.stdout


def test_only_md_and_sh_scanned(tmp_path):
    """Files outside .md/.sh extensions are ignored."""
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("english\n", encoding="utf-8")
    (skill / "notes.txt").write_text(f"Korean here: {HANGUL_SAMPLE_1}\n", encoding="utf-8")
    (skill / "data.json").write_text(f'{{"k": "{HANGUL_SAMPLE_1}"}}\n', encoding="utf-8")
    result = _run_py([str(skill)], cwd=REPO_ROOT)
    assert result.returncode == 0
    assert "clean" in result.stdout


def test_nested_md_files_are_scanned(tmp_path):
    """Subdirectory .md files are caught (os.walk recursion)."""
    skill = tmp_path / "skill"
    nested = skill / "topics"
    nested.mkdir(parents=True)
    (skill / "SKILL.md").write_text("english\n", encoding="utf-8")
    (nested / "guide.md").write_text(f"Buried Korean: {HANGUL_SAMPLE_2}\n", encoding="utf-8")
    result = _run_py([str(skill)], cwd=REPO_ROOT)
    assert result.returncode == 1
    assert "1 Korean lines found" in result.stdout


def test_default_argument_is_skills_dir(tmp_path):
    """No CLI args defaults to scanning ./skills relative to cwd.

    Hermetic: builds its own ./skills fixture instead of asserting on the real
    repo tree — a local working branch may legitimately carry Korean content
    (locale data, private topics), and a test that scans the live checkout
    blocks every push from such a machine via the pre-push CI-parity gate.
    """
    dirty = tmp_path / "skills" / "skill-with-hangul"
    dirty.mkdir(parents=True)
    (dirty / "SKILL.md").write_text(
        f"# dirty\nKorean: {HANGUL_SAMPLE_1}\n", encoding="utf-8"
    )
    result = _run_py([], cwd=tmp_path)
    # Detecting the planted Korean proves ./skills was scanned by default.
    assert result.returncode == 1, result.stderr
    assert "skill-with-hangul" in result.stdout


def test_untracked_and_ignored_files_skipped_in_git_repo(tmp_path):
    """Inside a git repo, only tracked files are publish material: untracked
    working files and gitignored locale data (a skill's data/ dir) must not
    trip the gate. Outside a repo the scanner falls back to scanning all."""
    repo = tmp_path
    skills = repo / "skills"
    skill = skills / "myskill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("english only\n", encoding="utf-8")
    (skill / ".gitignore").write_text("data/\n", encoding="utf-8")
    data = skill / "data"
    data.mkdir()
    (data / "locale.md").write_text(f"ignored Korean: {HANGUL_SAMPLE_1}\n", encoding="utf-8")
    (skill / "draft.md").write_text(f"untracked Korean: {HANGUL_SAMPLE_2}\n", encoding="utf-8")

    def _git(*args):
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8",
            env=_no_git_env(),
        )

    if _git("init", "-q").returncode != 0:
        pytest.skip("git unavailable")
    _git("config", "user.email", "t@t")
    _git("config", "user.name", "t")
    _git("add", "skills/myskill/SKILL.md", "skills/myskill/.gitignore")
    _git("commit", "-q", "-m", "baseline")

    result = _run_py(["skills"], cwd=repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "clean" in result.stdout


def test_scanner_ignores_poisoned_grep(tmp_path):
    """Regression: the scanner must NOT depend on the ambient ``grep``.

    The original bash implementation shelled out to ``grep -rP``, so a
    ugrep-as-grep wrapper (or any grep that reports "no match") produced false
    negatives — Korean text shipped to GitHub uncaught. The Python rewrite reads
    files directly. Prepend a ``grep`` that always exits 1 ("no match") and
    confirm Korean is still detected. If a future refactor reintroduces a grep
    dependency, this test flips to a false-clean and fails.
    """
    tree = tmp_path / "tree"
    dirty = tree / "skill-with-hangul"
    dirty.mkdir(parents=True)
    (dirty / "SKILL.md").write_text(f"# x\nKorean: {HANGUL_SAMPLE_1}\n", encoding="utf-8")

    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    fake_grep = fake_bin / "grep"
    fake_grep.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")  # always "no match"
    fake_grep.chmod(0o755)

    env = dict(os.environ, PATH=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT), str(tree)],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, env=env,
    )
    assert result.returncode == 1, result.stderr
    assert "skill-with-hangul" in result.stdout
    assert "BLOCKED" in result.stdout


def test_max_matches_env_limits_printed_lines(tmp_path):
    """MAX_MATCHES caps the matched lines printed per skill; the header count
    (total Korean lines) is unaffected."""
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "".join(f"Korean {HANGUL_SAMPLE_1} line {i}\n" for i in range(4)),
        encoding="utf-8",
    )
    env = dict(os.environ, MAX_MATCHES="1")
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT), str(skill)],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, env=env,
    )
    assert result.returncode == 1
    assert "4 Korean lines found" in result.stdout  # header counts all matches
    printed = [ln for ln in result.stdout.splitlines() if "SKILL.md:" in ln]
    assert len(printed) == 1  # but only MAX_MATCHES=1 line is printed
