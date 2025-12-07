from typing import Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.db.models import F as DjangoF

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.navigation import NAV_BACK_BUTTON
from bot_app.models import User
from bot_app.services.ai_service import _build_city_context, generate_recommendation
from bot_app.states.assistant import AssistantState

router = Router()

ASSISTANT_BUTTON = "🤖 AI-Помощник"


@sync_to_async
def get_user_with_city(telegram_id: int) -> Optional[User]:
    return (
        User.objects.select_related("city")
        .filter(telegram_id=telegram_id)
        .first()
    )


@sync_to_async
def check_and_decrement_ai_balance(telegram_id: int) -> tuple[bool, int]:
    """
    Проверяет баланс AI-запросов и уменьшает его на 1.
    Возвращает (успех, текущий_баланс)
    """
    user = User.objects.filter(telegram_id=telegram_id).first()
    if not user:
        return False, 0

    if user.ai_requests_balance <= 0:
        return False, 0

    User.objects.filter(telegram_id=telegram_id).update(
        ai_requests_balance=DjangoF("ai_requests_balance") - 1
    )
    # Обновляем объект для получения нового значения
    user.refresh_from_db()
    return True, user.ai_requests_balance


@router.message(F.text == ASSISTANT_BUTTON)
async def start_assistant(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    user = await get_user_with_city(from_user.id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
        return

    if not user.city:
        await message.answer("У вас не указан город. Пройдите регистрацию через /start.")
        return

    await state.clear()
    await state.set_state(AssistantState.chatting)
    await state.update_data(city_id=user.city_id, city_name=user.city.name)

    await message.answer(
        f"🤖 <b>AI-Помощник</b>\n\n"
        f"Привет! Я помогу тебе спланировать время в {user.city.name}.\n\n"
        "Можешь спросить меня:\n"
        "• Где пожить на бюджет?\n"
        "• Куда сходить в выходные?\n"
        "• Составь план на день/неделю\n"
        "• Где поесть недорого?\n"
        "• Что делать с бюджетом X на Y дней?\n\n"
        f"💡 Доступно запросов: {user.ai_requests_balance}\n\n"
        "Просто напиши свой вопрос!",
        reply_markup=main_menu_keyboard(),
    )


@router.message(StateFilter(AssistantState.chatting), F.text == NAV_BACK_BUTTON)
async def exit_assistant(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Вы вышли из режима AI-помощника.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(StateFilter(AssistantState.chatting))
async def process_assistant_query(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    user_query = (message.text or "").strip()
    if not user_query:
        await message.answer("Пожалуйста, задайте вопрос.")
        return

    # Проверяем и уменьшаем баланс AI-запросов
    success, remaining_balance = await check_and_decrement_ai_balance(from_user.id)
    if not success:
        await message.answer(
            "❌ У вас закончились запросы к AI-помощнику.\n\n"
            "Чтобы получить больше запросов, оставьте отзыв о месте через '➕ Добавить отзыв'. "
            "За каждый опубликованный отзыв вы получите 10 запросов к AI-помощнику.",
            reply_markup=main_menu_keyboard(),
        )
        return

    data = await state.get_data()
    city_id = data.get("city_id")
    city_name = data.get("city_name")

    if not city_id:
        await message.answer("Ошибка: не указан город. Начните заново.")
        await state.clear()
        return

    # Показываем, что бот думает
    thinking_msg = await message.answer("🤔 Думаю...")

    # Собираем контекст из базы данных
    city_context = await sync_to_async(_build_city_context)(city_id)

    # Генерируем ответ
    response = await sync_to_async(generate_recommendation)(
        user_query, city_context, city_name
    )

    # Удаляем сообщение "Думаю..."
    await thinking_msg.delete()

    # Отправляем ответ с HTML форматированием и информацией об оставшихся запросах
    response_with_balance = (
        f"{response}\n\n"
        f"💡 Осталось запросов к AI-помощнику: {remaining_balance}"
    )
    await message.answer(
        response_with_balance, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )
