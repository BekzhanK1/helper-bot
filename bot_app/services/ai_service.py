import json
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async
from django.conf import settings

from bot_app.models import Guide, Place, Review

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

SYSTEM_PROMPT = (
    "Ты помощник, который проверяет отзывы о местах. "
    "Сначала оцени, похож ли текст на спам. "
    "Если всё в порядке, опиши отзыв одним предложением."
)

USER_TEMPLATE = (
    "Проверь отзыв на спам. Если всё ок, сделай саммари (1 предложение). "
    'Верни JSON строго в формате с ЛАТИНСКИМИ буквами: {{"is_spam": bool, "summary": str}}.'
    "ВАЖНО: используй латинские буквы в ключах JSON (is_spam, а не is_spам).\n\n"
    "Отзыв:\n{review}"
)

SUMMARY_SYSTEM_PROMPT = (
    "Ты помощник по городским местам. Проанализируй отзывы пользователей. "
    "Напиши объективный вывод на русском языке (максимум 2-3 предложения). "
    "Сначала выдели главное достоинство, затем главный недостаток (если есть). "
    "Не используй вводные фразы типа 'Судя по отзывам', пиши сразу по сути."
)

SUMMARY_USER_TEMPLATE = (
    "Вот короткие отзывы пользователей:\n\n{reviews}\n\n"
    "Сформируй итоговое описание в 2-3 предложениях."
)

SUMMARY_PLACEHOLDER = "Пока недостаточно отзывов для анализа"

_client = None


def _get_client() -> Optional["OpenAI"]:
    global _client
    if not settings.OPENAI_API_KEY or OpenAI is None:
        print("analyze_review: OpenAI client unavailable (missing key or package).")
        return None
    if _client is None:
        print("analyze_review: initializing OpenAI client.")
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def analyze_review(text: str) -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        print("analyze_review: returning default result because client is None.")
        return {"is_spam": False, "summary": ""}

    content = None  # Initialize here for exception handler
    try:
        preview = text[:120].replace("\n", " ")
        print(f"analyze_review: sending text (len={len(text)}): {preview!r}")

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(review=text)},
            ],
        )

        content = completion.choices[0].message.content or "{}"
        print(
            f"analyze_review: RAW LLM RESPONSE TYPE={type(content)}, LEN={len(content)}")
        print(f"analyze_review: RAW LLM RESPONSE CONTENT={content!r}")

        parsed = json.loads(content)
        print(f"analyze_review: parsed JSON={parsed}")

        result = {
            "is_spam": bool(parsed.get("is_spam")),
            "summary": str(parsed.get("summary", "")).strip(),
        }
        print(f"analyze_review result: {result}")
        return result

    except json.JSONDecodeError as exc:  # pragma: no cover
        print(f"analyze_review: JSON decode error: {exc}")
        print(f"analyze_review: failed to parse content: {content!r}")
        return {"is_spam": False, "summary": ""}
    except Exception as exc:  # pragma: no cover
        print(f"analyze_review: exception {type(exc).__name__}: {exc}")
        print(f"analyze_review: content at time of exception: {content!r}")
        import traceback
        traceback.print_exc()
        return {"is_spam": False, "summary": ""}


def _build_reviews_block(reviews: List[str]) -> str:
    return "\n".join(f"{idx}. {text}" for idx, text in enumerate(reviews, start=1))


def summarize_reviews(reviews: List[str]) -> str:
    client = _get_client()
    if client is None:
        return ""

    reviews_block = _build_reviews_block(reviews)
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": SUMMARY_USER_TEMPLATE.format(reviews=reviews_block),
                },
            ],
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception:  # pragma: no cover
        return ""


def _fetch_place_and_reviews(place_id: int):
    try:
        place = Place.objects.get(id=place_id)
    except Place.DoesNotExist:
        return None, []
    reviews = list(
        Review.objects.filter(place=place, status=Review.Status.PUBLISHED)
        .order_by("-id")
        .values_list("text", flat=True)[:10]
    )
    return place, reviews


def _save_place_summary(place: Place, summary: str) -> None:
    place.ai_summary = summary
    place.save(update_fields=["ai_summary"])


async def update_place_summary(place_id: int) -> None:
    place, reviews = await sync_to_async(_fetch_place_and_reviews)(place_id)
    if not place:
        return

    if not reviews:
        await sync_to_async(_save_place_summary)(place, SUMMARY_PLACEHOLDER)
        return

    summary = await sync_to_async(summarize_reviews)(list(reviews))
    summary = summary or SUMMARY_PLACEHOLDER
    await sync_to_async(_save_place_summary)(place, summary)


def _build_city_context(city_id: int) -> str:
    """Собрать контекст о городе из базы данных"""
    # Получаем все места с отзывами, отсортированные по рейтингу
    places = Place.objects.filter(
        city_id=city_id, review_count__gt=0
    ).select_related("category").order_by("-avg_rating", "-review_count")[:100]

    guides = Guide.objects.filter(city_id=city_id)[:20]

    context_parts = []

    # Места с отзывами - группируем по категориям для удобства
    if places:
        context_parts.append(
            "=== МЕСТА В ГОРОДЕ (ИСПОЛЬЗУЙ ТОЛЬКО ЭТИ РЕАЛЬНЫЕ МЕСТА) ===\n")
        context_parts.append(
            "ВАЖНО: Используй ТОЧНЫЕ названия и адреса из этого списка. Не выдумывай места!\n\n")

        # Группируем по категориям
        places_by_category = {}
        for place in places:
            category_name = place.category.name if place.category else "Без категории"
            if category_name not in places_by_category:
                places_by_category[category_name] = []
            places_by_category[category_name].append(place)

        for category_name, category_places in places_by_category.items():
            context_parts.append(f"\n--- {category_name} ---\n")
            for place in category_places:
                place_info = f"• {place.name}"
                place_info += f"\n  Адрес: {place.address}"
                if place.avg_rating:
                    place_info += f"\n  Рейтинг: {place.avg_rating:.1f}/5 ({place.review_count} отзывов)"
                if place.average_price and place.average_price > 0:
                    place_info += f"\n  Средний чек: ~{place.average_price} ₸"
                if place.ai_summary:
                    place_info += f"\n  Отзывы: {place.ai_summary}"
                context_parts.append(place_info + "\n")

    # Гайды
    if guides:
        context_parts.append("\n=== ГАЙДЫ ===\n")
        for guide in guides:
            guide_info = f"- {guide.topic}"
            if guide.category:
                guide_info += f" ({guide.category.name})"
            guide_info += f"\n  {guide.content[:300]}..." if len(
                guide.content) > 300 else f"\n  {guide.content}"
            context_parts.append(guide_info + "\n")

    return "\n".join(context_parts)


ASSISTANT_SYSTEM_PROMPT = (
    "Ты AI-помощник для туристов и местных жителей в городе. "
    "Твоя задача - помогать людям планировать время, находить места, "
    "составлять маршруты и давать рекомендации на основе информации из базы данных и интернета. "
    "\n\n"
    "КРИТИЧЕСКИ ВАЖНО - ОГРАНИЧЕНИЯ:\n"
    "- Ты МОЖЕШЬ отвечать ТОЛЬКО на вопросы, связанные с туризмом, путешествиями, местами в городе, ресторанами, кафе, достопримечательностями, развлечениями, отелями, транспортом, планированием маршрутов, бюджетами на поездки\n"
    "- Если пользователь задает вопрос НЕ связанный с туризмом или городом (например, программирование, общие знания, математика, наука и т.д.), ты ДОЛЖЕН вежливо отказать и напомнить, что ты помогаешь только с вопросами о туризме и местах в городе\n"
    "- Примеры НЕПОДХОДЯЩИХ вопросов: 'напиши код на Python', 'что такое квантовая физика', 'реши уравнение', 'как работает компьютер'\n"
    "- Примеры ПОДХОДЯЩИХ вопросов: 'где поесть', 'куда сходить', 'составь план на день', 'где остановиться', 'что посмотреть'\n"
    "\n"
    "КРИТИЧЕСКИ ВАЖНО - РАБОТА С ДАННЫМИ:\n"
    "- ВСЕГДА отвечай на вопрос пользователя, даже если в базе данных нет мест или их мало\n"
    "- Если в базе данных есть подходящие места - используй их с ТОЧНЫМИ названиями, адресами, рейтингами и средними чеками\n"
    "- Если в базе данных НЕТ подходящих мест или их недостаточно - модель АВТОМАТИЧЕСКИ использует веб-поиск для нахождения информации\n"
    "- НИКОГДА не проси пользователя предоставить данные из базы - это твоя задача найти информацию\n"
    "- ВСЕГДА комбинируй информацию: если есть места в базе - используй их, если нет - найди через веб-поиск\n"
    "- При использовании информации из интернета, указывай конкретные места с адресами и ценами\n"
    "- НЕ выдумывай названия заведений или адреса - используй только реальные данные из базы или интернета\n"
    "- При составлении планов ВСЕГДА указывай конкретные названия и адреса\n"
    "- Учитывай бюджет пользователя, если он указан - используй места с подходящими средними чеками\n"
    "- Делай планы реалистичными и интересными\n"
    "- Отвечай на русском языке, дружелюбно и полезно\n"
    "- Если пользователь спрашивает про конкретный день недели, учитывай это при планировании\n"
    "- Форматируй ответ в HTML для Telegram (используй <b> для жирного, <i> для курсива, НЕ используй <br> - используй обычные переносы строк)"
)


def generate_recommendation(user_query: str, city_context: str, city_name: str) -> str:
    """Генерировать рекомендацию на основе запроса пользователя и контекста города"""
    client = _get_client()
    if client is None:
        return "Извините, AI-помощник временно недоступен. Попробуйте позже."

    user_message = (
        f"Пользователь спрашивает: {user_query}\n\n"
        f"Город: {city_name}\n\n"
        f"=== ИНФОРМАЦИЯ ИЗ БАЗЫ ДАННЫХ ===\n{city_context}\n\n"
        "КРИТИЧЕСКИ ВАЖНО - ОГРАНИЧЕНИЯ:\n"
        "- Если вопрос НЕ связан с туризмом, местами в городе, ресторанами, достопримечательностями, отелями, транспортом или планированием поездок - ВЕЖЛИВО откажись и напомни, что ты помогаешь только с вопросами о туризме\n"
        "- НЕ отвечай на вопросы о программировании, науке, математике, общих знаниях и других темах, не связанных с туризмом\n"
        "\n"
        "КРИТИЧЕСКИ ВАЖНЫЕ ИНСТРУКЦИИ:\n"
        "- ВСЕГДА отвечай на вопрос пользователя, даже если в базе данных нет мест или их мало\n"
        "- Если в базе данных есть подходящие места - используй их с точными названиями и адресами\n"
        "- Если в базе данных НЕТ подходящих мест или их недостаточно - модель АВТОМАТИЧЕСКИ использует веб-поиск для нахождения информации\n"
        "- НИКОГДА не проси пользователя предоставить данные из базы - это твоя задача найти информацию через веб-поиск\n"
        "- НЕ говори пользователю 'мне нужны данные из базы' или 'поделись данными' - модель сама должна найти информацию\n"
        "- ВНИМАТЕЛЬНО изучи список мест в базе - там могут быть места для разных категорий\n"
        "- Если в базе есть подходящее место, ОБЯЗАТЕЛЬНО используй его\n"
        "- ВСЕГДА дополняй информацию из базы результатами веб-поиска - найди дополнительные места в интернете\n"
        "- Модель автоматически использует веб-поиск для нахождения мест, которые отсутствуют в базе\n"
        "- После получения результатов веб-поиска, ИСПОЛЬЗУЙ эту информацию в ответе - указывай конкретные места, адреса, цены\n"
        "- Комбинируй информацию: используй места из базы (если есть) + места из интернета (всегда)\n"
        "- При составлении планов указывай конкретные названия, адреса и средние чеки из базы И из интернета\n"
        "- Форматируй ответ в HTML для Telegram: используй <b>текст</b> для жирного, <i>текст</i> для курсива\n"
        "- НЕ используй <br> или другие HTML теги для переносов - используй обычные переносы строк (Enter)\n"
        "- НЕ используй markdown (**, __, # и т.д.), только HTML теги <b> и <i>"
    )

    try:
        # Используем модель с встроенным веб-поиском OpenAI
        # Пробуем использовать Responses API с web_search tool
        try:
            # Пробуем использовать Responses API (если доступен)
            response_obj = client.responses.create(
                model="gpt-4o",
                tools=[{"type": "web_search"}],
                input=user_message,
                instructions=ASSISTANT_SYSTEM_PROMPT,
            )
            response = response_obj.output_text or ""
        except (AttributeError, Exception) as e:
            # Если Responses API не доступен, используем Chat Completions с моделью, поддерживающей веб-поиск
            print(f"Responses API not available, trying search models: {e}")
            try:
                # Используем модель с поддержкой веб-поиска для Chat Completions
                # Модели с веб-поиском не поддерживают temperature
                completion = client.chat.completions.create(
                    model="gpt-4o-search-preview",  # Модель с поддержкой веб-поиска
                    messages=[
                        {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                )
                response = (
                    completion.choices[0].message.content or "").strip()
            except Exception as search_error:
                print(
                    f"Search model not available ({search_error}), using regular model with fallback")
                # Если модели с веб-поиском нет, используем обычную модель
                # Модель будет использовать свои знания
                completion = client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.7,
                    messages=[
                        {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                )
                response = (
                    completion.choices[0].message.content or "").strip()

        # Убираем markdown форматирование, если оно есть
        import re
        import html

        # Заменяем markdown на HTML
        response = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', response)
        response = re.sub(r'__(.+?)__', r'<b>\1</b>', response)
        response = re.sub(r'\*(.+?)\*', r'<i>\1</i>', response)
        response = re.sub(r'_(.+?)_', r'<i>\1</i>', response)
        response = re.sub(r'### (.+?)\n', r'<b>\1</b>\n', response)
        response = re.sub(r'## (.+?)\n', r'<b>\1</b>\n', response)
        response = re.sub(r'# (.+?)\n', r'<b>\1</b>\n', response)

        # Удаляем HTML теги, которые Telegram не поддерживает
        # Заменяем <br>, <br/>, <br /> на обычные переносы строк
        response = re.sub(r'<br\s*/?>', '\n', response, flags=re.IGNORECASE)
        # Удаляем другие неподдерживаемые теги, если они есть
        response = re.sub(r'</?p>', '\n', response, flags=re.IGNORECASE)
        response = re.sub(r'</?div>', '\n', response, flags=re.IGNORECASE)
        response = re.sub(r'</?span>', '', response, flags=re.IGNORECASE)
        response = re.sub(r'</?strong>', '', response, flags=re.IGNORECASE)
        response = re.sub(r'</?em>', '', response, flags=re.IGNORECASE)
        response = re.sub(r'</?code>', '', response, flags=re.IGNORECASE)
        response = re.sub(r'</?pre>', '', response, flags=re.IGNORECASE)
        response = re.sub(r'</?ul>', '\n', response, flags=re.IGNORECASE)
        response = re.sub(r'</?ol>', '\n', response, flags=re.IGNORECASE)
        response = re.sub(r'</?li>', '\n• ', response, flags=re.IGNORECASE)
        response = re.sub(r'</?h[1-6]>', '\n', response, flags=re.IGNORECASE)

        # Исправляем незакрытые теги <b> и <i>
        # Считаем количество открывающих и закрывающих тегов
        open_b = len(re.findall(r'<b>', response, re.IGNORECASE))
        close_b = len(re.findall(r'</b>', response, re.IGNORECASE))
        open_i = len(re.findall(r'<i>', response, re.IGNORECASE))
        close_i = len(re.findall(r'</i>', response, re.IGNORECASE))

        # Закрываем незакрытые теги в конце
        if open_b > close_b:
            response += '</b>' * (open_b - close_b)
        if open_i > close_i:
            response += '</i>' * (open_i - close_i)

        # Удаляем лишние закрывающие теги (если их больше, чем открывающих)
        if close_b > open_b:
            # Удаляем лишние закрывающие теги с конца
            response = re.sub(r'</b>', '', response,
                              count=close_b - open_b, flags=re.IGNORECASE)
        if close_i > open_i:
            response = re.sub(r'</i>', '', response,
                              count=close_i - open_i, flags=re.IGNORECASE)

        # Экранируем символы < и >, которые не являются частью разрешенных тегов
        # Сначала временно заменяем разрешенные теги
        response = response.replace('<b>', '___TAG_B_OPEN___')
        response = response.replace('</b>', '___TAG_B_CLOSE___')
        response = response.replace('<i>', '___TAG_I_OPEN___')
        response = response.replace('</i>', '___TAG_I_CLOSE___')

        # Экранируем все оставшиеся < и >
        response = html.escape(response)

        # Возвращаем разрешенные теги обратно
        response = response.replace('___TAG_B_OPEN___', '<b>')
        response = response.replace('___TAG_B_CLOSE___', '</b>')
        response = response.replace('___TAG_I_OPEN___', '<i>')
        response = response.replace('___TAG_I_CLOSE___', '</i>')

        # Убираем множественные переносы строк (больше 2 подряд)
        response = re.sub(r'\n{3,}', '\n\n', response)

        return response
    except Exception as exc:
        print(
            f"generate_recommendation: exception {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return "Извините, произошла ошибка при генерации рекомендации. Попробуйте переформулировать вопрос."
