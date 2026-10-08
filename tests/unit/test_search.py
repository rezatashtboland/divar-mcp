from pathlib import Path

import httpx
import pytest
import respx

from divar_mcp import config
from divar_mcp.client.http import HttpClient
from divar_mcp.models.filters import SearchFilters
from divar_mcp.services.search import _relative_text, fetch_page, search

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
LIST_URL = f"{config.BASE_URL}/s/tehran/real-estate"


@pytest.fixture(scope="module")
def list_html() -> str:
    return (FIXTURES / "tehran_real_estate.html").read_text(encoding="utf-8")


@pytest.fixture
async def client():
    c = HttpClient(rate_rps=10_000, wait_base=0.001)
    yield c
    await c.close()


@respx.mock
async def test_fetch_page_merges_rows_and_schema(client: HttpClient, list_html: str) -> None:
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    listings, pagination = await fetch_page(client, "tehran", "real-estate")
    assert len(listings) >= 20
    assert pagination.has_more is True
    priced = [x for x in listings if x.price_toman or x.rent_amount or x.deposit_amount]
    assert len(priced) >= 5
    with_geo = [x for x in listings if x.location]
    assert len(with_geo) >= 5
    assert all(x.city == "tehran" and x.token for x in listings)
    assert any(x.area for x in listings)
    assert any(x.rooms for x in listings)
    assert all(x.city_name_fa == "تهران" for x in listings if x.city_name_fa)


@respx.mock
async def test_search_first_page_single_request(client: HttpClient, list_html: str) -> None:
    route = respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    result = await search(client, SearchFilters(city="tehran", category="real-estate"))
    assert len(result.listings) == config.DEFAULT_PAGE_SIZE
    assert result.page == 1
    assert result.has_more is True
    assert route.call_count == 1


@respx.mock
async def test_search_second_page_dedupes_and_stops(client: HttpClient, list_html: str) -> None:
    route = respx.get(url__startswith=LIST_URL).mock(
        return_value=httpx.Response(200, text=list_html)
    )
    result = await search(
        client, SearchFilters(city="tehran", category="real-estate", page=2, page_size=20)
    )
    # same fixture on every hop: duplicates after hop 1, so only the ~24
    # known cards exist and page 2 holds just the remainder of them
    assert route.call_count == 2
    assert result.total_count == 26
    assert len(result.listings) == result.total_count - 20
    assert result.continue_hint


@respx.mock
async def test_price_filter_bounds(client: HttpClient, list_html: str) -> None:
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    result = await search(
        client,
        SearchFilters(city="tehran", category="real-estate", max_price=200_000_000_000),
    )
    for listing in result.listings:
        if listing.price_toman is not None:
            assert listing.price_toman <= 200_000_000_000
    narrow = await search(
        client,
        SearchFilters(city="tehran", category="real-estate", min_price=999_000_000_000_000),
    )
    assert narrow.listings == []


@respx.mock
async def test_area_and_rooms(client: HttpClient, list_html: str) -> None:
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    result = await search(
        client, SearchFilters(city="tehran", category="real-estate", min_area=50, rooms=1)
    )
    for listing in result.listings:
        if listing.area is not None:
            assert listing.area >= 50
        if listing.rooms is not None:
            assert listing.rooms == 1


@respx.mock
async def test_district_persian_and_latin(client: HttpClient, list_html: str) -> None:
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    base = await search(client, SearchFilters(city="tehran", category="real-estate"))
    district = next(x.district_name_fa for x in base.listings if x.district_name_fa)
    fa = await search(
        client, SearchFilters(city="tehran", category="real-estate", districts=[district])
    )
    named = [x for x in fa.listings if x.district_name_fa]
    assert named
    assert all(district in x.district_name_fa for x in named)
    latin = await search(
        client,
        SearchFilters(city="tehran", category="real-estate", districts=["gharbi-gisha-or-tehran"]),
    )
    assert [x for x in latin.listings if x.district_name_fa] == []


@respx.mock
async def test_sort_cheapest(client: HttpClient, list_html: str) -> None:
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    result = await search(
        client,
        SearchFilters(city="tehran", category="real-estate", sort="cheapest", page_size=50),
    )
    priced = [lst.price_toman for lst in result.listings if lst.price_toman is not None]
    assert priced == sorted(priced)


@respx.mock
async def test_posted_within_days(client: HttpClient, list_html: str) -> None:
    from datetime import datetime, timedelta, timezone

    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=list_html))
    narrow = await search(
        client,
        SearchFilters(city="tehran", category="real-estate", posted_within_days=1),
    )
    wide = await search(
        client,
        SearchFilters(city="tehran", category="real-estate", posted_within_days=3650),
    )
    assert narrow.total_count < wide.total_count
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    for listing in narrow.listings:
        posted = datetime.fromisoformat(listing.posted_at.replace("Z", "+00:00"))
        assert posted >= cutoff


def test_relative_text() -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    assert _relative_text(now.isoformat()) == "امروز"
    assert _relative_text((now - timedelta(days=1)).isoformat()) == "دیروز"
    assert _relative_text((now - timedelta(days=3)).isoformat()) == "۳ روز پیش"
    assert _relative_text(None) == ""
    assert _relative_text("garbage") == ""
