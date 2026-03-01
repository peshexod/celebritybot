from decimal import Decimal
from pathlib import Path

from aiogram.types import FSInputFile


def format_price(value: int | float | Decimal) -> str:
    return f"{Decimal(value):.2f} ₽"


def as_telegram_photo(source: str) -> str | FSInputFile:
    if source.startswith(("http://", "https://")):
        return source

    path = Path(source)
    if path.is_absolute() or source.startswith("./") or source.startswith("../") or "/" in source:
        return FSInputFile(source)

    return source
