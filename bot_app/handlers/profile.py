from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.profile_kbs import (
    city_selection_keyboard,
    profile_inline_keyboard,
)
from bot_app.models import City, Review, User
from bot_app.states.profile import ProfileState

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


@sync_to_async
def get_active_cities():
    return list(City.objects.filter(is_active=True).order_by("name").values("id", "name"))


@sync_to_async
def update_user_city(user_id: int, city_id: int) -> City | None:
    try:
        city = City.objects.get(id=city_id, is_active=True)
    except City.DoesNotExist:
        return None
    User.objects.filter(telegram_id=user_id).update(city=city)
    return city


def _format_profile_text(user: User, review_count: int) -> str:
    city_name = user.city.name if user.city else "Не указан"
    role = user.get_role_display()
    status = STATUS_LABELS.get(user.status, user.get_status_display())
    return (
        "📇 <b>Ваш профиль</b>\n\n"
        f"🏙 Город: <b>{city_name}</b>\n"
        f"🧭 Роль: <b>{role}</b>\n"
        f"🏅 Статус: <b>{status}</b>\n"
        f"🔋 Баланс запросов: <b>{user.balance_requests}</b>\n"
        f"✨ Репутация: <b>{user.reputation_points}</b>\n"
        f"📝 Отзывов: <b>{review_count}</b>"
    )


async def _send_profile(message: Message, telegram_id: int) -> None:
    user, review_count = await get_user_with_stats(telegram_id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
        return
    text = _format_profile_text(user, review_count)
    await message.answer(
        text,
        reply_markup=profile_inline_keyboard(),
    )


@router.message(StateFilter("*"), F.text == PROFILE_BUTTON)
async def show_profile(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return
    await _send_profile(message, from_user.id)


@router.callback_query(F.data == "change_city")
async def start_city_change(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = callback.from_user
    if not user:
        await callback.message.answer("Не удалось определить ваш Telegram ID.")
        return

    cities = await get_active_cities()
    if not cities:
        await callback.message.answer("Список городов пока пуст. Попробуйте позже.")
        return

    await state.set_state(ProfileState.waiting_for_city)
    city_rows = [(city["id"], city["name"]) for city in cities]
    await callback.message.answer(
        "Выберите новый город:",
        reply_markup=city_selection_keyboard(city_rows),
    )


@router.callback_query(StateFilter(ProfileState.waiting_for_city), F.data == "cancel_change_city")
async def cancel_city_change(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Изменение города отменено.")
    await _send_profile(callback.message, callback.from_user.id)


@router.callback_query(StateFilter(ProfileState.waiting_for_city), F.data.startswith("set_city:"))
async def apply_city_change(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = callback.data or ""
    try:
        _, city_id_str = data.split(":", 1)
        city_id = int(city_id_str)
    except (ValueError, AttributeError):
        await callback.message.answer("Некорректный город. Попробуйте снова.")
        return

    user = callback.from_user
    if not user:
        await callback.message.answer("Не удалось определить ваш Telegram ID.")
        return

    city = await update_user_city(user.id, city_id)
    if not city:
        await callback.message.answer("Не удалось обновить город. Попробуйте снова.")
        return

    await state.clear()
    await callback.message.answer(f"✅ Город успешно изменён на {city.name}!")
    await _send_profile(callback.message, user.id)
