from typing import List, Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.db.models import F as DjangoF

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.navigation import NAV_BACK_BUTTON
from bot_app.keyboards.search import (
    category_keyboard,
    place_review_keyboard,
    results_navigation_keyboard,
)
from bot_app.models import Category, Place, User
from bot_app.states.search import SearchState

router = Router()


@sync_to_async
def get_user_with_city(telegram_id: int) -> Optional[User]:
    return (
        User.objects.select_related("city")
        .filter(telegram_id=telegram_id)
        .first()
    )


@sync_to_async
def categories_for_city(city_id: int) -> List[str]:
    qs = (
        Category.objects.filter(places__city_id=city_id)
        .distinct()
        .order_by("name")
    )
    return list(qs.values_list("name", flat=True))


@sync_to_async
def all_categories() -> List[str]:
    return list(Category.objects.order_by("name").values_list("name", flat=True))


@sync_to_async
def find_category_by_name(name: str) -> Optional[Category]:
    return Category.objects.filter(name__iexact=name.strip()).first()


@sync_to_async
def deduct_user_request(telegram_id: int) -> bool:
    updated = (
        User.objects.filter(telegram_id=telegram_id, balance_requests__gt=0)
        .update(balance_requests=DjangoF("balance_requests") - 1)
    )
    return bool(updated)


@sync_to_async
def search_places(city_id: int, category_id: int) -> List[Place]:
    pinned = list(
        Place.objects.filter(
            city_id=city_id,
            category_id=category_id,
            is_pinned=True,
        ).order_by("-avg_rating")
    )
    organic = list(
        Place.objects.filter(
            city_id=city_id,
            category_id=category_id,
            is_pinned=False,
            review_count__gt=0,
        )
        .order_by("-avg_rating", "-review_count")
    )
    seen = {place.id for place in pinned}
    ordered = pinned + [place for place in organic if place.id not in seen]
    return ordered


def render_place_card(place: Place) -> str:
    rating = f"{place.avg_rating:.1f}" if place.avg_rating else "—"
    summary = place.ai_summary or "AI-описание появится позже."
    return (
        f"<b>{place.name}</b>\n"
        f"⭐ {rating} | {place.review_count} отзывов\n"
        f"📍 {place.address}\n"
        f"{summary}"
    )


@router.message(F.text == "🔍 Найти место")
async def start_search(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    user = await get_user_with_city(from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Нажмите /start.")
        return

    if not user.city:
        await message.answer("У вас не выбран город. Пройдите регистрацию заново через /start.")
        return

    categories = await categories_for_city(user.city_id)
    if not categories:
        categories = await all_categories()
    if not categories:
        await message.answer("Категории пока отсутствуют. Попробуйте позже.")
        return

    await state.clear()
    await state.set_state(SearchState.category)
    await state.update_data(city_id=user.city_id)
    await message.answer(
        "Выберите категорию, чтобы найти интересные места:",
        reply_markup=category_keyboard(categories),
    )


@router.message(SearchState.category)
async def process_category(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        await state.clear()
        return

    category = await find_category_by_name(message.text or "")
    if not category:
        await message.answer("Не нашёл такую категорию. Выберите вариант из списка.")
        return

    data = await state.get_data()
    city_id = data.get("city_id")
    if not city_id:
        await message.answer("Неизвестный город. Начните заново через /start.")
        await state.clear()
        return

    has_balance = await deduct_user_request(from_user.id)
    if not has_balance:
        await message.answer("Лимиты исчерпаны! Напиши отзыв, чтобы получить +10 запросов.")
        await state.clear()
        return

    await state.update_data(category_id=category.id)
    places = await search_places(city_id=city_id, category_id=category.id)
    await state.set_state(SearchState.results)

    if not places:
        await message.answer(
            "В базе пока пусто, но вот данные из Google Maps... (скоро подключим API).",
            reply_markup=results_navigation_keyboard(),
        )
        return

    for place in places:
        await message.answer(
            render_place_card(place),
            reply_markup=place_review_keyboard(place.id),
        )

    await message.answer(
        "Что дальше?",
        reply_markup=results_navigation_keyboard(),
    )


@router.message(StateFilter(SearchState.results), F.text == NAV_BACK_BUTTON)
async def search_back_to_categories(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    city_id = data.get("city_id")
    if not city_id:
        await state.clear()
        await message.answer("Неизвестный город. Начните поиск заново.", reply_markup=main_menu_keyboard())
        return

    categories = await categories_for_city(city_id)
    if not categories:
        categories = await all_categories()
    if not categories:
        await state.clear()
        await message.answer("Категории пока отсутствуют. Возвращаю в главное меню.", reply_markup=main_menu_keyboard())
        return

    await state.set_state(SearchState.category)
    await state.update_data(category_id=None)
    await message.answer(
        "Выберите другую категорию:",
        reply_markup=category_keyboard(categories),
    )


@router.message(StateFilter(SearchState.results))
async def search_results_fallback(message: Message) -> None:
    await message.answer(
        "Используйте кнопки внизу, чтобы вернуться или открыть меню.",
        reply_markup=results_navigation_keyboard(),
    )
