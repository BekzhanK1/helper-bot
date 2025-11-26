from typing import Dict, List, Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TelegramUser
from asgiref.sync import sync_to_async
from django.db import transaction
from django.db.models import F as DjangoF

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.navigation import NAV_BACK_BUTTON
from bot_app.keyboards.review import (
    CREATE_PLACE_BUTTON,
    PHOTO_DONE_BUTTON,
    address_keyboard,
    category_keyboard,
    photo_keyboard,
    place_name_keyboard,
    place_suggestions_keyboard,
    rating_keyboard,
    text_keyboard,
)
from bot_app.models import Category, Place, Review, User
from bot_app.services.ai_service import analyze_review, update_place_summary
from bot_app.states.review import AddReviewState

router = Router()

PLACE_RESULTS_LIMIT = 6
LEAVE_REVIEW_PREFIX = "leave_review"


@sync_to_async
def get_user_with_city(telegram_id: int) -> Optional[User]:
    return (
        User.objects.select_related("city")
        .filter(telegram_id=telegram_id)
        .first()
    )


@sync_to_async
def search_places(city_id: int, name_query: str) -> List[Dict[str, str]]:
    qs = (
        Place.objects.filter(city_id=city_id, name__icontains=name_query)
        .order_by("name")[:PLACE_RESULTS_LIMIT]
    )
    return list(qs.values("id", "name", "address"))


@sync_to_async
def list_categories() -> List[Dict[str, str]]:
    return list(Category.objects.order_by("name").values("id", "name"))


@sync_to_async
def get_place(place_id: int) -> Optional[Place]:
    return Place.objects.filter(id=place_id).first()


@sync_to_async
def user_has_review(user_id: int, place_id: int) -> bool:
    return Review.objects.filter(user_id=user_id, place_id=place_id).exists()


@sync_to_async
def create_place_record(
    *,
    city_id: int,
    category_id: int,
    name: str,
    address: str,
) -> Optional[Place]:
    if not Category.objects.filter(id=category_id).exists():
        return None
    return Place.objects.create(
        name=name,
        address=address,
        city_id=city_id,
        category_id=category_id,
        location={},
    )


@sync_to_async
def create_pending_review(
    *,
    user_id: int,
    place_id: int,
    rating: int,
    text: str,
    photos: List[str],
) -> Review:
    return Review.objects.create(
        user_id=user_id,
        place_id=place_id,
        rating=rating,
        text=text,
        status=Review.Status.PENDING,
        is_verified_by_ai=False,
        photo_ids=photos,
    )


@sync_to_async
def mark_review_rejected(review_id: int) -> None:
    Review.objects.filter(id=review_id).update(status=Review.Status.REJECTED)


@sync_to_async
@transaction.atomic
def publish_review(review_id: int, summary: str) -> None:
    review = (
        Review.objects.select_for_update()
        .select_related("place")
        .get(id=review_id)
    )
    place = review.place

    total_score = place.avg_rating * place.review_count
    place.review_count += 1
    place.avg_rating = (total_score + review.rating) / place.review_count
    if summary:
        place.ai_summary = summary
    place.save(update_fields=["avg_rating", "review_count", "ai_summary"])

    review.status = Review.Status.PUBLISHED
    review.save(update_fields=["status"])

    User.objects.filter(telegram_id=review.user_id).update(
        balance_requests=DjangoF("balance_requests") + 10,
        reputation_points=DjangoF("reputation_points") + 10,
    )


def sanitize_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


async def ensure_user_registered(
    message: Message,
    state: FSMContext,
    telegram_user: Optional[TelegramUser] = None,
) -> Optional[User]:
    from_user = telegram_user or message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return None

    user = await get_user_with_city(from_user.id)
    if not user:
        await state.clear()
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
        return None

    if not user.city:
        await state.clear()
        await message.answer("У вас не указан город. Пройдите регистрацию через /start.")
        return None
    return user


async def _start_review_flow_from_place(
    callback: CallbackQuery,
    state: FSMContext,
    place_id: int,
) -> None:
    if not callback.message:
        return

    user = await ensure_user_registered(
        callback.message,
        state,
        telegram_user=callback.from_user,
    )
    if not user:
        return

    has_review = await user_has_review(user.telegram_id, place_id)
    if has_review:
        await callback.message.answer("Вы уже оставляли отзыв об этом месте.")
        return

    place = await get_place(place_id)
    if not place:
        await callback.message.answer("Место не найдено. Обновите список и попробуйте снова.")
        return

    await state.clear()
    await state.update_data(
        user_id=user.telegram_id,
        city_id=user.city_id,
        place_id=place.id,
        place_name=place.name,
    )
    await state.set_state(AddReviewState.rating)
    await callback.message.answer(
        f"Оставим отзыв о <b>{place.name}</b>. Поставьте оценку от 1 до 5:",
        reply_markup=rating_keyboard(),
    )


@router.callback_query(F.data.startswith(f"{LEAVE_REVIEW_PREFIX}:"))
async def handle_leave_review_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = callback.data or ""
    try:
        _, place_id_str = data.split(":", 1)
        place_id = int(place_id_str)
    except (ValueError, AttributeError):
        await callback.message.answer("Не удалось определить место. Попробуйте ещё раз.")
        return

    await _start_review_flow_from_place(callback, state, place_id)


@router.callback_query(F.data.startswith("review_"))
async def handle_review_shortcut(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = callback.data or ""
    try:
        _, place_id_str = data.split("_", 1)
        place_id = int(place_id_str)
    except (ValueError, AttributeError):
        await callback.message.answer("Не удалось определить место. Попробуйте ещё раз.")
        return

    await _start_review_flow_from_place(callback, state, place_id)


@router.message(F.text == "➕ Добавить отзыв")
async def start_review(message: Message, state: FSMContext) -> None:
    user = await ensure_user_registered(message, state)
    if not user:
        return

    await state.clear()
    await state.update_data(user_id=user.telegram_id, city_id=user.city_id)
    await state.set_state(AddReviewState.place_name)
    await message.answer(
        "Давайте начнём! Введите название места, о котором хотите рассказать:",
        reply_markup=place_name_keyboard(),
    )


@router.message(StateFilter(AddReviewState.place_name))
async def process_place_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    city_id = data.get("city_id")
    if not city_id:
        await state.clear()
        await message.answer("Не удалось определить город. Начните заново через /start.")
        return

    place_name = sanitize_text(message.text)
    if not place_name:
        await message.answer("Пожалуйста, введите название места.")
        return

    matches = await search_places(city_id, place_name)
    await state.update_data(place_name=place_name, place_id=None)

    if matches:
        await state.update_data(place_options=matches)
        await state.set_state(AddReviewState.place_selection)
        option_names = [item["name"] for item in matches]
        text = "Нашёл такие места. Выберите одно из списка или создайте новое:"
        await message.answer(text, reply_markup=place_suggestions_keyboard(option_names))
        return

    await state.set_state(AddReviewState.address)
    await message.answer(
        "Введите адрес этого места (улица, номер дома):",
        reply_markup=address_keyboard(),
    )


@router.message(StateFilter(AddReviewState.place_selection))
async def process_place_selection(message: Message, state: FSMContext) -> None:
    text = sanitize_text(message.text)
    if not text:
        await message.answer("Выберите вариант из списка.")
        return

    if text == CREATE_PLACE_BUTTON:
        await state.set_state(AddReviewState.address)
        await message.answer("Введите адрес нового места:", reply_markup=address_keyboard())
        return

    data = await state.get_data()
    options: List[Dict[str, str]] = data.get("place_options", [])
    matched = next(
        (opt for opt in options if opt["name"].lower() == text.lower()), None)
    if not matched:
        await message.answer("Не нашёл такой вариант. Выберите кнопку из списка.")
        return

    await state.update_data(place_id=matched["id"])
    await ask_for_rating(message, state)


@router.message(StateFilter(AddReviewState.address))
async def process_address(message: Message, state: FSMContext) -> None:
    address = sanitize_text(message.text)
    if not address:
        await message.answer("Пожалуйста, укажите адрес.")
        return

    data = await state.get_data()
    city_id = data.get("city_id")
    place_name = data.get("place_name")
    if not city_id or not place_name:
        await state.clear()
        await message.answer("Не удалось определить город или название. Начните заново.")
        return

    categories = await list_categories()
    if not categories:
        await message.answer(
            "Категории ещё не настроены. Обратитесь к администратору."
        )
        await state.clear()
        return

    await state.update_data(address=address, category_options=categories)
    await state.set_state(AddReviewState.category)
    await message.answer(
        "Выберите категорию для этого места:",
        reply_markup=category_keyboard([item["name"] for item in categories]),
    )


@router.message(StateFilter(AddReviewState.category))
async def process_category_selection(message: Message, state: FSMContext) -> None:
    category_name = sanitize_text(message.text)
    if not category_name:
        await message.answer("Пожалуйста, выберите категорию из списка.")
        return

    data = await state.get_data()
    options: List[Dict[str, str]] = data.get("category_options", [])
    matched = next(
        (opt for opt in options if opt["name"].lower(
        ) == category_name.lower()),
        None,
    )
    if not matched:
        await message.answer("Категория не найдена. Выберите вариант с клавиатуры.")
        return

    city_id = data.get("city_id")
    place_name = data.get("place_name")
    address = data.get("address")
    if not all([city_id, place_name, address]):
        await state.clear()
        await message.answer("Недостаточно данных, начните заново через '➕ Добавить отзыв'.")
        return

    place = await create_place_record(
        city_id=city_id,
        category_id=matched["id"],
        name=place_name,
        address=address,
    )
    if not place:
        await message.answer("Не удалось сохранить место. Попробуйте позже.")
        await state.clear()
        return

    await state.update_data(place_id=place.id, category_options=None)
    await ask_for_rating(message, state)


async def ask_for_rating(message: Message, state: FSMContext) -> None:
    await state.set_state(AddReviewState.rating)
    await message.answer(
        "Поставьте оценку месту от 1 до 5:",
        reply_markup=rating_keyboard(),
    )


@router.message(StateFilter(AddReviewState.rating), F.text.in_(("1", "2", "3", "4", "5")))
async def process_rating(message: Message, state: FSMContext) -> None:
    rating = int(message.text)
    await state.update_data(rating=rating)
    await state.set_state(AddReviewState.text)
    await message.answer(
        "Опишите ваш опыт: что понравилось, что нет?",
        reply_markup=text_keyboard(),
    )


@router.message(StateFilter(AddReviewState.rating))
async def rating_fallback(message: Message) -> None:
    await message.answer("Используйте кнопки 1-5, чтобы выбрать оценку.")


@router.message(StateFilter(AddReviewState.text))
async def process_text(message: Message, state: FSMContext) -> None:
    review_text = sanitize_text(message.text)
    if not review_text:
        await message.answer("Текст отзыва не может быть пустым.")
        return

    await state.update_data(review_text=review_text)
    await state.set_state(AddReviewState.photos)
    await message.answer(
        "Отправьте фотографии (можно несколько). Когда закончите, нажмите 'Готово'.",
        reply_markup=photo_keyboard(),
    )


@router.message(StateFilter(AddReviewState.photos), F.photo)
async def collect_photos(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    file_id = photo.file_id
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(file_id)
    await state.update_data(photos=photos)
    await message.answer("Фото сохранено. Добавьте ещё или нажмите 'Готово'.")


@router.message(StateFilter(AddReviewState.photos), F.text == PHOTO_DONE_BUTTON)
async def finalize_review(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = data.get("user_id")
    place_id = data.get("place_id")
    rating = data.get("rating")
    review_text = data.get("review_text")
    photos = data.get("photos", [])

    if not all([user_id, place_id, rating, review_text]):
        await state.clear()
        await message.answer(
            "Не хватает данных для отзыва. Начните заново через '➕ Добавить отзыв'.",
            reply_markup=main_menu_keyboard(),
        )
        return

    review = await create_pending_review(
        user_id=user_id,
        place_id=place_id,
        rating=rating,
        text=review_text,
        photos=photos,
    )

    print(f"AI moderation: analyzing review_id={review.id}")
    analysis = await sync_to_async(analyze_review)(review_text)
    print(f"AI moderation: result={analysis}")
    is_spam = bool(analysis.get("is_spam"))
    summary = analysis.get("summary", "")

    if is_spam:
        await mark_review_rejected(review.id)
        await state.clear()
        await message.answer(
            "Отзыв выглядит как спам, поэтому он не был опубликован.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await publish_review(review.id, summary)
    await update_place_summary(place_id)
    await state.clear()
    await message.answer(
        "Спасибо! Отзыв опубликован. Вам начислено 10 запросов.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(StateFilter(AddReviewState.photos))
async def photos_fallback(message: Message) -> None:
    await message.answer("Отправьте фото или нажмите 'Готово', когда закончите.")


@router.message(StateFilter(AddReviewState.place_selection), F.text == NAV_BACK_BUTTON)
async def back_to_place_name_from_selection(message: Message, state: FSMContext) -> None:
    await state.set_state(AddReviewState.place_name)
    await message.answer(
        "Введите название места ещё раз:",
        reply_markup=place_name_keyboard(),
    )


@router.message(StateFilter(AddReviewState.address), F.text == NAV_BACK_BUTTON)
async def back_to_place_name_from_address(message: Message, state: FSMContext) -> None:
    await state.set_state(AddReviewState.place_name)
    await message.answer(
        "Вернулись к вводу названия. Напишите его снова:",
        reply_markup=place_name_keyboard(),
    )


@router.message(StateFilter(AddReviewState.category), F.text == NAV_BACK_BUTTON)
async def back_to_address_from_category(message: Message, state: FSMContext) -> None:
    await state.update_data(address=None, category_options=None)
    await state.set_state(AddReviewState.address)
    await message.answer(
        "Введите адрес места ещё раз:",
        reply_markup=address_keyboard(),
    )


@router.message(StateFilter(AddReviewState.rating), F.text == NAV_BACK_BUTTON)
async def back_to_place_name_from_rating(message: Message, state: FSMContext) -> None:
    await state.update_data(place_id=None, rating=None)
    await state.set_state(AddReviewState.place_name)
    await message.answer(
        "Хорошо, выберем место заново. Введите название:",
        reply_markup=place_name_keyboard(),
    )


@router.message(StateFilter(AddReviewState.text), F.text == NAV_BACK_BUTTON)
async def back_to_rating_from_text(message: Message, state: FSMContext) -> None:
    await state.set_state(AddReviewState.rating)
    await message.answer(
        "Изменим оценку. Выберите значение 1-5:",
        reply_markup=rating_keyboard(),
    )


@router.message(StateFilter(AddReviewState.photos), F.text == NAV_BACK_BUTTON)
async def back_to_text_from_photos(message: Message, state: FSMContext) -> None:
    await state.set_state(AddReviewState.text)
    await message.answer(
        "Вернёмся к тексту отзыва. Напишите его снова (или отправьте другой):",
        reply_markup=text_keyboard(),
    )
