#!/usr/bin/env python3
"""SkillSpector: Static linter and security scanner for Claude Code and Antigravity skills.

Implements structural validation (frontmatter, description length, topic references)
and security auditing (pipe to bash, hardcoded secrets, unconstrained deletion, prompt injection).
"""

import argparse
import json
import os
import re
import sys
import subprocess

try:
    import yaml
except ImportError:
    yaml = None
from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillSpector:
    """Linter and security auditor for skills."""

    # Security rule regexes
    SEC_01_PIPE_SHELL = re.compile(
        r"(?:curl|wget)\s+[^\n|]+\|\s*(?:\S*/)?(?:env\s+)?(?:ba)?sh\b", re.IGNORECASE
    )
    SEC_02_SECRETS = re.compile(
        r"(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{82}|AKIA[0-9A-Z]{16}|bearer\s+[a-zA-Z0-9_\-\.]{20,})",
        re.IGNORECASE,
    )
    SEC_03_UNCONSTRAINED_RM = re.compile(
        r"rm\s+-(?:rf|fr|r)\s+(?:/|/\*|~|~/\*|\$HOME|\$ROOT)(?:\s|$)", re.IGNORECASE
    )
    SEC_05_PROMPT_INJECTION = re.compile(
        r"(?:ignore\s+all\s+previous\s+instructions|disregard\s+all\s+prior\s+instructions|system\s+prompt\s+override)",
        re.IGNORECASE,
    )
    TOPIC_FILE_REF = re.compile(r"\[[a-zA-Z0-9_\-]+\.md\]|\b[a-zA-Z0-9_\-]+\.md\b")

    def __init__(self):
        pass

    def scan_skill(self, skill_path: str, *, metadata_only=False, require_version=False) -> Dict[str, Any]:
        """Scan a skill directory or single SKILL.md file."""
        p = Path(skill_path)
        if p.is_file():
            skill_dir = p.parent
            skill_file = p
        else:
            skill_dir = p
            skill_file = p / "SKILL.md"

        errors: List[str] = []
        warnings: List[str] = []

        if not skill_file.exists():
            return {
                "skill": str(skill_dir),
                "valid": False,
                "errors": [f"SKILL.md not found in {skill_dir}"],
                "warnings": [],
            }

        try:
            content = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return {"skill": str(skill_dir), "valid": False,
                    "errors": [f"Cannot read SKILL.md: {exc}"], "warnings": []}
        frontmatter, body = self._parse_frontmatter(content)

        if frontmatter is None:
            errors.append("Invalid or missing YAML frontmatter in SKILL.md")
        else:
            self._validate_frontmatter(frontmatter, errors, warnings, metadata_only=metadata_only)
            if require_version:
                self._validate_version(content, errors)

        if not metadata_only:
            self._check_security(content, errors, warnings)

        # Also check other .md files in skill_dir for security issues
        if not metadata_only and skill_dir.is_dir():
            for other_md in skill_dir.glob("**/*.md"):
                if other_md.resolve() != skill_file.resolve():
                    other_content = other_md.read_text(encoding="utf-8", errors="replace")
                    self._check_security(other_content, errors, warnings, filename=other_md.name)

        is_valid = len(errors) == 0
        return {
            "skill": str(skill_dir),
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
        }

    FRONTMATTER = re.compile(
        r"\A---[ \t]*\r?\n(.*?)^---[ \t]*(?:\r?\n|\Z)", re.MULTILINE | re.DOTALL
    )

    def _parse_frontmatter(self, content: str) -> tuple[Optional[Dict[str, Any]], str]:
        """Use safe YAML decoding, including escapes and block-scalar chomping."""
        match = self.FRONTMATTER.match(content)
        if match is None or yaml is None:
            return None, content
        try:
            frontmatter = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None, content
        if not isinstance(frontmatter, dict):
            return None, content
        return frontmatter, content[match.end():]

    def _validate_version(self, content: str, errors: List[str]) -> None:
        """Keep the repository's double-quoted metadata.version convention."""
        match = self.FRONTMATTER.match(content)
        node = yaml.compose(match.group(1), Loader=yaml.SafeLoader)
        version = None
        for key, value in node.value:
            if key.value == "metadata" and isinstance(value, yaml.MappingNode):
                for nested_key, nested_value in value.value:
                    if nested_key.value == "version":
                        version = nested_value
        if (not isinstance(version, yaml.ScalarNode) or version.style != '"'
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version.value)):
            errors.append('metadata.version must be a double-quoted semver ("X.Y.Z")')

    def _validate_frontmatter(
        self, fm: Dict[str, Any], errors: List[str], warnings: List[str],
        *, metadata_only: bool = False
    ) -> None:
        """Validate frontmatter fields according to standard."""
        # GUARD: native repository metadata requires a scalar; standalone scans keep legacy behavior.
        if metadata_only and "allowed-tools" in fm and not isinstance(fm["allowed-tools"], str):
            errors.append("Frontmatter allowed-tools must be a string")

        name = fm.get("name")
        if not name:
            errors.append("Frontmatter missing required field 'name'")
        elif not re.match(r"^[a-zA-Z0-9_\-\.]+$", str(name)):
            errors.append(f"Frontmatter name '{name}' contains invalid characters")

        desc = fm.get("description")
        if not isinstance(desc, str) or not desc.strip():
            errors.append("Frontmatter description must be a non-empty string")
            return
        if len(desc) > 1024:
            errors.append(
                f"Frontmatter description length ({len(desc)}) exceeds 1024 character limit"
            )
        for match in self.TOPIC_FILE_REF.findall(desc):
            warnings.append(
                f"Description contains topic filename reference '{match}'. Use descriptive trigger phrases instead."
            )

    def _check_security(
        self, content: str, errors: List[str], warnings: List[str], filename: str = "SKILL.md"
    ) -> None:
        """Run security checks against markdown content."""
        if self.SEC_01_PIPE_SHELL.search(content):
            errors.append(
                f"SEC-01 (High): Dangerous shell pipe pattern detected (curl/wget | sh/bash) in {filename}"
            )

        if self.SEC_02_SECRETS.search(content):
            errors.append(
                f"SEC-02 (Critical): Potential hardcoded credential or token detected in {filename}"
            )

        if self.SEC_03_UNCONSTRAINED_RM.search(content):
            errors.append(
                f"SEC-03 (Critical): Destructive unconstrained deletion (rm -rf /) detected in {filename}"
            )

        if self.SEC_05_PROMPT_INJECTION.search(content):
            errors.append(
                f"SEC-05 (High): Instruction override or prompt injection pattern detected in {filename}"
            )


EXCLUDED_DIRECTORIES = {
    ".git", ".worktrees", "worktrees", ".workspaces", ".venv", "venv",
    "node_modules", "__pycache__", ".tmp",
}


def _excluded(parts):
    return any(part in EXCLUDED_DIRECTORIES or part.endswith(".bak") for part in parts)


def _discover_skill_files(path: Path, tracked: bool):
    """Discover root and nested skills without following unrelated worktrees."""
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    path = path.absolute()
    if tracked:
        directory = path.parent if path.is_file() else path
        root_result = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if root_result.returncode:
            raise ValueError(f"Cannot discover tracked skills outside a Git repository: {path}")
        root = Path(root_result.stdout.strip())
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "SKILL.md", "**/SKILL.md"],
            capture_output=True,
        )
        if listing.returncode:
            raise ValueError(f"Git tracked-skill discovery failed: {path}")
        for entry in listing.stdout.split(b"\0"):
            if not entry:
                continue
            relative = Path(entry.decode("utf-8"))
            candidate = root / relative
            if _excluded(relative.parts[:-1]):
                continue
            if candidate == path or path in candidate.parents:
                if not candidate.resolve().is_relative_to(root.resolve()):
                    raise ValueError(f"Tracked skill resolves outside its repository: {relative}")
                yield candidate
    elif path.is_file():
        if path.name != "SKILL.md":
            raise ValueError(f"Expected SKILL.md: {path}")
        yield path
    else:
        for directory, names, filenames in os.walk(path, followlinks=False):
            names[:] = sorted(name for name in names if not _excluded((name,)))
            if "SKILL.md" in filenames:
                yield Path(directory) / "SKILL.md"


def main():
    parser = argparse.ArgumentParser(description="SkillSpector: Static skill linter and security auditor")
    parser.add_argument("paths", nargs="*", default=["."], help="Skill file or root/nested skill tree")
    parser.add_argument("--json", action="store_true", help="Output JSON; invalid results still exit 1")
    parser.add_argument("--frontmatter-only", action="store_true", help="Validate metadata without auditing topic prose")
    parser.add_argument("--require-version", action="store_true", help="Require double-quoted metadata.version semver")
    parser.add_argument("--tracked", action="store_true", help="Restrict repository discovery to tracked SKILL.md files")
    args = parser.parse_args()
    if yaml is None:
        parser.error("PyYAML is required; see requirements-lint.txt (no automatic installation)")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    linter = SkillSpector()
    results = []
    seen = set()
    for raw in args.paths:
        path = Path(raw)
        try:
            files = sorted(_discover_skill_files(path, args.tracked))
            if not files:
                raise ValueError(f"No SKILL.md files found: {path}")
            for skill in files:
                identity = skill.resolve()
                if identity not in seen:
                    seen.add(identity)
                    results.append(linter.scan_skill(
                        str(skill), metadata_only=args.frontmatter_only,
                        require_version=args.require_version,
                    ))
        except (OSError, UnicodeError, ValueError) as exc:
            results.append({"skill": str(path), "valid": False,
                            "errors": [str(exc)], "warnings": []})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"SkillSpector scanned {len(results)} skill(s):")
        for result in results:
            status = "PASS" if result["valid"] else "FAIL"
            print(f"\n{status}: {result['skill']}")
            for error in result["errors"]:
                print(f"  Error: {error}")
            for warning in result["warnings"]:
                print(f"  Warning: {warning}")
        print(f"\nSummary: {sum(len(r['errors']) for r in results)} error(s), "
              f"{sum(len(r['warnings']) for r in results)} warning(s)")
    return 1 if any(not result["valid"] for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
