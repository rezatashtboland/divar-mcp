"""Shared data models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SellerType = Literal["owner", "agency", "builder", "dealer"]


class City(BaseModel):
    id: str
    name_fa: str
    name_en: str
    slug: str


class Category(BaseModel):
    id: str
    slug: str
    name_fa: str
    name_en: str = ""
    parent_id: str | None = None
    icon: str | None = None


class GeoLocation(BaseModel):
    latitude: float
    longitude: float
    address: str = ""
    neighborhood: str = ""


class SellerInfo(BaseModel):
    name: str = ""
    type: SellerType | None = None
    rating: float | None = None
    phone: str | None = None
    member_since: str | None = None
