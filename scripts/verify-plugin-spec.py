#!/usr/bin/env python3
"""
verify-plugin-spec.py -- Agent Plugins Specification v1.0.0 conformance linter.

Duplicated identically across es6kr/skills and es6kr/claude-plugins (this
workspace's established duplicate-copy-plus-test policy for cross-repo
scripts with no shared package to import from -- same pattern as the
plane_create_issue.py pair; see the 2026-08-20 Fable audit's "linter dual
implementation drift" revision). Keep both copies byte-identical when
touching this file.

Validates every plugin.json this repo's .claude-plugin/marketplace.json
references against the canonical Agent Plugins v1.0.0 schema (a pinned
fixture under fixtures/ -- no network fetch, so CI stays offline-safe and
supply-chain-clean), plus three invariants the spec's JSON Schema doesn't
encode but this workspace requires:
  - a root plugin.json's .claude-plugin/plugin.json mirror (if present) must
    stay byte-identical to it (root is canonical, the mirror is a
    Claude-Code-compat copy)
  - each plugin.json's version must match its marketplace.json entry's
    version (the exact 0.1.0-vs-0.1.1 drift class this linter exists to
    catch)
  - a marketplace.json entry's "source" path must stay within the repo root
    (no ../ escape) AND must resolve to a directory that actually exists on
    disk -- a stale entry left over from a plugin that moved/was deleted
    without its marketplace.json entry being cleaned up is caught here, not
    silently skipped (this is deliberately stricter than the "manifest not
    written yet" skip below: a missing directory is never valid, a missing
    plugin.json inside an existing directory can be, during migration)
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "fixtures" / "plugin.schema.1.0.0.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

NAME_RE = re.compile(r'^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$')
ALLOWED_TOP_LEVEL_KEYS = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}
CANONICAL_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def validate_manifest(data: dict, path: str) -> list:
    """Hand-rolled validation against the pinned schema's constraints (this
    repo's scripts are stdlib-only, no jsonschema dependency). Returns a list
    of error strings; empty means valid."""
    errors = []
    if not isinstance(data, dict):
        return [f"{path}: manifest root must be a JSON object"]

    if "$schema" not in data:
        errors.append(f"{path}: missing required field '$schema'")
    elif data["$schema"] != CANONICAL_SCHEMA_URL:
        errors.append(f"{path}: '$schema' must be {CANONICAL_SCHEMA_URL!r}, got {data['$schema']!r}")

    if "name" not in data:
        errors.append(f"{path}: missing required field 'name'")
    else:
        name = data["name"]
        if not isinstance(name, str) or not (1 <= len(name) <= 64) or not NAME_RE.match(name):
            errors.append(
                f"{path}: 'name' {name!r} violates spec pattern "
                "(1-64 chars, lowercase alphanumeric/./-, no leading/trailing '-', no '--' or '..')"
            )

    for str_field in ("version", "description", "homepage", "repository", "license"):
        if str_field in data and not isinstance(data[str_field], str):
            errors.append(f"{path}: field '{str_field}' must be a string, got {type(data[str_field]).__name__}")

    if "author" in data:
        author = data["author"]
        if not isinstance(author, dict):
            errors.append(f"{path}: field 'author' must be an object, got {type(author).__name__}")
        else:
            allowed_author_keys = {"name", "email", "url"}
            extra_author_keys = set(author.keys()) - allowed_author_keys
            if extra_author_keys:
                errors.append(f"{path}: 'author' contains unexpected key(s): {sorted(extra_author_keys)}")
            for key in allowed_author_keys:
                if key in author and not isinstance(author[key], str):
                    errors.append(f"{path}: author.{key} must be a string, got {type(author[key]).__name__}")

    if "keywords" in data:
        keywords = data["keywords"]
        if not isinstance(keywords, list):
            errors.append(f"{path}: field 'keywords' must be an array of strings, got {type(keywords).__name__}")
        else:
            for idx, item in enumerate(keywords):
                if not isinstance(item, str):
                    errors.append(f"{path}: keywords[{idx}] must be a string, got {type(item).__name__}")

    if "extensions" in data:
        extensions = data["extensions"]
        if not isinstance(extensions, dict):
            errors.append(f"{path}: field 'extensions' must be an object, got {type(extensions).__name__}")
        else:
            for key, val in extensions.items():
                if not isinstance(val, dict):
                    errors.append(f"{path}: extensions.{key} must be an object, got {type(val).__name__}")

    extra_keys = set(data.keys()) - ALLOWED_TOP_LEVEL_KEYS
    if extra_keys:
        errors.append(f"{path}: unexpected top-level key(s) outside the closed manifest: {sorted(extra_keys)}")
    return errors


def check_dual_manifest_equality(canonical_path: Path, mirror_path: Path) -> list:
    if not mirror_path.exists():
        return []
    if canonical_path.read_bytes() != mirror_path.read_bytes():
        return [f"{mirror_path}: drifted from canonical {canonical_path} -- must stay byte-identical"]
    return []


def check_version_matches_marketplace(manifest: dict, entry: dict, plugin_json_path: Path) -> list:
    manifest_version = manifest.get("version")
    entry_version = entry.get("version")
    if manifest_version != entry_version:
        return [
            f"{plugin_json_path}: version {manifest_version!r} does not match "
            f"marketplace.json entry {entry.get('name')!r} version {entry_version!r}"
        ]
    return []


def check_path_containment(entry: dict) -> list:
    """A marketplace.json entry's "source" must resolve inside the repo
    root -- a ../ escape would let a plugin declare files outside this repo
    as part of its package."""
    source = entry.get("source", "./")
    resolved = (REPO_ROOT / source).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError:
        return [f"marketplace.json entry {entry.get('name')!r}: source {source!r} escapes the repo root"]
    return []


def check_source_directory_exists(entry: dict) -> list:
    """A marketplace.json entry's "source" directory must exist on disk --
    unlike a missing plugin.json (which can mean "not migrated to a
    standalone manifest yet"), a missing directory means the entry itself is
    stale (its plugin moved or was deleted and the catalog wasn't updated)."""
    source = entry.get("source", "./")
    resolved = (REPO_ROOT / source).resolve()
    if not resolved.is_dir():
        return [f"marketplace.json entry {entry.get('name')!r}: source {source!r} does not exist on disk"]
    return []


def iter_marketplace_entries():
    marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
    return marketplace.get("plugins", [])


def main() -> int:
    errors = []
    checked = 0
    for entry in iter_marketplace_entries():
        errors.extend(check_path_containment(entry))
        errors.extend(check_source_directory_exists(entry))

        source = entry.get("source", "./")
        plugin_dir = (REPO_ROOT / source).resolve()
        plugin_json_path = plugin_dir / "plugin.json"
        if not plugin_json_path.exists():
            # Not every marketplace entry has a standalone manifest yet --
            # this linter enforces conformance for manifests that exist, it
            # doesn't mandate every entry have one (a separate migration item).
            continue

        checked += 1
        manifest = json.loads(plugin_json_path.read_text(encoding="utf-8"))
        rel_path = str(plugin_json_path.relative_to(REPO_ROOT))
        errors.extend(validate_manifest(manifest, rel_path))
        errors.extend(check_version_matches_marketplace(manifest, entry, plugin_json_path))

        if plugin_dir == REPO_ROOT:
            mirror_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
            errors.extend(check_dual_manifest_equality(plugin_json_path, mirror_path))

    if errors:
        for e in errors:
            print(f"[verify-plugin-spec] FAIL: {e}", file=sys.stderr)
        return 1

    print(f"[verify-plugin-spec] OK: {checked} plugin.json manifest(s) conform to Agent Plugins v1.0.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
