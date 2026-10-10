"""Bounded hook regressions; payload commands are data, never executed."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "skills/hook-kit/resources"


class CommandGuards(unittest.TestCase):
    def setUp(self):
        self.fixture_env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.clean = self.repo("clean", "clean")
        self.dirty = self.repo("dirty space", "fix\n\n± Conflicts:\n± file")

    def repo(self, name, message):
        path = self.base / name
        path.mkdir()
        for args in (["init", "-q"], ["config", "user.name", "Test"],
                     ["config", "user.email", "test@example.invalid"],
                     ["-c", "core.hooksPath=/dev/null", "commit", "-q", "--allow-empty", "-m", message]):
            subprocess.run(["git", "-C", str(path), *args], env=self.fixture_env, check=True, capture_output=True)
        return path

    def rebase(self, command, cwd=None):
        return subprocess.run(["bash", str(RESOURCES / "check-rebase-conflict-residue.sh")],
                              input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
                              text=True, capture_output=True, cwd=cwd or self.clean, env=self.fixture_env)

    def test_effective_rebase_repository(self):
        q = shlex.quote(str(self.dirty))
        git_path = shutil.which("git")
        assert git_path is not None
        git = shlex.quote(git_path)
        for command in (f"git -C {q} rebase --continue",
                        f"git -c core.editor=true -C {q} --no-pager rebase --continue",
                        f"GIT_EDITOR=true {git} -C {q} rebase --continue",
                        f"env GIT_EDITOR=true git -C {q} rebase --continue",
                        f"cd {q} && git rebase --continue"):
            with self.subTest(command=command):
                self.assertEqual(self.rebase(command).returncode, 2)

    def test_only_effective_repo_is_inspected(self):
        self.assertEqual(self.rebase(f"cd {shlex.quote(str(self.clean))} && git rebase --continue", self.dirty).returncode, 0)
        self.assertEqual(self.rebase(f"git -C {shlex.quote(str(self.clean))} rebase --continue", self.dirty).returncode, 0)

    def test_unresolved_cd_does_not_inspect_hook_repository(self):
        for command in ("cd missing-directory && git rebase --continue",
                        'cd "$UNKNOWN_REPO" && git rebase --continue'):
            with self.subTest(command=command):
                self.assertEqual(self.rebase(command, self.dirty).returncode, 0)

    def test_mentions_and_payload_side_effects_are_not_executed(self):
        marker = self.base / "must-not-exist"
        for command in ('echo "git rebase --continue"', 'printf "%s" "git -C nowhere rebase --continue"',
                        "echo ';' 'git rebase --continue'", "'git rebase --continue'", 'echo "x; git rebase --continue"'):
            with self.subTest(command=command):
                self.assertEqual(self.rebase(command, self.dirty).returncode, 0)
        self.rebase(f"touch {shlex.quote(str(marker))} && git rebase --continue")
        self.assertFalse(marker.exists())

    def slash(self, requested, evidence):
        home = self.base / "home"
        (home / ".agents/skills/task-flow").mkdir(parents=True, exist_ok=True)
        transcript = self.base / "transcript.jsonl"
        rows = [{"type": "user", "message": {"content": f"<command-name>/{requested}</command-name>"}}, evidence]
        transcript.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        result = subprocess.run(["bash", str(RESOURCES / "check-slash-command-skill-invoked.sh")],
                                input=json.dumps({"transcript_path": str(transcript)}), text=True,
                                capture_output=True, env={**os.environ, "HOME": str(home), "RALPH_LOOP": "0"})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout).get("decision") if result.stdout.strip() else "allow"

    def test_explicitly_different_namespace_does_not_satisfy_command(self):
        self.assertEqual(self.slash("alpha:task-flow", self.call("beta:task-flow")), "block")

    def test_only_actual_assistant_skill_tool_use_counts(self):
        for evidence in (self.call("task-flow", name="Other"),
                         self.call("task-flow", kind="text"),
                         {"type": "user", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "task-flow"}}]}},
                         {"type": "assistant", "message": {"content": [{"type": "text", "text": 'Skill("task-flow")'}]}}):
            with self.subTest(evidence=evidence):
                self.assertEqual(self.slash("task-flow", evidence), "block")

    def test_bare_and_namespace_compatibility(self):
        for requested, invoked in (("task-flow", "task-flow"), ("alpha:task-flow", "alpha:task-flow"),
                                   ("alpha:task-flow", "task-flow"), ("task-flow", "beta:task-flow")):
            with self.subTest(requested=requested, invoked=invoked):
                self.assertEqual(self.slash(requested, self.call(invoked)), "allow")

    @staticmethod
    def call(skill, name="Skill", kind="tool_use"):
        return {"type": "assistant", "message": {"content": [{"type": kind, "name": name, "input": {"skill": skill}}]}}


def test_fixture_without_tmpdir(monkeypatch, tmp_path):
    monkeypatch.delenv('TMPDIR', raising=False)
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    case = CommandGuards()
    try:
        case.setUp()
        assert case.clean.is_dir() and case.dirty.is_dir()
    finally:
        case.doCleanups()


if __name__ == "__main__":
    unittest.main()
