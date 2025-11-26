from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.models import Review, User

router = Router()

PROFILE_BUTTON = "👤 Профиль"

STATUS_LABELS = {
    User.Status.NOVICE: "Новичок",
    User.Status.EXPERT: "Эксперт",
    User.Status.LEGEND: "Легенда",
}


@sync_to_async
def get_user_with_stats(telegram_id: int):
    user = (
        User.objects.select_related("city")
        .filter(telegram_id=telegram_id)
        .first()
    )
    if not user:
        return None, 0
    review_count = Review.objects.filter(user=user).count()
    return user, review_count


@router.message(StateFilter("*"), F.text == PROFILE_BUTTON)
async def show_profile(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    user, review_count = await get_user_with_stats(from_user.id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
        return

    city_name = user.city.name if user.city else "Не указан"
    role = user.get_role_display()
    status = STATUS_LABELS.get(user.status, user.get_status_display())

    text = (
        "📇 <b>Ваш профиль</b>\n\n"
        f"🏙 Город: <b>{city_name}</b>\n"
        f"🧭 Роль: <b>{role}</b>\n"
        f"🏅 Статус: <b>{status}</b>\n"
        f"🔋 Баланс запросов: <b>{user.balance_requests}</b>\n"
        f"✨ Репутация: <b>{user.reputation_points}</b>\n"
        f"📝 Отзывов: <b>{review_count}</b>"
    )

    await message.answer(text, reply_markup=main_menu_keyboard())
