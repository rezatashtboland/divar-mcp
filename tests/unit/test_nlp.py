import pytest

from divar_mcp.services.nlp import parse_query

Q1 = (
    "ارزانترین خانه ۶۰ متری برای اجاره و ۲ خواب با اسانسور و انباری "
    "توی شهر تهران که توی ۳ روز گذشته ثبت شده و توی محله گیشا هست"
)
Q1_EXPECTED = {
    "city": "tehran",
    "category": "real-estate",
    "deal_type": "rent",
    "min_area": 55,
    "max_area": 65,
    "rooms": 2,
    "has_elevator": True,
    "has_storage": True,
    "districts": ["gisha"],
    "posted_within_days": 3,
    "sort": "cheapest",
}

Q2 = "peugeot 206 model 1400 automatic white under 300 million toman in Tehran"
Q2_EXPECTED = {
    "city": "tehran",
    "category": "car",
    "query": "peugeot 206",
    "max_price": 300_000_000,
    "model_year_min": 1399,
    "transmission": "automatic",
    "color": "white",
}


def test_prd_query1_exact() -> None:
    filters = parse_query(Q1)
    assert filters.model_dump(exclude_none=True) == Q1_EXPECTED


def test_prd_query2_exact() -> None:
    filters = parse_query(Q2)
    assert filters.model_dump(exclude_none=True) == Q2_EXPECTED


def test_city_and_category_hints_override() -> None:
    filters = parse_query("یه آپارتمان", city="shiraz", category="vehicles")
    assert filters.city == "shiraz"
    assert filters.category == "vehicles"


def test_default_city_and_category() -> None:
    filters = parse_query("چیزی که نمی‌فهمم")
    assert filters.city == "tehran"
    assert filters.category == "real-estate"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("یک خواب", 1),
        ("۳ خواب", 3),
    ],
)
def test_rooms_variants(query: str, expected: int) -> None:
    assert parse_query(query).rooms == expected


def test_area_range() -> None:
    f = parse_query("بین ۵۰ تا ۷۰ متر")
    assert f.min_area == 50
    assert f.max_area == 70


def test_price_range_and_bounds() -> None:
    f = parse_query("بین ۱ تا ۲ میلیارد")
    assert f.min_price == 1_000_000_000
    assert f.max_price == 2_000_000_000
    assert parse_query("زیر ۵۰۰ میلیون").max_price == 500_000_000
    assert parse_query("بیشتر از ۲ میلیارد").min_price == 2_000_000_000


@pytest.mark.parametrize(
    ("query", "days"),
    [
        ("توی ۳ روز گذشته", 3),
        ("در هفته گذشته", 7),
        ("امروز", 1),
        ("این هفته", 7),
    ],
)
def test_time_queries(query: str, days: int) -> None:
    assert parse_query(query).posted_within_days == days


@pytest.mark.parametrize(
    ("query", "deal"),
    [
        ("اجاره آپارتمان", "rent"),
        ("رهن و اجاره آپارتمان", "rent"),
        ("فروش ویلا", "sell"),
        ("اجاره روزانه سوئیت", "daily_rent"),
    ],
)
def test_deal_types(query: str, deal: str) -> None:
    assert parse_query(query).deal_type == deal


def test_car_attributes_english_and_persian() -> None:
    f = parse_query("پراید ۱۳۹۵ دنده ای سفید کارکرد ۵۰ هزار")
    assert f.category == "car"
    assert f.transmission == "manual"
    assert f.color == "white"
    assert f.mileage_max == 50_000
    assert "پراید" in (f.query or "")


def test_english_car_query_finds_persian_city() -> None:
    f = parse_query("hyundai tucson 2019 automatic in Mashhad")
    assert f.city == "mashhad"
    assert f.category == "car"
    assert f.transmission == "automatic"
    assert f.query == "hyundai tucson 2019"


def test_features_without_ba_prefix_ignored() -> None:
    f = parse_query("آپارتمان ۸۰ متری فروش")
    assert f.has_elevator is None
    assert f.has_parking is None
    assert f.deal_type == "sell"
    assert f.min_area == 75 and f.max_area == 85
