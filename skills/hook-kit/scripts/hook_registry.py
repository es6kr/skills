"""Hook registry core: derive registrations from hooks.json, validate a registry.

The registry's first-class key is a hook's *logical identity* — its basename
with the extension stripped — not its file path. That single choice is what
lets the schema tell three things apart that a path- or basename-comparison
collapses into one bucket:

- the same guard registered in both marketplaces (fires twice per trigger)
- a `.sh` that was rewritten as `.js` (one guard, two runtimes, migration history)
- both of those runtimes left registered at once (fires twice again)

Everything here operates on plain dicts and is import-safe with no third-party
packages, so the test suite runs under the repo's `uvx --from pytest pytest
tests` invocation. YAML reading/writing lives in the CLI wrapper
(`hook_registry_verify.py`), which is the only place a PyYAML import appears.

Schema (see plan-hook-registry-schema.md §2):

    schema_version: 1
    hooks:
      - id: <stem>                      # basename without extension
        owner_skill: <skill dir name>
        marketplace: es6kr-skills | es6kr-plugins | user-settings | antigravity
        status: active | dormant | orphan | removed
        implementations: [{runtime, file, since?, until?, note?}]
        registrations:   [{surface, event, matcher, command, timeout?}]
        description: <str>
        tombstone: {removed_at, reason, detail, replacement?}   # status: removed
"""

from __future__ import annotations

import os
import posixpath
import re

PLUGIN_ROOT_MARKER = "${CLAUDE_PLUGIN_ROOT}/"

VALID_STATUSES = frozenset({"active", "dormant", "orphan", "removed"})
VALID_MARKETPLACES = frozenset(
    {"es6kr-skills", "es6kr-plugins", "user-settings", "antigravity"}
)

# Runtimes that mean "this file is a thin wrapper that execs a sibling", vs the
# implementations it would exec. A wrapper and its implementation must live in
# the same skill; a relocation that splits them silently breaks the exec path.
WRAPPER_RUNTIMES = frozenset({"sh"})
IMPL_RUNTIMES = frozenset({"py", "js"})

_EXT_RUNTIME = {
    ".sh": "sh",
    ".bash": "sh",
    ".py": "py",
    ".js": "js",
    ".mjs": "js",
    ".cjs": "js",
}


class Finding:
    """A single validation failure, addressed to a hook id."""

    __slots__ = ("code", "hook_id", "detail")

    def __init__(self, code: str, hook_id: str, detail: str) -> None:
        self.code = code
        self.hook_id = hook_id
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Finding({self.code!r}, {self.hook_id!r}, {self.detail!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Finding):
            return NotImplemented
        return (self.code, self.hook_id, self.detail) == (
            other.code,
            other.hook_id,
            other.detail,
        )

    def __hash__(self) -> int:
        return hash((self.code, self.hook_id, self.detail))


# --- derivation -------------------------------------------------------------


def stem_of(path: str) -> str:
    """Logical identity of a hook file: basename minus extension."""
    base = posixpath.basename(str(path).replace("\\", "/"))
    root, ext = posixpath.splitext(base)
    # Only strip extensions we recognise, so a dotted name like `a.b` that is
    # not a known runtime keeps its full basename as its identity.
    return root if ext.lower() in _EXT_RUNTIME else base


def runtime_of(path: str) -> str:
    base = posixpath.basename(str(path).replace("\\", "/"))
    _, ext = posixpath.splitext(base)
    return _EXT_RUNTIME.get(ext.lower(), "other")


def owner_skill_of(path: str) -> str | None:
    """`skills/<owner>/resources/x.sh` -> `<owner>`; None when unrecognised."""
    parts = str(path).replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "skills":
        return parts[1]
    return None


_TOKEN_SPLIT = re.compile(r"[\s\"']+")


def iter_command_paths(command: str):
    """Yield every plugin-root-relative path referenced by a command string.

    Commands appear bare, quoted, and interpreter-prefixed
    (`bash "${CLAUDE_PLUGIN_ROOT}/..."`, `python3 ${CLAUDE_PLUGIN_ROOT}/...`),
    so tokenise on whitespace and quotes rather than assuming a shape.
    """
    for token in _TOKEN_SPLIT.split(command):
        if PLUGIN_ROOT_MARKER in token:
            yield token.split(PLUGIN_ROOT_MARKER, 1)[1]


def parse_registrations(hooks_json: dict, surface: str, marketplace: str) -> list[dict]:
    """Flatten a hooks.json document into one record per (file, event, matcher)."""
    out: list[dict] = []
    events = hooks_json.get("hooks", hooks_json)
    if not isinstance(events, dict):
        return out
    for event, groups in events.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher", "")
            for hook in group.get("hooks", []) or []:
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command")
                if not isinstance(command, str):
                    continue
                for rel in iter_command_paths(command):
                    out.append(
                        {
                            "surface": surface,
                            "marketplace": marketplace,
                            "event": event,
                            "matcher": matcher,
                            "command": command,
                            "file": rel,
                            "id": stem_of(rel),
                            "timeout": hook.get("timeout"),
                        }
                    )
    return out


def scan_resources(root: str, marketplace: str) -> set[str]:
    """Repo-relative paths of every hook script under `skills/*/resources/`."""
    found: set[str] = set()
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return found
    for skill in sorted(os.listdir(skills_dir)):
        resources = os.path.join(skills_dir, skill, "resources")
        if not os.path.isdir(resources):
            continue
        for name in sorted(os.listdir(resources)):
            if runtime_of(name) == "other":
                continue
            found.add(f"skills/{skill}/resources/{name}")
    return found


# --- validation -------------------------------------------------------------


def _files_of(hook: dict) -> list[str]:
    return [
        impl.get("file", "")
        for impl in hook.get("implementations") or []
        if isinstance(impl, dict) and impl.get("file")
    ]


def _is_superseded(impl: dict) -> bool:
    """An implementation retired by a later migration step."""
    return bool(impl.get("until"))


def _check_schema(hook: dict, seen: dict, findings: list) -> bool:
    """Structural checks. Returns False when the entry is too broken to inspect."""
    hook_id = hook.get("id")
    if not hook_id:
        findings.append(Finding("SCHEMA", "<missing id>", "entry has no id"))
        return False

    status = hook.get("status")
    if status not in VALID_STATUSES:
        findings.append(
            Finding(
                "SCHEMA",
                hook_id,
                f"status {status!r} is not one of {sorted(VALID_STATUSES)}",
            )
        )

    marketplace = hook.get("marketplace")
    if marketplace not in VALID_MARKETPLACES:
        findings.append(
            Finding(
                "SCHEMA",
                hook_id,
                f"marketplace {marketplace!r} is not one of {sorted(VALID_MARKETPLACES)}",
            )
        )

    key = (hook_id, marketplace)
    if key in seen:
        findings.append(
            Finding(
                "SCHEMA",
                hook_id,
                f"duplicate entry for id in marketplace {marketplace!r} — "
                "one entry per (id, marketplace)",
            )
        )
    seen[key] = True

    if status == "removed" and not hook.get("tombstone"):
        findings.append(
            Finding(
                "SCHEMA",
                hook_id,
                "status: removed requires a tombstone block — deletion records "
                "are preserved, not dropped",
            )
        )

    return True


def _check_tombstone(hook: dict, present: set[str], findings: list) -> None:
    hook_id = hook["id"]
    reappeared = [f for f in _files_of(hook) if f in present]
    if reappeared:
        findings.append(
            Finding(
                "TOMBSTONE_REINTRODUCED",
                hook_id,
                "removed hook is back on disk: " + ", ".join(sorted(reappeared)),
            )
        )
    if hook.get("registrations"):
        findings.append(
            Finding(
                "TOMBSTONE_REINTRODUCED",
                hook_id,
                "removed hook still has registrations",
            )
        )


def _check_registrations(hook: dict, present: set[str], findings: list) -> None:
    hook_id = hook["id"]
    regs = hook.get("registrations") or []

    missing = sorted({r.get("file") or "" for r in regs} - present - {""})
    # Registrations carry a command, not always a parsed file; derive when absent.
    derived_missing = set()
    for reg in regs:
        files = list(iter_command_paths(reg.get("command", ""))) or (
            [reg["file"]] if reg.get("file") else []
        )
        for rel in files:
            if rel not in present:
                derived_missing.add(rel)
    for rel in sorted(derived_missing.union(missing)):
        findings.append(
            Finding(
                "ORPHAN_REGISTRATION",
                hook_id,
                f"registered script is not on disk: {rel} — it exits 127, which "
                "reads to the harness as 'the guard had no objection'",
            )
        )

    slots: dict[tuple, int] = {}
    for reg in regs:
        slot = (reg.get("surface"), reg.get("event"), reg.get("matcher"))
        slots[slot] = slots.get(slot, 0) + 1
    for slot, count in sorted(slots.items(), key=lambda kv: str(kv[0])):
        if count > 1:
            findings.append(
                Finding(
                    "DUPLICATE_REGISTRATION",
                    hook_id,
                    f"{count} registrations share {slot} — the guard fires "
                    f"{count} times per trigger",
                )
            )

    registered_runtimes = set()
    for reg in regs:
        paths = list(iter_command_paths(reg.get("command", "")))
        if not paths and reg.get("file"):
            paths = [reg["file"]]
        for rel in paths:
            registered_runtimes.add(runtime_of(rel))
    if len(registered_runtimes - {"other"}) > 1:
        findings.append(
            Finding(
                "DOUBLE_FIRING_MIGRATION",
                hook_id,
                "two runtimes of the same hook are registered simultaneously "
                f"({sorted(registered_runtimes)}) — a migration must retire the "
                "old one, not run both",
            )
        )

    declared = hook.get("status")
    if declared == "active" and not regs:
        findings.append(
            Finding(
                "STATUS_MISMATCH",
                hook_id,
                "status: active but nothing is registered — declare it dormant "
                "or register it",
            )
        )
    if declared == "dormant" and regs:
        findings.append(
            Finding(
                "STATUS_MISMATCH",
                hook_id,
                "status: dormant but registrations exist",
            )
        )


def _check_wrapper_pairing(hook: dict, findings: list) -> None:
    """A `.sh` wrapper and the implementation it execs must share a skill.

    Splitting them is what turned a relocation into a hard block on every
    Edit/Write: the wrapper kept exec'ing a sibling path that no longer held
    the implementation. A superseded (`until:`) entry is migration history, not
    a live exec pair, so it is excluded.
    """
    live = [
        impl
        for impl in hook.get("implementations") or []
        if isinstance(impl, dict) and impl.get("file") and not _is_superseded(impl)
    ]
    wrappers = [i for i in live if runtime_of(i["file"]) in WRAPPER_RUNTIMES]
    impls = [i for i in live if runtime_of(i["file"]) in IMPL_RUNTIMES]
    if not wrappers or not impls:
        return
    for wrapper in wrappers:
        for impl in impls:
            w_owner = owner_skill_of(wrapper["file"])
            i_owner = owner_skill_of(impl["file"])
            if w_owner != i_owner:
                findings.append(
                    Finding(
                        "WRAPPER_IMPL_SPLIT",
                        hook["id"],
                        f"wrapper {wrapper['file']} and implementation "
                        f"{impl['file']} live in different skills — the wrapper "
                        "execs a sibling path that does not exist",
                    )
                )


def _check_dual_marketplace(hooks: list, findings: list) -> None:
    by_id: dict[str, set] = {}
    for hook in hooks:
        if hook.get("status") == "removed" or not hook.get("registrations"):
            continue
        hook_id = hook.get("id")
        if not hook_id:
            continue
        by_id.setdefault(hook_id, set()).add(hook.get("marketplace"))

    for hook_id, marketplaces in sorted(by_id.items()):
        if len(marketplaces) > 1:
            findings.append(
                Finding(
                    "DUAL_MARKETPLACE",
                    hook_id,
                    "live in more than one marketplace "
                    f"({sorted(str(m) for m in marketplaces)}) — it fires once "
                    "per marketplace, and the two copies drift apart",
                )
            )


def validate(registry: dict, disk_index: dict) -> list[Finding]:
    """Cross-check a registry against what is actually on disk.

    `disk_index` maps a marketplace name to the set of repo-relative script
    paths present in it.
    """
    findings: list[Finding] = []
    hooks = registry.get("hooks") or []
    seen: dict = {}

    for hook in hooks:
        if not isinstance(hook, dict):
            findings.append(Finding("SCHEMA", "<non-mapping>", repr(hook)[:80]))
            continue
        if not _check_schema(hook, seen, findings):
            continue

        present = set(disk_index.get(hook.get("marketplace"), ()) or ())

        if hook.get("status") == "removed":
            _check_tombstone(hook, present, findings)
            continue

        _check_registrations(hook, present, findings)
        _check_wrapper_pairing(hook, findings)

    _check_dual_marketplace(
        [h for h in hooks if isinstance(h, dict)],
        findings,
    )
    return findings
