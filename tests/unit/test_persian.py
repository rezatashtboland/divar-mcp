from divar_mcp.utils.persian import (
    district_matches,
    normalize_digits,
    normalize_letters,
    normalize_text,
    to_persian_digits,
    transliterate,
    word_to_int,
)


def test_transliterate() -> None:
    assert transliterate("گیشا") == "gisha"
    assert transliterate("تهران") == "thran"
    assert transliterate("نبرد") == "nbrd"
    assert transliterate("gisha") == "gisha"


def test_district_matches() -> None:
    assert district_matches("گیشا", "gisha")
    assert district_matches("تهران", "tehran")
    assert district_matches("ونک", "vanak")
    assert district_matches("گیشای غربی", "gisha")
    assert district_matches("گیشا", "گیشا")
    assert not district_matches("گیشا", "vanak")
    assert not district_matches("گیشا", "gharbi-gisha-or-tehran")
    assert not district_matches("بنی‌هاشم", "هاشمی")


def test_word_to_int() -> None:
    assert word_to_int("یک") == 1
    assert word_to_int("سه") == 3
    assert word_to_int("۲") == 2
    assert word_to_int("ده") == 10
    assert word_to_int("زیاد") is None


def test_normalize_digits_persian() -> None:
    assert normalize_digits("۱۲۳۴۵۶۷۸۹۰") == "1234567890"


def test_normalize_digits_arabic_indic() -> None:
    assert normalize_digits("٤٥٦") == "456"


def test_normalize_digits_mixed() -> None:
    assert normalize_digits("۶۰m۲") == "60m2"
    assert normalize_digits("abc") == "abc"


def test_normalize_letters_yeh_and_kaf() -> None:
    assert normalize_letters("علي") == "علی"
    assert normalize_letters("كتب") == "کتب"


def test_normalize_text_full_pipeline() -> None:
    raw = "آپارتمان  ۶۰  متری می‌شود"
    out = normalize_text(raw)
    assert "60" in out
    assert "  " not in out
    assert "\u200c" not in out  # ZWNJ removed for matching
    assert "میشود" in out


def test_normalize_text_lowercases_latin() -> None:
    assert normalize_text("Peugeot 206") == "peugeot 206"


def test_normalize_text_strips_tatweel_and_soft_hyphen() -> None:
    assert normalize_text("دی‍وار") == "دیوار"
    assert normalize_text("دی­وار") == "دیوار"


def test_to_persian_digits() -> None:
    assert to_persian_digits(123) == "۱۲۳"
    assert to_persian_digits("45.6") == "۴۵.۶"
