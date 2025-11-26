from typing import Iterable, List

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


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
    rows = [[KeyboardButton(text=name) for name in row] for row in chunked(city_names, 2)]
    return ReplyKeyboardMarkup(
        keyboard=rows or [[KeyboardButton(text="Нет доступных городов")]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Выберите город",
    )


ROLE_LABELS = ["Турист", "Студент", "Местный"]


def role_keyboard() -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=label)] for label in ROLE_LABELS]
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Выберите роль",
    )

