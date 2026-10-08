"""Fetch and map a single listing detail page into a Listing model."""

from __future__ import annotations

import re
from typing import Any

import jdatetime

from .. import config
from ..client.http import DivarUnavailableError, HttpClient
from ..client.jsonld import extract_jsonld, pick_listing_node
from ..client.page_state import PageStateError, current_post, extract_state
from ..models.common import GeoLocation, SellerInfo
from ..models.listing import DealType, Listing
from ..utils.persian import normalize_digits, normalize_text, word_to_int
from ..utils.price import parse_amount, toman_to_rial

_JALALI_RE = re.compile(r"(\d{1,2})\s*([\u0600-\u06FF]+)\s*(\d{4})")
_MONTHS_FA = (
    "فروردين",
    "ارديبهشت",
    "خرداد",
    "تير",
    "مرداد",
    "شهريور",
    "مهر",
    "آبان",
    "آذر",
    "دي",
    "بهمن",
    "اسفند",
)

_INT_ROW_LABELS: dict[str, str] = {
    "متراژ": "area",
    "مساحت": "area",
    "زیربنا": "area",
    "سال ساخت": "construction_year",
    "ساخت": "construction_year",
    "تعداد اتاق": "rooms",
    "اتاق": "rooms",
    "طبقه": "floor",
    "تعداد طبقات": "total_floors",
    "تعداد طباق": "total_floors",
    "مدل": "model_year",
    "سال تولید": "model_year",
    "کارکرد": "mileage",
}

_BOOL_ROW_LABELS: dict[str, str] = {
    "آسانسور": "has_elevator",
    "اسانسور": "has_elevator",
    "پارکینگ": "has_parking",
    "انباری": "has_storage",
    "بالکن": "has_balcony",
}

_YES = {"بله", "دارد", "هست", "پارکینگ دارد"}
_NO = {"خیر", "ندارد", "نیست", "ندارد."}


class ListingNotFoundError(DivarUnavailableError):
    def __init__(self) -> None:
        super().__init__(
            "این آگهی در دیوار پیدا نشد یا منقضی شده است.",
            "This listing was not found on divar.ir or has expired.",
        )


async def fetch_listing_detail(
    http: HttpClient, token: str, slug: str = "", city: str | None = None
) -> Listing:
    url = f"{config.BASE_URL}/v/{slug or token}/{token}"
    html = await http.get_text(url, cache="detail")
    try:
        state = extract_state(html)
    except PageStateError as exc:
        raise ListingNotFoundError() from exc
    post = current_post(state)
    if post is None:
        raise ListingNotFoundError()
    if city and post.get("city", {}).get("slug") and post["city"]["slug"] != city:
        raise DivarUnavailableError(
            f"این آگهی مربوط به شهر {post['city']['slug']} است، نه {city}.",
            f"This listing belongs to {post['city']['slug']}, not {city}.",
        )
    return parse_detail_post(post, url=url, jsonld_entries=extract_jsonld(html))


def parse_detail_post(
    post: dict[str, Any],
    url: str = "",
    jsonld_entries: list[dict[str, Any]] | None = None,
) -> Listing:
    seo = post.get("seo") or {}
    web_info = seo.get("webInfo") or {}
    token = str(post.get("token") or "")
    html_url = url or str(web_info.get("url") or "")
    slug = _slug_from_url(html_url, token)

    entries = jsonld_entries or []
    ld = pick_listing_node(entries, token=token) or (entries[0] if entries else {})

    title = str(web_info.get("title") or ld.get("name") or seo.get("title") or "")
    description = _description(ld, post)
    rows = _detail_rows(post)
    category, category_name_fa = _category(post, web_info)

    price_toman = _price_from_rows(rows)
    if price_toman is None and isinstance(ld.get("offers"), dict):
        raw_price = parse_amount(str(ld["offers"].get("price") or ""))
        if raw_price is not None:
            price_toman = raw_price
    price = toman_to_rial(price_toman) if price_toman is not None else None

    location = _location(ld, web_info)
    deal_type = _deal_type(category, rows)

    kwargs: dict[str, Any] = {
        "token": token,
        "slug": slug,
        "url": html_url,
        "title": title,
        "description": description,
        "category": category,
        "category_name_fa": category_name_fa,
        "city": str(post.get("city", {}).get("slug") or ""),
        "city_name_fa": str(post.get("city", {}).get("name") or ""),
        "district": "",
        "district_name_fa": str(web_info.get("district_persian") or ""),
        "price": price,
        "price_toman": price_toman,
        "price_currency": "IRR" if price is not None else None,
        "deal_type": deal_type,
        "images": _images(post, ld),
        "posted_at": _posted_at(seo),
        "seller": SellerInfo(),
        "location": location,
        "schema_data": ld,
    }

    for label, field in _INT_ROW_LABELS.items():
        value = _row_value(rows, label)
        if value is None:
            continue
        number = word_to_int(value)
        if number is not None:
            kwargs[field] = float(number) if field == "area" else number
    if kwargs.get("rooms") is None:
        kwargs["rooms"] = word_to_int(str(ld.get("numberOfRooms") or ""))
    if kwargs.get("area") is None and isinstance(ld.get("floorSize"), dict):
        kwargs["area"] = _to_float(ld["floorSize"].get("value"))
    for label, field in _BOOL_ROW_LABELS.items():
        value = _row_value(rows, label)
        if value is None:
            continue
        cleaned = normalize_text(value)
        if cleaned in _YES:
            kwargs[field] = True
        elif cleaned in _NO:
            kwargs[field] = False

    return Listing.model_validate(kwargs)


def _slug_from_url(url: str, token: str) -> str:
    match = re.search(r"/v/([^/]+)/" + re.escape(token), url or "")
    return match.group(1) if match else ""


def _description(ld: dict[str, Any], post: dict[str, Any]) -> str:
    from_ld = ld.get("description")
    if from_ld:
        return str(from_ld).strip()
    chunks: list[str] = []
    for widget in _widgets(post, "DESCRIPTION"):
        data = _dto_data(widget)
        text = data.get("description") or data.get("text") or ""
        if str(text).strip() and str(text).strip() != "توضیحات":
            chunks.append(str(text).strip())
    return "\n".join(chunks)


def _images(post: dict[str, Any], ld: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for widget in _widgets(post, "IMAGE"):
        data = _dto_data(widget)
        for item in data.get("items") or []:
            image = item.get("image") or {}
            url = item.get("image_url") or image.get("url") or ""
            if url and url not in urls:
                urls.append(str(url))
    if not urls and ld.get("image"):
        urls.append(str(ld["image"]))
    return urls


def _location(ld: dict[str, Any], web_info: dict[str, Any]) -> GeoLocation | None:
    geo = ld.get("geo")
    if not isinstance(geo, dict):
        return None
    lat = _to_float(geo.get("latitude"))
    lng = _to_float(geo.get("longitude"))
    if lat is None or lng is None:
        return None
    return GeoLocation(
        latitude=lat,
        longitude=lng,
        address=str(geo.get("address") or ""),
        neighborhood=str(web_info.get("district_persian") or ""),
    )


def _category(post: dict[str, Any], web_info: dict[str, Any]) -> tuple[str, str]:
    slug = ""
    # Breadcrumbs come deepest-first; the first category value is the most
    # specific one (e.g. apartment-sell under residential-sell under real-estate).
    for crumb in post.get("seo", {}).get("breadcrumbs") or []:
        value = (
            crumb.get("searchData", {})
            .get("formData", {})
            .get("category", {})
            .get("str", {})
            .get("value")
        )
        if value:
            slug = str(value)
            break
    name = str(web_info.get("category_slug_persian") or "")
    return slug, name


def _deal_type(category: str, rows: dict[str, str]) -> DealType | None:
    normalized = normalize_text(category)
    if "daily" in normalized or "روزانه" in normalized:
        return "daily_rent"
    if "rent-to-own" in normalized or ("پیش فروش" in normalized and "اجاره" in normalized):
        return "rent_to_own"
    if "rent" in normalized or "اجاره" in normalized:
        return "rent"
    if "sell" in normalized or "فروش" in normalized:
        return "sell"
    if any("اجاره" in label or "رهن" in label for label in rows):
        return "rent"
    if any("قیمت" in label for label in rows):
        return "sell"
    return None


def _price_from_rows(rows: dict[str, str]) -> int | None:
    for label in ("قیمت کل", "قیمت", "قیمت پیشنهادی"):
        value = _row_value(rows, label)
        if value:
            amount = parse_amount(value)
            if amount is not None:
                return amount
    return None


def _detail_rows(post: dict[str, Any]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for widget in _widgets(post, "LIST_DATA"):
        data = _dto_data(widget)
        for item in data.get("items") or []:
            title = str(item.get("title") or "").strip()
            if title:
                rows[title] = str(item.get("value") or "").strip()
        title = str(data.get("title") or "").strip()
        if title and data.get("value") is not None:
            rows[title] = str(data.get("value") or "").strip()
    return rows


def _row_value(rows: dict[str, str], label: str) -> str | None:
    if label in rows:
        return rows[label]
    for key, value in rows.items():
        if normalize_text(label) == normalize_text(key):
            return value
    return None


def _widgets(post: dict[str, Any], section: str) -> list[dict[str, Any]]:
    raw = (post.get("sections") or {}).get(section) or []
    widgets: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        body = item.get("data") if "widgetType" not in item else item
        if isinstance(body, dict):
            widgets.append(body)
    return widgets


def _dto_data(widget: dict[str, Any]) -> dict[str, Any]:
    dto = widget.get("dto") or {}
    data = dto.get("data") or {}
    return data if isinstance(data, dict) else {}


def _posted_at(seo: dict[str, Any]) -> str | None:
    title = str(seo.get("title") or "")
    match = _JALALI_RE.search(normalize_digits(title))
    if match:
        day, month_name, year = int(match.group(1)), match.group(2), int(match.group(3))
        month = _month_number(month_name)
        if month:
            try:
                greg = jdatetime.date(year, month, day).togregorian()
                return f"{greg.isoformat()}T00:00:00+03:30"
            except ValueError:
                pass
    unavailable = str(seo.get("unavailableAfter") or "")
    if unavailable:
        return f"{unavailable[:19]}Z"
    return None


def _month_number(name: str) -> int | None:
    def simplify(word: str) -> str:
        return word.replace("آ", "ا").replace("ی", "ي").replace("ك", "ک")

    target = simplify(normalize_text(name))
    for index, month in enumerate(_MONTHS_FA, start=1):
        if simplify(month) == target:
            return index
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = normalize_digits(str(value)).replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    return float(match.group(0)) if match else None
