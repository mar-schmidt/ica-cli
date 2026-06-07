#!/usr/bin/env python3
"""Generate .agent/skill.json from .agent/SKILL.md frontmatter."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: PyYAML. Install with `pip install pyyaml`."
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = ROOT / ".agent" / "SKILL.md"
SKILL_JSON = ROOT / ".agent" / "skill.json"
ENTRYPOINT = "ica"

COMMANDS = [
    "login account",
    "login elevated",
    "logout",
    "logout account",
    "logout elevated",
    "list ls",
    "list show",
    "list create",
    "list add",
    "list check",
    "list uncheck",
    "list remove",
    "list delete",
    "recipe get",
    "recipe favorites",
    "product search",
    "cart show",
    "cart keepalive",
    "cart add",
    "cart remove",
]

REQUIRED_KEYS = ["name", "version", "description", "compatibility"]
NAME_PATTERN = re.compile(
    r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$",
)


def parse_frontmatter(markdown_text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---\n", markdown_text, flags=re.S)
    if not match:
        raise ValueError("Could not find YAML frontmatter in SKILL.md")
    parsed = yaml.safe_load(match.group(1))
    if not isinstance(parsed, dict):
        raise ValueError("Frontmatter must parse to a YAML mapping")
    return parsed


def validate_frontmatter(frontmatter: dict) -> None:
    missing = [key for key in REQUIRED_KEYS if key not in frontmatter]
    if missing:
        raise ValueError(f"Missing required frontmatter keys: {missing}")

    name = str(frontmatter.get("name", ""))
    if not NAME_PATTERN.match(name):
        raise ValueError(
            "Invalid `name`: use kebab-case [a-z0-9-], max 64 chars.",
        )

    description = str(frontmatter.get("description", ""))
    if not description:
        raise ValueError("Invalid `description`: must not be empty.")
    if len(description) > 1024:
        raise ValueError("Invalid `description`: max length is 1024 chars.")
    if "<" in description or ">" in description:
        raise ValueError("Invalid `description`: do not use < or >.")

    compatibility = frontmatter.get("compatibility")
    if isinstance(compatibility, list):
        compatibility = [str(item) for item in compatibility]
    elif isinstance(compatibility, str):
        compatibility = [compatibility]
    else:
        raise ValueError("Invalid `compatibility`: use string or list.")
    if not compatibility:
        raise ValueError("Invalid `compatibility`: must not be empty.")


def build_manifest(frontmatter: dict) -> dict:
    compatibility = frontmatter["compatibility"]
    if isinstance(compatibility, str):
        compatibility = [compatibility]
    else:
        compatibility = [str(item) for item in compatibility]

    return {
        "name": str(frontmatter["name"]),
        "version": str(frontmatter["version"]),
        "schemaVersion": "1",
        "description": str(frontmatter["description"]),
        "source": (
            "https://raw.githubusercontent.com/mar-schmidt/ica-cli/master/"
            ".agent/SKILL.md"
        ),
        "install": frontmatter.get("install", {}),
        "entrypoint": ENTRYPOINT,
        "commands": COMMANDS,
        "compatibility": compatibility,
    }


def main() -> int:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"Missing skill file: {SKILL_MD}")
    frontmatter = parse_frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    validate_frontmatter(frontmatter)
    manifest = build_manifest(frontmatter)
    SKILL_JSON.parent.mkdir(parents=True, exist_ok=True)
    SKILL_JSON.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {SKILL_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
