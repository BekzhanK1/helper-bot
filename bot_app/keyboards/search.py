from typing import Iterable, List

from aiogram.types import ReplyKeyboardMarkup

from .navigation import get_navigation_keyboard


def _chunk(items: Iterable[str], size: int = 2) -> List[list[str]]:
    iterator = iter(items)
    rows: List[list[str]] = []
    while True:
        chunk = [next(iterator, None) for _ in range(size)]
        chunk = [item for item in chunk if item]
        if not chunk:
            break
        rows.append(chunk)
    return rows


def category_keyboard(categories: list[str]) -> ReplyKeyboardMarkup:
    rows = _chunk(categories, 2)
    return get_navigation_keyboard(rows, include_back=False, include_menu=True)
