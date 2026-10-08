from pathlib import Path

import httpx
import pytest
import respx

from divar_mcp import config
from divar_mcp.client.http import HttpClient
from divar_mcp.client.page_state import extract_state
from divar_mcp.services.discovery import (
    categories_from_root,
    fetch_categories,
    fetch_cities,
    parse_city_links,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
async def client():
    c = HttpClient(rate_rps=10_000, wait_base=0.001)
    yield c
    await c.close()


def test_categories_from_root_tree() -> None:
    html = (FIXTURES / "tehran_categories.html").read_text(encoding="utf-8")
    root = extract_state(html)["search"]["rootCat"]
    categories = categories_from_root(root)
    top = [c for c in categories if c.parent_id is None]
    assert len(top) >= 8
    slugs = {c.slug for c in top}
    assert {"real-estate", "vehicles", "electronic-devices"} <= slugs
    names = {c.slug: c.name_fa for c in top}
    assert names["real-estate"] == "املاک"
    kids = [c for c in categories if c.parent_id == "real-estate"]
    assert len(kids) >= 4
    assert all(c.slug != c.parent_id for c in kids)


def test_categories_from_root_none_root_returns_empty() -> None:
    assert categories_from_root(None) == []


def test_parse_city_links() -> None:
    html = (
        '<a href="/s/mashhad">مشهد</a><a href="/s/tehran">تهران</a>'
        '<a href="/s/isfahan">اصفهان</a><a href="/s/tehran">تکراری</a>'
    )
    cities = parse_city_links(html)
    slugs = [c.slug for c in cities]
    assert slugs == ["mashhad", "tehran", "isfahan"]


@respx.mock
async def test_fetch_cities_falls_back_to_static(client: HttpClient) -> None:
    respx.get("https://divar.ir/").mock(return_value=httpx.Response(200, text="<html></html>"))
    cities = await fetch_cities(client)
    assert len(cities) == 30
    assert cities[0].slug == "tehran"
    assert cities[0].name_fa == "تهران"


@respx.mock
async def test_fetch_cities_parses_live_links(client: HttpClient) -> None:
    html = '<a href="/s/mashhad">مشهد</a>' * 1 + "<a href='/s/shiraz'>شیراز</a>"
    html = html.replace("'", '"')
    suffixes = ["الف", "ب", "پ", "ت", "ث"]
    html = html + "".join(f'<a href="/s/city{i}">شهر{s}</a>' for i, s in enumerate(suffixes))
    respx.get("https://divar.ir/").mock(return_value=httpx.Response(200, text=html))
    client._caches["cities"].clear()
    cities = await fetch_cities(client)
    assert len(cities) == 7
    assert {c.slug for c in cities} == {"mashhad", "shiraz"} | {f"city{i}" for i in range(5)}


@respx.mock
async def test_fetch_categories_from_city_page(client: HttpClient) -> None:
    html = (FIXTURES / "tehran_categories.html").read_text(encoding="utf-8")
    respx.get(f"{config.BASE_URL}/s/tehran").mock(return_value=httpx.Response(200, text=html))
    categories = await fetch_categories(client, "tehran")
    real_estate = next(c for c in categories if c.slug == "real-estate")
    assert real_estate.name_fa == "املاک"
    sub = [c for c in categories if c.parent_id == "real-estate"]
    assert sub


@respx.mock
async def test_fetch_categories_survives_bad_page(client: HttpClient) -> None:
    respx.get(f"{config.BASE_URL}/s/unknown-city").mock(
        return_value=httpx.Response(200, text="<html>no state</html>")
    )
    with pytest.raises(ValueError):
        await fetch_categories(client, "unknown-city")
