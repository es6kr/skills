"""Unit tests for bash-guard heredoc handling and Python 3.9 compatibility (PR #556 review fixes).

Covers:
- Copilot #1 & CodeRabbit #7: Heredoc execution (bash <<EOF) and unquoted command substitutions ($(cmd)) must not bypass SIMPLE_BLOCKS.
- Copilot #6: from __future__ import annotations must not shadow the module docstring.
- Copilot #4: strip_heredoc_bodies delimiter regex must recognize escaped (\\EOF) and hyphenated (END-JSON) delimiters.
- Copilot #2: edit-guard.sh git environment isolation must include -u GIT_COMMON_DIR.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
BASH_GUARD_PATH = REPO_ROOT / "skills" / "hook-kit" / "resources" / "bash-guard.py"
EDIT_GUARD_PATH = REPO_ROOT / "skills" / "hook-kit" / "resources" / "edit-guard.sh"


class TestBashGuardReviewFindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("bash_guard", BASH_GUARD_PATH)
        assert spec is not None and spec.loader is not None
        cls.bash_guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.bash_guard)

    def test_bash_guard_docstring_preserved(self):
        """Copilot #6: __doc__ must not be None after from __future__ import annotations."""
        self.assertIsNotNone(self.bash_guard.__doc__)
        self.assertIn("bash-guard.py", self.bash_guard.__doc__)

    def test_heredoc_fed_to_interpreter_is_blocked(self):
        """CodeRabbit #7: heredocs fed to interpreters (bash/sh/pipeline) must be evaluated by SIMPLE_BLOCKS."""
        cmd1 = "bash <<'EOF'\ndocker rm my-container\nEOF"
        code1, _, _ = self.bash_guard.evaluate(cmd1, False)
        self.assertIn(code1, (1, 2), "bash <<'EOF' with docker rm must be blocked")

        cmd2 = "cat <<'EOF' | bash\ndocker rm my-container\nEOF"
        code2, _, _ = self.bash_guard.evaluate(cmd2, False)
        self.assertIn(code2, (1, 2), "pipeline to bash with docker rm must be blocked")

    def test_unquoted_heredoc_command_substitution_is_blocked(self):
        """Copilot #1: unquoted heredocs with $(...) or `...` command substitution must be evaluated."""
        cmd = "cat <<EOF\n$(docker rm my-container)\nEOF"
        code, _, _ = self.bash_guard.evaluate(cmd, False)
        self.assertIn(code, (1, 2), "cat <<EOF with unquoted $(docker rm) command substitution must be blocked")

    def test_inert_heredoc_delimiters_allowed(self):
        """Copilot #4: strip_heredoc_bodies must support \\EOF and hyphenated delimiters like END-JSON."""
        cmd_escaped = "cat <<\\EOF\nterraform apply -auto-approve\nEOF"
        code_esc, _, _ = self.bash_guard.evaluate(cmd_escaped, False)
        self.assertEqual(code_esc, 0, "cat <<\\EOF inert prose must be allowed")

        cmd_hyphen = "cat <<END-JSON\nterraform apply -auto-approve\nEND-JSON"
        code_hyphen, _, _ = self.bash_guard.evaluate(cmd_hyphen, False)
        self.assertEqual(code_hyphen, 0, "cat <<END-JSON inert prose must be allowed")

    def test_edit_guard_unsets_git_common_dir(self):
        """Copilot #2: check_main_checkout_edit_es6kr_skills must unset GIT_COMMON_DIR."""
        content = EDIT_GUARD_PATH.read_text(encoding="utf-8")
        self.assertIn("-u GIT_COMMON_DIR", content, "edit-guard.sh must unset GIT_COMMON_DIR in git invocations")


if __name__ == "__main__":
    unittest.main()
