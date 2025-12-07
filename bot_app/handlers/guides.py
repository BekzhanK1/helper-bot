from typing import List, Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.navigation import NAV_BACK_BUTTON, get_navigation_keyboard
from bot_app.keyboards.search import category_keyboard
from bot_app.models import Guide, GuideCategory, User
from bot_app.states.guides import GuidesState

router = Router()

GUIDES_BUTTON = "📚 Гайды"
GUIDE_LIMIT = 10


@sync_to_async
def get_user_with_city(telegram_id: int):
    return (
        User.objects.select_related("city")
        .filter(telegram_id=telegram_id)
        .first()
    )


@sync_to_async
def categories_for_guides(city_id: Optional[int]) -> List[str]:
    """Получить категории гайдов, для которых есть гайды в городе"""
    if city_id:
        qs = (
            GuideCategory.objects.filter(guides__city_id=city_id)
            .distinct()
            .order_by("name")
        )
        categories = list(qs.values_list("name", flat=True))
        if categories:
            return categories

    # Если нет гайдов для города, показываем все категории с гайдами
    qs = (
        GuideCategory.objects.filter(guides__isnull=False)
        .distinct()
        .order_by("name")
    )
    return list(qs.values_list("name", flat=True))


@sync_to_async
def find_guide_category_by_name(name: str) -> Optional[GuideCategory]:
    return GuideCategory.objects.filter(name__iexact=name.strip()).first()


@sync_to_async
def fetch_guide_topics_by_category(city_id: Optional[int], category_id: int) -> List[dict]:
    """Получить список топиков гайдов по категории для города"""
    query = Guide.objects.filter(category_id=category_id)

    if city_id:
        # Сначала ищем гайды для конкретного города
        city_guides = list(
            query.filter(city_id=city_id)
            .order_by("topic")
            .values("id", "topic", "city__name")
        )
        if city_guides:
            return city_guides

    # Если нет гайдов для города, показываем гайды из других городов
    return list(
        query.order_by("city__name", "topic")
        .values("id", "topic", "city__name")
    )


@sync_to_async
def get_guide_by_id(guide_id: int) -> Optional[dict]:
    """Получить конкретный гайд по ID"""
    guide = Guide.objects.filter(id=guide_id).select_related(
        "city", "category").first()
    if not guide:
        return None
    return {
        "id": guide.id,
        "topic": guide.topic,
        "content": guide.content,
        "city__name": guide.city.name if guide.city else "Город",
        "category__name": guide.category.name if guide.category else None,
    }


def format_guide_topics(topics: List[dict], category_name: str, city_name: Optional[str] = None) -> str:
    """Форматировать список топиков гайдов для отображения"""
    if city_name:
        header = f"📚 <b>Гайды: {category_name}</b>\n📍 {city_name}"
    else:
        header = f"📚 <b>Гайды: {category_name}</b>"

    if not topics:
        return f"{header}\n\nГайды по этой категории пока не готовы."

    lines = [header]
    for idx, topic_data in enumerate(topics, start=1):
        guide_city = topic_data.get("city__name") or "Город"
        topic = topic_data["topic"]
        lines.append(f"{idx}. <b>{topic}</b> ({guide_city})")
    return "\n".join(lines)


def format_guide_content(guide: dict) -> str:
    """Форматировать содержимое конкретного гайда"""
    topic = guide["topic"]
    content = guide["content"]
    city_name = guide.get("city__name") or "Город"
    category_name = guide.get("category__name")

    header = f"📚 <b>{topic}</b>"
    if category_name:
        header += f" | {category_name}"
    header += f"\n📍 {city_name}"

    return f"{header}\n\n{content}"


@router.message(StateFilter("*"), F.text == GUIDES_BUTTON)
async def start_guides(message: Message, state: FSMContext) -> None:
    from_user = message.from_user
    if not from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    user = await get_user_with_city(from_user.id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
        return

    categories = await categories_for_guides(user.city_id if user.city else None)
    if not categories:
        await message.answer(
            "Гайды пока не готовы. Загляните позже!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.clear()
    await state.set_state(GuidesState.category)
    await state.update_data(city_id=user.city_id if user.city else None, city_name=user.city.name if user.city else None)
    await message.answer(
        "Выберите категорию гайдов:",
        reply_markup=category_keyboard(categories),
    )


@router.message(StateFilter(GuidesState.category))
async def process_guide_category(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Выберите категорию из списка.")
        return

    category = await find_guide_category_by_name(text)
    if not category:
        await message.answer("Не нашёл такую категорию. Выберите вариант из списка.")
        return

    data = await state.get_data()
    city_id = data.get("city_id")
    city_name = data.get("city_name")

    topics = await fetch_guide_topics_by_category(city_id, category.id)
    if not topics:
        await message.answer(
            f"Гайды по категории '{category.name}' пока не готовы.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.set_state(GuidesState.topic_selection)
    await state.update_data(
        category_id=category.id,
        category_name=category.name,
        guide_topics=[{"id": t["id"], "topic": t["topic"]} for t in topics],
    )

    text = format_guide_topics(topics, category.name, city_name)
    keyboard = get_navigation_keyboard(
        [[t["topic"]] for t in topics], include_back=True, include_menu=True
    )
    await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(GuidesState.topic_selection), F.text == NAV_BACK_BUTTON)
async def back_to_categories(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    city_id = data.get("city_id")

    categories = await categories_for_guides(city_id)
    if not categories:
        await state.clear()
        await message.answer(
            "Гайды пока не готовы. Загляните позже!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.set_state(GuidesState.category)
    await state.update_data(
        category_id=None,
        category_name=None,
        guide_topics=None,
        current_guide_id=None,
    )
    await message.answer(
        "Выберите другую категорию гайдов:",
        reply_markup=category_keyboard(categories),
    )


@router.message(StateFilter(GuidesState.topic_selection))
async def process_topic_selection(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Выберите гайд из списка.")
        return

    data = await state.get_data()
    topics = data.get("guide_topics", [])

    # Сначала проверяем, не ввел ли пользователь номер (1, 2, 3 и т.д.)
    selected_topic = None
    try:
        topic_index = int(text) - 1
        if 0 <= topic_index < len(topics):
            selected_topic = topics[topic_index]
    except ValueError:
        # Не число, ищем по названию
        pass

    # Если не нашли по номеру, ищем по названию
    if not selected_topic:
        # Убираем город из скобок, если он есть в тексте пользователя
        text_clean = text.split("(")[0].strip()

        for topic_data in topics:
            topic_name = topic_data["topic"].lower()
            # Проверяем точное совпадение или вхождение
            if topic_name == text.lower() or topic_name == text_clean.lower() or text_clean.lower() in topic_name:
                selected_topic = topic_data
                break

    if not selected_topic:
        await message.answer("Не нашёл такой гайд. Выберите вариант из списка или введите номер.")
        return

    guide = await get_guide_by_id(selected_topic["id"])
    if not guide:
        await message.answer("Не удалось загрузить гайд. Попробуйте снова.")
        return

    # Показываем содержимое гайда
    text = format_guide_content(guide)
    await message.answer(text)

    # Автоматически возвращаемся к списку топиков
    city_id = data.get("city_id")
    city_name = data.get("city_name")
    category_id = data.get("category_id")
    category_name = data.get("category_name")

    topics_list = await fetch_guide_topics_by_category(city_id, category_id)
    if topics_list:
        await state.update_data(
            guide_topics=[{"id": t["id"], "topic": t["topic"]}
                          for t in topics_list],
            current_guide_id=None,
        )

        text = format_guide_topics(topics_list, category_name, city_name)
        keyboard = get_navigation_keyboard(
            [[t["topic"]] for t in topics_list], include_back=True, include_menu=True
        )
        await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(GuidesState.guide_content), F.text == NAV_BACK_BUTTON)
async def back_to_topics(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    city_id = data.get("city_id")
    city_name = data.get("city_name")
    category_id = data.get("category_id")
    category_name = data.get("category_name")

    if not category_id:
        await state.clear()
        await message.answer("Ошибка. Начните заново.", reply_markup=main_menu_keyboard())
        return

    topics = await fetch_guide_topics_by_category(city_id, category_id)
    if not topics:
        await message.answer(
            "Гайды по этой категории больше не доступны.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.set_state(GuidesState.topic_selection)
    await state.update_data(
        guide_topics=[{"id": t["id"], "topic": t["topic"]} for t in topics],
        current_guide_id=None,
    )

    text = format_guide_topics(topics, category_name, city_name)
    keyboard = get_navigation_keyboard(
        [[t["topic"]] for t in topics], include_back=True, include_menu=True
    )
    await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(GuidesState.guide_content))
async def guide_content_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Используйте кнопки для навигации.")
        return

    # Если пользователь ввел название топика или номер, пытаемся найти его
    data = await state.get_data()
    topics = data.get("guide_topics", [])

    selected_topic = None
    # Сначала проверяем, не ввел ли пользователь номер (1, 2, 3 и т.д.)
    try:
        topic_index = int(text) - 1
        if 0 <= topic_index < len(topics):
            selected_topic = topics[topic_index]
    except ValueError:
        # Не число, ищем по названию
        text_clean = text.split("(")[0].strip()
        for topic_data in topics:
            topic_name = topic_data["topic"].lower()
            if topic_name == text.lower() or topic_name == text_clean.lower() or text_clean.lower() in topic_name:
                selected_topic = topic_data
                break

    if selected_topic:
        guide = await get_guide_by_id(selected_topic["id"])
        if guide:
            # Показываем содержимое гайда
            text = format_guide_content(guide)
            await message.answer(text)

            # Автоматически возвращаемся к списку топиков
            city_id = data.get("city_id")
            city_name = data.get("city_name")
            category_id = data.get("category_id")
            category_name = data.get("category_name")

            topics_list = await fetch_guide_topics_by_category(city_id, category_id)
            if topics_list:
                await state.set_state(GuidesState.topic_selection)
                await state.update_data(
                    guide_topics=[{"id": t["id"], "topic": t["topic"]}
                                  for t in topics_list],
                    current_guide_id=None,
                )

                text = format_guide_topics(
                    topics_list, category_name, city_name)
                keyboard = get_navigation_keyboard(
                    [[t["topic"]] for t in topics_list], include_back=True, include_menu=True
                )
                await message.answer(text, reply_markup=keyboard)
                return

    await message.answer(
        "Используйте кнопки для навигации или вернитесь в главное меню.",
        reply_markup=main_menu_keyboard(),
    )
