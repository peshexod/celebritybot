from decimal import Decimal

from bot.utils.helpers import format_price


def test_format_price_from_int() -> None:
    assert format_price(299) == "299.00 ₽"


def test_format_price_from_decimal() -> None:
    assert format_price(Decimal("199.9")) == "199.90 ₽"
