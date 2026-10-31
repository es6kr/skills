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

EXPECTED_ALLOWED_TOOLS = {'backlog': ['Read', 'Edit', 'Write', 'Grep', 'Bash(gh:*)', 'Bash(python3:*)'],
 'claudify': ['Read', 'Write', 'Edit', 'Glob', 'Skill', 'Bash(mkdir:*)'],
 'consolidate': ['Agent', 'AskUserQuestion', 'Bash', 'Edit', 'Glob', 'Grep', 'Read', 'Write'],
 'fix-plan': ['Read', 'Edit', 'Write', 'Grep', 'Bash(gh:*)', 'Bash(mv:*)', 'Bash(mkdir:*)'],
 'github-repo': ['Read',
                 'Edit',
                 'Write',
                 'Bash(gh:*)',
                 'Bash(git:*)',
                 'Bash(ls:*)',
                 'Bash(mkdir:*)'],
 'hook-kit': ['Read',
              'Edit',
              'Grep',
              'Bash(cp:*)',
              'Bash(diff:*)',
              'Bash(ls:*)',
              'Bash(mkdir:*)',
              'Bash(mv:*)',
              'Bash(bash -n:*)',
              'Bash(jq:*)',
              'Bash(chmod:*)',
              'Bash(test:*)',
              'Bash(find:*)',
              'AskUserQuestion']}

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

    def test_doctor_rejects_unwired_fallback_hooks(self):
        self.repository()
        self.assertEqual(self.command([self.git, "config", "core.hooksPath", ".git/hooks"]).returncode, 0)
        self.assertIn("FAIL", self.doctor_row())

    def test_doctor_rejects_missing_repository_linter(self):
        self.repository()
        (self.root / "skills/skill-kit/scripts/skillspector_lint.py").unlink()
        self.assertIn("FAIL", self.doctor_row())

    def test_doctor_rejects_drifted_repository_linter(self):
        self.repository()
        (self.root / "skills/skill-kit/scripts/skillspector_lint.py").write_text("# not the canonical linter\n", encoding="utf-8")
        self.assertIn("FAIL", self.doctor_row())


    def skill_with_tools(self, scalar):
        path = self.skill()
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("\n---\n", f"\nallowed-tools: {scalar}\n---\n", 1),
                        encoding="utf-8")
        return path

    def test_metadata_mode_rejects_nonstring_allowed_tools(self):
        for scalar in ['[Read, "Bash(gh pr:*)"]', "[]", "null", "true", "42", "{Read: true}"]:
            with self.subTest(scalar=scalar):
                result = MODULE.SkillSpector().scan_skill(
                    str(self.skill_with_tools(scalar)), metadata_only=True)
                self.assertFalse(result["valid"], result)
                self.assertTrue(any("allowed-tools must be a string" in error
                                    for error in result["errors"]), result)

    def test_metadata_mode_accepts_optional_string_allowed_tools(self):
        self.assertTrue(MODULE.SkillSpector().scan_skill(
            str(self.skill()), metadata_only=True)["valid"])
        for value in ["", "Read", "Read Bash(gh pr:*) Bash(bash -n:*)"]:
            with self.subTest(value=value):
                result = MODULE.SkillSpector().scan_skill(
                    str(self.skill_with_tools(json.dumps(value))), metadata_only=True)
                self.assertTrue(result["valid"], result)

    def test_full_scan_keeps_legacy_list_allowed_tools(self):
        result = MODULE.SkillSpector().scan_skill(str(self.skill_with_tools('[Read, Grep]')))
        self.assertTrue(result["valid"], result)

    def test_json_and_text_reject_array_allowed_tools_in_metadata_mode(self):
        path = self.skill_with_tools('[Read, "Bash(gh pr:*)"]')
        result = self.cli("--frontmatter-only", "--json", path)
        rows = json.loads(result.stdout)
        self.assertEqual(len(rows), 1, rows)
        self.assertFalse(rows[0]["valid"], rows)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        result = self.cli("--frontmatter-only", path)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("allowed-tools must be a string", result.stdout)

    def test_wrapper_rejects_array_allowed_tools(self):
        self.repository()
        self.skill_with_tools('[Read, Grep]')
        result = self.command([self.bash, self.root / "scripts/lint-frontmatter.sh"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("allowed-tools must be a string", result.stdout)

    def test_doctor_rejects_array_allowed_tools(self):
        self.repository()
        self.skill_with_tools('[Read, Grep]')
        self.assertIn("FAIL", self.doctor_row())

    def test_repository_allowed_tools_preserve_all_declared_entries(self):
        for slug, expected in EXPECTED_ALLOWED_TOOLS.items():
            with self.subTest(skill=slug):
                path = ROOT / "skills" / slug / "SKILL.md"
                metadata, _ = MODULE.SkillSpector()._parse_frontmatter(path.read_text(encoding="utf-8"))
                self.assertIsNotNone(metadata)
                self.assertIsInstance(metadata["allowed-tools"], str)
                self.assertEqual(metadata["allowed-tools"], " ".join(expected))

if __name__ == "__main__":
    unittest.main()
