"""PR623 regressions: payloads are data; no Orca command is executed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def question(text, *options):
    return {"question": text, "options": [{"label": o} for o in options]}


class OrcaPendingTests(unittest.TestCase):
    def hook(self, name, payload):
        result = subprocess.run(
            ["bash", str(ROOT / "resources" / name)],
            input=json.dumps(payload), text=True, capture_output=True,
            env={**os.environ, "ORCA_CLI_COMMAND": ""},
        )
        self.assertIn(result.returncode, (0, 2), result.stderr)
        return result.returncode

    def ask(self, *questions):
        return self.hook("block-orca-ask-without-split-option.sh", {
            "tool_name": "AskUserQuestion", "tool_input": {"questions": questions},
        })

    def test_split_option_cannot_be_borrowed_from_another_question(self):
        self.assertEqual(2, self.ask(
            question("Launch an Orca session?", "New tab", "Hold"),
            question("How should a CSV be parsed?", "Split on commas"),
        ))

    def test_unrelated_orca_name_is_not_a_launch(self):
        for text in ("Rename the Orca project?", "What should we name the Orca workspace?",
                     "Rename the Orca session?", "Publish the Orca session summary to the wiki?"):
            with self.subTest(text=text):
                self.assertEqual(0, self.ask(question(text, "Alpha", "Beta")))

    def test_exception_cannot_be_borrowed_from_another_question(self):
        self.assertEqual(2, self.ask(
            question("Launch an Orca session?", "New tab"),
            question("The other tab has 4 panes", "Hold"),
        ))
    def test_negated_split_is_not_an_option(self):
        for option in ("Do not split", "No split", "Without splitting the pane",
                       "Skip the split", "Split unavailable", "Do not add a pane",
                       "Do not split; create a new tab"):
            with self.subTest(option=option):
                self.assertEqual(2, self.ask(question(
                    "Launch an Orca session?", option, "New tab")))

    def test_affirmative_split_alternatives_remain_allowed(self):
        for option in ("Split the current tab", "Add a pane", "Split, not a new tab",
                       "Do not create a tab; split the current tab",
                       "No new tab, split instead", "Vertical split"):
            with self.subTest(option=option):
                self.assertEqual(0, self.ask(question("Launch an Orca session?", option)))

    def test_documented_exceptions_remain_allowed(self):
        for exception in ("4 panes", "ORCA_PANE_LIMIT_REACHED",
                          "ORCA_NEW_WORKSPACE_APPROVED", "ORCA_FILE_CONFLICT"):
            with self.subTest(exception=exception):
                self.assertEqual(0, self.ask(question(
                    "Launch an Orca session? " + exception, "New tab")))
    def split(self, command, transcript=True):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transcript.jsonl"
            path.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
            payload = {"tool_name": "Bash", "tool_input": {"command": command}}
            if transcript:
                payload["transcript_path"] = str(path)
            return self.hook("block-orca-split-without-ask.sh", payload)

    def test_approval_must_be_on_each_guarded_command(self):
        for command in (
            "printf ORCA_ASK_CONFIRMED=1; orca terminal split",
            "ORCA_ASK_CONFIRMED=1 true; orca repo add /repo",
            "orca terminal split; ORCA_ASK_CONFIRMED=1 orca repo add /repo",
            "ORCA_ASK_CONFIRMED=1 orca terminal split; orca repo add /repo",
            "orca terminal split --title ORCA_ASK_CONFIRMED=1",
            "ORCA_ASK_CONFIRMED=10 orca terminal split",
        ):
            with self.subTest(command=command):
                self.assertEqual(2, self.split(command))

    def test_prefixed_and_absolute_commands_are_guarded(self):
        for command in ("  orca terminal split", "FOO=bar orca repo add /repo",
                        "/opt/bin/orca-ide terminal split", "  FOO=bar /opt/bin/orca-dev repo add /repo",
                        "true\n  orca terminal split"):
            with self.subTest(command=command):
                self.assertEqual(2, self.split(command))

    def test_bound_approval_and_quoted_literals_remain_allowed(self):
        for command in ("ORCA_ASK_CONFIRMED=1 orca terminal split",
                        " FOO=bar ORCA_ASK_CONFIRMED=1 /opt/bin/orca repo add /repo",
                        "ORCA_ASK_CONFIRMED=1 orca terminal split; ORCA_ASK_CONFIRMED=1 orca repo add /repo",
                        "echo \"orca terminal split\"", "printf \"orca repo add /repo\""):
            with self.subTest(command=command):
                self.assertEqual(0, self.split(command))
        self.assertEqual(0, self.split("orca terminal split", transcript=False))


if __name__ == "__main__":
    unittest.main()
