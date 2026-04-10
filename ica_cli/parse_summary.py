"""Parse free-text shopping lines (quantity, unit, name)."""

from __future__ import annotations

import logging
import re
from typing import Any

from ica_cli.const import DEFAULT_ARTICLE_GROUP_ID

_LOGGER = logging.getLogger(__name__)

# From ha-ica-todo coordinator.parse_summary
_LINE_RE = re.compile(
    r"^(?P<a>((?P<min_quantity>\d-)?(?P<quantity>[0-9,.]*)? )|(?P<b>))"
    r"(?P<unit>st|förp|kg|hg|g|l|dl|cl|ml|msk|tsk|krm)? ?(?P<name>.+)$",
)


def get_article_group(product_name: str, articles: list[dict] | None) -> int:
    """Match product name to ICA article tree parentId, or default."""
    if not articles:
        return DEFAULT_ARTICLE_GROUP_ID
    pn = product_name.casefold().strip()
    for art in articles:
        if art.get("name", "").casefold() == pn:
            return int(art.get("parentId") or DEFAULT_ARTICLE_GROUP_ID)
    return DEFAULT_ARTICLE_GROUP_ID


def parse_summary(
    summary: str,
    articles: list[dict] | None = None,
) -> dict[str, Any]:
    """Parse '2 st mjölk' into productName, quantity, unit, articleGroupId."""
    r = _LINE_RE.search(summary.strip())
    if not r:
        return {
            "summary": summary,
            "productName": summary.strip(),
            "articleGroupId": get_article_group(summary, articles),
        }
    quantity = r.group("quantity")
    unit = r.group("unit")
    product_name = (r.group("name") or "").strip() or summary
    article_group_id = get_article_group(product_name, articles)
    ti: dict[str, Any] = {
        "summary": summary,
        "productName": product_name,
        "articleGroupId": article_group_id,
    }
    if unit:
        ti["unit"] = unit
    if quantity:
        ti["quantity"] = quantity
    if ti.get("quantity"):
        if ti.get("unit"):
            ti["summary"] = f"{ti['quantity']} {ti['unit']} {product_name}"
        else:
            ti["summary"] = f"{ti['quantity']} {product_name}"
    _LOGGER.debug("parse_summary %r -> %s", summary, ti)
    return ti
