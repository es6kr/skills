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
from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillSpector:
    """Linter and security auditor for skills."""

    # Security rule regexes
    SEC_01_PIPE_SHELL = re.compile(
        r"(?:curl|wget)\s+[^\n|]+\|\s*(?:ba)?sh", re.IGNORECASE
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

    def scan_skill(self, skill_path: str) -> Dict[str, Any]:
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

        content = skill_file.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = self._parse_frontmatter(content)

        if frontmatter is None:
            errors.append("Invalid or missing YAML frontmatter in SKILL.md")
        else:
            self._validate_frontmatter(frontmatter, errors, warnings)

        self._check_security(content, errors, warnings)

        # Also check other .md files in skill_dir for security issues
        if skill_dir.is_dir():
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

    def _parse_frontmatter(self, content: str) -> tuple[Optional[Dict[str, Any]], str]:
        """Parse frontmatter without external yaml dependency."""
        if not content.startswith("---"):
            return None, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None, content

        fm_text = parts[1]
        body = parts[2]

        fm_dict: Dict[str, Any] = {}
        current_key: Optional[str] = None
        current_dict: Optional[Dict[str, Any]] = None

        for line in fm_text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            if line.startswith("  ") and current_dict is not None and ":" in line_str:
                sub_k, sub_v = line_str.split(":", 1)
                current_dict[sub_k.strip()] = sub_v.strip()
                continue

            if ":" in line_str:
                k, v = line_str.split(":", 1)
                k = k.strip()
                v = v.strip()
                if not v:
                    current_key = k
                    current_dict = {}
                    fm_dict[k] = current_dict
                else:
                    fm_dict[k] = v
                    current_key = None
                    current_dict = None

        return fm_dict, body

    def _validate_frontmatter(
        self, fm: Dict[str, Any], errors: List[str], warnings: List[str]
    ) -> None:
        """Validate frontmatter fields according to standard."""
        name = fm.get("name")
        if not name:
            errors.append("Frontmatter missing required field 'name'")
        elif not re.match(r"^[a-zA-Z0-9_\-\.]+$", str(name)):
            errors.append(f"Frontmatter name '{name}' contains invalid characters")

        desc = fm.get("description", "")
        if not desc:
            warnings.append("Frontmatter missing recommended field 'description'")
        else:
            desc_str = str(desc)
            if len(desc_str) > 1024:
                errors.append(
                    f"Frontmatter description length ({len(desc_str)}) exceeds 1024 character limit"
                )

            # Check if topic filenames are referenced in description
            matches = self.TOPIC_FILE_REF.findall(desc_str)
            if matches:
                for match in matches:
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


def main():
    parser = argparse.ArgumentParser(
        description="SkillSpector: Static skill linter and security auditor"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Path(s) to skill directory or skills parent directory",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    linter = SkillSpector()
    results = []

    for path in args.paths:
        p = Path(path)
        if (p / "SKILL.md").exists() or (p.is_file() and p.name == "SKILL.md"):
            results.append(linter.scan_skill(str(p)))
        elif p.is_dir():
            found_skills = list(p.glob("**/SKILL.md"))
            if found_skills:
                for s in found_skills:
                    results.append(linter.scan_skill(str(s.parent)))
            else:
                results.append(linter.scan_skill(str(p)))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        total_errors = sum(len(r["errors"]) for r in results)
        total_warnings = sum(len(r["warnings"]) for r in results)
        print(f"SkillSpector scanned {len(results)} skill(s):")
        for r in results:
            status = "✅ PASS" if r["valid"] else "❌ FAIL"
            print(f"\n{status}: {r['skill']}")
            for err in r["errors"]:
                print(f"  ❌ Error: {err}")
            for warn in r["warnings"]:
                print(f"  ⚠️ Warning: {warn}")

        print(f"\nSummary: {total_errors} error(s), {total_warnings} warning(s)")
        if total_errors > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
