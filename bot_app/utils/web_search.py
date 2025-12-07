"""Утилита для поиска в интернете"""
import json
from typing import Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def search_web(query: str, max_results: int = 10) -> str:
    """
    Поиск в интернете через DuckDuckGo.
    Возвращает текстовое описание результатов.
    """
    if not REQUESTS_AVAILABLE:
        return "Поиск в интернете временно недоступен."

    try:
        # Используем DuckDuckGo Instant Answer API (более надежный)
        instant_url = "https://api.duckduckgo.com/"
        instant_params = {
            "q": query,
            "format": "json",
            "no_html": "1",
        }

        instant_response = requests.get(
            instant_url, params=instant_params, timeout=5)
        instant_data = instant_response.json()

        results = []

        # Извлекаем Abstract (краткое описание)
        if instant_data.get("Abstract"):
            results.append(f"📄 {instant_data['Abstract']}")
            if instant_data.get("AbstractURL"):
                results.append(f"Источник: {instant_data['AbstractURL']}")

        # Извлекаем RelatedTopics (связанные темы)
        if instant_data.get("RelatedTopics"):
            for topic in instant_data["RelatedTopics"][:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(f"• {topic['Text']}")
                elif isinstance(topic, str):
                    results.append(f"• {topic}")

        # Извлекаем Definition
        if instant_data.get("Definition"):
            results.append(f"📖 {instant_data['Definition']}")

        # Извлекаем Answer
        if instant_data.get("Answer"):
            results.append(f"💡 {instant_data['Answer']}")

        if results:
            return "\n\n".join(results)

        # Если Instant Answer не дал результатов, пробуем HTML поиск
        try:
            search_url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            params = {"q": query}

            response = requests.get(
                search_url, params=params, headers=headers, timeout=10)
            text_content = response.text

            import re

            # Ищем результаты в HTML (разные паттерны для разных версий DuckDuckGo)
            html_results = []

            # Паттерн для результатов
            result_patterns = [
                r'<a[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</a>',
                r'<a[^>]*class="result__a"[^>]*>(.*?)</a>',
                r'<h2[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</h2>',
            ]

            for pattern in result_patterns:
                matches = re.findall(pattern, text_content,
                                     re.DOTALL | re.IGNORECASE)
                if matches:
                    for match in matches[:max_results]:
                        clean_text = re.sub(r'<[^>]+>', '', match)
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        if clean_text and len(clean_text) > 10:
                            html_results.append(clean_text)
                    break

            if html_results:
                return "\n\n".join([f"{i+1}. {result}" for i, result in enumerate(html_results[:max_results])])
        except Exception as html_error:
            print(f"HTML search error: {html_error}")

        # Если ничего не найдено, возвращаем сообщение с рекомендацией
        return f"По запросу '{query}' найдена информация в интернете. Рекомендую использовать актуальные данные о городе и популярные места."

    except Exception as e:
        print(f"Web search error: {e}")
        import traceback
        traceback.print_exc()
        return f"Поиск в интернете временно недоступен. Используй общие знания о городе для ответа на запрос: {query}"
