from decimal import Decimal


def format_price(value: int | float | Decimal) -> str:
    return f"{Decimal(value):.2f} ₽"
