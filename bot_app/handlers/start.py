from typing import List, Optional

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.navigation import NAV_BACK_BUTTON
from bot_app.keyboards.registration import city_keyboard, role_keyboard
from bot_app.models import City, User
from bot_app.states.registration import RegistrationState

router = Router()

ROLE_TO_CODE = {
    "Турист": User.Role.TOURIST,
    "Студент": User.Role.STUDENT,
    "Местный": User.Role.LOCAL,
}


@sync_to_async
def fetch_user(telegram_id: int) -> Optional[User]:
    return (
        User.objects.select_related("city")
        .filter(telegram_id=telegram_id)
        .first()
    )


@sync_to_async
def list_active_cities() -> List[str]:
    return list(City.objects.filter(is_active=True).order_by("name").values_list("name", flat=True))


@sync_to_async
def get_city_by_name(name: str) -> Optional[City]:
    return City.objects.filter(is_active=True, name__iexact=name.strip()).first()


@sync_to_async
def create_user(
    *,
    telegram_id: int,
    username: Optional[str],
    full_name: Optional[str],
    city: City,
    role: str,
) -> User:
    return User.objects.create(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        city=city,
        role=role,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    user = await fetch_user(from_user.id)
    if user:
        await state.clear()
        await message.answer(
            "С возвращением! Чем займёмся?",
            reply_markup=main_menu_keyboard(),
        )
        return

    cities = await list_active_cities()
    if not cities:
        await message.answer("Пока нет доступных городов. Попробуйте позже.")
        return

    await state.set_state(RegistrationState.city)
    await message.answer(
        "Привет! Выберите город, чтобы настроить рекомендации:",
        reply_markup=city_keyboard(cities),
    )


@router.message(RegistrationState.city)
async def process_city(message: Message, state: FSMContext) -> None:
    selected_city = await get_city_by_name(message.text or "")
    if not selected_city:
        await message.answer("Не нашёл такой город. Выберите вариант из клавиатуры.")
        return

    await state.update_data(city_id=selected_city.id)
    await state.set_state(RegistrationState.role)
    await message.answer(
        "Отлично! Расскажите, кто вы:",
        reply_markup=role_keyboard(),
    )


@router.message(RegistrationState.role)
async def process_role(message: Message, state: FSMContext) -> None:
    role = ROLE_TO_CODE.get((message.text or "").strip())
    if not role:
        await message.answer(
            "Выберите роль из предложенных вариантов.",
            reply_markup=role_keyboard(),
        )
        return

    data = await state.get_data()
    city_id = data.get("city_id")
    if not city_id:
        await state.clear()
        await message.answer("Не удалось найти город. Попробуйте заново через /start.")
        return

    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID. Попробуйте /start.")
        return

    try:
        city = await sync_to_async(City.objects.get)(id=city_id)
    except City.DoesNotExist:
        await state.clear()
        await message.answer("Не удалось найти выбранный город. Начните заново через /start.")
        return
    await create_user(
        telegram_id=from_user.id,
        username=from_user.username,
        full_name=from_user.full_name,
        city=city,
        role=role,
    )
    await state.clear()

    await message.answer(
        "Регистрация завершена! Добро пожаловать в City Guide.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(StateFilter(RegistrationState.role), F.text == NAV_BACK_BUTTON)
async def registration_back_to_city(message: Message, state: FSMContext) -> None:
    cities = await list_active_cities()
    if not cities:
        await state.clear()
        await message.answer("Пока нет доступных городов. Попробуйте позже.")
        return

    await state.update_data(city_id=None)
    await state.set_state(RegistrationState.city)
    await message.answer(
        "Вернёмся к выбору города. Пожалуйста, выберите город:",
        reply_markup=city_keyboard(cities),
    )
