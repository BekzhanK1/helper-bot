from typing import Iterable, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def profile_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏙 Сменить город",
                                  callback_data="change_city")]
        ]
    )


def city_selection_keyboard(
    cities: Sequence[tuple[int | str, str]],
    *,
    cancel_callback: str = "cancel_change_city",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(0, len(cities), 2):
        chunk = cities[idx: idx + 2]
        row = [
            InlineKeyboardButton(
                text=name, callback_data=f"set_city:{city_id}")
            for city_id, name in chunk
        ]
        rows.append(row)

    rows.append([InlineKeyboardButton(
        text="⬅️ Отмена", callback_data=cancel_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
