from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_app.keyboards.main import main_menu_keyboard

router = Router()

HELP_BUTTON = "🆘 Помощь"

HELP_TEXT = (
    "ℹ️ <b>Как пользоваться City Guide</b>\n\n"
    "• <b>🔍 Найти место</b> — подбор рекомендаций по городу и категории.\n"
    "• <b>➕ Добавить отзыв</b> — поделитесь впечатлениями и получите +10 запросов.\n"
    "• <b>👤 Профиль</b> — ваш город, роль, статус и статистика.\n"
    "• <b>📚 Гайды</b> — подборка тематических маршрутов и советов.\n"
    "• <b>Я был тут</b> в карточках — быстрый переход к отзыву именно об этом месте.\n\n"
    "Если что‑то пошло не так, просто нажмите «🏠 Главное меню» и начните заново."
)


@router.message(StateFilter("*"), F.text == HELP_BUTTON)
async def show_help(message: Message, state: FSMContext) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())

