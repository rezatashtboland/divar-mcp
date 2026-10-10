"""Price parsing and formatting utilities."""

from __future__ import annotations

import re
from typing import Optional

_MULTIPLIERS = {
    "هزار": 1_000,
    "ميليون": 1_000_000,
    "میلیون": 1_000_000,
    "ميليارد": 1_000_000_000,
    "میلیارد": 1_000_000_000,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}

_CURRENCY_SUFFIXES = {
    "تومان": 1,
    "تومن": 1,
    "ریال": 0.1,
    "rial": 0.1,
    "toman": 1,
}


def parse_amount(text: str) -> Optional[int]:
    """Parse Persian/English price text to integer (tomans)."""
    if not text:
        return None
    # Convert Persian decimal point to regular dot, remove thousands separators
    normalized = text.replace(",", "").replace("،", "").replace("\u066b", ".")
    # Find number with optional multiplier and currency
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*"
        r"(هزار|ميليون|میلیون|ميليارد|میلیارد|thousand|million|billion)?\s*"
        r"(تومان|تومن|ریال|rial|toman)?",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        return None
    value_str, multiplier_str, currency_str = match.groups()
    try:
        value = float(value_str)
    except ValueError:
        return None
    multiplier = _MULTIPLIERS.get(multiplier_str or "", 1)
    currency_factor = _CURRENCY_SUFFIXES.get((currency_str or "").lower(), 1)
    result = int(value * multiplier * currency_factor)
    return result


def toman_to_rial(toman: int) -> int:
    """Convert toman to rial (1 toman = 10 rial)."""
    return toman * 10


def rial_to_toman(rial: int) -> int:
    """Convert rial to toman (10 rial = 1 toman)."""
    return rial // 10


_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ENGLISH_DIGITS = "0123456789"
_PERSIAN_DIGIT_MAP = str.maketrans(_ENGLISH_DIGITS, _PERSIAN_DIGITS)


def format_number(number: int) -> str:
    """Format integer with Persian digits and comma grouping."""
    if number == 0:
        return "۰"
    parts: list[str] = []
    s = str(number)
    # Add commas for thousands
    for i in range(len(s) - 1, -1, -3):
        start = max(0, i - 2)
        parts.append(s[start:i+1])
    result = ",".join(reversed(parts))
    return result.translate(_PERSIAN_DIGIT_MAP)


def format_toman_words(toman: int) -> str:
    """Format toman amount as Persian words with digits."""
    if toman < 0:
        return ""
    if toman == 0:
        return "صفر"
    parts: list[str] = []
    if toman >= 1_000_000_000:
        billions = toman // 1_000_000_000
        remainder = toman % 1_000_000_000
        if remainder >= 100_000_000:  # At least 0.1 billion
            # Use decimal notation: e.g., 1.5 billion
            value = toman / 1_000_000_000
            parts.append(f"{value:g} میلیارد")
            toman = 0
        else:
            parts.append(f"{billions} میلیارد")
            toman = remainder
    if toman >= 1_000_000:
        millions = toman // 1_000_000
        remainder = toman % 1_000_000
        if remainder >= 100_000:  # At least 0.1 million
            value = toman / 1_000_000
            parts.append(f"{value:g} میلیون")
            toman = 0
        else:
            parts.append(f"{millions} میلیون")
            toman = remainder
    if toman >= 1_000:
        thousands = toman // 1_000
        parts.append(f"{thousands} هزار")
        toman %= 1_000
    if toman > 0:
        parts.append(str(toman))
    return " و ".join(p for p in parts).translate(_PERSIAN_DIGIT_MAP)