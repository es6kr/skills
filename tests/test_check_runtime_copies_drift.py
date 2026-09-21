"""Unit tests for scripts/check-runtime-copies-drift.py.

The script is a pre-push gate: when a push touches a file that
hook-registry.yaml (es6kr/claude-plugins) declares as `runtime_copies`-
tracked, it shells out to that sibling repo's own
`hook_registry_verify.py --check --check-copies` and blocks the push only
on a COPY_DRIFT / PARTIALLY_REMOVED finding — not on unrelated findings,
and not at all when the sibling checkout is absent on this machine.

No PyYAML dependency: `extract_canonical_paths` is a small dependency-free
line scanner (mirrors hook_registry.py's own "import-safe, no PyYAML"
design) so this test file runs unmodified under the CI pytest job, which
installs only `pytest` (see .github/workflows/test.yml `pytest` job).

Run:
  python -m pytest tests/test_check_runtime_copies_drift.py -v
"""
import importlib.util
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO_ROOT, "scripts", "check-runtime-copies-drift.py")


def _load():
    spec = importlib.util.spec_from_file_location("check_runtime_copies_drift", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


SAMPLE_REGISTRY = """\
schema_version: 1
hooks:
- id: bash-guard
  owner_skill: hook-kit
  marketplace: es6kr-skills
  status: active
  implementations:
  - runtime: py
    file: skills/hook-kit/resources/bash-guard.py
  registrations:
  - surface: hooks.json
    event: PreToolUse
    matcher: Bash
    command: ${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/bash-guard.py
  runtime_copies:
    canonical: skills/hook-kit/resources/bash-guard.py
    expected_roots:
    - ~/.claude/plugins/cache/es6kr-skills
    - ~/.claude/plugins/marketplaces/es6kr-skills
    sync_medium: syncthing
- id: no-copies-tracked
  owner_skill: hook-kit
  marketplace: es6kr-skills
  status: active
  implementations:
  - runtime: sh
    file: skills/hook-kit/resources/no-copies-tracked.sh
  registrations:
  - surface: hooks.json
    event: PreToolUse
    matcher: Bash
    command: ${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/no-copies-tracked.sh
"""


# --- extract_canonical_paths -------------------------------------------------

def test_extract_canonical_paths_single_entry():
    paths = mod.extract_canonical_paths(SAMPLE_REGISTRY)
    assert paths == {"skills/hook-kit/resources/bash-guard.py"}


def test_extract_canonical_paths_ignores_entries_without_runtime_copies():
    # no-copies-tracked has no runtime_copies block at all -> not in the set
    paths = mod.extract_canonical_paths(SAMPLE_REGISTRY)
    assert "skills/hook-kit/resources/no-copies-tracked.sh" not in paths


def test_extract_canonical_paths_multiple_entries():
    text = SAMPLE_REGISTRY + """\
- id: second-tracked
  owner_skill: hook-kit
  marketplace: es6kr-skills
  status: active
  implementations:
  - runtime: sh
    file: skills/hook-kit/resources/second.sh
  registrations: []
  runtime_copies:
    canonical: skills/hook-kit/resources/second.sh
    expected_roots:
    - ~/.claude/skills
"""
    paths = mod.extract_canonical_paths(text)
    assert paths == {
        "skills/hook-kit/resources/bash-guard.py",
        "skills/hook-kit/resources/second.sh",
    }


def test_extract_canonical_paths_ignores_canonical_key_outside_runtime_copies_block():
    # A same-named "canonical:" key that sits under an unrelated mapping
    # (not runtime_copies) must not be picked up -- otherwise the filter
    # stops meaning "runtime_copies-tracked" and starts meaning "any
    # canonical: line anywhere in the file".
    text = """\
schema_version: 1
hooks:
- id: decoy
  owner_skill: hook-kit
  marketplace: es6kr-skills
  status: active
  implementations:
  - runtime: sh
    file: skills/hook-kit/resources/decoy.sh
  registrations: []
  unrelated_block:
    canonical: skills/hook-kit/resources/decoy.sh
    other: value
"""
    paths = mod.extract_canonical_paths(text)
    assert paths == set()


def test_extract_canonical_paths_block_ends_at_dedent():
    # A canonical: line that appears AFTER the runtime_copies block has
    # ended (sibling key at the same or lower indent) must not be captured.
    text = """\
schema_version: 1
hooks:
- id: dedent-check
  owner_skill: hook-kit
  marketplace: es6kr-skills
  status: active
  implementations:
  - runtime: sh
    file: skills/hook-kit/resources/dedent.sh
  registrations: []
  runtime_copies:
    expected_roots:
    - ~/.claude/skills
  trailing_block:
    canonical: not-a-real-canonical-path
"""
    paths = mod.extract_canonical_paths(text)
    assert paths == set()


def test_extract_canonical_paths_empty_registry():
    assert mod.extract_canonical_paths("schema_version: 1\nhooks: []\n") == set()


# --- touches_tracked_copy -----------------------------------------------------

def test_touches_tracked_copy_true_on_intersection():
    canonical = {"skills/hook-kit/resources/bash-guard.py"}
    changed = ["README.md", "skills/hook-kit/resources/bash-guard.py"]
    assert mod.touches_tracked_copy(changed, canonical) is True


def test_touches_tracked_copy_false_when_disjoint():
    canonical = {"skills/hook-kit/resources/bash-guard.py"}
    changed = ["README.md", "skills/other/foo.py"]
    assert mod.touches_tracked_copy(changed, canonical) is False


def test_touches_tracked_copy_false_when_changed_files_empty():
    canonical = {"skills/hook-kit/resources/bash-guard.py"}
    assert mod.touches_tracked_copy([], canonical) is False


def test_touches_tracked_copy_false_when_canonical_paths_empty():
    assert mod.touches_tracked_copy(["skills/hook-kit/resources/bash-guard.py"], set()) is False


# --- parse_changed_files -------------------------------------------------------

def test_parse_changed_files_splits_and_strips_blank_lines():
    text = "skills/a/x.py\n\nskills/b/y.sh\n"
    assert mod.parse_changed_files(text) == ["skills/a/x.py", "skills/b/y.sh"]


def test_parse_changed_files_empty_string():
    assert mod.parse_changed_files("") == []


# --- build_verify_command -------------------------------------------------------

def test_build_verify_command_shape():
    cmd = mod.build_verify_command(
        plugins_root="/plugins/root",
        repo_root="/repo/root",
        verify_script="/plugins/root/scripts/hook_registry_verify.py",
    )
    assert cmd == [
        "uv", "run", "--with", "pyyaml", "python",
        "/plugins/root/scripts/hook_registry_verify.py",
        "--check", "--check-copies",
        "--repo-root", "/repo/root",
        "--plugins-root", "/plugins/root",
    ]


# --- main: soft-skip paths -----------------------------------------------------

def test_main_soft_skips_when_plugins_root_missing(tmp_path, capsys):
    missing_root = str(tmp_path / "does-not-exist")
    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", missing_root],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "skipped" in captured.err.lower()


def test_main_soft_skips_when_no_relevant_file_changed(tmp_path, monkeypatch):
    plugins_root = tmp_path / "claude-plugins"
    plugins_root.mkdir()
    (plugins_root / "hook-registry.yaml").write_text(SAMPLE_REGISTRY, encoding="utf-8")
    scripts_dir = plugins_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "hook_registry_verify.py").write_text("# stub\n", encoding="utf-8")

    called = []
    monkeypatch.setattr(mod, "_run_subprocess", lambda cmd: called.append(cmd))

    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", str(plugins_root)],
        stdin_text="README.md\nskills/unrelated/foo.py\n",
    )
    assert rc == 0
    assert called == []  # the verify tool must never be invoked for an unrelated diff


def test_main_soft_skips_when_verify_script_missing(tmp_path, monkeypatch, capsys):
    plugins_root = tmp_path / "claude-plugins"
    plugins_root.mkdir()
    (plugins_root / "hook-registry.yaml").write_text(SAMPLE_REGISTRY, encoding="utf-8")
    # scripts/hook_registry_verify.py intentionally absent

    called = []
    monkeypatch.setattr(mod, "_run_subprocess", lambda cmd: called.append(cmd))

    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", str(plugins_root)],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 0
    assert called == []
    captured = capsys.readouterr()
    assert "skipped" in captured.err.lower()


def test_main_soft_skips_when_uv_not_on_path(tmp_path, monkeypatch, capsys):
    plugins_root = tmp_path / "claude-plugins"
    plugins_root.mkdir()
    (plugins_root / "hook-registry.yaml").write_text(SAMPLE_REGISTRY, encoding="utf-8")
    scripts_dir = plugins_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "hook_registry_verify.py").write_text("# stub\n", encoding="utf-8")

    called = []
    monkeypatch.setattr(mod, "_run_subprocess", lambda cmd: called.append(cmd))
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)

    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", str(plugins_root)],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 0
    assert called == []
    captured = capsys.readouterr()
    assert "skipped" in captured.err.lower()
    assert "uv" in captured.err.lower()


# --- main: the verify tool is actually invoked and its verdict is honoured ----

class _FakeCompletedProcess:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _make_plugins_root(tmp_path):
    plugins_root = tmp_path / "claude-plugins"
    plugins_root.mkdir()
    (plugins_root / "hook-registry.yaml").write_text(SAMPLE_REGISTRY, encoding="utf-8")
    scripts_dir = plugins_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "hook_registry_verify.py").write_text("# stub\n", encoding="utf-8")
    return plugins_root


def test_main_invokes_verify_with_expected_command_when_relevant_file_touched(tmp_path, monkeypatch):
    plugins_root = _make_plugins_root(tmp_path)
    repo_root = tmp_path / "skills-repo"
    repo_root.mkdir()

    captured_cmd = {}

    def fake_run(cmd):
        captured_cmd["cmd"] = cmd
        return _FakeCompletedProcess(stdout="registry: no findings\n", returncode=0)

    monkeypatch.setattr(mod, "_run_subprocess", fake_run)

    rc = mod.main(
        ["--repo-root", str(repo_root), "--plugins-root", str(plugins_root)],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 0
    assert captured_cmd["cmd"] == mod.build_verify_command(
        plugins_root=str(plugins_root),
        repo_root=str(repo_root),
        verify_script=str(plugins_root / "scripts" / "hook_registry_verify.py"),
    )


def test_main_blocks_on_copy_drift_finding(tmp_path, monkeypatch):
    plugins_root = _make_plugins_root(tmp_path)
    monkeypatch.setattr(
        mod,
        "_run_subprocess",
        lambda cmd: _FakeCompletedProcess(
            stdout="\nCOPY_DRIFT (1)\n  - bash-guard: copies differ from the canonical file in ~/.claude/skills\n\ntotal findings: 1\n",
            returncode=1,
        ),
    )
    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", str(plugins_root)],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 1


def test_main_blocks_on_partially_removed_finding(tmp_path, monkeypatch):
    plugins_root = _make_plugins_root(tmp_path)
    monkeypatch.setattr(
        mod,
        "_run_subprocess",
        lambda cmd: _FakeCompletedProcess(
            stdout="\nPARTIALLY_REMOVED (1)\n  - bash-guard: removed hook still present in ~/.claude/skills\n\ntotal findings: 1\n",
            returncode=1,
        ),
    )
    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", str(plugins_root)],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 1


def test_main_does_not_block_on_unrelated_finding(tmp_path, monkeypatch):
    # hook_registry_verify.py --check validates the WHOLE registry, not just
    # copy drift -- an unrelated finding (e.g. ORPHAN_REGISTRATION on a
    # different hook) must not fail this push.
    plugins_root = _make_plugins_root(tmp_path)
    monkeypatch.setattr(
        mod,
        "_run_subprocess",
        lambda cmd: _FakeCompletedProcess(
            stdout="\nORPHAN_REGISTRATION (1)\n  - some-other-hook: registered script missing\n\ntotal findings: 1\n",
            returncode=1,
        ),
    )
    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", str(plugins_root)],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 0


def test_main_clean_check_returns_zero(tmp_path, monkeypatch):
    plugins_root = _make_plugins_root(tmp_path)
    monkeypatch.setattr(
        mod,
        "_run_subprocess",
        lambda cmd: _FakeCompletedProcess(stdout="registry: no findings\n", returncode=0),
    )
    rc = mod.main(
        ["--repo-root", str(tmp_path), "--plugins-root", str(plugins_root)],
        stdin_text="skills/hook-kit/resources/bash-guard.py\n",
    )
    assert rc == 0


# --- CLI smoke test: real subprocess, no monkeypatching -----------------------

def test_cli_invocation_soft_skips_when_plugins_root_missing(tmp_path):
    # Exercises real argparse + stdin wiring end-to-end without needing uv,
    # pyyaml, or a claude-plugins checkout on the machine running the test.
    missing_root = str(tmp_path / "nonexistent-claude-plugins")
    result = subprocess.run(
        [sys.executable, CANON, "--repo-root", str(tmp_path), "--plugins-root", missing_root],
        input="skills/hook-kit/resources/bash-guard.py\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "skipped" in result.stderr.lower()
