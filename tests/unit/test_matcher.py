import pytest

from divar_mcp.models.filters import SearchFilters
from divar_mcp.models.listing import Listing
from divar_mcp.services.matcher import best_match, rank_candidates, score_listing


def _listing(token: str, **kwargs: object) -> Listing:
    return Listing.model_validate({"token": token, "slug": token, **kwargs})


F = SearchFilters(
    city="tehran",
    category="real-estate",
    deal_type="rent",
    rooms=2,
    min_area=55,
    max_area=65,
    has_elevator=True,
    districts=["gisha"],
    sort="cheapest",
)


def test_score_perfect_vs_partial_vs_mismatch() -> None:
    perfect = _listing(
        "a",
        deal_type="rent",
        rooms=2,
        area=60,
        has_elevator=True,
        district_name_fa="گیشا",
        price_toman=1_000_000_000,
    )
    partial = _listing("b", deal_type="rent", rooms=2, area=60)
    mismatch = _listing(
        "b",
        deal_type="sell",
        rooms=4,
        area=120,
        has_elevator=False,
        district_name_fa="ونک",
    )
    s_perfect, matched, missed = score_listing(perfect, F)
    s_partial, _, _ = score_listing(partial, F)
    s_mismatch, _, _ = score_listing(mismatch, F)
    assert s_perfect > s_partial > s_mismatch
    assert "rooms" in matched
    assert any("elevator" in m or "has_elevator" in m for m in missed) is False
    _, m2, m2_missed = score_listing(mismatch, F)
    assert m2 == []
    assert len(m2_missed) >= 3


def test_price_window_counts() -> None:
    f = SearchFilters(city="tehran", category="real-estate", max_price=2_000_000_000)
    inside = _listing("a", price_toman=1_500_000_000)
    outside = _listing("b", price_toman=2_500_000_000)
    unknown = _listing("c")
    assert score_listing(inside, f)[0] > score_listing(outside, f)[0]
    assert score_listing(inside, f)[0] > score_listing(unknown, f)[0]
    assert score_listing(unknown, f)[0] > score_listing(outside, f)[0]


def test_rank_orders_by_score_then_price() -> None:
    cheap = _listing("cheap", rooms=2, price_toman=900_000_000)
    dear = _listing("dear", rooms=2, price_toman=1_900_000_000)
    off = _listing("off", rooms=5)
    ranked = rank_candidates([dear, off, cheap], F)
    assert [x.listing.token for x in ranked[:2]] == ["cheap", "dear"]


def test_best_match_and_reasoning() -> None:
    best_l = _listing(
        "best",
        title="آپارتمان گیشا",
        deal_type="rent",
        rooms=2,
        area=60,
        has_elevator=True,
        district_name_fa="گیشا",
        price_toman=1_000_000_000,
    )
    other = _listing("other", title="یک خواب ونک", deal_type="sell", rooms=1)
    best, alternatives, reasoning = best_match([other, best_l], F)
    assert best is not None and best.token == "best"
    assert [x.token for x in alternatives] == ["other"]
    assert "آپارتمان گیشا" in reasoning
    assert "۱ میلیارد" in reasoning


def test_best_match_empty_candidates() -> None:
    best, alternatives, reasoning = best_match([], F)
    assert best is None
    assert alternatives == []
    assert reasoning


@pytest.mark.parametrize("lang", ["fa", "en"])
def test_reasoning_language(monkeypatch: pytest.MonkeyPatch, lang: str) -> None:
    monkeypatch.setenv("DIVAR_MCP_LANG", lang)
    _best, _, reasoning = best_match([_listing("x", rooms=2)], F)
    assert _best is not None
    assert reasoning
    if lang == "fa":
        assert any("\u0600" <= ch <= "\u06ff" for ch in reasoning)
