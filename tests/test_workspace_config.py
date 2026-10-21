"""Exercise the public resolver's CLI output contract in isolated homes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/hook-kit/resources/workspace-config.sh"
BASH = shutil.which("bash")
ROLES = ("artifacts", "checklist", "backlog", "rag", "wiki", "staging")


def run_resolver(tmp_path, config_text, mode, *, python_available=True, profile=None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    config = home / "explicit.json"
    if config_text is not None:
        config.write_text(config_text, encoding="utf-8")
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR"}}
    env.update(HOME=home.as_posix(), USERPROFILE=str(home),
               AGENT_WORKSPACE_CONFIG=config.as_posix())
    if profile is not None:
        env["AGENT_WORKSPACE_PROFILE"] = profile
    env["PATH"] = (str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")) if python_available else ""
    assert BASH, "Bash is required for the shell resolver contract"
    return subprocess.run([BASH, "--noprofile", "--norc", SCRIPT.as_posix(), mode, home.as_posix()],
                          env=env, capture_output=True, text=True, timeout=15)


@pytest.mark.parametrize("config_text", [None, "{", "[]", '{"profiles": [1]}'])
def test_degraded_json_remains_json(tmp_path, config_text):
    result = run_resolver(tmp_path, config_text, "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "profile": "default", "roles": {role: {"kind": "none"} for role in ROLES}}


@pytest.mark.parametrize("config_text", [None, "{", "[]", '{"profiles": [1]}'])
def test_degraded_export_is_unchanged(tmp_path, config_text):
    result = run_resolver(tmp_path, config_text, "--export")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["WSCFG_PROFILE=default"] + [
        f"WSCFG_{role.upper()}_KIND=none" for role in ROLES]


@pytest.mark.parametrize("mode", ["--json", "--export"])
@pytest.mark.parametrize("python_available,config_text", [(False, None), (True, '{"defaults": 1}')])
def test_shell_fallback_preserves_requested_format(tmp_path, mode, python_available, config_text):
    result = run_resolver(tmp_path, config_text, mode, python_available=python_available)
    assert result.returncode == 0, result.stderr
    if mode == "--json":
        assert json.loads(result.stdout) == {
            "profile": "default", "roles": {role: {"kind": "none"} for role in ROLES}}
    else:
        assert result.stdout.splitlines() == ["WSCFG_PROFILE=default"] + [
            f"WSCFG_{role.upper()}_KIND=none" for role in ROLES]


@pytest.mark.parametrize("mode", ["--json", "--export"])
@pytest.mark.parametrize("version", [1, 2])
def test_valid_config_and_explicit_profile_are_unchanged(tmp_path, mode, version):
    endpoint = "https://rag.example.test"
    selected = ({"qdrant_url": endpoint, "cwd_match": ["not-this-home"]} if version == 1 else {
        "match": {"path_components": ["not-this-home"]},
        "roles": {"rag": {"kind": "qdrant", "endpoint": endpoint}}})
    cfg = {"version": version, "profiles": {"selected": selected}}
    result = run_resolver(tmp_path, json.dumps(cfg), mode, profile="selected")
    assert result.returncode == 0, result.stderr
    if mode == "--json":
        data = json.loads(result.stdout)
        assert data["profile"] == "selected"
        assert data["roles"]["rag"]["kind"] == "qdrant"
        assert data["roles"]["rag"]["endpoint"] == endpoint
    else:
        lines = result.stdout.splitlines()
        assert "WSCFG_PROFILE=selected" in lines
        assert "WSCFG_RAG_KIND=qdrant" in lines
        assert f"WSCFG_RAG_ENDPOINT={endpoint}" in lines
