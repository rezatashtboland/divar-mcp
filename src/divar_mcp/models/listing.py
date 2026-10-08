"""Listing model covering real-estate, vehicle and generic marketplace fields."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .common import GeoLocation, SellerInfo

DealType = Literal["rent", "sell", "rent_to_own", "daily_rent"]
Transmission = Literal["automatic", "manual"]
FuelType = Literal["gasoline", "diesel", "hybrid", "electric", "cng"]
BodyType = Literal["sedan", "hatchback", "suv", "coupe", "van", "pickup"]
PriceCurrency = Literal["IRR", "Toman"]


class Listing(BaseModel):
    token: str
    slug: str = ""
    url: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    category_name_fa: str = ""
    city: str = ""
    city_name_fa: str = ""
    district: str = ""
    district_name_fa: str = ""

    price: int | None = None
    price_toman: int | None = None
    price_currency: PriceCurrency | None = None

    area: float | None = None
    rooms: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    construction_year: int | None = None
    has_elevator: bool | None = None
    has_parking: bool | None = None
    has_storage: bool | None = None
    has_balcony: bool | None = None
    deal_type: DealType | None = None
    rent_amount: int | None = None
    deposit_amount: int | None = None

    model_year: int | None = None
    mileage: int | None = None
    transmission: Transmission | None = None
    fuel_type: FuelType | None = None
    body_type: BodyType | None = None
    color: str | None = None

    images: list[str] = Field(default_factory=list)
    posted_at: str | None = None
    posted_at_relative: str = ""
    seller: SellerInfo = Field(default_factory=SellerInfo)
    location: GeoLocation | None = None

    schema_data: dict[str, Any] = Field(default_factory=dict)
