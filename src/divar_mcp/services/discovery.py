"""City and category discovery from divar.ir pages, with static fallback."""

from __future__ import annotations

import re
from typing import Any

from .. import config
from ..client.http import DivarUnavailableError, HttpClient
from ..client.page_state import PageStateError, extract_state, root_category
from ..models.common import Category, City

_CITY_LINK_RE = re.compile(r'<a[^>]+href="(/s/([a-z0-9-]+))"[^>]*>([^<]{1,40})</a>')
_MIN_LIVE_CITIES = 5


def static_cities() -> list[City]:
    return [
        City(id=slug, slug=slug, name_fa=name_fa, name_en=name_en)
        for slug, name_fa, name_en in config.STATIC_CITIES
    ]


def parse_city_links(html: str) -> list[City]:
    """Collect /s/{slug} city links with their Persian anchor text."""
    seen: dict[str, City] = {}
    for _url, slug, text in _CITY_LINK_RE.findall(html):
        name = text.strip()
        if slug in seen or not name or any(ch.isdigit() for ch in name):
            continue
        seen[slug] = City(id=slug, slug=slug, name_fa=name, name_en="")
    return list(seen.values())


async def fetch_cities(http: HttpClient) -> list[City]:
    """City list from the site front page; static top-30 fallback on failure."""
    cities: list[City] = []
    try:
        html = await http.get_text(f"{config.BASE_URL}/", cache="cities")
        cities = parse_city_links(html)
    except (DivarUnavailableError, PageStateError):
        cities = []
    if len(cities) < _MIN_LIVE_CITIES:
        return static_cities()
    return cities


def categories_from_root(root: dict[str, Any] | None) -> list[Category]:
    """Flatten the rootCat tree into top-level categories plus subcategories."""
    if not root:
        return []
    categories: list[Category] = []
    for child in root.get("children") or []:
        slug = str(child.get("slug") or "")
        if not slug:
            continue
        categories.append(
            Category(
                id=slug,
                slug=slug,
                name_fa=str(child.get("name") or ""),
                parent_id=None,
            )
        )
        for sub in child.get("children") or []:
            sub_slug = str(sub.get("slug") or "")
            if not sub_slug:
                continue
            categories.append(
                Category(
                    id=sub_slug,
                    slug=sub_slug,
                    name_fa=str(sub.get("name") or ""),
                    parent_id=slug,
                )
            )
    return categories


async def fetch_categories(http: HttpClient, city: str) -> list[Category]:
    """Category hierarchy for a city, read from the city page state."""
    html = await http.get_text(f"{config.BASE_URL}/s/{city}", cache="cities")
    categories = categories_from_root(root_category(extract_state(html)))
    if not categories:
        raise ValueError(
            f"هیچ دسته‌بندی برای شهر «{city}» پیدا نشد. / No categories found for city '{city}'."
        )
    return categories
