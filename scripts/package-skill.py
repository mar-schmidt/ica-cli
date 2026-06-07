#!/usr/bin/env python3
"""Package the .agent skill folder into a .skill archive."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agent"
OUTPUT_DIR = ROOT / "dist"
OUTPUT_FILE = OUTPUT_DIR / "ica-cli.skill"

INCLUDE_NAMES = {
    "SKILL.md",
    "skill.json",
    "examples",
    "references",
    "scripts",
    "assets",
}


def ensure_manifest() -> None:
    script = ROOT / "scripts" / "generate-skill-manifest.py"
    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        check=True,
    )


def iter_included_files() -> list[Path]:
    if not SKILL_DIR.exists():
        raise FileNotFoundError(f"Missing skill directory: {SKILL_DIR}")
    skill_md = SKILL_DIR / "SKILL.md"
    skill_json = SKILL_DIR / "skill.json"
    if not skill_md.exists():
        raise FileNotFoundError(f"Missing required file: {skill_md}")
    if not skill_json.exists():
        raise FileNotFoundError(f"Missing required file: {skill_json}")

    files: list[Path] = []
    for path in sorted(SKILL_DIR.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(SKILL_DIR)
        top = rel.parts[0]
        if top not in INCLUDE_NAMES:
            continue
        files.append(path)
    return files


def build_archive(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = iter_included_files()
    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as zf:
        for file_path in files:
            rel = file_path.relative_to(SKILL_DIR)
            zip_info = zipfile.ZipInfo(str(rel))
            zip_info.date_time = (2024, 1, 1, 0, 0, 0)
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            zip_info.external_attr = 0o644 << 16
            zf.writestr(zip_info, file_path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help="Output .skill file path.",
    )
    args = parser.parse_args()
    ensure_manifest()
    output = Path(args.output).expanduser().resolve()
    build_archive(output)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
