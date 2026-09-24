"""Unit tests for scripts/verify-plugin-spec.py (Agent Plugins v1.0.0 linter).

Covers the four checks the script performs beyond bare JSON-Schema shape:
name-pattern rejection, dual-manifest (root <-> .claude-plugin/) equality,
plugin.json <-> marketplace.json version matching, and marketplace "source"
path containment. Uses importlib module loading since scripts/verify-plugin-
spec.py has a hyphen in its filename (not importable as a normal module),
same pattern as test_plane_sync.py.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify-plugin-spec.py"

spec = importlib.util.spec_from_file_location("verify_plugin_spec", str(SCRIPT_PATH))
verify_plugin_spec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_plugin_spec)


VALID_MANIFEST = {
    "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
    "name": "es6kr",
    "version": "0.1.1",
    "description": "Reusable AI coding skills",
}


class TestValidateManifest:
    def test_valid_manifest_no_errors(self):
        assert verify_plugin_spec.validate_manifest(VALID_MANIFEST, "plugin.json") == []

    def test_missing_schema_field(self):
        data = {k: v for k, v in VALID_MANIFEST.items() if k != "$schema"}
        errors = verify_plugin_spec.validate_manifest(data, "plugin.json")
        assert any("$schema" in e for e in errors)

    def test_wrong_schema_url(self):
        data = {**VALID_MANIFEST, "$schema": "https://example.com/other.json"}
        errors = verify_plugin_spec.validate_manifest(data, "plugin.json")
        assert any("$schema" in e for e in errors)

    def test_missing_name_field(self):
        data = {k: v for k, v in VALID_MANIFEST.items() if k != "name"}
        errors = verify_plugin_spec.validate_manifest(data, "plugin.json")
        assert any("name" in e for e in errors)

    @pytest.mark.parametrize("bad_name", [
        "Es6kr",           # uppercase
        "es6--kr",         # double hyphen
        "-es6kr",          # leading hyphen
        "es6kr-",          # trailing hyphen
        "es6..kr",         # double dot
        "",                # empty
        "a" * 65,          # too long
    ])
    def test_rejects_invalid_names(self, bad_name):
        data = {**VALID_MANIFEST, "name": bad_name}
        errors = verify_plugin_spec.validate_manifest(data, "plugin.json")
        assert any("name" in e for e in errors), f"expected rejection for {bad_name!r}"

    @pytest.mark.parametrize("good_name", ["es6kr", "a", "my-plugin", "plugin.name", "a1b2c3"])
    def test_accepts_valid_names(self, good_name):
        data = {**VALID_MANIFEST, "name": good_name}
        errors = verify_plugin_spec.validate_manifest(data, "plugin.json")
        assert not any("name" in e for e in errors), f"unexpected rejection for {good_name!r}"

    def test_rejects_unexpected_top_level_key(self):
        data = {**VALID_MANIFEST, "not_a_spec_field": True}
        errors = verify_plugin_spec.validate_manifest(data, "plugin.json")
        assert any("unexpected top-level key" in e for e in errors)


class TestDualManifestEquality:
    def test_identical_copies_no_error(self, tmp_path):
        canonical = tmp_path / "plugin.json"
        mirror = tmp_path / "mirror.json"
        canonical.write_text('{"a": 1}', encoding="utf-8")
        mirror.write_text('{"a": 1}', encoding="utf-8")
        assert verify_plugin_spec.check_dual_manifest_equality(canonical, mirror) == []

    def test_drifted_copies_reported(self, tmp_path):
        canonical = tmp_path / "plugin.json"
        mirror = tmp_path / "mirror.json"
        canonical.write_text('{"a": 1}', encoding="utf-8")
        mirror.write_text('{"a": 2}', encoding="utf-8")
        errors = verify_plugin_spec.check_dual_manifest_equality(canonical, mirror)
        assert len(errors) == 1
        assert "drifted" in errors[0]

    def test_missing_mirror_no_error(self, tmp_path):
        canonical = tmp_path / "plugin.json"
        mirror = tmp_path / "does_not_exist.json"
        canonical.write_text('{"a": 1}', encoding="utf-8")
        assert verify_plugin_spec.check_dual_manifest_equality(canonical, mirror) == []


class TestVersionMatchesMarketplace:
    def test_matching_versions_no_error(self, tmp_path):
        manifest = {"version": "0.1.1"}
        entry = {"name": "es6kr", "version": "0.1.1"}
        assert verify_plugin_spec.check_version_matches_marketplace(manifest, entry, tmp_path / "plugin.json") == []

    def test_mismatched_versions_reported(self, tmp_path):
        manifest = {"version": "0.1.0"}
        entry = {"name": "es6kr", "version": "0.1.1"}
        errors = verify_plugin_spec.check_version_matches_marketplace(manifest, entry, tmp_path / "plugin.json")
        assert len(errors) == 1
        assert "0.1.0" in errors[0] and "0.1.1" in errors[0]


class TestPathContainment:
    def test_normal_relative_source_ok(self):
        entry = {"name": "code-quality", "source": "./plugins/code-quality"}
        assert verify_plugin_spec.check_path_containment(entry) == []

    def test_root_source_ok(self):
        entry = {"name": "es6p", "source": "./"}
        assert verify_plugin_spec.check_path_containment(entry) == []

    def test_escaping_source_rejected(self):
        entry = {"name": "evil", "source": "../../etc"}
        errors = verify_plugin_spec.check_path_containment(entry)
        assert len(errors) == 1
        assert "escapes" in errors[0]


class TestSourceDirectoryExists:
    def test_existing_directory_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        (tmp_path / "plugins" / "real").mkdir(parents=True)
        entry = {"name": "real", "source": "./plugins/real"}
        assert verify_plugin_spec.check_source_directory_exists(entry) == []

    def test_missing_directory_reported(self, tmp_path, monkeypatch):
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        entry = {"name": "ghost", "source": "./plugins/ghost"}
        errors = verify_plugin_spec.check_source_directory_exists(entry)
        assert len(errors) == 1
        assert "does not exist" in errors[0]


class TestMainIntegration:
    """End-to-end: build a tiny fake repo under tmp_path and point the
    script's module-level REPO_ROOT/MARKETPLACE_PATH constants at it."""

    def _build_fake_repo(self, tmp_path, plugin_extra=None, marketplace_version="0.1.1", mirror_content=None):
        (tmp_path / ".claude-plugin").mkdir()
        manifest = dict(VALID_MANIFEST)
        if plugin_extra:
            manifest.update(plugin_extra)
        (tmp_path / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        if mirror_content is not None:
            (tmp_path / ".claude-plugin" / "plugin.json").write_text(mirror_content, encoding="utf-8")
        marketplace = {"plugins": [{"name": "es6kr", "source": "./", "version": marketplace_version}]}
        (tmp_path / ".claude-plugin" / "marketplace.json").write_text(json.dumps(marketplace), encoding="utf-8")
        return tmp_path

    def _run_main(self, monkeypatch, tmp_path):
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(verify_plugin_spec, "MARKETPLACE_PATH", tmp_path / ".claude-plugin" / "marketplace.json")
        return verify_plugin_spec.main()

    def test_valid_repo_exits_zero(self, tmp_path, monkeypatch, capsys):
        self._build_fake_repo(tmp_path, mirror_content=json.dumps(VALID_MANIFEST))
        assert self._run_main(monkeypatch, tmp_path) == 0
        assert "OK" in capsys.readouterr().out

    def test_version_mismatch_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        self._build_fake_repo(tmp_path, marketplace_version="9.9.9", mirror_content=json.dumps(VALID_MANIFEST))
        assert self._run_main(monkeypatch, tmp_path) == 1
        assert "FAIL" in capsys.readouterr().err

    def test_dual_manifest_drift_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        self._build_fake_repo(tmp_path, mirror_content='{"$schema": "wrong"}')
        assert self._run_main(monkeypatch, tmp_path) == 1
        assert "FAIL" in capsys.readouterr().err

    def test_no_mirror_still_passes(self, tmp_path, monkeypatch, capsys):
        self._build_fake_repo(tmp_path, mirror_content=None)
        assert self._run_main(monkeypatch, tmp_path) == 0

    def test_stale_marketplace_entry_missing_directory_fails(self, tmp_path, monkeypatch, capsys):
        self._build_fake_repo(tmp_path, mirror_content=json.dumps(VALID_MANIFEST))
        marketplace_path = tmp_path / ".claude-plugin" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        marketplace["plugins"].append({"name": "ghost", "source": "./plugins/ghost", "version": "0.1.0"})
        marketplace_path.write_text(json.dumps(marketplace), encoding="utf-8")
        assert self._run_main(monkeypatch, tmp_path) == 1
        assert "does not exist" in capsys.readouterr().err


class TestRealRepoManifestsConform:
    """Smoke test: this repo's own plugin.json / marketplace.json must pass."""

    def test_real_repo_conforms(self, capsys):
        assert verify_plugin_spec.main() == 0, capsys.readouterr().err


class TestMarketplaceThreeTierArchitecture:
    """Enforce the 3-Tier Marketplace Bundle Architecture from llm-wiki/pages/reference/es6kr-skills-repo.md."""

    def test_marketplace_has_three_bundles_and_labs_contains_slug_squats(self):
        marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        assert marketplace_path.exists()
        data = json.loads(marketplace_path.read_text(encoding="utf-8"))
        plugins = {p["name"]: p for p in data.get("plugins", [])}

        assert set(plugins.keys()) == {"es6kr", "task", "labs"}, (
            f"Expected plugins ['es6kr', 'task', 'labs'], got {list(plugins.keys())}"
        )

        labs_skills = set(plugins["labs"].get("skills", []))
        expected_labs = {
            "./skills/backlog",
            "./skills/harness",
            "./skills/orca",
            "./skills/choco",
            "./skills/forge",
            "./skills/omz",
            "./skills/code-workflow",
        }
        assert expected_labs.issubset(labs_skills), (
            f"Expected labs to contain {expected_labs}, but got {labs_skills}"
        )

        task_skills = set(plugins["task"].get("skills", []))
        expected_task = {
            "./skills/next",
            "./skills/wip",
            "./skills/fix",
            "./skills/task-plan",
            "./skills/task-exec",
            "./skills/task-flow",
        }
        assert expected_task.issubset(task_skills), (
            f"Expected task bundle to contain {expected_task}, but got {task_skills}"
        )

        # Core bundle must not contain labs skills
        core_skills = set(plugins["es6kr"].get("skills", []))
        overlap = core_skills.intersection(expected_labs)
        assert not overlap, f"Core bundle 'es6kr' must not contain slug-squatting skills: {overlap}"


class TestOrphanPluginDirectories:
    """Reverse of TestSourceDirectoryExists: a bundle on disk that the catalog
    never lists. This is the PR #38 failure -- plugins/worker shipped with a
    plugin.json and no marketplace.json entry, so no harness ever loaded it and
    no catalog-driven check ever visited it."""

    def _bundle(self, tmp_path, name):
        d = tmp_path / "plugins" / name
        d.mkdir(parents=True)
        (d / "plugin.json").write_text(json.dumps(VALID_MANIFEST), encoding="utf-8")
        return d

    def test_registered_bundle_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        self._bundle(tmp_path, "listed")
        entries = [{"name": "listed", "source": "./plugins/listed"}]
        assert verify_plugin_spec.check_orphan_plugin_directories(entries) == []

    def test_unlisted_bundle_reported(self, tmp_path, monkeypatch):
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        self._bundle(tmp_path, "worker")
        entries = [{"name": "root", "source": "./"}]
        errors = verify_plugin_spec.check_orphan_plugin_directories(entries)
        assert len(errors) == 1
        assert "plugins/worker" in errors[0]
        assert "nothing loads it" in errors[0]

    def test_root_source_does_not_claim_nested_bundles(self, tmp_path, monkeypatch):
        """source './' covers the repo root only. It must not be read as claiming
        plugins/<name>, which is what made the omission look harmless."""
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        self._bundle(tmp_path, "a")
        self._bundle(tmp_path, "b")
        entries = [{"name": "root", "source": "./"}]
        assert len(verify_plugin_spec.check_orphan_plugin_directories(entries)) == 2

    def test_directory_without_manifest_ignored(self, tmp_path, monkeypatch):
        """A scratch directory under plugins/ is not yet a bundle."""
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        (tmp_path / "plugins" / "scratch").mkdir(parents=True)
        assert verify_plugin_spec.check_orphan_plugin_directories([]) == []

    def test_no_plugins_dir_is_noop(self, tmp_path, monkeypatch):
        """Repos without a plugins/ tree (e.g. the sibling copy of this linter)
        must be unaffected."""
        monkeypatch.setattr(verify_plugin_spec, "REPO_ROOT", tmp_path)
        assert verify_plugin_spec.check_orphan_plugin_directories([]) == []

