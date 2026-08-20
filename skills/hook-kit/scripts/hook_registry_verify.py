#!/usr/bin/env python3
"""Bootstrap and verify `skills/hook-kit/hook-registry.yaml`.

    # regenerate the draft from what is actually registered and on disk
    uv run --with pyyaml python skills/hook-kit/scripts/hook_registry_verify.py \
        --bootstrap --plugins-root ~/ghq/github.com/es6kr/claude-plugins

    # cross-check the committed registry against hooks.json + disk
    uv run --with pyyaml python skills/hook-kit/scripts/hook_registry_verify.py --check

`--bootstrap` derives each entry's status from observation rather than trusting
a declaration:

    registered + file present  -> active
    registered + file missing  -> orphan   (exits 127; reads as "no objection")
    file present, unregistered -> dormant

Existing `status: removed` entries are carried over untouched. Tombstones are
the one thing bootstrap must never regenerate away — a removal record that a
rescan can erase is not a record.

The validation logic lives in `hook_registry.py`, which is import-safe and
dependency-free so the test suite needs no packages. PyYAML is required here
and only here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hook_registry as hr  # noqa: E402

DEFAULT_REGISTRY = os.path.join("skills", "hook-kit", "hook-registry.yaml")
SCHEMA_VERSION = 1

MARKETPLACES = (
    ("es6kr-skills", None),  # root filled in from --repo-root
    ("es6kr-plugins", None),  # root filled in from --plugins-root
)


def _require_yaml():
    try:
        import yaml  # noqa: PLC0415
    except ImportError:  # pragma: no cover - environment guard
        sys.exit(
            "PyYAML is required for this command.\n"
            "  uv run --with pyyaml python "
            "skills/hook-kit/scripts/hook_registry_verify.py ..."
        )
    return yaml


def load_hooks_json(root: str) -> dict:
    path = os.path.join(root, "hooks", "hooks.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def collect(root: str, marketplace: str) -> tuple[list[dict], set[str]]:
    registrations = hr.parse_registrations(
        load_hooks_json(root), surface="hooks.json", marketplace=marketplace
    )
    return registrations, hr.scan_resources(root, marketplace)


def build_entries(roots: dict[str, str]) -> tuple[list[dict], dict[str, set[str]]]:
    entries: list[dict] = []
    disk_index: dict[str, set[str]] = {}

    for marketplace, root in roots.items():
        registrations, present = collect(root, marketplace)
        disk_index[marketplace] = present

        by_id: dict[str, dict] = {}
        for reg in registrations:
            slot = by_id.setdefault(
                reg["id"], {"registrations": [], "files": set(), "owners": set()}
            )
            slot["registrations"].append(
                {
                    "surface": reg["surface"],
                    "event": reg["event"],
                    "matcher": reg["matcher"],
                    "command": reg["command"],
                    **({"timeout": reg["timeout"]} if reg["timeout"] else {}),
                }
            )
            slot["files"].add(reg["file"])
            owner = hr.owner_skill_of(reg["file"])
            if owner:
                slot["owners"].add(owner)

        for rel in present:
            slot = by_id.setdefault(
                hr.stem_of(rel), {"registrations": [], "files": set(), "owners": set()}
            )
            slot["files"].add(rel)
            owner = hr.owner_skill_of(rel)
            if owner:
                slot["owners"].add(owner)

        for hook_id, slot in sorted(by_id.items()):
            on_disk = {f for f in slot["files"] if f in present}
            if slot["registrations"]:
                status = "active" if on_disk else "orphan"
            else:
                status = "dormant"
            # Prefer the owner of a file that actually exists; a registration
            # pointing at a vanished path would otherwise name a stale owner.
            owners = sorted(
                {hr.owner_skill_of(f) for f in (on_disk or slot["files"])} - {None}
            )
            entries.append(
                {
                    "id": hook_id,
                    "owner_skill": owners[0] if owners else "unknown",
                    "marketplace": marketplace,
                    "status": status,
                    "implementations": [
                        {"runtime": hr.runtime_of(f), "file": f}
                        for f in sorted(slot["files"])
                    ],
                    "registrations": slot["registrations"],
                }
            )

    return entries, disk_index


def merge_tombstones(entries: list[dict], existing: dict) -> list[dict]:
    """Carry `status: removed` entries forward; a rescan must not erase them."""
    keep = [
        hook
        for hook in existing.get("hooks") or []
        if isinstance(hook, dict) and hook.get("status") == "removed"
    ]
    live_keys = {(h["id"], h["marketplace"]) for h in entries}
    merged = list(entries)
    for hook in keep:
        key = (hook.get("id"), hook.get("marketplace"))
        if key in live_keys:
            # A tombstoned hook came back. Keep the tombstone so validate()
            # reports TOMBSTONE_REINTRODUCED instead of quietly overwriting it.
            merged = [h for h in merged if (h["id"], h["marketplace"]) != key]
        merged.append(hook)
    return sorted(merged, key=lambda h: (h.get("marketplace", ""), h.get("id", "")))


def load_registry(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    yaml = _require_yaml()
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def write_registry(path: str, registry: dict) -> None:
    yaml = _require_yaml()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            "# Generated by skills/hook-kit/scripts/hook_registry_verify.py "
            "--bootstrap\n"
            "# Status is derived from observation, not declaration. Tombstones\n"
            "# (status: removed) are hand-written and survive regeneration.\n"
        )
        yaml.safe_dump(
            registry, fh, sort_keys=False, allow_unicode=True, width=100
        )


def report(findings: list) -> int:
    if not findings:
        print("registry: no findings")
        return 0
    by_code: dict[str, list] = {}
    for finding in findings:
        by_code.setdefault(finding.code, []).append(finding)
    for code in sorted(by_code):
        group = by_code[code]
        print(f"\n{code} ({len(group)})")
        for finding in sorted(group, key=lambda f: f.hook_id)[:40]:
            print(f"  - {finding.hook_id}: {finding.detail}")
        if len(group) > 40:
            print(f"  ... and {len(group) - 40} more")
    print(f"\ntotal findings: {len(findings)}")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--plugins-root",
        default=os.path.expanduser("~/ghq/github.com/es6kr/claude-plugins"),
        help="checkout of the es6kr-plugins marketplace",
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="with --bootstrap, print instead of write"
    )
    args = parser.parse_args(argv)

    if not (args.bootstrap or args.check):
        parser.error("pass --bootstrap, --check, or both")

    roots = {
        "es6kr-skills": args.repo_root,
        "es6kr-plugins": args.plugins_root,
    }
    missing_root = [m for m, r in roots.items() if not os.path.isdir(r)]
    if missing_root:
        print(
            f"warning: marketplace root not found, skipping: {missing_root}",
            file=sys.stderr,
        )
        roots = {m: r for m, r in roots.items() if os.path.isdir(r)}

    registry_path = os.path.join(args.repo_root, args.registry)
    exit_code = 0

    if args.bootstrap:
        entries, disk_index = build_entries(roots)
        merged = merge_tombstones(entries, load_registry(registry_path))
        registry = {"schema_version": SCHEMA_VERSION, "hooks": merged}
        counts: dict[str, int] = {}
        for hook in merged:
            counts[hook["status"]] = counts.get(hook["status"], 0) + 1
        print(
            f"bootstrap: {len(merged)} hooks — "
            + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        )
        if args.dry_run:
            print(f"(dry run — would write {registry_path})")
        else:
            write_registry(registry_path, registry)
            print(f"wrote {registry_path}")
        if args.check:
            exit_code = report(hr.validate(registry, disk_index))
        return exit_code

    registry = load_registry(registry_path)
    if not registry:
        print(f"no registry at {registry_path} — run --bootstrap first", file=sys.stderr)
        return 2
    disk_index = {m: hr.scan_resources(r, m) for m, r in roots.items()}
    return report(hr.validate(registry, disk_index))


if __name__ == "__main__":
    raise SystemExit(main())
