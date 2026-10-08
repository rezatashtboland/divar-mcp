"""Side-by-side comparison of 2-5 listings."""

from __future__ import annotations

from ..models.filters import ComparisonResult
from ..models.listing import Listing
from ..utils.price import format_toman_words

_COMPARE_FIELDS = [
    ("price_toman", "قیمت (تومان)", lambda v: format_toman_words(v) if v else "نامشخص"),
    ("area", "متراژ (متر)", lambda v: str(v) if v else "نامشخص"),
    ("rooms", "تعداد اتاق", lambda v: str(v) if v else "نامشخص"),
    ("floor", "طبقه", lambda v: str(v) if v else "نامشخص"),
    ("construction_year", "سال ساخت", lambda v: str(v) if v else "نامشخص"),
    ("deal_type", "نوع معامله", lambda v: v if v else "نامشخص"),
    ("has_elevator", "آسانسور", lambda v: "دارد" if v else "ندارد" if v is not None else "نامشخص"),
    ("has_parking", "پارکینگ", lambda v: "دارد" if v else "ندارد" if v is not None else "نامشخص"),
    ("has_storage", "انباری", lambda v: "دارد" if v else "ندارد" if v is not None else "نامشخص"),
    ("has_balcony", "بالکن", lambda v: "دارد" if v else "ندارد" if v is not None else "نامشخص"),
    ("district_name_fa", "محله", lambda v: v if v else "نامشخص"),
    ("city_name_fa", "شهر", lambda v: v if v else "نامشخص"),
    ("category", "دسته‌بندی", lambda v: v if v else "نامشخص"),
    ("posted_at", "تاریخ ثبت", lambda v: v if v else "نامشخص"),
]


def compare_listings(listings: list[Listing]) -> ComparisonResult:
    if len(listings) < 2:
        raise ValueError("حداقل دو آگهی برای مقایسه لازم است. / At least two listings required.")
    if len(listings) > 5:
        raise ValueError("حداکثر پنج آگهی قابل مقایسه است. / At most five listings allowed.")

    diff: dict[str, dict[str, str]] = {}
    tokens = [lst.token for lst in listings]

    for attr, label, formatter in _COMPARE_FIELDS:
        values = {}
        for token, listing in zip(tokens, listings, strict=True):
            val = getattr(listing, attr, None)
            values[token] = formatter(val)  # type: ignore[no-untyped-call]
        # Include only if not all the same
        uniq = set(values.values())
        if len(uniq) > 1:
            diff[label] = values

    summary = _build_summary(listings, diff)
    return ComparisonResult(comparison=diff, summary=summary)


def parse_price(text: str) -> int:
    """Parse a Persian price word like \"۱ میلیارد\" to integer toman."""
    import re

    from ..utils.persian import normalize_digits

    norm = normalize_digits(text)
    match = re.search(r"(\d+(?:\.\d+)?)", norm)
    if not match:
        return 0
    value = float(match.group(1))
    if "میلیارد" in text:
        value *= 1_000_000_000
    elif "میلیون" in text:
        value *= 1_000_000
    elif "هزار" in text:
        value *= 1_000
    return int(value)


def _build_summary(listings: list[Listing], diff: dict[str, dict[str, str]]) -> str:
    if not diff:
        return "هیچ تفاوتی یافت نشد. / No differences found."
    parts = [f"مقایسه {len(listings)} آگهی:"]
    # price
    price_diff = diff.get("قیمت (تومان)")
    if price_diff:
        sorted_prices = sorted(
            ((t, v) for t, v in price_diff.items() if v != "نامشخص"),
            key=lambda x: parse_price(x[1]),
        )
        if sorted_prices:
            cheapest = sorted_prices[0][0]
            parts.append(f"ارزان‌ترین: {cheapest}")
    # area
    area_diff = diff.get("متراژ (متر)")
    if area_diff:
        sorted_area = sorted(
            ((t, v) for t, v in area_diff.items() if v != "نامشخص"),
            key=lambda x: float(x[1]),
            reverse=True,
        )
        if sorted_area:
            biggest = sorted_area[0][0]
            parts.append(f"بزرگ‌ترین: {biggest}")
    return " | ".join(parts)
