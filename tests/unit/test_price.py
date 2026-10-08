import pytest

from divar_mcp.utils.price import (
    format_number,
    format_toman_words,
    parse_amount,
    rial_to_toman,
    toman_to_rial,
)


def test_rial_toman_conversions() -> None:
    assert rial_to_toman(1_000_000) == 100_000
    assert toman_to_rial(100_000) == 1_000_000
    assert rial_to_toman(toman_to_rial(12_345_670)) == 12_345_670


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("۲ میلیارد", 2_000_000_000),
        ("۲ میلیارد تومان", 2_000_000_000),
        ("۶۰۰ میلیون", 600_000_000),
        ("۵۰۰ هزار", 500_000),
        ("۱.۵ میلیارد", 1_500_000_000),
        ("۱٫۵ میلیارد", 1_500_000_000),
        ("۳۰۰۰۰۰۰۰۰۰ ریال", 300_000_000),
        ("300 million", 300_000_000),
        ("300 million toman", 300_000_000),
        ("2 billion", 2_000_000_000),
        ("500 thousand", 500_000),
        ("زیر ۲ میلیارد", 2_000_000_000),
        ("۱,۵۰۰,۰۰۰,۰۰۰", 1_500_000_000),
        ("۱۵۰ میلیون تومن", 150_000_000),
        ("12,000,000 ریال", 1_200_000),
    ],
)
def test_parse_amount(text: str, expected: int) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "بدون عدد", "خیلی گران"])
def test_parse_amount_no_number_returns_none(text: str) -> None:
    assert parse_amount(text) is None


def test_format_toman_words() -> None:
    assert format_toman_words(2_000_000_000) == "۲ میلیارد"
    assert format_toman_words(1_500_000_000) == "۱.۵ میلیارد"
    assert format_toman_words(600_000_000) == "۶۰۰ میلیون"
    assert format_toman_words(500_000) == "۵۰۰ هزار"
    assert format_toman_words(900) == "۹۰۰"


def test_format_number_grouping_and_digits() -> None:
    assert format_number(1_234_567) == "۱,۲۳۴,۵۶۷"
    assert format_number(0) == "۰"
