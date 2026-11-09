"""Keep the FA metadata suite in the owning CI step and propagate its failures.

The shell controls below execute the workflow's actual run block with synthetic
suite exit statuses. They do not substitute for running the real FA suite.
The existing pytest job discovers this module without another workflow step.
"""

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"
FA_SUITE = "skills/fa/scripts/test-fa-classify-meta.py"


def python_step():
    text = WORKFLOW.read_text(encoding="utf-8")
    blocks = re.findall(
        r"(?m)^      - name: Python tests\n        run: \|\n"
        r"((?:          [^\n]*(?:\n|$)|\n)+)",
        text,
    )
    if len(blocks) != 1:
        raise AssertionError("Expected exactly one owning Python tests run block")
    return textwrap.dedent(blocks[0]).rstrip() + "\n"


def suite_paths(script):
    loop = re.search(r"(?ms)^for t in (.*?); do$", script)
    if loop is None:
        raise AssertionError("Expected the explicit Python suite loop")
    return shlex.split(loop.group(1).replace("\\\n", " "))


def run_step_with_suite_status(fa_exit):
    bash = os.environ.get("FA_CI_TEST_BASH") or shutil.which("bash")
    if not bash:
        raise AssertionError("The owning Ubuntu CI workflow requires Bash")
    # Only suite commands are collaborators: execute the real Bash control flow.
    recorders = """python3() {
  printf 'FA_CI_CALL|python3|%s\\n' "$*"
  if [ "$1" = "skills/fa/scripts/test-fa-classify-meta.py" ]; then
    return "$FA_CI_TEST_CHILD_EXIT"
  fi
  return 0
}
bash() {
  printf 'FA_CI_CALL|bash|%s\\n' "$*"
  return 0
}
"""
    environment = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "TMPDIR")
        if key in os.environ
    }
    environment.update(
        FA_CI_TEST_CHILD_EXIT=str(fa_exit), BASH_ENV="", ENV=""
    )
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-e", "-s"],
        input=(recorders + python_step()).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
        env=environment,
        timeout=15,
        check=False,
    )
    calls = [
        tuple(line.split("|", 2)[1:])
        for line in result.stdout.decode("utf-8").splitlines()
        if line.startswith("FA_CI_CALL|")
    ]
    return result, calls


class TestFaCiEnrollment(unittest.TestCase):
    def test_fa_metadata_suite_is_enrolled_exactly_once(self):
        paths = suite_paths(python_step())
        self.assertEqual(paths.count(FA_SUITE), 1)
        self.assertTrue((REPO_ROOT / FA_SUITE).is_file())

    def test_successful_suites_keep_the_step_green(self):
        result, calls = run_step_with_suite_status(0)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertIn(
            ("python3", "skills/fix-plan/scripts/update_item.py --test"), calls
        )
        self.assertEqual(calls[-1], (
            "bash",
            "skills/hook-kit/resources/block-live-action-without-workflow-skill.sh --test",
        ))

    def test_failing_fa_suite_fails_the_step_without_skipping_later_tests(self):
        result, calls = run_step_with_suite_status(7)
        self.assertEqual(result.returncode, 1, result.stderr.decode("utf-8"))
        self.assertEqual(calls.count(("python3", FA_SUITE)), 1)
        self.assertLess(
            calls.index(("python3", FA_SUITE)),
            calls.index(("python3", "skills/fix-plan/scripts/update_item.py --test")),
        )
        self.assertEqual(calls[-1], (
            "bash",
            "skills/hook-kit/resources/block-live-action-without-workflow-skill.sh --test",
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
