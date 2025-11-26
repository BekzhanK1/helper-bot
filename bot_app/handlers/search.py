from typing import List, Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from asgiref.sync import sync_to_async
from django.db.models import F as DjangoF

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.navigation import NAV_BACK_BUTTON
from bot_app.keyboards.search import category_keyboard
from bot_app.keyboards.search_kbs import build_place_navigation_keyboard
from bot_app.models import Category, Place, Review, User
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


@sync_to_async
def get_place_by_id(place_id: int) -> Optional[Place]:
    return Place.objects.filter(id=place_id).first()


@sync_to_async
def get_recent_place_photos(place_id: int, limit: int = 5) -> List[str]:
    photos: List[str] = []
    qs = (
        Review.objects.filter(
            place_id=place_id,
            status=Review.Status.PUBLISHED,
            photo_ids__isnull=False,
        )
        .order_by("-id")
        .values_list("photo_ids", flat=True)
    )
    for batch in qs:
        if not batch:
            continue
        batch_list = list(batch)
        photos.extend(batch_list)
        if len(photos) >= limit:
            break
    return photos[:limit]


def render_place_card(place: Place) -> str:
    rating = f"{place.avg_rating:.1f}" if place.avg_rating else "—"
    ai_summary = place.ai_summary or "AI-описание появится позже."
    return (
        f"🏆 <b>{place.name}</b> (⭐ {rating} / 📝 {place.review_count})\n"
        f"📍 {place.address}\n\n"
        "🤖 <i>Мнение нейросети:</i>\n"
        f"{ai_summary}"
    )


async def send_place_card(
    target_message: Message,
    state: FSMContext,
    *,
    new_message: bool = False,
) -> None:
    data = await state.get_data()
    place_ids: List[int] = data.get("found_place_ids") or []
    total = len(place_ids)
    if total == 0:
        text = "Нет подходящих мест. Вернитесь назад и выберите другую категорию."
        if new_message:
            await target_message.answer(text, reply_markup=main_menu_keyboard())
        else:
            await target_message.edit_text(text, reply_markup=main_menu_keyboard())
        return

    current_index = data.get("current_index", 0)
    current_index = max(0, min(current_index, total - 1))
    place = await get_place_by_id(place_ids[current_index])
    if not place:
        await target_message.answer("Не удалось загрузить место. Попробуйте снова позже.")
        return

    text = render_place_card(place)
    keyboard = build_place_navigation_keyboard(
        current_index=current_index,
        total=total,
        place_id=place.id,
    )

    photos = await get_recent_place_photos(place.id)
    if photos and new_message:
        media = [InputMediaPhoto(media=file_id) for file_id in photos]
        await target_message.answer_media_group(media)

    if new_message:
        await target_message.answer(text, reply_markup=keyboard)
    else:
        await target_message.edit_text(text, reply_markup=keyboard)


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


async def _run_search_for_category(
    message: Message,
    state: FSMContext,
    *,
    category: Category,
) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        await state.clear()
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

    places = await search_places(city_id=city_id, category_id=category.id)
    await state.set_state(SearchState.results)

    if not places:
        await state.update_data(found_place_ids=[], current_index=0)
        await message.answer(
            "В базе пока пусто, но вот данные из Google Maps... (скоро подключим API).",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.update_data(
        category_id=category.id,
        found_place_ids=[place.id for place in places],
        current_index=0,
    )
    await send_place_card(message, state, new_message=True)


@router.message(SearchState.category)
async def process_category(message: Message, state: FSMContext) -> None:
    category = await find_category_by_name(message.text or "")
    if not category:
        await message.answer("Не нашёл такую категорию. Выберите вариант из списка.")
        return

    await _run_search_for_category(message, state, category=category)


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
    await state.update_data(
        category_id=None,
        found_place_ids=[],
        current_index=0,
    )
    await message.answer(
        "Выберите другую категорию:",
        reply_markup=category_keyboard(categories),
    )


@router.message(StateFilter(SearchState.results))
async def search_results_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Используйте кнопки под карточкой или введите категорию заново.")
        return

    category = await find_category_by_name(text)
    if category:
        await _run_search_for_category(message, state, category=category)
        return

    await message.answer(
        "Используйте кнопки под карточкой, чтобы листать места или откройте меню.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(StateFilter(SearchState.results), F.data == "nav_next")
async def handle_next(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    place_ids: List[int] = data.get("found_place_ids") or []
    index = data.get("current_index", 0)
    if index >= len(place_ids) - 1:
        await callback.answer("Это последняя карточка.")
        return

    await state.update_data(current_index=index + 1)
    await send_place_card(callback.message, state)
    await callback.answer()


@router.callback_query(StateFilter(SearchState.results), F.data == "nav_prev")
async def handle_prev(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    index = data.get("current_index", 0)
    if index <= 0:
        await callback.answer("Это первая карточка.")
        return

    await state.update_data(current_index=index - 1)
    await send_place_card(callback.message, state)
    await callback.answer()


@router.callback_query(StateFilter(SearchState.results), F.data == "nav_ignore")
async def handle_nav_ignore(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(StateFilter(SearchState.results), F.data == "main_menu")
async def handle_nav_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
