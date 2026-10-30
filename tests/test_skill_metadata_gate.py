"""Regression tests for decoded skill metadata and mandatory repository lint."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/skill-kit/scripts/skillspector_lint.py"
WRAPPER = ROOT / "scripts/lint-frontmatter.sh"
DOCTOR = ROOT / "skills/git-repo/scripts/git-repo-doctor.sh"
SPEC = importlib.util.spec_from_file_location("metadata_gate_spector", CLI)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class MetadataGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-metadata-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        for key in list(self.env):
            if key.startswith("GIT_"):
                self.env.pop(key)
        self.env.update(PYTHONUTF8="1", PYTHON=Path(sys.executable).as_posix())
        self.bash = shutil.which("bash")
        self.git = shutil.which("git")
        self.assertIsNotNone(self.bash)
        self.assertIsNotNone(self.git)

    def command(self, argv):
        return subprocess.run(list(map(str, argv)), cwd=self.root, env=self.env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=40)

    def skill(self, relative="skills/example/SKILL.md", scalar='"A valid description."'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\nname: example\nmetadata:\n  version: "0.1.0"\n'
                        f'description: {scalar}\n---\n# Example\n', encoding="utf-8")
        return path

    def scan(self, scalar):
        return MODULE.SkillSpector().scan_skill(str(self.skill(scalar=scalar)))

    def cli(self, *args):
        return self.command([sys.executable, CLI, *args])

    def repository(self, scalar='"A valid description."'):
        self.assertEqual(self.command([self.git, "init", "--quiet"]).returncode, 0)
        self.command([self.git, "config", "core.hooksPath", ".githooks"])
        self.skill(scalar=scalar)
        self.skill("skills/skill-kit/SKILL.md")
        helper = self.root / "skills/skill-kit/scripts/skillspector_lint.py"
        helper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CLI, helper)
        wrapper = self.root / "scripts/lint-frontmatter.sh"
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WRAPPER, wrapper)
        hooks = self.root / ".githooks"
        hooks.mkdir()
        (hooks / "pre-push").write_text("#!/usr/bin/env bash\nset -eu\nbash scripts/lint-frontmatter.sh\n", encoding="utf-8")
        workflow = self.root / ".github/workflows/test.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: Test\non: [push]\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
                            "    steps:\n      - run: bash scripts/lint-frontmatter.sh\n", encoding="utf-8")
        self.assertEqual(self.command([self.git, "add", "."]).returncode, 0)

    def doctor_row(self):
        result = self.command([self.bash, DOCTOR, self.root])
        text = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        rows = [line for line in text.splitlines() if line.startswith("COND-SKILL")]
        self.assertEqual(len(rows), 1, result.stdout + result.stderr)
        return rows[0]

    def test_boundary_and_unicode_count_decoded_characters(self):
        for value, valid in [("x"*1024, True), ("x"*1025, False), ("\U0001f680"*1024, True)]:
            with self.subTest(length=len(value), valid=valid):
                result = self.scan(json.dumps(value, ensure_ascii=False))
                self.assertEqual(result["valid"], valid, result)

    def test_yaml_escaped_unicode_is_not_source_spelling(self):
        self.assertTrue(self.scan('"' + "\\u0061"*1024 + '"')["valid"])

    def test_block_clipping_newline_counts_toward_budget(self):
        self.assertTrue(self.scan("|-\n  " + "x"*1024)["valid"])
        self.assertFalse(self.scan("|\n  " + "x"*1024)["valid"])

    def test_quoted_separator_is_not_frontmatter_boundary(self):
        path = self.skill(scalar='"literal --- separator"')
        parsed, _ = MODULE.SkillSpector()._parse_frontmatter(path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["description"], "literal --- separator")

    def test_nonstring_blank_and_malformed_descriptions_fail(self):
        for scalar in ["null", "true", "123", "[]", '"   "', '"unterminated']:
            with self.subTest(scalar=scalar):
                self.assertFalse(self.scan(scalar)["valid"])

    def test_missing_description_is_error(self):
        path = self.skill()
        path.write_text('---\nname: example\n---\nBody\n', encoding="utf-8")
        self.assertFalse(MODULE.SkillSpector().scan_skill(str(path))["valid"])

    def test_json_and_text_both_fail_invalid_metadata(self):
        path = self.skill(scalar='"' + "x"*1025 + '"')
        result = self.cli("--json", path)
        self.assertFalse(json.loads(result.stdout)[0]["valid"])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.cli(path).returncode, 1)

    def test_root_skill_does_not_hide_nested_plugin(self):
        self.skill("SKILL.md")
        self.skill("plugins/nested/skills/example/SKILL.md", '"' + "x"*1025 + '"')
        result = self.cli("--json", self.root)
        self.assertEqual(len(json.loads(result.stdout)), 2)
        self.assertEqual(result.returncode, 1)

    def test_discovery_deduplicates_overlapping_arguments(self):
        path = self.skill()
        result = self.cli("--json", self.root, path)
        self.assertEqual(len(json.loads(result.stdout)), 1)
        self.assertEqual(result.returncode, 0)

    def test_discovery_excludes_worktrees_and_backups(self):
        self.skill()
        for excluded in [".worktrees/old", "worktrees/old", ".workspaces/old", "example.bak", "node_modules/pkg"]:
            self.skill(excluded + "/SKILL.md", '"' + "x"*1025 + '"')
        result = self.cli("--json", self.root)
        self.assertEqual(len(json.loads(result.stdout)), 1)
        self.assertEqual(result.returncode, 0)

    def test_wrapper_rejects_nested_plugin_overflow(self):
        self.repository()
        self.skill("plugins/nested/skills/example/SKILL.md", '"' + "x"*1025 + '"')
        self.assertEqual(self.command([self.git, "add", "."]).returncode, 0)
        result = self.command([self.bash, self.root / "scripts/lint-frontmatter.sh"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("1024", result.stdout + result.stderr)

    def test_wrapper_ignores_untracked_local_skill(self):
        self.repository()
        self.skill("skills/private/SKILL.md", '"' + "x"*1025 + '"')
        result = self.command([self.bash, self.root / "scripts/lint-frontmatter.sh"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wrapper_preserves_quoted_semver_requirement(self):
        self.repository()
        path = self.root / "skills/example/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace('version: "0.1.0"', "version: 0.1.0"), encoding="utf-8")
        result = self.command([self.bash, self.root / "scripts/lint-frontmatter.sh"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_doctor_executes_lint_not_just_hook_name(self):
        self.repository('"' + "x"*1025 + '"')
        self.assertIn("FAIL", self.doctor_row())

    def test_doctor_requires_ci_wiring(self):
        self.repository()
        (self.root / ".github/workflows/test.yml").write_text("# bash scripts/lint-frontmatter.sh\nname: Test\njobs: {}\n", encoding="utf-8")
        self.assertIn("FAIL", self.doctor_row())

    def test_doctor_rejects_comment_and_echo_only_hook(self):
        self.repository()
        (self.root / ".githooks/pre-push").write_text('#!/bin/sh\n# bash scripts/lint-frontmatter.sh\necho "lint-frontmatter.sh"\n', encoding="utf-8")
        self.assertIn("FAIL", self.doctor_row())

    def test_doctor_rejects_missing_wrapper(self):
        self.repository()
        (self.root / "scripts/lint-frontmatter.sh").unlink()
        self.assertIn("FAIL", self.doctor_row())

    def test_doctor_rejects_version_only_wrapper(self):
        self.repository()
        (self.root / "scripts/lint-frontmatter.sh").write_text('#!/bin/sh\necho "version 0.1.0"\nexit 0\n', encoding="utf-8")
        self.assertIn("FAIL", self.doctor_row())

    def test_doctor_accepts_wired_valid_metadata(self):
        self.repository()
        self.assertIn("PASS", self.doctor_row())

if __name__ == "__main__":
    unittest.main()
