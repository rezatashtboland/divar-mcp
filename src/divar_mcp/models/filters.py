"""Search filter and tool result models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .common import SellerType
from .listing import BodyType, DealType, FuelType, Listing, Transmission

SortOption = Literal["newest", "cheapest", "most_expensive", "best_selling", "most_viewed"]


class SearchFilters(BaseModel):
    city: str
    category: str
    query: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    rooms: int | list[int] | None = None
    floor: int | None = None
    deal_type: DealType | None = None
    districts: list[str] | None = None
    has_elevator: bool | None = None
    has_parking: bool | None = None
    has_storage: bool | None = None
    has_balcony: bool | None = None
    construction_after: int | None = None
    posted_within_days: int | None = None
    seller_type: SellerType | None = None
    model_year_min: int | None = None
    model_year_max: int | None = None
    mileage_max: int | None = None
    transmission: Transmission | None = None
    fuel_type: FuelType | None = None
    body_type: BodyType | None = None
    color: str | None = None
    sort: SortOption | None = None
    page: int | None = Field(default=None, ge=1)
    page_size: int | None = Field(default=None, ge=1, le=50)


class SearchResult(BaseModel):
    listings: list[Listing] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False
    continue_hint: str | None = None


class FindBestMatchResult(BaseModel):
    best_match: Listing | None = None
    alternatives: list[Listing] = Field(default_factory=list)
    reasoning: str = ""
    extracted_filters: SearchFilters


class ComparisonResult(BaseModel):
    comparison: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
