from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MAIN_MENU_BUTTONS = [
    "🔍 Найти место",
    "➕ Добавить отзыв",
    "👤 Профиль",
    "📚 Гайды",
    "🆘 Помощь",
]


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [
            KeyboardButton(text=MAIN_MENU_BUTTONS[0]),
            KeyboardButton(text=MAIN_MENU_BUTTONS[1]),
        ],
        [
            KeyboardButton(text=MAIN_MENU_BUTTONS[2]),
            KeyboardButton(text=MAIN_MENU_BUTTONS[3]),
        ],
        [KeyboardButton(text=MAIN_MENU_BUTTONS[4])],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
