import pytest
from pydantic import ValidationError

from divar_mcp.models.common import Category, City, GeoLocation, SellerInfo
from divar_mcp.models.filters import (
    ComparisonResult,
    FindBestMatchResult,
    SearchFilters,
    SearchResult,
)
from divar_mcp.models.listing import Listing


def _minimal_listing_payload() -> dict[str, object]:
    return {
        "token": "gaGvMW2J",
        "slug": "apartment-64m-nabrd-jnobi",
        "url": "https://divar.ir/v/x/gaGvMW2J",
        "title": "آپارتمان ۶۴ متری",
        "category": "real-estate",
        "city": "tehran",
    }


def test_city_and_category_models() -> None:
    city = City(id="tehran", name_fa="تهران", name_en="Tehran", slug="tehran")
    assert city.slug == "tehran"
    cat = Category(id="real-estate", slug="real-estate", name_fa="املاک", name_en="Real Estate")
    assert cat.parent_id is None
    sub = Category(
        id="apartment",
        slug="apartment",
        name_fa="آپارتمان",
        name_en="Apartment",
        parent_id="real-estate",
    )
    assert sub.parent_id == "real-estate"


def test_geo_and_seller_defaults() -> None:
    geo = GeoLocation(latitude=35.7, longitude=51.4)
    assert geo.address == "" and geo.neighborhood == ""
    seller = SellerInfo()
    assert seller.name == "" and seller.type is None and seller.rating is None


def test_minimal_listing_validates() -> None:
    listing = Listing.model_validate(_minimal_listing_payload())
    assert listing.description == ""
    assert listing.images == []
    assert listing.area is None
    assert listing.deal_type is None
    assert listing.schema_data == {}


def test_full_listing_round_trip() -> None:
    payload = _minimal_listing_payload()
    payload.update(
        {
            "description": "توضیحات کامل",
            "price": 2_000_000_000,
            "price_toman": 200_000_000,
            "price_currency": "IRR",
            "area": 64.0,
            "rooms": 2,
            "floor": 3,
            "total_floors": 8,
            "construction_year": 1395,
            "has_elevator": True,
            "has_parking": True,
            "has_storage": False,
            "deal_type": "rent",
            "rent_amount": 15_000_000,
            "deposit_amount": 200_000_000,
            "model_year": 1400,
            "mileage": 45_000,
            "transmission": "automatic",
            "fuel_type": "gasoline",
            "body_type": "sedan",
            "images": ["https://i.divar.ir/1.jpg"],
            "posted_at": "2026-10-07T10:00:00Z",
            "posted_at_relative": "۳ روز پیش",
            "seller": {"name": "مالک", "type": "owner"},
            "location": {"latitude": 35.7, "longitude": 51.4, "neighborhood": "گیشا"},
            "schema_data": {"@type": "Apartment"},
        }
    )
    listing = Listing.model_validate(payload)
    assert listing.seller.type == "owner"
    assert listing.location is not None and listing.location.neighborhood == "گیشا"
    dumped = listing.model_dump(mode="json")
    again = Listing.model_validate(dumped)
    assert again == listing


def test_invalid_deal_type_rejected() -> None:
    payload = _minimal_listing_payload()
    payload.update({"deal_type": "lease"})
    with pytest.raises(ValidationError):
        Listing.model_validate(payload)
    with pytest.raises(ValidationError):
        SearchFilters(city="tehran", category="real-estate", sort="relevance")


def test_search_filters_minimal_and_full() -> None:
    f = SearchFilters(city="tehran", category="real-estate")
    assert f.page is None and f.districts is None
    full = SearchFilters(
        city="tehran",
        category="real-estate",
        min_price=1_000_000_000,
        max_price=2_000_000_000,
        min_area=55,
        max_area=65,
        rooms=[1, 2],
        deal_type="rent",
        districts=["gisha"],
        has_elevator=True,
        posted_within_days=3,
        sort="cheapest",
        page=2,
        page_size=20,
    )
    assert full.rooms == [1, 2]
    schema = SearchFilters.model_json_schema()
    assert schema["properties"]["city"]["type"] == "string"
    assert set(schema["properties"]["deal_type"]["anyOf"][0]["enum"]) == {
        "rent",
        "sell",
        "rent_to_own",
        "daily_rent",
    }


def test_search_filters_car_fields() -> None:
    f = SearchFilters(
        city="tehran",
        category="car",
        model_year_min=1399,
        transmission="automatic",
        color="white",
    )
    assert f.model_year_min == 1399
    assert f.color == "white"


def test_result_wrappers() -> None:
    listing = Listing.model_validate(_minimal_listing_payload())
    res = SearchResult(listings=[listing], total_count=1, page=1, page_size=20, has_more=False)
    assert res.model_dump(mode="json")["listings"][0]["token"] == "gaGvMW2J"
    match = FindBestMatchResult(
        best_match=listing,
        alternatives=[],
        reasoning="ارزان‌ترین گزینه با همه ویژگی‌ها",
        extracted_filters=SearchFilters(city="tehran", category="real-estate"),
    )
    assert match.best_match is not None
    cmp = ComparisonResult(comparison={"price": {}}, summary="خلاصه")
    assert cmp.summary == "خلاصه"
