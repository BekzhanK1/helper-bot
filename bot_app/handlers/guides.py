from typing import List, Tuple

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.models import Guide, User

router = Router()

GUIDES_BUTTON = "📚 Гайды"
GUIDE_LIMIT = 5


@sync_to_async
def get_user_with_city(telegram_id: int):
    return (
        User.objects.select_related("city")
        .filter(telegram_id=telegram_id)
        .first()
    )


@sync_to_async
def fetch_guides(city_id: int | None) -> Tuple[List[dict], bool]:
    if city_id:
        city_guides = list(
            Guide.objects.filter(city_id=city_id)
            .order_by("topic")[:GUIDE_LIMIT]
            .values("topic", "content", "city__name")
        )
        if city_guides:
            return city_guides, True

    fallback = list(
        Guide.objects.all()
        .order_by("city__name", "topic")[:GUIDE_LIMIT]
        .values("topic", "content", "city__name")
    )
    return fallback, False


def format_guides(guides: List[dict], city_label: str) -> str:
    lines = [city_label]
    for idx, guide in enumerate(guides, start=1):
        city_name = guide.get("city__name") or "Город"
        topic = guide["topic"]
        content = guide["content"]
        lines.append(f"{idx}. <b>{topic}</b> ({city_name})\n{content}")
    return "\n\n".join(lines)


@router.message(StateFilter("*"), F.text == GUIDES_BUTTON)
async def show_guides(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    user = await get_user_with_city(from_user.id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
        return

    guides, is_city_specific = await fetch_guides(user.city_id if user.city else None)
    if not guides:
        await message.answer(
            "Гайды пока не готовы. Загляните позже!",
            reply_markup=main_menu_keyboard(),
        )
        return

    if is_city_specific and user.city:
        header = f"📚 <b>Гайды для {user.city.name}</b>"
    else:
        header = "📚 <b>Гайды по другим городам</b>"

    text = format_guides(guides, header)
    await message.answer(text, reply_markup=main_menu_keyboard())
