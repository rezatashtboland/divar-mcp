"""Listing search over divar.ir list pages with cursor-to-page emulation.

Divar pages carry ~25 cards and a ``last_post_date`` cursor instead of
numbered pages; ``page``/``page_size`` are emulated by walking cursors,
deduplicating by token, and slicing (hard cap: MAX_CURSOR_HOPS per search).
Fields the list pages do not expose (seller type, vehicle specs) are kept
soft: listings pass such filters when the value is unknown.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from .. import config
from ..client.http import HttpClient
from ..client.page_state import (
    Pagination,
    PostRow,
    extract_state,
    iter_post_widgets,
    linked_data,
    parse_pagination,
)
from ..models.filters import SearchFilters, SearchResult
from ..models.listing import DealType, Listing
from ..utils.persian import (
    district_matches,
    normalize_text,
    to_persian_digits,
    word_to_int,
)
from ..utils.price import parse_amount, toman_to_rial

_TOKEN_IN_URL_RE = re.compile(r"/([A-Za-z0-9_-]{4,20})$")
_SLUG_IN_URL_RE = re.compile(r"/v/[^/]+/([A-Za-z0-9_-]{4,20})$")


def _linked_index(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        url = str(entry.get("url") or "")
        # Try to match /v/{slug}/{token} pattern first
        match = _SLUG_IN_URL_RE.search(url)
        if match:
            index[match.group(1)] = entry
            continue
        # Fallback: try to match token at end of URL
        match = _TOKEN_IN_URL_RE.search(url)
        if match:
            index[match.group(1)] = entry
    return index


def _relative_text(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        posted = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    days = max((datetime.now(timezone.utc).date() - posted.date()).days, 0)
    if days == 0:
        return "امروز"
    if days == 1:
        return "دیروز"
    return f"{to_persian_digits(days)} روز پیش"


def _deal_from_texts(category_slug: str, ld_category: str, middle_text: str) -> DealType | None:
    for text in (ld_category, category_slug, middle_text):
        normalized = normalize_text(text)
        if not normalized:
            continue
        if "روزانه" in normalized or "daily" in normalized:
            return "daily_rent"
        if "اجاره" in normalized or "rent" in normalized:
            return "rent"
        if "فروش" in normalized or "sell" in normalized:
            return "sell"
    return None


def _amounts_from_texts(row: PostRow, ld: dict[str, Any]) -> dict[str, int | None]:
    values: dict[str, Any] = {
        "price": None,
        "price_toman": None,
        "rent_amount": None,
        "deposit_amount": None,
        "price_currency": None,
    }
    offers = ld.get("offers")
    if isinstance(offers, dict) and offers.get("price"):
        try:
            irr = int(str(offers["price"]).replace(",", ""))
            values["price"] = irr
            values["price_toman"] = irr // 10
            values["price_currency"] = "IRR"
            return values
        except ValueError:
            pass
    for text in (row.middle_text, row.top_text):
        if not text:
            continue
        prefix = normalize_text(text.split(":")[0])
        amount = parse_amount(text)
        if amount is None:
            continue
        if "اجاره" in prefix and values["rent_amount"] is None:
            values["rent_amount"] = toman_to_rial(amount)
        elif ("ودیعه" in prefix or "رهن" in prefix) and values["deposit_amount"] is None:
            values["deposit_amount"] = toman_to_rial(amount)
        elif values["price_toman"] is None:
            values["price_toman"] = amount
            values["price"] = toman_to_rial(amount)
            values["price_currency"] = "Toman"
    return values


def merge_listing(row: PostRow, ld: dict[str, Any], city: str, category: str) -> Listing:
    url = str(ld.get("url") or f"{config.BASE_URL}/v/{row.token}/{row.token}")
    slug_match = _SLUG_IN_URL_RE.search(url)
    ld_category = str(ld.get("accommodationCategory") or "")
    area: float | None = None
    floor_size = ld.get("floorSize")
    if isinstance(floor_size, dict):
        try:
            area = float(str(floor_size.get("value")).replace(",", ""))
        except (TypeError, ValueError):
            area = None
    geo = ld.get("geo") if isinstance(ld.get("geo"), dict) else None
    location = None
    if geo:
        try:
            location = {
                "latitude": float(geo["latitude"]),
                "longitude": float(geo["longitude"]),
                "address": str(geo.get("address") or ""),
                "neighborhood": row.web_info.district_persian,
            }
        except (KeyError, TypeError, ValueError):
            location = None
    images = [url_img for url_img in (str(ld.get("image") or ""), row.image_url) if url_img]
    kwargs: dict[str, Any] = {
        "token": row.token,
        "slug": slug_match.group(1) if slug_match else "",
        "url": url,
        "title": row.title or str(ld.get("name") or ""),
        "category": category,
        "category_name_fa": row.web_info.category_slug_persian or ld_category,
        "city": city,
        "city_name_fa": row.web_info.city_persian,
        "district": "",
        "district_name_fa": row.web_info.district_persian,
        "area": area,
        "rooms": word_to_int(str(ld.get("numberOfRooms") or "")),
        "deal_type": _deal_from_texts(category, ld_category, row.middle_text),
        "images": images,
        "posted_at": row.posted_at,
        "posted_at_relative": _relative_text(row.posted_at),
        "location": location,
        "schema_data": ld,
        **_amounts_from_texts(row, ld),
    }
    return Listing.model_validate({k: v for k, v in kwargs.items() if v is not None})


async def fetch_page(
    http: HttpClient, city: str, category: str, cursor: str | None = None, query: str | None = None
) -> tuple[list[Listing], Pagination]:
    url = f"{config.BASE_URL}/s/{city}/{category}"
    params = []
    if query:
        params.append(f"q={quote(query)}")
    if cursor:
        params.append(f"last_post_date={quote(cursor, safe='')}")
    if params:
        url += "?" + "&".join(params)
    html = await http.get_text(url, cache="search")
    state = extract_state(html)
    index = _linked_index(linked_data(state))
    listings = [
        merge_listing(row, index.get(row.token, {}), city, category)
        for row in iter_post_widgets(state)
    ]
    return listings, parse_pagination(state)


def _matches(listing: Listing, f: SearchFilters) -> bool:
    # For non-real-estate categories, the search API handles keyword matching.
    # Only apply structured filters client-side.
    if f.category != "real-estate" and f.query:
        # Skip full-text query matching for products - API does this
        pass
    elif f.query:
        haystack = normalize_text(f"{listing.title} {listing.description or ''}")
        query_terms = [t for t in normalize_text(f.query).split() if len(t) > 1]
        if query_terms:
            if not all(term in haystack for term in query_terms):
                return False
    if f.min_price is not None or f.max_price is not None:
        if listing.price_toman is None:
            return False
        if f.min_price is not None and listing.price_toman < f.min_price:
            return False
        if f.max_price is not None and listing.price_toman > f.max_price:
            return False
    if f.min_area is not None or f.max_area is not None:
        if listing.area is None:
            return False
        if f.min_area is not None and listing.area < f.min_area:
            return False
        if f.max_area is not None and listing.area > f.max_area:
            return False
    if f.rooms is not None and listing.rooms is not None:
        wanted = [f.rooms] if isinstance(f.rooms, int) else f.rooms
        if listing.rooms not in wanted:
            return False
    if f.floor is not None and listing.floor is not None and listing.floor != f.floor:
        return False
    if f.deal_type and listing.deal_type and listing.deal_type != f.deal_type:
        return False
    if f.has_elevator and listing.has_elevator is False:
        return False
    if f.has_parking and listing.has_parking is False:
        return False
    if f.has_storage and listing.has_storage is False:
        return False
    if f.has_balcony and listing.has_balcony is False:
        return False
    if (
        f.construction_after
        and listing.construction_year
        and listing.construction_year < f.construction_after
    ):
        return False
    if f.posted_within_days is not None and listing.posted_at:
        try:
            posted = datetime.fromisoformat(listing.posted_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        age = (datetime.now(timezone.utc) - posted).days
        if age > f.posted_within_days:
            return False
    return not (
        f.districts
        and listing.district_name_fa
        and not any(district_matches(listing.district_name_fa, d) for d in f.districts)
    )


def _sorted(items: list[Listing], sort: str | None) -> list[Listing]:
    if sort == "cheapest":
        return sorted(items, key=lambda lst: (lst.price_toman is None, lst.price_toman or 0))
    if sort == "most_expensive":
        return sorted(items, key=lambda lst: (lst.price_toman is None, -(lst.price_toman or 0)))
    if sort in ("newest", None):
        return sorted(
            items, key=lambda lst: (lst.posted_at is None, lst.posted_at or ""), reverse=True
        )
    return items


async def search(http: HttpClient, filters: SearchFilters) -> SearchResult:
    page = filters.page or 1
    page_size = filters.page_size or config.DEFAULT_PAGE_SIZE
    target = page * page_size
    collected: dict[str, Listing] = {}
    cursor: str | None = None
    has_more = False
    hint: str | None = None
    for _ in range(config.MAX_CURSOR_HOPS):
        listings, pagination = await fetch_page(http, filters.city, filters.category, cursor, filters.query)
        new = 0
        for listing in listings:
            if listing.token not in collected:
                collected[listing.token] = listing
                new += 1
        has_more = pagination.has_more
        if len(collected) >= target or not has_more or new == 0:
            if has_more and len(collected) < target and new == 0:
                hint = f"cursor={pagination.last_post_date}"
            break
        cursor = pagination.last_post_date
        if cursor is None:
            break
    else:
        if has_more and len(collected) < target:
            hint = "بیش از حد مجاز صفحه جابه‌جا شدیم؛ فیلترها را دقیق‌تر کنید."
    filtered = [listing for listing in collected.values() if _matches(listing, filters)]
    ordered = _sorted(filtered, filters.sort)
    start = (page - 1) * page_size
    window = ordered[start : start + page_size]
    if len(ordered) > start + page_size:
        has_more = True
    return SearchResult(
        listings=window,
        total_count=len(ordered),
        page=page,
        page_size=page_size,
        has_more=has_more,
        continue_hint=hint,
    )
