from typing import Iterable, List

from aiogram.types import ReplyKeyboardMarkup

from .navigation import get_navigation_keyboard

CREATE_PLACE_BUTTON = "➕ Создать новое место"
PHOTO_DONE_BUTTON = "Готово"


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


def place_name_keyboard() -> ReplyKeyboardMarkup:
    return get_navigation_keyboard([], include_back=False, include_menu=True)


def place_suggestions_keyboard(options: list[str]) -> ReplyKeyboardMarkup:
    rows = _chunk(options, 2)
    rows.append([CREATE_PLACE_BUTTON])
    return get_navigation_keyboard(rows, include_back=True, include_menu=True)


def address_keyboard() -> ReplyKeyboardMarkup:
    return get_navigation_keyboard([], include_back=True, include_menu=True)


def category_keyboard(categories: list[str]) -> ReplyKeyboardMarkup:
    rows = _chunk(categories, 2)
    return get_navigation_keyboard(rows, include_back=True, include_menu=True)


def rating_keyboard() -> ReplyKeyboardMarkup:
    rows = [["1", "2", "3", "4", "5"]]
    return get_navigation_keyboard(rows, include_back=True, include_menu=True)


def text_keyboard() -> ReplyKeyboardMarkup:
    return get_navigation_keyboard([], include_back=True, include_menu=True)


def photo_keyboard() -> ReplyKeyboardMarkup:
    rows = [[PHOTO_DONE_BUTTON]]
    return get_navigation_keyboard(rows, include_back=True, include_menu=True)
