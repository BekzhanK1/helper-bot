from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_place_navigation_keyboard(
    *,
    current_index: int,
    total: int,
    place_id: int,
) -> InlineKeyboardMarkup:
    prev_button = (
        InlineKeyboardButton(text="⬅️", callback_data="nav_prev")
        if current_index > 0
        else InlineKeyboardButton(text=" ", callback_data="nav_ignore")
    )
    next_button = (
        InlineKeyboardButton(text="➡️", callback_data="nav_next")
        if current_index < total - 1
        else InlineKeyboardButton(text=" ", callback_data="nav_ignore")
    )
    counter_button = InlineKeyboardButton(
        text=f"{current_index + 1} из {total}",
        callback_data="nav_ignore",
    )

    review_button = InlineKeyboardButton(
        text="✍️ Оставить отзыв",
        callback_data=f"review_{place_id}",
    )

    menu_button = InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu",
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [prev_button, counter_button, next_button],
            [review_button],
            [menu_button],
        ]
    )

