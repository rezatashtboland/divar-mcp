"""Parse ``<script type="application/ld+json">`` blocks from page HTML."""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup

NON_LISTING_TYPES = frozenset(
    {
        "BreadcrumbList",
        "WebSite",
        "WebPage",
        "Organization",
        "SearchAction",
        "ImageObject",
        "ListItem",
        "SiteNavigationElement",
    }
)


def extract_jsonld(html: str) -> list[dict[str, Any]]:
    """Return every JSON-LD object found in the page, flattening arrays."""
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict[str, Any]] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        text = tag.string or tag.get_text()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            entries.extend(item for item in parsed if isinstance(item, dict))
        elif isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def type_of(entry: dict[str, Any]) -> str:
    raw = entry.get("@type")
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw or "")


def pick_listing_node(
    entries: list[dict[str, Any]], token: str | None = None
) -> dict[str, Any] | None:
    """Pick the schema.org node describing the listing itself."""
    for entry in entries:
        t = type_of(entry)
        if not t or t in NON_LISTING_TYPES:
            continue
        if token is not None and token not in json.dumps(entry, ensure_ascii=False):
            continue
        return entry
    return None
