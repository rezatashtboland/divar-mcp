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
    assert transliterate("\u06af\u06cc\u0634\u0627") == "gisha"  # گیشا
    assert transliterate("\u062a\u0647\u0631\u0627\u0646") == "thran"  # تهران
    assert transliterate("\u0646\u0628\u0631\u062f") == "nbrd"  # نبرد
    assert transliterate("gisha") == "gisha"


def test_district_matches() -> None:
    from divar_mcp.utils.persian import normalize_text
    district = "\u06af\u06cc\u0634\u0627\u06cc \u063a\u0631\u0628\u06cc"  # گیشای غربی
    target = "gisha"
    norm_district = normalize_text(district)
    norm_target = normalize_text(target)
    with open("D:\\Develop\\divar-mcp\\debug_test.txt", "w", encoding="utf-8") as f:
        f.write(f"norm_district={repr(norm_district)}, norm_target={repr(norm_target)}, target in district={norm_target in norm_district}\n")
    
    assert district_matches("\u06af\u06cc\u0634\u0627", "gisha")  # گیشا
    assert district_matches("\u062a\u0647\u0631\u0627\u0646", "tehran")  # تهران
    assert district_matches("\u0648\u0646\u06a9", "vanak")  # ونک
    assert district_matches("\u06af\u06cc\u0634\u0627\u06cc \u063a\u0631\u0628\u06cc", "gisha")  # گیشای غربی
    assert district_matches("\u06af\u06cc\u0634\u0627", "\u06af\u06cc\u0634\u0627")  # گیشا
    assert not district_matches("\u06af\u06cc\u0634\u0627", "vanak")
    assert not district_matches("\u06af\u06cc\u0634\u0627", "gharbi-gisha-or-tehran")
    assert not district_matches("\u0628\u0646\u06cc\u200c\u0647\u0627\u0634\u0645", "\u0647\u0627\u0634\u0645\u06cc")  # بنی‌هاشم، هاشمی


def test_word_to_int() -> None:
    assert word_to_int("یک") == 1
    assert word_to_int("سه") == 3
    assert word_to_int("۲") == 2
    assert word_to_int("ده") == 10
    assert word_to_int("زیاد") is None


def test_normalize_digits_persian() -> None:
    assert normalize_digits("\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9\u06f0") == "1234567890"  # ۱۲۳۴۵۶۷۸۹۰


def test_normalize_digits_arabic_indic() -> None:
    assert normalize_digits("\u0664\u0665\u0666") == "456"  # ٤٥٦


def test_normalize_digits_mixed() -> None:
    assert normalize_digits("\u06f6\u06f0m\u06f2") == "60m2"  # ۶۰m۲
    assert normalize_digits("abc") == "abc"


def test_normalize_letters_yeh_and_kaf() -> None:
    assert normalize_letters("\u0639\u0644\u064a") == "\u0639\u0644\u06cc"  # على -> علی
    assert normalize_letters("\u0643\u062a\u0628") == "\u06a9\u062a\u0628"  # كتب -> کتب


def test_normalize_text_full_pipeline() -> None:
    raw = "\u0622\u067e\u0627\u0631\u062a\u0627\u0645\u0627\u0646  \u06f6\u06f0  \u0645\u062a\u0631\u06cc \u0645\u06cc\u200c\u0634\u0648\u062f"  # آپارتمان  ۶۰  متری می‌شود
    out = normalize_text(raw)
    assert "60" in out
    assert "  " not in out
    assert "\u200c" not in out  # ZWNJ removed for matching
    assert "\u0645\u06cc\u0634\u0648\u062f" in out  # میشود


def test_normalize_text_lowercases_latin() -> None:
    assert normalize_text("Peugeot 206") == "peugeot 206"


def test_normalize_text_strips_tatweel_and_soft_hyphen() -> None:
    assert normalize_text("\u062f\u06cc\u200d\u0648\u0627\u0631") == "\u062f\u06cc\u0648\u0627\u0631"  # دی‍وار -> دیوار
    assert normalize_text("\u062f\u06cc\u00ad\u0648\u0627\u0631") == "\u062f\u06cc\u0648\u0627\u0631"  # دی­وار -> دیوار


def test_to_persian_digits() -> None:
    assert to_persian_digits(123) == "\u06f1\u06f2\u06f3"  # ۱۲۳
    assert to_persian_digits("45.6") == "\u06f4\u06f5.\u06f6"  # ۴۵.۶
