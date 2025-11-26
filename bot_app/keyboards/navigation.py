from typing import List, Sequence

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

NAV_BACK_BUTTON = "⬅️ Назад"
NAV_MENU_BUTTON = "🏠 Главное меню"


def get_navigation_keyboard(
    button_rows: Sequence[Sequence[str]],
    *,
    include_back: bool = True,
    include_menu: bool = True,
    resize: bool = True,
) -> ReplyKeyboardMarkup:
    """
    Build a reply keyboard with domain-specific buttons and an optional navigation row.
    """

    keyboard: List[List[KeyboardButton]] = [
        [KeyboardButton(text=text) for text in row] for row in button_rows
    ]

    nav_row: List[KeyboardButton] = []
    if include_back:
        nav_row.append(KeyboardButton(text=NAV_BACK_BUTTON))
    if include_menu:
        nav_row.append(KeyboardButton(text=NAV_MENU_BUTTON))

    if nav_row:
        keyboard.append(nav_row)

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=resize)
