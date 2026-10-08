import pytest

from divar_mcp.models.listing import Listing
from divar_mcp.services.comparison import compare_listings


def _listing(token: str, **kw: object) -> Listing:
    return Listing.model_validate({"token": token, "slug": token, **kw})


def test_compare_two_listings_basic() -> None:
    a = _listing("a", price_toman=1_000_000_000, area=60, rooms=2, has_elevator=True)
    b = _listing("b", price_toman=2_000_000_000, area=90, rooms=3, has_elevator=False)
    res = compare_listings([a, b])
    assert res.comparison["قیمت (تومان)"]["a"] != res.comparison["قیمت (تومان)"]["b"]
    assert "ارزان‌ترین" in res.summary


def test_compare_requires_two() -> None:
    with pytest.raises(ValueError):
        compare_listings([_listing("a")])


def test_compare_max_five() -> None:
    with pytest.raises(ValueError):
        compare_listings([_listing(str(i)) for i in range(6)])


def test_identical_listings_no_diff() -> None:
    a = _listing("a", price_toman=1_000_000_000, area=60, rooms=2)
    b = _listing("b", price_toman=1_000_000_000, area=60, rooms=2)
    res = compare_listings([a, b])
    assert res.comparison == {}
    assert "هیچ تفاوتی" in res.summary


def test_compare_persian_labels() -> None:
    a = _listing("a", price_toman=1_000_000_000, area=60, rooms=2, has_elevator=True)
    b = _listing("b", price_toman=2_000_000_000, area=90, rooms=3, has_elevator=False)
    res = compare_listings([a, b])
    assert "قیمت (تومان)" in res.comparison
    assert "متراژ (متر)" in res.comparison
    assert "آسانسور" in res.comparison
    assert res.comparison["آسانسور"]["a"] == "دارد"
    assert res.comparison["آسانسور"]["b"] == "ندارد"
