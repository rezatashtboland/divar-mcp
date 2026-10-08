import json
from pathlib import Path

from divar_mcp.client.jsonld import extract_jsonld, pick_listing_node

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_extract_jsonld_from_detail_fixture() -> None:
    html = (FIXTURES / "listing_detail.html").read_text(encoding="utf-8")
    entries = extract_jsonld(html)
    assert entries
    types = {e.get("@type") for e in entries}
    assert "Apartment" in types


def test_extract_jsonld_skips_broken_and_flattens_lists() -> None:
    html = (
        "<html><head>"
        '<script type="application/ld+json">{"@type": "WebSite", "name": "x"}</script>'
        '<script type="application/ld+json">{broken json</script>'
        '<script type="application/ld+json">'
        + json.dumps([{"@type": "BreadcrumbList"}, {"@type": "Product", "name": "p"}])
        + "</script></head><body></body></html>"
    )
    entries = extract_jsonld(html)
    assert [e["@type"] for e in entries] == ["WebSite", "BreadcrumbList", "Product"]


def test_pick_listing_node_skips_site_meta() -> None:
    entries = [
        {"@type": "BreadcrumbList"},
        {"@type": "WebSite"},
        {"@type": "Apartment", "url": "https://divar.ir/v/tok-x/gaGfdm8V"},
    ]
    node = pick_listing_node(entries)
    assert node is not None and node["@type"] == "Apartment"
    assert pick_listing_node(entries, token="nope") is None
    assert pick_listing_node(entries, token="gaGfdm8V") is not None


def test_pick_listing_node_handles_type_lists() -> None:
    node = pick_listing_node([{"@type": ["Product", "Thing"], "name": "n"}])
    assert node is not None
