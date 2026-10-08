"""Rule-based Persian/English query parsing into SearchFilters.

Regex rules from the PRD run over normalized text (ASCII digits, unified
ی/ک, lower-case Latin, ZWNJ removed). Consumed spans are stripped from the
text to produce the free-text ``query`` for product-style categories.
"""

from __future__ import annotations

import re
from typing import Any

from .. import config
from ..models.filters import SearchFilters
from ..utils.persian import normalize_text, transliterate, word_to_int
from ..utils.price import parse_amount

_MULTIPLIER = re.compile(r"هزار|میلیون|میلیارد|thousand|million|billion", re.IGNORECASE)
_AMOUNT_SPAN = (
    r"\d+(?:\.\d+)?(?:\s*(?:هزار|میلیون|میلیارد|thousand|million|billion))?"
    r"(?:\s*(?:تومان|تومن|ریال|toman|rial))?"
)

_CURRENCY_MULTIPLIERS = {
    "هزار": 1_000,
    "میلیون": 1_000_000,
    "میلیارد": 1_000_000_000,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}

_REAL_ESTATE_TERMS = {
    "آپارتمان",
    "اپارتمان",
    "خانه",
    "ویلا",
    "سوئیت",
    "سوییت",
    "مغازه",
    "زمین",
    "برج",
    "آشپزخانه",
    "خواب",
    "متری",
    "رهن",
}
_CAR_WORDS = {"خودرو", "ماشین", "سواری", "car"}
_CAR_BRANDS = {
    "پژو",
    "پراید",
    "پارس",
    "تیبا",
    "سمن",
    "ساینا",
    "سمند",
    "دنا",
    "مگان",
    "رایان",
    "ریا",
    "رشید",
    "زامیاد",
    "کوییک",
    "شاهین",
    "تولید",
    "santro",
    "samand",
    "peugeot",
    "pride",
    "hyundai",
    "toyota",
    "benz",
    "bmw",
    "kia",
    "ford",
    "nissan",
    "mvm",
    "chery",
    "jacks",
    "tiggo",
    "dena",
    "tucson",
    "sandero",
    "logan",
}
_DIGITAL_TERMS = {"موبایل", "گوشی", "لپ‌تاپ", "لپتاپ", "کنسول", "phone", "mobile", "laptop"}

_COLORS = {
    "سفید": "white",
    "white": "white",
    "مشکی": "black",
    "black": "black",
    "قرمز": "red",
    "red": "red",
    "آبی": "blue",
    "blue": "blue",
    "خاکستری": "gray",
    "gray": "gray",
    "grey": "gray",
    "نقره‌ای": "silver",
    "نقره ای": "silver",
    "silver": "silver",
    "بژ": "beige",
    "beige": "beige",
    "کرم": "beige",
}

_FEATURE_KEYS = {
    "اسانسور": "has_elevator",
    "آسانسور": "has_elevator",
    "پارکینگ": "has_parking",
    "انباری": "has_storage",
    "بالکن": "has_balcony",
}
_CONNECTORS = {"و", "همچنین"}

_DISTRICT_STOP = {"هست", "است", "توی", "در", "که", "از", "را", "و", "هستی"}

CityIndex = dict[str, str]


def _city_index() -> CityIndex:
    index: CityIndex = {}
    for slug, name_fa, name_en in config.STATIC_CITIES:
        index[normalize_text(name_fa)] = slug
        if name_en:
            index[normalize_text(name_en)] = slug
        index[slug] = slug
    return index


_CITY_INDEX = _city_index()


def _overlaps(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < s_end and s_start < end for s_start, s_end in spans)


def _match_amount(text: str) -> int | None:
    return parse_amount(text)


def parse_query(query: str, city: str | None = None, category: str | None = None) -> SearchFilters:
    norm = normalize_text(query).replace("\u066b", ".")
    spans: list[tuple[int, int]] = []

    def take(pattern: str) -> re.Match[str] | None:
        for match in re.finditer(pattern, norm):
            if not _overlaps(spans, match.start(), match.end()):
                spans.append(match.span())
                return match
        return None

    values: dict[str, object] = {}

    if take(r"ارزانترین|ارزان ترین|ارزانتر|cheapest|arzan"):
        values["sort"] = "cheapest"
    elif take(r"گرانترین|گران ترین|most_expensive"):
        values["sort"] = "most_expensive"

    if take(r"اجاره\s*روزانه|روزانه"):
        values["deal_type"] = "daily_rent"
    elif take(r"رهن\s*و\s*اجاره") or take(r"اجاره"):
        values["deal_type"] = "rent"
    elif take(r"فروش|فروشی"):
        values["deal_type"] = "sell"

    time_match = take(r"(?:توی|در)?\s*(\d+)\s*(روز|هفته|ماه)[^.]*گذشته")
    if time_match:
        count = int(time_match.group(1))
        unit = time_match.group(2)
        values["posted_within_days"] = count * {"روز": 1, "هفته": 7, "ماه": 30}[unit]
    elif take(r"هفته\s*گذشته|این هفته"):
        values["posted_within_days"] = 7
    elif take(r"امروز|همین امروز"):
        values["posted_within_days"] = 1

    area_range = take(r"بین\s*(\d+(?:\.\d+)?)\s*(?:متر)?\s*(?:تا|تو|به)\s*(\d+(?:\.\d+)?)\s*متر")
    if area_range:
        values["min_area"] = float(area_range.group(1))
        values["max_area"] = float(area_range.group(2))
    else:
        price_range = take(
            r"بین\s*(\d+(?:\.\d+)?)\s*(هزار|میلیون|میلیارد|thousand|million|billion)?"
            r"\s*(?:تا|تو|به|الى)\s*(\d+(?:\.\d+)?)\s*(هزار|میلیون|میلیارد|thousand|million|billion)?"
            r"(?:\s*(?:تومان|تومن|ریال|toman|rial))?"
        )
        if price_range and (price_range.group(2) or price_range.group(4)):
            low, unit_a, high, unit_b = price_range.groups()
            unit = unit_a or unit_b
            factor = _CURRENCY_MULTIPLIERS.get(str(unit), 1)
            values["min_price"] = int(float(low) * factor)
            values["max_price"] = int(float(high) * factor)
        elif price_range:
            spans.pop()
        else:
            upper = take(rf"(?:زیر|کمتر از|تا سقف|under|below)\s*({_AMOUNT_SPAN})")
            if upper:
                amount = _match_amount(upper.group(1))
                if amount is not None:
                    values["max_price"] = amount
            lower = take(rf"(?:بیشتر از|بیش از|بالای|over|more than)\s*({_AMOUNT_SPAN})")
            if lower:
                amount = _match_amount(lower.group(1))
                if amount is not None:
                    values["min_price"] = amount

    if "min_area" not in values:
        area_match = take(r"(\d+(?:\.\d+)?)\s*(?:متری|متر)")
        if area_match:
            area = float(area_match.group(1))
            values["min_area"] = area - 5
            values["max_area"] = area + 5

    rooms_match = take(r"(یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|\d+)\s*-?\s*خواب")
    if rooms_match:
        rooms = word_to_int(rooms_match.group(1))
        if rooms is not None:
            values["rooms"] = rooms

    _apply_features(norm, spans, values)

    mileage = take(rf"کارکرد\s*({_AMOUNT_SPAN})")
    if mileage:
        km = _match_amount(mileage.group(1))
        if km is not None:
            values["mileage_max"] = km

    if take(r"اتوماتیک|automatic|auto\b"):
        values["transmission"] = "automatic"
    elif take(r"دنده\s*ای|manual"):
        values["transmission"] = "manual"

    fuel = take(r"بنزین|gasoline")
    if fuel:
        values["fuel_type"] = "gasoline"
    elif take(r"دیزل|diesel"):
        values["fuel_type"] = "diesel"
    elif take(r"هیبرید|hybrid"):
        values["fuel_type"] = "hybrid"
    elif take(r"برقی|electric"):
        values["fuel_type"] = "electric"
    elif take(r"سی‌ان‌جی|دوگانه|cng"):
        values["fuel_type"] = "cng"

    model_match = take(r"(?:مدل|model)\s*(\d{4})")
    if model_match:
        values["model_year_min"] = int(model_match.group(1)) - 1

    _apply_color(norm, spans, values)

    detected_city, city_spans = _detect_city(norm)
    spans.extend(city_spans)
    values["city"] = city or detected_city or "tehran"

    district_slug = _detect_district(norm, spans)
    if district_slug:
        values["districts"] = [district_slug]

    guess = _guess_category(norm)
    values["category"] = category or guess

    if values["category"] not in ("real-estate",):
        leftover = _leftover(norm, spans)
        if leftover:
            values["query"] = leftover

    return SearchFilters.model_validate(values)


def _apply_features(norm: str, spans: list[tuple[int, int]], values: dict[str, Any]) -> None:
    tokens = re.split(r"\s+", norm)
    positions = _token_positions(norm)
    for i, token in enumerate(tokens):
        cleaned = token.strip(".،:؛!")
        field = _FEATURE_KEYS.get(cleaned)
        if not field or field in values:
            continue
        j = i - 1
        while j >= 0 and tokens[j].strip(".،:؛!") in _CONNECTORS | set(_FEATURE_KEYS):
            j -= 1
        if j >= 0 and tokens[j].strip(".،:؛!") in {"با", "دارای"}:
            values[field] = True
            start, end = positions[i]
            if not _overlaps(spans, start, end):
                spans.append((start, end))


def _token_positions(text: str) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for match in re.finditer(r"\S+", text):
        positions.append(match.span())
    return positions


def _apply_color(norm: str, spans: list[tuple[int, int]], values: dict[str, Any]) -> None:
    for phrase, color in _COLORS.items():
        pattern = rf"(?<![\w]){re.escape(normalize_text(phrase))}(?![\w])"
        for match in re.finditer(pattern, norm):
            if not _overlaps(spans, match.start(), match.end()):
                spans.append(match.span())
                values["color"] = color
                return


def _detect_city(norm: str) -> tuple[str | None, list[tuple[int, int]]]:
    spans: list[tuple[int, int]] = []
    found: str | None = None
    for match in re.finditer(r"\S+", norm):
        token = match.group(0).strip(".،:؛!")
        slug = _CITY_INDEX.get(token)
        if slug:
            found = found or slug
            start, end = match.span()
            lead = re.search(r"(?:in|at|by|به|از|شهر)\s+$", norm[:start])
            if lead:
                start = start - (lead.end() - lead.start())
            spans.append((start, end))
    return found, spans


def _detect_district(norm: str, spans: list[tuple[int, int]]) -> str | None:
    match = re.search(r"(?:محله|منطقه|بزرگراه|خیابان)\s+([\u0600-\u06FF0-9a-zA-Z\- ]+)", norm)
    if not match:
        return None
    parts = match.group(1).split()
    kept: list[str] = []
    for part in parts:
        if part in _DISTRICT_STOP:
            break
        kept.append(part)
        if len(kept) >= 3:
            break
    if not kept:
        return None
    name = " ".join(kept)
    spans.append((match.start(1), match.start(1) + len(name)))
    return transliterate(name) or name


def _guess_category(norm: str) -> str:
    tokens = [t.strip(".،:؛!") for t in norm.split()]
    if any(t in _CAR_BRANDS or t in _CAR_WORDS for t in tokens):
        return "car"
    if any(t in _REAL_ESTATE_TERMS for t in tokens):
        return "real-estate"
    if any(t in _DIGITAL_TERMS for t in tokens):
        return "electronic-devices"
    if "اجاره" in norm or "رهن" in norm:
        return "real-estate"
    return "real-estate"


def _leftover(norm: str, spans: list[tuple[int, int]]) -> str:
    marks = sorted(spans)
    out: list[str] = []
    cursor = 0
    for start, end in marks:
        if start > cursor:
            out.append(norm[cursor:start])
        cursor = max(cursor, end)
    out.append(norm[cursor:])
    text = re.sub(r"\s+", " ", " ".join(out)).strip(" .،,:؛")
    return text if len(text.split()) >= 1 else ""
