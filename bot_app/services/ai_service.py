import json
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async
from django.conf import settings

from bot_app.models import Place, Review

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
    "Верни JSON строго в формате {{\"is_spам\": bool, \"summary\": str}}.\n\n"
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
