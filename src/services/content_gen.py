"""
Проект: GigaChat_Content_Assistant
Версия: 1.0
Статус: Первая deploy версия

Модуль: src/services/content_gen.py
Разработчик: GEN AI + @AI_NeuroStaff / Dubinin Vladimir


Content Generation Service: Генерация и валидация контента
==========================================================

Модуль инкапсулирует бизнес-логику приложения. Он отвечает за сборку финальных
запросов (промптов) на основе пользовательских данных, вызов LLM-клиента
и постобработку ответов (парсинг JSON, возврат генераторов потока).

Основные возможности:
- Подстановка пользовательских параметров (ниша, ЦА, формат) в шаблоны промптов.
- Безопасное извлечение и строгая валидация JSON-массивов с помощью Pydantic.
- Предоставление потоковых генераторов (streaming) для интерфейса (рассылки, статьи).
- Синхронная обработка для структурированных данных (контент-план).

Переменные:
- Внешние: 
    - Данные состояния приложения не используются напрямую. Все параметры передаются 
      явно через аргументы функций (Pure Functions), что облегчает тестирование.
- Внутренние (локальные):
    - prompt_template: Загруженный сырой шаблон текста из папки assets.
    - final_prompt: Сформированный промпт с подставленными переменными.

Функции:
- _extract_json_from_text(text: str) -> str
    (Внутренняя) Очищает ответ LLM от лишнего текстового "мусора" (например, "Вот ваш план:"),
    находя и возвращая строго блок с JSON-массивом [...].
- generate_content_plan(...) -> List[ContentPlanItem]
    Синхронно генерирует контент-план. Возвращает строго типизированный список Pydantic-моделей.
- generate_broadcast_stream(...) -> Generator[str, None, None]
    Асинхронно (потоком) генерирует посты для рассылок и соцсетей с учетом Tone of Voice.
- generate_lead_magnet_stream(...) -> Generator[str, None, None]
    Асинхронно (потоком) генерирует объемные полезные материалы (гайды, чек-листы).
- generate_seo_article_stream(...) -> Generator[str, None, None]
    Асинхронно (потоком) генерирует длинные SEO-статьи с учетом ключевых слов.

Связи с другими модулями:
- src.services.llm_client:
    Использует функции generate_sync, generate_stream, load_prompt для связи с GigaChat.
- src.models.schemas:
    Использует ContentPlanItem и ContentPlan для валидации JSON.
"""

import json
import re
from typing import List, Generator
from pydantic import ValidationError

# Импортируем функции для работы с LLM из нашего модуля-адаптера
from src.services.llm_client import generate_sync, generate_stream, load_prompt

# Импортируем Pydantic-схемы для строгой типизации ответов
from src.models import ContentPlanItem, ContentPlan

def _extract_json_from_text(text: str) -> str:
    """Извлекает JSON массив из ответа LLM, игнорируя вступительные и завершающие фразы."""
    match = re.search(r'\[.*\]', text, re.DOTALL)
    return match.group(0) if match else text

def generate_content_plan(niche: str, period: str, channels: str, extra_context: str) -> List[ContentPlanItem]:
    """Генерирует контент-план и возвращает валидированный список объектов."""
    prompt_template = load_prompt("content_plan")
    final_prompt = prompt_template.format(
        niche=niche, period=period, channels=channels, extra_context=extra_context
    )
    
    # Используем низкую температуру для большей детерминированности формата JSON
    raw_response = generate_sync(final_prompt, temperature=0.3)
    clean_json_str = _extract_json_from_text(raw_response)
    
    try:
        parsed_data = json.loads(clean_json_str)
        # Оборачиваем список в словарь для валидации корневой модели ContentPlan
        if isinstance(parsed_data, list):
            parsed_data = {"items": parsed_data}
        return ContentPlan(**parsed_data).items
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Ошибка парсинга ответа от LLM: {str(e)}\nСырой ответ: {raw_response}")

def generate_broadcast_stream(channel: str, business_niche: str, topic: str, tone: str, brand_keywords: str) -> Generator[str, None, None]:
    """Генерирует посты для рассылок в виде потока (streaming)."""
    prompt_template = load_prompt("broadcasts")
    final_prompt = prompt_template.format(
        channel=channel, business_niche=business_niche, topic=topic, tone=tone, brand_keywords=brand_keywords
    )
    return generate_stream(final_prompt, temperature=0.7)

def generate_lead_magnet_stream(lm_type: str, topic: str, audience: str, length: str, business_niche: str) -> Generator[str, None, None]:
    """Генерирует текст лид-магнита в виде потока (streaming)."""
    prompt_template = load_prompt("lead_magnets")
    final_prompt = prompt_template.format(
        lm_type=lm_type, topic=topic, audience=audience, length=length, business_niche=business_niche
    )
    return generate_stream(final_prompt, temperature=0.7)

def generate_seo_article_stream(business_niche: str, topic: str, target_keywords: str, length: str) -> Generator[str, None, None]:
    """Генерирует SEO статью в виде потока (streaming) с повышенной креативностью."""
    prompt_template = load_prompt("seo_articles")
    final_prompt = prompt_template.format(
        business_niche=business_niche, topic=topic, target_keywords=target_keywords, length=length
    )
    return generate_stream(final_prompt, temperature=0.8)