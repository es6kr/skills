"""Tests for scripts/check-hangul.py — the Hangul scanner used by CI.

These tests exercise the scanner via subprocess so we cover both the Python
implementation and the thin bash wrapper that CI invokes. We deliberately do
not import the module — it lives outside any package and the public contract
is the CLI behavior.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
PY_SCRIPT = REPO_ROOT / "scripts" / "check-hangul.py"
SH_WRAPPER = REPO_ROOT / "scripts" / "check-hangul.sh"

# Sample Hangul characters composed programmatically so this test file itself
# contains zero Korean, keeping the scanner clean on its own repo.
HANGUL_SAMPLE_1 = chr(0xAC00) + chr(0xB098)
HANGUL_SAMPLE_2 = chr(0xD55C) + chr(0xAE00)


def _run_py(args, cwd):
    return subprocess.run(
        [sys.executable, str(PY_SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def _run_sh(args, cwd):
    return subprocess.run(
        ["bash", str(SH_WRAPPER), *args],
        capture_output=True, text=True, cwd=cwd,
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


def test_default_argument_is_skills_dir():
    """No CLI args defaults to scanning ./skills relative to cwd."""
    result = _run_py([], cwd=REPO_ROOT)
    # Real repo skills/ tree should be clean (CI enforces this).
    assert result.returncode == 0
    assert "All skills clean" in result.stdout


def test_shell_wrapper_matches_python_output(skill_tree):
    """The bash wrapper must produce identical output to the Python script."""
    py = _run_py([str(skill_tree)], cwd=REPO_ROOT)
    sh = _run_sh([str(skill_tree)], cwd=REPO_ROOT)
    assert py.returncode == sh.returncode
    assert py.stdout == sh.stdout
