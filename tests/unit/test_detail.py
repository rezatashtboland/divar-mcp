from pathlib import Path

import pytest

from divar_mcp.client.jsonld import extract_jsonld
from divar_mcp.client.page_state import extract_current_post
from divar_mcp.services.detail import parse_detail_post

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def detail_fixture() -> tuple[dict, list[dict]]:
    html = (FIXTURES / "listing_detail.html").read_text(encoding="utf-8")
    return extract_current_post(html), extract_jsonld(html)  # type: ignore[arg-type,return-value]


@pytest.fixture(scope="module")
def detail_post(detail_fixture: tuple[dict, list[dict]]) -> dict:
    return detail_fixture[0]


@pytest.fixture(scope="module")
def listing(detail_fixture: tuple[dict, list[dict]]):
    post, entries = detail_fixture
    return parse_detail_post(
        post,
        url="https://divar.ir/v/یکخوابه-۶۳-متری/gaGfdm8V",
        jsonld_entries=entries,
    )


def test_core_identity_fields(listing) -> None:
    assert listing.token == "gaGfdm8V"
    assert listing.slug == "یکخوابه-۶۳-متری"
    assert listing.city == "tehran"
    assert listing.city_name_fa == "تهران"
    assert "۶۳ متری" in listing.title
    assert listing.district_name_fa == "کوی بیمه"
    assert listing.category == "apartment-sell"
    assert listing.deal_type == "sell"


def test_property_fields(listing) -> None:
    assert listing.area == 63.0
    assert listing.rooms == 1
    assert listing.floor == 4
    assert listing.construction_year == 1396


def test_price_fields(listing) -> None:
    assert listing.price_toman == 18_500_000_000
    assert listing.price == 185_000_000_000
    assert listing.price_currency == "IRR"


def test_description_images_location(listing) -> None:
    assert "فوری فروشی" in listing.description
    assert listing.images and listing.images[0].startswith("https://")
    assert listing.location is not None
    assert abs(listing.location.latitude - 35.7050) < 0.01
    assert abs(listing.location.longitude - 51.3193) < 0.01
    assert listing.location.neighborhood == "کوی بیمه"


def test_posted_at_parsed(listing) -> None:
    assert listing.posted_at is not None
    assert listing.posted_at.startswith("2026-10-08")


def test_schema_data_kept(listing) -> None:
    assert listing.schema_data.get("@type") == "Apartment"
