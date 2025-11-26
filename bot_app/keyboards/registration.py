from typing import Iterable, List

from aiogram.types import ReplyKeyboardMarkup

from .navigation import get_navigation_keyboard


def chunked(iterable: Iterable[str], size: int = 2) -> List[list[str]]:
    rows: List[list[str]] = []
    iterator = iter(iterable)
    while True:
        chunk = list(filter(None, [next(iterator, None) for _ in range(size)]))
        if not chunk:
            break
        rows.append(chunk)
    return rows


def city_keyboard(city_names: list[str]) -> ReplyKeyboardMarkup:
    button_rows = chunked(city_names, 2) or [["Нет доступных городов"]]
    return get_navigation_keyboard(button_rows, include_back=False, include_menu=True)


ROLE_LABELS = ["Турист", "Студент", "Местный"]


def role_keyboard() -> ReplyKeyboardMarkup:
    button_rows = [[label] for label in ROLE_LABELS]
    return get_navigation_keyboard(button_rows, include_back=True, include_menu=True)
