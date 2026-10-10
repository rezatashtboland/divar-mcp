"""Persian text normalization and utilities."""

from __future__ import annotations

import re

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ENGLISH_DIGITS = "0123456789"
_DIGIT_MAP = str.maketrans(_PERSIAN_DIGITS, _ENGLISH_DIGITS)
_PERSIAN_DIGIT_MAP = str.maketrans(_ENGLISH_DIGITS, _PERSIAN_DIGITS)

_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ARABIC_DIGIT_MAP = str.maketrans(_ARABIC_INDIC_DIGITS, _ENGLISH_DIGITS)


def normalize_letters(text: str) -> str:
    """Normalize Arabic letters to Persian (yeh, kaf)."""
    if not text:
        return ""
    return text.replace("ي", "ی").replace("ك", "ک")


def normalize_text(text: str) -> str:
    """Normalize Persian/Arabic text for matching."""
    if not text:
        return ""
    # Replace Arabic yeh/kaf with Persian
    text = text.replace("ي", "ی").replace("ك", "ک")
    # Remove zero-width non-joiner, zero-width joiner, tatweel, soft hyphen
    text = text.replace("\u200c", "").replace("\u200d", "").replace("\u0640", "").replace("\u00ad", "")
    # Convert Persian and Arabic digits to English
    text = text.translate(_DIGIT_MAP).translate(_ARABIC_DIGIT_MAP)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Lowercase Latin letters
    return text.lower().strip()


def normalize_digits(text: str) -> str:
    """Convert Persian/Arabic digits in text to English digits."""
    if not text:
        return ""
    return text.translate(_DIGIT_MAP).translate(_ARABIC_DIGIT_MAP)


def to_persian_digits(number: int | float | str) -> str:
    """Convert a number to Persian digit string."""
    return str(number).translate(_PERSIAN_DIGIT_MAP)


def transliterate(text: str) -> str:
    """Convert Persian text to latin slug (lowercase, no spaces)."""
    if not text:
        return ""
    normalized = normalize_text(text)
    # Replace Persian characters with Latin equivalents
    persian_to_latin = {
        'ا': 'a', 'آ': 'a', 'ب': 'b', 'پ': 'p', 'ت': 't', 'ث': 's',
        'ج': 'j', 'چ': 'ch', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'z',
        'ر': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's', 'ش': 'sh', 'ص': 's',
        'ض': 'z', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f',
        'ق': 'gh', 'ک': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n',
        'و': 'v', 'ه': 'h', 'ی': 'i', 'ئ': 'i', 'ء': '', 'ؤ': 'v',
    }
    result = ""
    for char in normalized:
        if char in persian_to_latin:
            result += persian_to_latin[char]
        elif char.isalnum() or char in ' -_':
            result += char
        else:
            result += '-'
    # Replace spaces and special chars with hyphens
    result = re.sub(r"[\s\W]+", "-", result)
    return result.strip("-")


_WORD_TO_INT = {
    "صفر": 0,
    "یک": 1,
    "یکِ": 1,
    "دو": 2,
    "دوِ": 2,
    "سه": 3,
    "سهِ": 3,
    "چهار": 4,
    "چهارِ": 4,
    "پنج": 5,
    "پنجِ": 5,
    "شش": 6,
    "ششِ": 6,
    "هفت": 7,
    "هفتِ": 7,
    "هشت": 8,
    "هشتِ": 8,
    "نه": 9,
    "نهِ": 9,
    "ده": 10,
    "دهِ": 10,
    "یازده": 11,
    "دوازده": 12,
    "سیزده": 13,
    "چهارده": 14,
    "پانزده": 15,
    "شانزده": 16,
    "هفده": 17,
    "هجده": 18,
    "نوزده": 19,
    "بیست": 20,
}


def word_to_int(text: str) -> int | None:
    """Convert Persian number word to integer."""
    if not text:
        return None
    normalized = normalize_text(text.strip())
    # Try direct word match
    if normalized in _WORD_TO_INT:
        return _WORD_TO_INT[normalized]
    # Try parsing as digits
    try:
        return int(normalized)
    except ValueError:
        return None


# Mapping from Latin district name to set of aliases (Persian and Latin)
_DISTRICT_ALIASES: dict[str, set[str]] = {
    "vanak": {"vanak", "وانک", "ونک"},
    "tajrish": {"tajrish", "تجریش"},
    "zafar": {"zafar", "ظفر"},
    "gisha": {"gisha", "گیشا"},
    "ekbatan": {"ekbatan", "اکباتان"},
    "golha": {"golha", "گلها"},
    "shahrak gharb": {"shahrak gharb", "شهرک غرب"},
    "yousef abad": {"yousef abad", "یوسف آباد"},
    "narmak": {"narmak", "نرمک"},
    "sadeghieh": {"sadeghieh", "صادقیه"},
    "punak": {"punak", "پونک"},
    "abbas abad": {"abbas abad", "عباس آباد"},
    "tehran pars": {"tehran pars", "تهران پارس"},
    "shemiran": {"shemiran", "شمیران"},
    "dolat abad": {"dolat abad", "دولت آباد"},
    "hassan abad": {"hassan abad", "حسن آباد"},
    "javadiyeh": {"javadiyeh", "جوادیه"},
    "nazarm": {"nazarm", "نظرم"},
    "amini": {"amini", "امینی"},
    "mahdieh": {"mahdieh", "مهديه"},
    "tehran": {"tehran", "تهران"},
}


def district_matches(district: str, target: str) -> bool:
    """Check if district matches target (with aliases)."""
    if not district or not target:
        return False
    norm_district = normalize_text(district)
    norm_target = normalize_text(target)
    if norm_district == norm_target:
        return True
    # Check aliases - target should be a key in the mapping
    if norm_target in _DISTRICT_ALIASES:
        aliases = _DISTRICT_ALIASES[norm_target]
        if norm_district in aliases:
            return True
        # Handle compound names like "گیشای غربی" -> "gisha"
        # Check if district starts with a Persian alias for this target
        for alias in aliases:
            # If alias is Persian (contains non-Latin chars) and district starts with it
            if any('\u0600' <= c <= '\u06ff' for c in alias) and norm_district.startswith(alias):
                return True
    return False
    norm_district = normalize_text(district)
    norm_target = normalize_text(target)
    if norm_district == norm_target:
        return True
    # Check aliases (city-specific, but we don't have city here)
    for aliases in _DISTRICT_ALIASES.values():
        if norm_district in aliases and norm_target in aliases:
            return True
    return False