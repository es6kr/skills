"""Deployment validation tests for es6kr/skills — context7 + ClawHub focus.

Only tests git-tracked skills to avoid false failures from untracked local
skill folders. Uses UTF-8 encoding explicitly for cross-platform support.
"""
import json
import os
import pathlib
import re
import subprocess
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"


def _tracked_skill_dirs():
    """Return list of skill directory paths that are tracked by git."""
    result = subprocess.run(
        ["git", "ls-files", "--", "skills/*/SKILL.md"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    dirs = []
    for line in result.stdout.strip().splitlines():
        # line = "skills/chezmoi/SKILL.md"
        parts = line.split("/")
        if len(parts) >= 2:
            dirs.append(SKILLS_DIR / parts[1])
    return sorted(set(dirs))


def _read(path):
    """Read a file as UTF-8 (works on both Windows cp949 and Linux)."""
    return path.read_text(encoding="utf-8")


# --- context7 compatibility ---


def test_skills_dir_exists():
    """context7 indexes skills/ folder."""
    assert SKILLS_DIR.is_dir(), "skills/ directory must exist"


def test_each_skill_has_skill_md():
    """context7 indexing target: skills/*/SKILL.md"""
    for skill_dir in _tracked_skill_dirs():
        assert (skill_dir / "SKILL.md").exists(), f"{skill_dir.name}/ missing SKILL.md"


def test_skill_md_has_valid_frontmatter():
    """SKILL.md frontmatter must have name and description (context7 + ClawHub)."""
    for skill_dir in _tracked_skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        content = _read(skill_md)
        parts = content.split("---")
        assert len(parts) >= 3, f"{skill_md}: no frontmatter (--- delimiters)"
        fm = parts[1]
        assert re.search(r"^name:", fm, re.M), f"{skill_md}: missing name"
        assert re.search(r"^description:", fm, re.M), f"{skill_md}: missing description"


# --- ClawHub deployment ---


def test_no_clawhub_metadata_in_repo():
    """.clawhub/ should not be committed (auto-generated on publish)."""
    result = subprocess.run(
        ["git", "ls-files", "--", "skills/**/.clawhub"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert not result.stdout.strip(), f".clawhub/ found in tracked files"


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="LICENSE check skipped in CI")
def test_each_skill_has_license():
    """ClawHub publish requires LICENSE."""
    for skill_dir in _tracked_skill_dirs():
        assert (skill_dir / "LICENSE").exists(), f"{skill_dir.name}/ missing LICENSE"


def test_no_secrets():
    """No credentials or internal IPs in any tracked skill."""
    pattern = re.compile(r"(glpat-|sk-[a-zA-Z0-9]{20,}|10\.0\.0\.\d+|14\.36\.\d+)")
    result = subprocess.run(
        ["git", "ls-files", "--", "skills/*.md", "skills/**/*.md"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    for relpath in result.stdout.strip().splitlines():
        f = REPO_ROOT / relpath
        if f.exists():
            content = _read(f)
            match = pattern.search(content)
            assert not match, f"{f}: secret pattern '{match.group()}'"


def test_no_korean_in_frontmatter():
    """All skills frontmatter must be English."""
    hangul = re.compile("[가-힣]")
    for skill_dir in _tracked_skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        content = _read(skill_md)
        parts = content.split("---")
        if len(parts) >= 3:
            matches = hangul.findall(parts[1])
            assert not matches, f"{skill_md}: Korean in frontmatter"


# --- Claude Code Plugin (superpowers pattern) ---


def test_plugin_json_valid():
    """plugin.json exists and has required fields."""
    pj = REPO_ROOT / ".claude-plugin" / "plugin.json"
    assert pj.exists(), ".claude-plugin/plugin.json must exist"
    data = json.loads(_read(pj))
    for field in ("name", "description", "version", "author"):
        assert field in data, f"plugin.json missing '{field}'"


def test_marketplace_json_valid():
    """marketplace.json exists with source='./' (superpowers pattern)."""
    mj = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert mj.exists(), ".claude-plugin/marketplace.json must exist"
    data = json.loads(_read(mj))
    assert "plugins" in data
    assert data["plugins"][0]["source"] == "./", "source must be './' (single plugin)"


# --- Sync validation ---


def test_skill_names_match_directories():
    """SKILL.md name field must match directory name."""
    for skill_dir in _tracked_skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        content = _read(skill_md)
        parts = content.split("---")
        if len(parts) >= 3:
            name_match = re.search(r"^name:\s*(.+)$", parts[1], re.M)
            if name_match:
                skill_name = name_match.group(1).strip()
                dir_name = skill_md.parent.name
                assert skill_name == dir_name, (
                    f"{skill_md}: name '{skill_name}' != dir '{dir_name}'"
                )
