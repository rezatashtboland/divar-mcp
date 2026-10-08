import json
from pathlib import Path

import pytest

from divar_mcp.client.page_state import (
    PageStateError,
    extract_current_post,
    extract_state,
    iter_post_widgets,
    linked_data,
    parse_pagination,
    root_category,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def list_html() -> str:
    return (FIXTURES / "tehran_real_estate.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def detail_html() -> str:
    return (FIXTURES / "listing_detail.html").read_text(encoding="utf-8")


def test_extract_state_returns_dict(list_html: str) -> None:
    state = extract_state(list_html)
    assert isinstance(state, dict)
    assert "nb" in state


def test_extract_state_handles_escaped_unicode() -> None:
    inner = json.dumps({"nb": {"pagination": {"hasMore": True}}}).replace("/", "\\u002F")
    html = f"<html><script>window.__PRELOADED_STATE__ = {inner};</script></html>"
    state = extract_state(html)
    assert state["nb"]["pagination"]["hasMore"] is True


def test_extract_state_missing_raises() -> None:
    with pytest.raises(PageStateError):
        extract_state("<html><body>nothing</body></html>")


def test_extract_state_invalid_json_raises() -> None:
    with pytest.raises(PageStateError):
        extract_state("<script>window.__PRELOADED_STATE__ = {broken</script>")


def test_pagination_fields(list_html: str) -> None:
    page = parse_pagination(extract_state(list_html))
    assert page.has_more is True
    assert page.last_post_date is not None
    assert page.last_post_date.startswith("20")


def test_post_widgets_populated(list_html: str) -> None:
    rows = iter_post_widgets(extract_state(list_html))
    assert len(rows) >= 20
    tokens = {r.token for r in rows}
    assert len(tokens) == len(rows)
    with_info = [r for r in rows if r.web_info.city_persian]
    assert len(with_info) >= 20
    assert all(r.token for r in rows)
    assert any(r.posted_at for r in rows)


def test_linked_data_schema_org(list_html: str) -> None:
    entries = linked_data(extract_state(list_html))
    assert len(entries) >= 20
    apartments = [e for e in entries if e.get("@type") == "Apartment"]
    assert apartments
    ap = apartments[0]
    assert ap["floorSize"]["value"]
    assert ap["geo"]["latitude"]
    assert ap["web_info"]["city_persian"] == "تهران"


def test_root_category_tree(list_html: str) -> None:
    root = root_category(extract_state(list_html))
    assert root is not None
    assert root["slug"] == "ROOT"
    children = root["children"]
    assert len(children) >= 5
    slugs = [c["slug"] for c in children]
    assert "real-estate" in slugs


def test_detail_current_post(detail_html: str) -> None:
    post = extract_current_post(detail_html)
    assert post is not None
    assert post["token"] == "gaGfdm8V"
    assert post["city"]["slug"] == "tehran"
    assert "LIST_DATA" in post["sections"]
    assert "DESCRIPTION" in post["sections"]
