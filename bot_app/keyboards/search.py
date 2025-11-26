from typing import Iterable, List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

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


def results_navigation_keyboard() -> ReplyKeyboardMarkup:
    return get_navigation_keyboard([], include_back=True, include_menu=True)


def place_review_keyboard(place_id: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        text="Я был тут (Оставить отзыв)",
        callback_data=f"leave_review:{place_id}",
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])
