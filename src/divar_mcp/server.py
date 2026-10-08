"""FastMCP server exposing the Divar tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client.http import HttpClient, get_default_client
from .models.filters import SearchFilters
from .models.listing import Listing
from .services.detail import fetch_listing_detail
from .services.discovery import fetch_categories, fetch_cities
from .services.matcher import find_best_match as _find_best_match
from .services.search import search

mcp = FastMCP("divar-mcp")


async def _with_client(coro: Callable[[HttpClient], Awaitable[Any]]) -> Any:
    http = get_default_client()
    try:
        return await coro(http)
    finally:
        await http.close()


async def _fetch_details(http: HttpClient, tokens: list[str]) -> list[Listing]:
    return [await fetch_listing_detail(http, t) for t in tokens]


@mcp.tool()
async def search_listings(filters: SearchFilters) -> dict[str, Any]:
    """Search Divar listings with filters and pagination."""
    result = await _with_client(lambda http: search(http, filters))
    return result.model_dump(mode="json", exclude_none=True)  # type: ignore[no-any-return]


@mcp.tool()
async def get_listing_details(token: str, city: str | None = None) -> dict[str, Any]:
    """Get complete details of a specific listing."""
    listing = await _with_client(lambda http: fetch_listing_detail(http, token, city=city))
    return listing.model_dump(mode="json", exclude_none=True)  # type: ignore[no-any-return]


@mcp.tool()
async def find_best_match(
    query: str, city: str | None = None, category: str | None = None, limit: int | None = None
) -> dict[str, Any]:
    """Find the best listing matching a natural language query."""
    result = await _with_client(
        lambda http: _find_best_match(http, query, city=city, category=category, limit=limit)
    )
    return result.model_dump(mode="json", exclude_none=True)  # type: ignore[no-any-return]


@mcp.tool()
async def get_cities() -> list[dict[str, Any]]:
    """List all supported cities."""
    cities = await _with_client(fetch_cities)
    return [c.model_dump(mode="json") for c in cities]


@mcp.tool()
async def get_categories(city: str) -> list[dict[str, Any]]:
    """List categories for a city."""
    categories = await _with_client(lambda http: fetch_categories(http, city))
    return [c.model_dump(mode="json") for c in categories]


@mcp.tool()
async def compare_listings(tokens: list[str]) -> dict[str, Any]:
    """Compare 2-5 listings side by side."""
    if len(tokens) < 2 or len(tokens) > 5:
        raise ValueError("باید بین 2 تا 5 توکن بدهید.")
    listings = await _with_client(lambda http: _fetch_details(http, tokens))
    from .services.comparison import compare_listings as do_cmp

    return do_cmp(listings).model_dump(mode="json", exclude_none=True)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
