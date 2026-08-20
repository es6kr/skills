"""Hook registry schema guards.

These cover the defect classes the registry exists to catch, each of which has
already happened at least once in this repo:

- a hook registered in both marketplaces so it fires twice per trigger
- the same script registered twice on one surface for the same (event, matcher)
- a `.sh` -> `.js` migration mistaken for a duplicate, or its two runtimes left
  registered simultaneously so both fire
- a hook that was deliberately removed reappearing on disk or in a registration
- a registration whose script is missing, which exits 127 and reads to the
  harness as "the guard had no objection"
- a `.sh` wrapper and the implementation it execs ending up in different skills,
  which is what turned a relocation into a hard block on every Edit/Write

The validation core is deliberately dependency-free and operates on plain
dicts, so this file runs under the repo's `uvx --from pytest pytest tests`
invocation without pulling in PyYAML. YAML lives at the CLI edge only.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_KIT_SCRIPTS = REPO_ROOT / "skills" / "hook-kit" / "scripts"

sys.path.insert(0, str(HOOK_KIT_SCRIPTS))

import hook_registry as hr  # noqa: E402


# --- helpers ---------------------------------------------------------------


def entry(hook_id, **overrides):
    """A minimal valid registry entry, overridable per test."""
    base = {
        "id": hook_id,
        "owner_skill": "hook-kit",
        "marketplace": "es6kr-skills",
        "status": "active",
        "implementations": [
            {"runtime": "sh", "file": f"skills/hook-kit/resources/{hook_id}.sh"}
        ],
        "registrations": [
            {
                "surface": "hooks.json",
                "event": "PreToolUse",
                "matcher": "Bash",
                "command": "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/"
                + f"{hook_id}.sh",
            }
        ],
    }
    base.update(overrides)
    return base


def codes(findings):
    return sorted(f.code for f in findings)


def disk(*paths):
    """A disk index: marketplace -> set of files present."""
    return {"es6kr-skills": set(paths), "es6kr-plugins": set()}


# --- stem / runtime derivation ---------------------------------------------


@pytest.mark.parametrize(
    "path,expected",
    [
        ("skills/hook-kit/resources/bash-guard.py", "bash-guard"),
        ("skills/wip/resources/block-wip-register-before-execute.sh", "block-wip-register-before-execute"),
        ("skills/cleanup/resources/x.js", "x"),
        # extension-less files keep their whole basename
        ("skills/hook-kit/resources/README", "README"),
    ],
)
def test_stem_strips_directory_and_extension(path, expected):
    assert hr.stem_of(path) == expected


def test_stem_ignores_extension_so_sh_and_js_share_one_identity():
    assert hr.stem_of("a/b/guard.sh") == hr.stem_of("c/d/guard.js")


@pytest.mark.parametrize(
    "path,expected",
    [
        ("x/y.sh", "sh"),
        ("x/y.py", "py"),
        ("x/y.js", "js"),
        ("x/y.mjs", "js"),
        ("x/y", "other"),
    ],
)
def test_runtime_derived_from_extension(path, expected):
    assert hr.runtime_of(path) == expected


# --- hooks.json parsing ----------------------------------------------------


def hooks_json(*commands):
    return {
        "description": "test fixture",
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": c} for c in commands],
                }
            ]
        },
    }


def test_parse_extracts_a_bare_command_path():
    regs = hr.parse_registrations(
        hooks_json("${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/a.sh"),
        surface="hooks.json",
        marketplace="es6kr-skills",
    )
    assert [r["file"] for r in regs] == ["skills/hook-kit/resources/a.sh"]
    assert regs[0]["event"] == "PreToolUse"
    assert regs[0]["matcher"] == "Bash"


def test_parse_handles_interpreter_prefix_and_quoting():
    regs = hr.parse_registrations(
        hooks_json(
            'bash "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/b.sh"',
            "python3 ${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/c.sh",
        ),
        surface="hooks.json",
        marketplace="es6kr-skills",
    )
    assert sorted(r["file"] for r in regs) == [
        "skills/hook-kit/resources/b.sh",
        "skills/hook-kit/resources/c.sh",
    ]


def test_parse_ignores_commands_without_a_plugin_root_path():
    regs = hr.parse_registrations(
        hooks_json("echo hello"),
        surface="hooks.json",
        marketplace="es6kr-skills",
    )
    assert regs == []


# --- clean baseline --------------------------------------------------------


def test_a_consistent_registry_produces_no_findings():
    registry = {"schema_version": 1, "hooks": [entry("guard-a")]}
    findings = hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh"))
    assert findings == []


# --- duplication axis ------------------------------------------------------


def test_same_id_active_in_both_marketplaces_is_a_dual_registration_violation():
    registry = {
        "schema_version": 1,
        "hooks": [
            entry("guard-a"),
            entry(
                "guard-a",
                marketplace="es6kr-plugins",
                implementations=[
                    {"runtime": "sh", "file": "skills/es6p-hooks/resources/guard-a.sh"}
                ],
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Bash",
                        "command": "${CLAUDE_PLUGIN_ROOT}/skills/es6p-hooks/resources/guard-a.sh",
                    }
                ],
            ),
        ],
    }
    index = {
        "es6kr-skills": {"skills/hook-kit/resources/guard-a.sh"},
        "es6kr-plugins": {"skills/es6p-hooks/resources/guard-a.sh"},
    }
    assert "DUAL_MARKETPLACE" in codes(hr.validate(registry, index))


def test_a_removed_entry_does_not_count_toward_dual_registration():
    """Tombstones are permanent, so they must not look like live duplicates."""
    registry = {
        "schema_version": 1,
        "hooks": [
            entry("guard-a"),
            entry(
                "guard-a",
                marketplace="es6kr-plugins",
                status="removed",
                implementations=[],
                registrations=[],
                tombstone={
                    "removed_at": "2026-08-16",
                    "reason": "dual-marketplace",
                    "detail": "consolidated into hook-kit",
                },
            ),
        ],
    }
    assert "DUAL_MARKETPLACE" not in codes(
        hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh"))
    )


def test_same_event_and_matcher_registered_twice_on_one_surface_is_a_violation():
    reg = {
        "surface": "hooks.json",
        "event": "PreToolUse",
        "matcher": "Bash",
        "command": "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-a.sh",
    }
    registry = {
        "schema_version": 1,
        "hooks": [entry("guard-a", registrations=[reg, dict(reg)])],
    }
    assert "DUPLICATE_REGISTRATION" in codes(
        hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh"))
    )


def test_the_same_script_on_two_different_matchers_is_not_a_duplicate():
    registry = {
        "schema_version": 1,
        "hooks": [
            entry(
                "guard-a",
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Edit",
                        "command": "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-a.sh",
                    },
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Write",
                        "command": "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-a.sh",
                    },
                ],
            )
        ],
    }
    assert codes(hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh"))) == []


# --- migration axis (sh -> js) ---------------------------------------------


def test_a_completed_sh_to_js_migration_is_history_not_a_duplicate():
    registry = {
        "schema_version": 1,
        "hooks": [
            entry(
                "guard-a",
                implementations=[
                    {
                        "runtime": "sh",
                        "file": "skills/hook-kit/resources/guard-a.sh",
                        "until": "2026-07-01",
                    },
                    {
                        "runtime": "js",
                        "file": "skills/hook-kit/resources/guard-a.js",
                        "since": "2026-07-01",
                    },
                ],
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Bash",
                        "command": "node ${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-a.js",
                    }
                ],
            )
        ],
    }
    assert codes(hr.validate(registry, disk("skills/hook-kit/resources/guard-a.js"))) == []


def test_both_runtimes_registered_at_once_means_the_guard_fires_twice():
    registry = {
        "schema_version": 1,
        "hooks": [
            entry(
                "guard-a",
                implementations=[
                    {"runtime": "sh", "file": "skills/hook-kit/resources/guard-a.sh"},
                    {"runtime": "js", "file": "skills/hook-kit/resources/guard-a.js"},
                ],
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Bash",
                        "command": "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-a.sh",
                    },
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Edit",
                        "command": "node ${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-a.js",
                    },
                ],
            )
        ],
    }
    index = disk(
        "skills/hook-kit/resources/guard-a.sh",
        "skills/hook-kit/resources/guard-a.js",
    )
    assert "DOUBLE_FIRING_MIGRATION" in codes(hr.validate(registry, index))


# --- lifecycle axis (tombstone) --------------------------------------------


def removed_entry(hook_id="guard-gone", **overrides):
    base = {
        "id": hook_id,
        "owner_skill": "hook-kit",
        "marketplace": "es6kr-skills",
        "status": "removed",
        "implementations": [
            {"runtime": "sh", "file": f"skills/hook-kit/resources/{hook_id}.sh"}
        ],
        "registrations": [],
        "tombstone": {
            "removed_at": "2026-08-18",
            "reason": "severe-latency",
            "detail": "WMI process scan on every Stop",
            "replacement": "batched into /cleanup",
        },
    }
    base.update(overrides)
    return base


def test_a_tombstoned_hook_absent_from_disk_is_the_expected_state():
    registry = {"schema_version": 1, "hooks": [removed_entry()]}
    assert hr.validate(registry, disk()) == []


def test_a_tombstoned_hook_reappearing_on_disk_fails():
    registry = {"schema_version": 1, "hooks": [removed_entry()]}
    index = disk("skills/hook-kit/resources/guard-gone.sh")
    assert "TOMBSTONE_REINTRODUCED" in codes(hr.validate(registry, index))


def test_a_tombstoned_hook_reappearing_as_a_registration_fails():
    registry = {
        "schema_version": 1,
        "hooks": [
            removed_entry(
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "Stop",
                        "matcher": "",
                        "command": "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-gone.sh",
                    }
                ]
            )
        ],
    }
    assert "TOMBSTONE_REINTRODUCED" in codes(hr.validate(registry, disk()))


def test_a_removed_entry_must_carry_a_tombstone_block():
    registry = {"schema_version": 1, "hooks": [removed_entry(tombstone=None)]}
    assert "SCHEMA" in codes(hr.validate(registry, disk()))


# --- registration-surface axis ---------------------------------------------


def test_a_registration_whose_script_is_missing_is_an_orphan():
    """exit 127 reads to the harness as 'no objection' — the silent failure."""
    registry = {"schema_version": 1, "hooks": [entry("guard-a")]}
    assert "ORPHAN_REGISTRATION" in codes(hr.validate(registry, disk()))


def test_a_file_present_but_unregistered_is_dormant_not_a_violation():
    registry = {
        "schema_version": 1,
        "hooks": [entry("guard-a", status="dormant", registrations=[])],
    }
    assert hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh")) == []


def test_declared_status_must_match_the_observed_state():
    """Claiming 'active' while nothing is registered is a stale declaration."""
    registry = {
        "schema_version": 1,
        "hooks": [entry("guard-a", registrations=[])],
    }
    assert "STATUS_MISMATCH" in codes(
        hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh"))
    )


# --- wrapper/implementation pairing ----------------------------------------


def test_a_wrapper_and_its_implementation_in_different_skills_is_a_violation():
    """The PR #340 regression: the .sh moved away from the .py it execs."""
    registry = {
        "schema_version": 1,
        "hooks": [
            entry(
                "guard-a",
                implementations=[
                    {"runtime": "sh", "file": "skills/hook-kit/resources/guard-a.sh"},
                    {"runtime": "py", "file": "skills/wip/resources/guard-a.py"},
                ],
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Edit",
                        "command": "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/guard-a.sh",
                    }
                ],
            )
        ],
    }
    index = disk(
        "skills/hook-kit/resources/guard-a.sh",
        "skills/wip/resources/guard-a.py",
    )
    assert "WRAPPER_IMPL_SPLIT" in codes(hr.validate(registry, index))


def test_a_wrapper_beside_its_implementation_is_fine():
    registry = {
        "schema_version": 1,
        "hooks": [
            entry(
                "guard-a",
                owner_skill="wip",
                implementations=[
                    {"runtime": "sh", "file": "skills/wip/resources/guard-a.sh"},
                    {"runtime": "py", "file": "skills/wip/resources/guard-a.py"},
                ],
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Edit",
                        "command": "${CLAUDE_PLUGIN_ROOT}/skills/wip/resources/guard-a.sh",
                    }
                ],
            )
        ],
    }
    index = disk(
        "skills/wip/resources/guard-a.sh",
        "skills/wip/resources/guard-a.py",
    )
    assert codes(hr.validate(registry, index)) == []


def test_a_migration_pair_across_skills_is_not_a_wrapper_split():
    """sh->js in different skills is a relocation record, not an exec pair."""
    registry = {
        "schema_version": 1,
        "hooks": [
            entry(
                "guard-a",
                owner_skill="wip",
                implementations=[
                    {
                        "runtime": "sh",
                        "file": "skills/hook-kit/resources/guard-a.sh",
                        "until": "2026-08-01",
                    },
                    {
                        "runtime": "js",
                        "file": "skills/wip/resources/guard-a.js",
                        "since": "2026-08-01",
                    },
                ],
                registrations=[
                    {
                        "surface": "hooks.json",
                        "event": "PreToolUse",
                        "matcher": "Edit",
                        "command": "node ${CLAUDE_PLUGIN_ROOT}/skills/wip/resources/guard-a.js",
                    }
                ],
            )
        ],
    }
    assert "WRAPPER_IMPL_SPLIT" not in codes(
        hr.validate(registry, disk("skills/wip/resources/guard-a.js"))
    )


# --- schema shape ----------------------------------------------------------


@pytest.mark.parametrize("bad_status", ["enabled", "deleted", "", None])
def test_status_must_come_from_the_known_set(bad_status):
    registry = {"schema_version": 1, "hooks": [entry("guard-a", status=bad_status)]}
    assert "SCHEMA" in codes(
        hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh"))
    )


def test_two_entries_may_share_an_id_only_across_different_marketplaces():
    registry = {
        "schema_version": 1,
        "hooks": [entry("guard-a"), entry("guard-a")],
    }
    assert "SCHEMA" in codes(
        hr.validate(registry, disk("skills/hook-kit/resources/guard-a.sh"))
    )


# --- the committed registry ------------------------------------------------
#
# These read the real YAML, so they need PyYAML. The repo's pytest invocation
# (`uvx --from pytest pytest tests`) does not supply it, so they skip there and
# run locally / wherever the dependency is present. Everything above stays
# dependency-free on purpose — the validation core must never need a package to
# be testable.

REGISTRY_PATH = REPO_ROOT / "skills" / "hook-kit" / "hook-registry.yaml"


def load_committed_registry():
    yaml = pytest.importorskip("yaml", reason="PyYAML not installed")
    if not REGISTRY_PATH.is_file():
        pytest.fail(f"registry missing: {REGISTRY_PATH}")
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_the_committed_registry_exists():
    assert REGISTRY_PATH.is_file(), f"{REGISTRY_PATH} — run --bootstrap"


def test_the_committed_registry_declares_the_current_schema_version():
    assert load_committed_registry()["schema_version"] == hr_schema_version()


def hr_schema_version():
    # Kept as a function so the constant has exactly one home (the CLI module),
    # without importing the CLI (which would pull in its PyYAML edge).
    return 1


def test_every_committed_entry_has_the_required_keys():
    registry = load_committed_registry()
    required = {"id", "owner_skill", "marketplace", "status"}
    missing = [
        hook.get("id", "<no id>")
        for hook in registry["hooks"]
        if not required.issubset(hook)
    ]
    assert missing == [], f"entries missing required keys: {missing}"


def test_every_committed_id_matches_the_stem_of_its_files():
    """The id IS the stem — a mismatch means dedup would silently miss a pair."""
    registry = load_committed_registry()
    bad = []
    for hook in registry["hooks"]:
        for impl in hook.get("implementations") or []:
            if hr.stem_of(impl["file"]) != hook["id"]:
                bad.append((hook["id"], impl["file"]))
    assert bad == [], f"id/stem mismatches: {bad}"


def test_the_committed_registry_is_structurally_valid():
    """Schema-shape only. Cross-checking against disk is the CLI's --check."""
    registry = load_committed_registry()
    findings = hr.validate(registry, {})
    schema_findings = [f for f in findings if f.code == "SCHEMA"]
    assert schema_findings == [], [str(f) for f in schema_findings]
