"""Rank candidate listings against extracted filters and explain the pick."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .. import config
from ..client.http import HttpClient
from ..models.filters import FindBestMatchResult, SearchFilters
from ..models.listing import Listing
from ..utils.persian import district_matches, normalize_text
from ..utils.price import format_toman_words
from .nlp import parse_query
from .search import search

Criterion = tuple[str, int, Callable[[Listing, SearchFilters], "bool | None"]]

_YES = "✅"


def _price_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.min_price is None and f.max_price is None:
        return None
    if lst.price_toman is None:
        return None
    below = f.min_price is not None and lst.price_toman < f.min_price
    above = f.max_price is not None and lst.price_toman > f.max_price
    return not (below or above)


def _area_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.min_area is None and f.max_area is None:
        return None
    if lst.area is None:
        return None
    return not (
        (f.min_area is not None and lst.area < f.min_area)
        or (f.max_area is not None and lst.area > f.max_area)
    )


def _rooms_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.rooms is None:
        return None
    if lst.rooms is None:
        return None
    wanted = [f.rooms] if isinstance(f.rooms, int) else f.rooms
    return lst.rooms in wanted


def _deal_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.deal_type is None:
        return None
    if lst.deal_type is None:
        return None
    return lst.deal_type == f.deal_type


def _feature_check(field_name: str) -> Callable[[Listing, SearchFilters], bool | None]:
    def check(lst: Listing, f: SearchFilters) -> bool | None:
        if not getattr(f, field_name):
            return None
        return getattr(lst, field_name) is True

    return check


def _district_check(lst: Listing, f: SearchFilters) -> bool | None:
    if not f.districts:
        return None
    if not lst.district_name_fa:
        return None
    return any(district_matches(lst.district_name_fa, d) for d in f.districts)


def _posted_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.posted_within_days is None:
        return None
    if not lst.posted_at:
        return None
    try:
        posted = datetime.fromisoformat(lst.posted_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - posted).days <= f.posted_within_days


def _query_check(lst: Listing, f: SearchFilters) -> bool | None:
    if not f.query:
        return None
    return normalize_text(f.query) in normalize_text(f"{lst.title} {lst.description}")


def _simple_eq(attr: str) -> Callable[[Listing, SearchFilters], bool | None]:
    def check(lst: Listing, f: SearchFilters) -> bool | None:
        wanted = getattr(f, attr)
        if wanted is None:
            return None
        got = getattr(lst, attr)
        if got is None:
            return None
        return str(got) == str(wanted)

    return check


def _model_year_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.model_year_min is None:
        return None
    if lst.model_year is None:
        return None
    ok = lst.model_year >= f.model_year_min
    if f.model_year_max is not None:
        ok = ok and lst.model_year <= f.model_year_max
    return ok


def _mileage_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.mileage_max is None:
        return None
    if lst.mileage is None:
        return None
    return lst.mileage <= f.mileage_max


def _construction_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.construction_after is None:
        return None
    if lst.construction_year is None:
        return None
    return lst.construction_year >= f.construction_after


def _floor_check(lst: Listing, f: SearchFilters) -> bool | None:
    if f.floor is None:
        return None
    if lst.floor is None:
        return None
    return lst.floor == f.floor


def _filters_set(filters: SearchFilters) -> dict[str, bool]:
    return {
        "price": filters.min_price is not None or filters.max_price is not None,
        "rooms": filters.rooms is not None,
        "district": bool(filters.districts),
        "deal_type": filters.deal_type is not None,
        "area": filters.min_area is not None or filters.max_area is not None,
        "query": bool(filters.query),
        "has_elevator": bool(filters.has_elevator),
        "has_parking": bool(filters.has_parking),
        "has_storage": bool(filters.has_storage),
        "has_balcony": bool(filters.has_balcony),
        "construction_after": filters.construction_after is not None,
        "posted_within_days": filters.posted_within_days is not None,
        "floor": filters.floor is not None,
        "model_year": filters.model_year_min is not None or filters.model_year_max is not None,
        "mileage_max": filters.mileage_max is not None,
        "transmission": filters.transmission is not None,
        "fuel_type": filters.fuel_type is not None,
        "body_type": filters.body_type is not None,
        "color": filters.color is not None,
    }


_CRITERIA: list[Criterion] = [
    ("price", 3, _price_check),
    ("rooms", 3, _rooms_check),
    ("district", 3, _district_check),
    ("deal_type", 2, _deal_check),
    ("area", 2, _area_check),
    ("query", 2, _query_check),
    ("has_elevator", 2, _feature_check("has_elevator")),
    ("has_parking", 2, _feature_check("has_parking")),
    ("has_storage", 2, _feature_check("has_storage")),
    ("has_balcony", 2, _feature_check("has_balcony")),
    ("construction_after", 1, _construction_check),
    ("posted_within_days", 1, _posted_check),
    ("floor", 1, _floor_check),
    ("model_year", 2, _model_year_check),
    ("mileage_max", 1, _mileage_check),
    ("transmission", 2, _simple_eq("transmission")),
    ("fuel_type", 1, _simple_eq("fuel_type")),
    ("body_type", 1, _simple_eq("body_type")),
    ("color", 1, _simple_eq("color")),
]


@dataclass(frozen=True)
class ScoredListing:
    listing: Listing
    score: float
    matched: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)


def score_listing(listing: Listing, filters: SearchFilters) -> tuple[float, list[str], list[str]]:
    set_map = _filters_set(filters)
    total_weight = sum(weight for name, weight, _ in _CRITERIA if set_map[name])
    earned = 0
    missed_weight = 0
    matched: list[str] = []
    missed: list[str] = []
    for name, weight, check in _CRITERIA:
        if not set_map[name]:
            continue
        verdict = check(listing, filters)
        if verdict is None:
            continue
        if verdict:
            earned += weight
            matched.append(name)
        else:
            missed_weight += weight
            missed.append(name)
    penalty = 0.5
    score = (earned - penalty * missed_weight) / total_weight if total_weight else 0.0
    return score, matched, missed


def rank_candidates(candidates: list[Listing], filters: SearchFilters) -> list[ScoredListing]:
    scored: list[ScoredListing] = []
    for listing in candidates:
        score, matched, missed = score_listing(listing, filters)
        scored.append(ScoredListing(listing=listing, score=score, matched=matched, missed=missed))

    def by_price(s: ScoredListing) -> tuple[int, int]:
        price = s.listing.price_toman
        if price is None:
            return (1, 0)
        return (0, price if filters.sort == "cheapest" else -price)

    if filters.sort in ("cheapest", "most_expensive"):
        scored.sort(key=by_price)
    else:
        scored.sort(key=lambda s: s.listing.posted_at or "", reverse=True)
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def _listing_label(listing: Listing) -> str:
    parts = [f"«{listing.title or listing.token}»"]
    if listing.price_toman:
        parts.append(f"قیمت {format_toman_words(listing.price_toman)} تومان")
    elif listing.rent_amount:
        parts.append(f"اجاره {format_toman_words(listing.rent_amount // 10)} تومان")
    if listing.area:
        parts.append(f"{int(listing.area)} متر")
    if listing.rooms is not None:
        parts.append(f"{listing.rooms} خواب")
    if listing.district_name_fa:
        parts.append(listing.district_name_fa)
    return "، ".join(str(p) for p in parts)


def best_match(
    candidates: list[Listing], filters: SearchFilters
) -> tuple[Listing | None, list[Listing], str]:
    ranked = rank_candidates(candidates, filters)
    if not ranked:
        if config.language() == "en":
            return None, [], "No listing matched the search."
        return None, [], "هیچ آگهی‌ای برای این جستجو پیدا نشد."
    top = ranked[0]
    alternatives = [s.listing for s in ranked[1:4]]
    if config.language() == "en":
        reasoning = (
            f"Best match among {len(ranked)} candidates: {_listing_label(top.listing)}. "
            f"Matching: {', '.join(top.matched) or 'none precisely'}. "
            f"Not satisfied: {', '.join(top.missed) or 'nothing'}."
        )
        return top.listing, alternatives, reasoning
    matched_text = "، ".join(top.matched) if top.matched else "مورد مشخصی"
    missed_text = "، ".join(top.missed) if top.missed else "هیچ‌کدام"
    reasoning = (
        f"{_YES} بهترین گزینه از بین {len(ranked)} آگهی: {_listing_label(top.listing)}. "
        f"فیلترهای برقرار: {matched_text}. فیلترهای برقرارنبودن: {missed_text}."
    )
    return top.listing, alternatives, reasoning


async def find_best_match(
    http: HttpClient,
    query: str,
    city: str | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> FindBestMatchResult:
    limit = limit or config.DEFAULT_MATCH_LIMIT
    filters = parse_query(query, city=city, category=category)
    # For the search API, use a simplified query with just the core product keywords
    # Extract keywords from the parsed query's query field
    search_query = filters.query
    if search_query:
        # Split into words and keep only meaningful ones (length > 2, not stop words)
        stop_words = {"بهترین", "ارزانترین", "مناسب", "برنامه", "نویسی", "باشه", "توی", "شهر", "کالا", "هم", "نو", "موجود", "بر اساس", "تاریخ", "درج", "جدیدترین", "ها", "در", "اولویت", "برای", "است", "این", "آن", "که", "و", "یا", "اما", "ولی", "چون", "زیرا", "بنابراین", "تمام", "صفحه", "صفح", "سایز", "سایزها", "اندازه", "قیمت", "گران", "ارزان", "کیفیت", "برند", "مدل", "رنگ", "مشکی", "سفید", "آبی", "قرمز"}
        words = [w for w in search_query.split() if len(w) > 2 and w not in stop_words]
        # Take first 2-3 meaningful words as search query (core product terms)
        search_query = " ".join(words[:3])
    search_filters = filters.model_copy(
        update={"page_size": min(limit, config.MAX_PAGE_SIZE), "page": 1, "query": search_query}
    )
    result = await search(http, search_filters)
    best, alternatives, reasoning = best_match(result.listings, filters)
    return FindBestMatchResult(
        best_match=best,
        alternatives=alternatives,
        reasoning=reasoning,
        extracted_filters=filters,
    )
