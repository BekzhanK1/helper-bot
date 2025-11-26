import json
from typing import Any, Dict, Optional

from django.conf import settings

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
