"""Recipe id resolution and Markdown rendering."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import html2text

from ica_cli.icatypes import IcaRecipe

_TAIL_DIGITS_RE = re.compile(r"-(\d+)\s*$")
_NUMERIC_ONLY_RE = re.compile(r"^\d+$")


def resolve_recipe_id(spec: str) -> int:
    """Resolve 712859, slug-712859, or full ica.se URL to numeric id."""
    s = spec.strip()
    if _NUMERIC_ONLY_RE.match(s):
        return int(s)
    if "ica.se" in s or s.startswith("http"):
        path = urlparse(s).path.rstrip("/")
        seg = path.split("/")[-1] if path else s
        m = _TAIL_DIGITS_RE.search(seg)
        if not m:
            raise ValueError(f"Could not parse recipe id from URL: {spec!r}")
        return int(m.group(1))
    m = _TAIL_DIGITS_RE.search(s)
    if not m:
        raise ValueError(
            f"Expected numeric id or slug ending with -<id>: {spec!r}"
        )
    return int(m.group(1))


def recipe_to_markdown(recipe: IcaRecipe) -> str:
    """Turn IcaRecipe JSON into readable Markdown."""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_links = False
    lines: list[str] = []
    title = recipe.get("Title") or "Recipe"
    lines.append(f"# {title}")
    lines.append("")
    meta: list[str] = []
    if recipe.get("Portions") is not None:
        meta.append(f"Portions: {recipe['Portions']}")
    if recipe.get("CookingTime"):
        meta.append(f"Time: {recipe['CookingTime']}")
    if recipe.get("Difficulty"):
        meta.append(f"Difficulty: {recipe['Difficulty']}")
    if meta:
        lines.append(" | ".join(meta))
        lines.append("")
    preamble = recipe.get("PreambleHTML")
    if preamble:
        lines.append(h.handle(preamble).strip())
        lines.append("")
    for group in recipe.get("IngredientGroups") or []:
        gname = group.get("GroupName")
        if gname:
            lines.append(f"## {gname}")
        ing = group.get("Ingredients")
        if ing:
            text = h.handle(ing).strip()
            lines.append(text)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def json_safe_recipe(recipe: IcaRecipe) -> dict[str, Any]:
    """Recipe dict for JSON output (already JSON-serializable)."""
    return dict(recipe)
