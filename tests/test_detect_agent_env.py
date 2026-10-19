"""Regression coverage for native Claude detection and unchanged routing.

Only synthetic environment signals are used; no agent/model is launched.
The child-session and conflicting-signal cases preserve existing behavior;
they do not adopt a new signal or define a new precedence policy.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
DETECTOR = ROOT / "skills/fix/scripts/detect-agent-env.sh"
BASH = shutil.which("bash")
HOME = "/__detect_agent_env_test_home__"
ORCA = {"__CFBundleIdentifier": "com.stablyai.orca", "TERM_PROGRAM": "Orca"}
AGY_IDE = {"__CFBundleIdentifier": "com.google.antigravity"}
CURSOR = {"__CFBundleIdentifier": "com.todesktop.230313mzl4w4u92"}
VSCODE = {"__CFBundleIdentifier": "com.microsoft.VSCode"}
CASES = [
    ("no_signals", {}, "unknown"),
    ("native_claudecode", {"CLAUDECODE": "1"}, "claude-code"),
    ("legacy_claude_code", {"CLAUDE_CODE": "1"}, "claude-code"),
    ("empty_native_signal", {"CLAUDECODE": ""}, "unknown"),
    ("orca_bundle_only", {"__CFBundleIdentifier": ORCA["__CFBundleIdentifier"]}, "unknown"),
    ("orca_term_only", {"TERM_PROGRAM": "Orca"}, "unknown"),
    ("orca_host_only", ORCA, "unknown"),
    ("native_claude_in_orca", {**ORCA, "CLAUDECODE": "1"}, "claude-code"),
    ("legacy_claude_in_orca", {**ORCA, "CLAUDE_CODE": "1"}, "claude-code"),
    ("agy_agent", {"ANTIGRAVITY_AGENT": "1"}, "antigravity-agent"),
    ("agy_agent_zero", {"ANTIGRAVITY_AGENT": "0"}, "unknown"),
    ("agy_ide_only", AGY_IDE, "antigravity"),
    ("native_claude_in_agy_ide", {**AGY_IDE, "CLAUDECODE": "1"}, "claude-code"),
    ("legacy_claude_in_agy_ide", {**AGY_IDE, "CLAUDE_CODE": "1"}, "claude-code"),
    ("cursor_ide_only", CURSOR, "cursor"),
    ("native_claude_in_cursor", {**CURSOR, "CLAUDECODE": "1"}, "claude-code"),
    ("vscode_ide_only", VSCODE, "vscode"),
    ("native_claude_in_vscode", {**VSCODE, "CLAUDECODE": "1"}, "claude-code"),
    ("agy_ide_variant", {"__CFBundleIdentifier": "com.google.antigravity-ide"}, "antigravity-ide"),
    ("child_session_remains_unadopted", {"CLAUDE_CODE_CHILD_SESSION": "1"}, "unknown"),
    ("child_session_in_orca_remains_unadopted", {**ORCA, "CLAUDE_CODE_CHILD_SESSION": "1"}, "unknown"),
    ("conflicting_native_signals_unchanged", {"CLAUDECODE": "1", "ANTIGRAVITY_AGENT": "1"}, "antigravity-agent"),
    ("conflicting_legacy_signals_unchanged", {"CLAUDE_CODE": "1", "ANTIGRAVITY_AGENT": "1"}, "claude-code"),
]


def expected_output(harness):
    if harness == "unknown":
        values = ("unknown", "unknown", "unknown")
    elif harness in ("antigravity", "antigravity-agent", "antigravity-ide"):
        values = ("GEMINI.md", f"{HOME}/.gemini/config/config.json", f"{HOME}/.agents/rules (READ-ONLY)")
    else:
        values = ("CLAUDE.md", f"{HOME}/.claude/settings.json", f"{HOME}/.claude/rules (WRITABLE)")
    return [harness, *[f"{key}={value}" for key, value in zip(
        ("RULES_FILE", "SETTINGS_FILE", "SHARED_RULES_DIR"), values
    )]]


@unittest.skipUnless(BASH, "Bash is required for the detector")
class DetectAgentEnvTests(unittest.TestCase):
    def check_case(self, signals, expected):
        # Keep OS bootstrap but never inherit agent signals, BASH_ENV, or auth.
        env = {key: os.environ[key] for key in (
            "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "SYSTEMDRIVE",
            "TMPDIR", "TMP", "TEMP"
        ) if key in os.environ}
        env.update({"HOME": HOME, "USERPROFILE": HOME, "LC_ALL": "C", "LANG": "C"})
        env.update(signals)
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", str(DETECTOR)],
            env=env, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.splitlines(), expected_output(expected))


def make_test(signals, expected):
    def test(self):
        self.check_case(signals, expected)
    return test


for name, signals, expected in CASES:
    setattr(DetectAgentEnvTests, "test_" + name, make_test(signals, expected))

if __name__ == "__main__":
    unittest.main()
